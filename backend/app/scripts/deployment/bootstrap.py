"""显式初始化系统必需数据，保留既有配置、口令和授权。"""

import json
import os
import re
from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.path_conf import SCRIPT_DIR, STATIC_DIR
from app.core.database import async_db_session
from app.modules.system.dept.model import DeptModel
from app.modules.system.dict.model import DictDataModel, DictTypeModel
from app.modules.system.menu.model import MenuModel
from app.modules.system.params.model import ParamsModel
from app.modules.system.product_config.service import ProductConfigService
from app.modules.system.role.model import RoleMenusModel, RoleModel
from app.modules.system.user.model import UserModel, UserRolesModel
from app.modules.task.storage.node.model import StorageNodeModel
from app.utils.password_util import PwdUtil

from .common import DeploymentError, initialization_lock, password_from_env, validate_environment
from .structure import ensure_structure, structure_state, validate_history


def load_seed(name: str) -> list[dict[str, Any]]:
    """严格读取仓库种子，缺文件或格式错误不得静默略过。"""
    try:
        rows = json.loads((SCRIPT_DIR / f"{name}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DeploymentError("INIT_DATA_INVALID", f"种子文件 {name}.json 无效", 2) from error
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise DeploymentError("INIT_DATA_INVALID", f"种子文件 {name}.json 必须为对象数组", 2)
    return rows


async def seed_system(db: AsyncSession, username: str, password: str | None) -> dict[str, int]:
    """按自然键只补缺失记录，初始管理员独立于旧演示账号种子。"""
    counts: Counter[str] = Counter()

    async def insert(model: Any, key: str, values: dict[str, Any]) -> Any:
        """重复保留键拒绝使用，已有记录不更新用户自定义值。"""
        statement = select(model).where(getattr(model, key) == values[key])
        if model is MenuModel and key == "permission":
            statement = statement.where(MenuModel.parent_id == values["parent_id"], MenuModel.type == values["type"], MenuModel.scope == values.get("scope", "web"))
        rows = (await db.scalars(statement)).all()
        if len(rows) > 1 or (rows and rows[0].is_deleted):
            raise DeploymentError("INIT_DATA_CONFLICT", f"{model.__tablename__} 的受管记录重复或已删除")
        if rows:
            return rows[0]
        obj = model(**values)
        db.add(obj)
        await db.flush()
        counts[model.__tablename__] += 1
        return obj

    async def menus(rows: list[dict[str, Any]], parent: int | None = None) -> None:
        """递归解析父子关系，不使用种子中的固定主键。"""
        for source in rows:
            values = {key: value for key, value in source.items() if key not in {"id", "parent_id", "children"}}
            values["parent_id"] = parent
            key = "route_name" if values.get("route_name") else "permission"
            if not values.get(key):
                raise DeploymentError("INIT_DATA_INVALID", "菜单须有路由名称或权限标识", 2)
            node = await insert(MenuModel, key, values)
            await menus(source.get("children", []), node.id)

    for values in load_seed("sys_param"):
        await insert(ParamsModel, "config_key", values)
    for source in load_seed("task_storage_node"):
        values = {key: value for key, value in source.items() if key != "id"}
        # 已有默认源由企业维护，补本地源时不争夺默认标志。
        if await db.scalar(select(StorageNodeModel.id).where(StorageNodeModel.is_default.is_(True), StorageNodeModel.is_deleted.is_(False))):
            values["is_default"] = False
        await insert(StorageNodeModel, "name", values)
    await menus(load_seed("sys_menu"))
    for values in load_seed("sys_dict_type"):
        await insert(DictTypeModel, "dict_type", values)
    for source in load_seed("sys_dict_data"):
        values = {key: value for key, value in source.items() if key not in {"dict_type_id", "id"}}
        dictionary = await db.scalar(select(DictTypeModel).where(DictTypeModel.dict_type == source["dict_type"]))
        if dictionary is None:
            raise DeploymentError("INIT_DATA_INVALID", "字典类型引用不存在", 2)
        values["dict_type_id"] = dictionary.id
        existing = (await db.scalars(select(DictDataModel).where(DictDataModel.dict_type_id == dictionary.id, DictDataModel.dict_value == values["dict_value"]))).all()
        if len(existing) > 1 or (existing and existing[0].is_deleted):
            raise DeploymentError("INIT_DATA_CONFLICT", "字典受管值重复或已删除")
        if not existing:
            db.add(DictDataModel(**values))
            counts["sys_dict_data"] += 1
    await db.flush()
    department = await insert(DeptModel, "code", {"code": "DEFAULT", "name": "系统部门", "status": 0, "order": 1})
    role = await insert(RoleModel, "code", {"code": "SUPER_ADMIN", "name": "超级管理员", "status": 0, "data_scope": 3, "order": 1})
    admin = await db.scalar(select(UserModel).where(UserModel.is_superuser.is_(True), UserModel.is_deleted.is_(False), UserModel.status == 0))
    if admin is None:
        if await db.scalar(select(UserModel.id).where(UserModel.username == username)):
            raise DeploymentError("INIT_DATA_CONFLICT", "初始管理员用户名已被占用，不会自动提权")
        if password is None:
            raise DeploymentError("INIT_PASSWORD_REQUIRED", "缺少初始管理员口令", 2)
        admin = UserModel(username=username, name="系统管理员", password=await PwdUtil.ahash_password(password), is_superuser=True, dept_id=department.id, status=0)
        db.add(admin)
        await db.flush()
        db.add(UserRolesModel(user_id=admin.id, role_id=role.id))
        granted = set((await db.scalars(select(RoleMenusModel.menu_id).where(RoleMenusModel.role_id == role.id))).all())
        for menu_id in (await db.scalars(select(MenuModel.id).where(MenuModel.is_deleted.is_(False)))).all():
            if menu_id not in granted:
                db.add(RoleMenusModel(role_id=role.id, menu_id=menu_id))
        counts["initial_admin"] += 1
    await ProductConfigService(db).initialize()
    return dict(counts)


async def initialize_database(apply: bool = False) -> dict[str, Any]:
    """预检只读；写入前锁定并复核，DDL与种子事务分离。"""
    validate_environment()
    for name in ("sys_param", "sys_menu", "sys_dict_type", "sys_dict_data", "task_storage_node"):
        load_seed(name)
    state = await structure_state()
    validate_history(state)
    if state["revision"] == [state["target"]] and (state["missing"] or state["drift"]):
        raise DeploymentError("INIT_SCHEMA_CONFLICT", f"当前版本结构损坏，缺表 {state['missing']}，差异 {state['drift']}")
    username = os.environ.get("INIT_ADMIN_USERNAME", "super")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{1,31}", username):
        raise DeploymentError("INIT_CONFIG_INVALID", "INIT_ADMIN_USERNAME 格式不正确", 2)
    if not apply:
        return {"mode": "dry-run", "structure": state, "stages": ["structure", "auxiliary_tables", "system_seeds", "initial_admin", "product_config", "storage_directory"]}
    async with initialization_lock():
        state = await structure_state()
        validate_history(state)
        has_admin = False
        if not state["missing"]:
            async with async_db_session() as db:
                has_admin = bool(await db.scalar(select(func.count()).select_from(UserModel).where(UserModel.is_superuser.is_(True), UserModel.is_deleted.is_(False), UserModel.status == 0)))
        password = None if has_admin else password_from_env("INIT_ADMIN_PASSWORD", username)
        await ensure_structure()
        from .check import ensure_auxiliary_tables

        await ensure_auxiliary_tables()
        async with async_db_session() as db, db.begin():
            counts = await seed_system(db, username, password)
        (STATIC_DIR / "upload").mkdir(parents=True, exist_ok=True)
    return {"mode": "apply", "created": counts, "message": "必要结构与基础数据初始化完成，已有密码、配置和授权保留"}
