"""完整结构自举、已提交迁移与只读结构检查，不自动生成或清理版本。"""

import asyncio
from typing import Any

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect

from app.config.path_conf import BASE_DIR
from app.core.base_model import MappedBase
from app.core.database import async_engine, create_tables
from app.utils.import_util import ImportUtil

from .common import DeploymentError, sqlite_path


def migration_config() -> Config:
    """配置文件使用绝对路径，不依赖调用方工作目录。"""
    return Config(str(BASE_DIR / "alembic.ini"))


def target_revision() -> str:
    """只接受一个完整的迁移头，禁止隐式选择分支。"""
    heads = ScriptDirectory.from_config(migration_config()).get_heads()
    if len(heads) != 1:
        raise DeploymentError("INIT_SCHEMA_CONFLICT", "迁移链必须且只能有一个head")
    return heads[0]


async def structure_state(compare: bool = True) -> dict[str, Any]:
    """仅反射已存在数据库；SQLite文件缺失时返回真空库计划。"""
    ImportUtil.find_models(MappedBase)
    head = target_revision()
    path = sqlite_path()
    if path is not None and not path.exists():
        return {"empty": True, "revision": [], "target": head, "missing": sorted(MappedBase.metadata.tables), "drift": []}

    def read(connection: Connection) -> dict[str, Any]:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "include_object": lambda obj, name, kind, reflected, compared: kind != "table" or name in MappedBase.metadata.tables}
        )
        revisions = list(context.get_current_heads())
        missing = sorted(set(MappedBase.metadata.tables) - tables)
        differences = compare_metadata(context, MappedBase.metadata) if compare and not missing else []
        # 只返回差异类型与表名，不打印默认值或业务行内容。
        drift = [str(item[0] if isinstance(item, tuple) else item[0][0]) for item in differences]
        return {"empty": not tables, "revision": revisions, "target": head, "missing": missing, "drift": drift}

    async with async_engine.connect() as connection:
        return await connection.run_sync(read)


def validate_history(state: dict[str, Any]) -> None:
    """非空库必须保有可解析历史，不能删版本或盲目stamp。"""
    if state["empty"]:
        return
    revisions = state["revision"]
    if len(revisions) != 1:
        raise DeploymentError("INIT_SCHEMA_CONFLICT", "非空库缺少可信单一版本，须先备份并人工核对")
    try:
        ScriptDirectory.from_config(migration_config()).get_revision(revisions[0])
    except Exception as error:
        raise DeploymentError("INIT_SCHEMA_CONFLICT", "缺少数据库对应的迁移脚本，请恢复完整发布版本") from error


async def ensure_structure() -> dict[str, Any]:
    """空库完整建表后校验并标记，已有库仅应用仓库迁移。"""
    state = await structure_state()
    validate_history(state)
    if state["empty"]:
        await create_tables()
        created = await structure_state()
        if created["missing"] or created["drift"]:
            raise DeploymentError("INIT_SCHEMA_CONFLICT", "新建结构与模型不一致，未标记迁移版本")
        await asyncio.to_thread(command.stamp, migration_config(), state["target"])
    else:
        if state["revision"] != [state["target"]]:
            await asyncio.to_thread(command.upgrade, migration_config(), "head")
    result = await structure_state()
    if result["missing"] or result["drift"]:
        raise DeploymentError("INIT_SCHEMA_CONFLICT", f"结构校验失败，缺表 {result['missing']}，差异 {result['drift']}")
    return result
