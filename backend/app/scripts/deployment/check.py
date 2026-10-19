"""启动和命令行共用只读验收，不以验收名义修复数据库。"""

from typing import Any

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import inspect, select

from app.config.setting import settings
from app.core.database import async_db_session, async_engine, engine
from app.modules.ai.chat.crud import _get_agno_db, init_agno_tables
from app.modules.system.dept.model import DeptModel
from app.modules.system.dict.model import DictTypeModel
from app.modules.system.menu.model import MenuModel
from app.modules.system.params.model import ParamsModel
from app.modules.system.position.model import PositionModel
from app.modules.system.product_config.crud import PRODUCT_CONFIG_KEY
from app.modules.system.product_config.service import ProductConfigService
from app.modules.system.role.model import RoleMenusModel, RoleModel
from app.modules.system.user.model import UserModel, UserPositionsModel, UserRolesModel

from .common import DeploymentError, validate_environment
from .structure import structure_state, validate_history


async def ensure_auxiliary_tables() -> None:
    """仅显式初始化调用，不能启动调度器或执行任何任务。"""
    await init_agno_tables()
    table = SQLAlchemyJobStore(engine=engine).jobs_t
    async with async_engine.begin() as connection:
        await connection.run_sync(lambda sync: table.create(sync, checkfirst=True))
    await check_auxiliary_tables()


async def check_auxiliary_tables() -> None:
    """通过库的只读反射检查AI结构，不依赖可能过期的表对象缓存。"""
    database = _get_agno_db()
    names = {
        "versions": "versions",
        "sessions": "session",
        "memories": "memory",
        "metrics": "metrics",
        "evals": "eval",
        "knowledge": "knowledge",
        "culture": "culture",
        "traces": "trace",
        "spans": "span",
    }
    try:
        for kind, name in names.items():
            # _get_table 的缓存由独立实例持有；校验直接走无缓存的反射入口。
            table = await database._get_or_create_table(getattr(database, f"{name}_table_name"), kind, False)
            if table is None:
                raise ValueError("missing auxiliary table")
        async with async_engine.connect() as connection:
            columns = await connection.run_sync(lambda sync: {column["name"] for column in inspect(sync).get_columns("apscheduler_jobs")})
        if not {"id", "next_run_time", "job_state"}.issubset(columns):
            raise ValueError("jobstore columns")
    except Exception as error:
        raise DeploymentError("INIT_AUX_SCHEMA_INVALID", "AI或任务辅助表缺失/结构无效，请执行 init-db --apply") from error


async def check_installation(redis: bool = False) -> dict[str, Any]:
    """未安装或版本不匹配则停止启动，缺业务单据不算失败。"""
    validate_environment()
    state = await structure_state()
    validate_history(state)
    if state["empty"] or state["missing"] or state["drift"] or state["revision"] != [state["target"]]:
        raise DeploymentError("APP_NOT_INITIALIZED", f"结构未就绪，请运行 init-db；缺表 {state['missing']}，差异 {state['drift']}")
    async with async_db_session() as db:
        required = {"sys_name", PRODUCT_CONFIG_KEY}
        keys = set((await db.scalars(select(ParamsModel.config_key).where(ParamsModel.is_deleted.is_(False)))).all())
        admin = await db.scalar(select(UserModel.id).where(UserModel.is_superuser.is_(True), UserModel.is_deleted.is_(False), UserModel.status == 0))
        menu = await db.scalar(select(MenuModel.id).where(MenuModel.route_name == "InventoryBasic", MenuModel.is_deleted.is_(False), MenuModel.status == 0))
        dictionary = await db.scalar(select(DictTypeModel.id).where(DictTypeModel.is_deleted.is_(False)))
        if not required.issubset(keys) or not admin or not menu or not dictionary:
            raise DeploymentError("APP_NOT_INITIALIZED", "必要管理员、菜单、参数或字典缺失，请执行 init-db --apply")
        await ProductConfigService(db).read()
        # 只核对引用完整性，不以验收为名变更已有授权或停用状态。
        for link, field, target in (
            (UserModel, "dept_id", DeptModel),
            (DeptModel, "parent_id", DeptModel),
            (MenuModel, "parent_id", MenuModel),
            (UserRolesModel, "user_id", UserModel),
            (UserRolesModel, "role_id", RoleModel),
            (UserPositionsModel, "user_id", UserModel),
            (UserPositionsModel, "position_id", PositionModel),
            (RoleMenusModel, "role_id", RoleModel),
            (RoleMenusModel, "menu_id", MenuModel),
        ):
            column = getattr(link, field)
            dangling = await db.scalar(select(column).where(column.is_not(None), ~column.in_(select(target.id))).limit(1))
            if dangling is not None:
                raise DeploymentError("INIT_DATA_CONFLICT", f"{link.__tablename__}.{field} 存在失效引用，请核对组织和菜单关联")
    await check_auxiliary_tables()
    if redis:
        from redis.asyncio import Redis

        client = Redis.from_url(settings.REDIS_URI)
        try:
            if not await client.ping():
                raise DeploymentError("INIT_REDIS_UNAVAILABLE", "Redis不可用")
        except DeploymentError:
            raise
        except Exception as error:
            raise DeploymentError("INIT_REDIS_UNAVAILABLE", "Redis连接或认证失败，请核对部署配置") from error
        finally:
            await client.aclose()
    return {"status": "ready", "revision": state["target"], "redis_checked": redis}
