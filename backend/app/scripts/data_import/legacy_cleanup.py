"""经审核的旧批次清理：精确清单、先备份、事务删除、保留行校验。"""

import base64
import hashlib
import json
import os
import shutil
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, Table, and_, delete, false, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.setting import settings
from app.core.base_model import MappedBase
from app.core.database import async_engine
from app.scripts.deployment.common import DeploymentError, initialization_lock
from app.utils.import_util import ImportUtil

from .legacy_audit import audit_dataset

DELETE_ORDER = (
    "ims_business_log",
    "ims_stock_log",
    "ims_receivable",
    "ims_payable",
    "ims_stock_balance",
    "ims_purchase_return_item",
    "ims_sale_return_item",
    "ims_stock_check_item",
    "ims_stock_opening_item",
    "ims_purchase_in_item",
    "ims_sale_out_item",
    "ims_purchase_return",
    "ims_sale_return",
    "ims_stock_check",
    "ims_stock_opening",
    "ims_purchase_in",
    "ims_sale_out",
    "ims_goods",
    "ims_goods_category",
    "ims_customer",
    "ims_supplier",
    "ims_warehouse",
    "sys_user_roles",
    "sys_user_positions",
    "sys_role_menus",
    "sys_role_depts",
    "sys_user",
    "sys_role",
    "sys_position",
    "sys_dept",
    "sys_param",
)


def encode_value(value: Any) -> Any:
    """导出类型标记，保留精确金额、日期和二进制，避免恢复时失真。"""
    if isinstance(value, (datetime, date, Decimal)):
        return {"type": type(value).__name__, "value": str(value)}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": base64.b64encode(value).decode()}
    raise TypeError(type(value).__name__)


def canonical(value: Any) -> str:
    """稳定排序用于快照和未删除行指纹，不输出业务内容。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=encode_value, separators=(",", ":"))


def save_private(path: Path, value: Any) -> str:
    """文件只允许新建，落盘后回读校验，敏感快照不放入代码仓库。"""
    content = canonical(value).encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    expected = hashlib.sha256(content).hexdigest()
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise DeploymentError("CLEANUP_BACKUP_INVALID", "备份回读校验失败，不执行删除")
    return expected


def target_predicate(table: Table, batch: dict[str, Any]) -> Any:
    """仅使用已批准单主键或关联表的精确复合主键。"""
    if table.name in batch["links"]:
        keys = batch["links"][table.name]
        return or_(*(and_(*(table.c[name] == value for name, value in row.items())) for row in keys)) if keys else false()
    ids = batch["ids"].get(table.name, [])
    if table.name == "sys_param":
        ids = [batch["manifest_id"], *batch["organization_manifest_ids"]]
    return table.c.id.in_(ids) if "id" in table.c else false()


async def snapshot(db: AsyncSession, tables: dict[str, Table], batch: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """备份目标整行，并给所有非目标表行生成指纹以发现级联误改。"""
    selected: dict[str, Any] = {}
    retained: dict[str, Any] = {}
    for name, table in tables.items():
        predicate = target_predicate(table, batch) if name in DELETE_ORDER else false()
        if name in DELETE_ORDER:
            selected[name] = [dict(row) for row in (await db.execute(select(table).where(predicate))).mappings()]
        rows = sorted(canonical(dict(row)) for row in (await db.execute(select(table).where(~predicate))).mappings())
        retained[name] = {"count": len(rows), "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest()}
    return selected, retained


def mysql_dump(directory: Path) -> dict[str, Any]:
    """调用官方逻辑备份工具，凭据仅经子进程环境传递。"""
    executable = shutil.which("mysqldump")
    if not executable:
        raise DeploymentError("CLEANUP_BACKUP_INVALID", "找不到mysqldump，不执行真实库清理")
    path = directory / "database-before.sql"
    if path.exists():
        raise DeploymentError("CLEANUP_BACKUP_INVALID", "备份文件已存在，拒绝覆盖")
    env = {**os.environ, "MYSQL_PWD": settings.DATABASE_PASSWORD}
    args = [
        executable,
        f"--host={settings.DATABASE_HOST}",
        f"--port={settings.DATABASE_PORT}",
        f"--user={settings.DATABASE_USER}",
        "--single-transaction",
        "--quick",
        "--no-tablespaces",
        "--set-gtid-purged=OFF",
        "--hex-blob",
        "--routines",
        "--events",
        "--triggers",
        f"--result-file={path}",
        "--databases",
        settings.DATABASE_NAME,
    ]
    result = subprocess.run(args, env=env, input="", capture_output=True, text=True, timeout=180)
    if result.returncode or not path.exists() or path.stat().st_size == 0:
        raise DeploymentError("CLEANUP_BACKUP_INVALID", f"mysqldump失败（退出码{result.returncode}），未删除数据")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


async def cleanup_legacy(report: Path, directory: Path, dataset: str, apply: bool = False) -> dict[str, Any]:
    """重新锁定并核查批准清单；所有SQL删除和保留行检查在同一事务。"""
    from redis.asyncio import Redis

    ImportUtil.find_models(MappedBase)
    approved = json.loads(report.read_text(encoding="utf-8"))
    identity = {"type": settings.DATABASE_TYPE, "host": settings.DATABASE_HOST, "name": settings.DATABASE_NAME}
    if approved.get("database") != identity or approved.get("environment") != settings.ENVIRONMENT.value:
        raise DeploymentError("CLEANUP_SCOPE_CHANGED", "批准清单与目标环境/数据库不匹配")
    batches = [row for row in approved.get("batches", []) if row.get("dataset") == dataset]
    if len(batches) != 1:
        raise DeploymentError("CLEANUP_SCOPE_CHANGED", "批准清单必须包含唯一的目标批次")
    batch = batches[0]
    if batch.get("external_references") or batch.get("warnings") or set(batch["ids"]) - set(DELETE_ORDER):
        raise DeploymentError("CLEANUP_SCOPE_CHANGED", "清单存在冲突、异常或未知表，不执行删除")
    if apply and (not directory.is_dir() or any(directory.iterdir())):
        raise DeploymentError("CLEANUP_BACKUP_INVALID", "备份目录须预先创建且为空")
    async with initialization_lock():
        metadata = MetaData()
        async with async_engine.connect() as connection:
            await connection.run_sync(metadata.reflect)
            if connection.dialect.name == "mysql":
                engines = (
                    await connection.execute(text("SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=:name AND TABLE_TYPE='BASE TABLE'"), {"name": settings.DATABASE_NAME})
                ).all()
                if any(engine != "InnoDB" for _, engine in engines):
                    raise DeploymentError("CLEANUP_SCOPE_CHANGED", "存在非事务表，不执行自动清理")
        tables = dict(metadata.tables)
        if settings.DATABASE_TYPE not in {"mysql", "sqlite"}:
            raise DeploymentError("CLEANUP_SCOPE_CHANGED", "当前仅验证了MySQL清理及SQLite测试")
        redis = Redis.from_url(settings.REDIS_URI) if settings.DATABASE_TYPE == "mysql" else None
        try:
            if redis:
                await redis.ping()
            async with async_engine.connect() as connection:
                connection = await connection.execution_options(isolation_level="SERIALIZABLE")
                async with connection.begin(), AsyncSession(bind=connection, autoflush=False) as db:
                    # 全库当前行/索引范围加锁，阻断本次核查与删除间的并发改动。
                    for table in sorted(tables.values(), key=lambda table: table.name):
                        await db.execute(select(*table.primary_key.columns).with_for_update() if len(table.primary_key.columns) else select(table).with_for_update())
                    params = tables["sys_param"]
                    value = await db.scalar(select(params.c.config_value).where(params.c.id == batch["manifest_id"], params.c.config_key == f"zhicang_init_demo_{dataset}"))
                    if not value:
                        raise DeploymentError("CLEANUP_SCOPE_CHANGED", "目标完成标记已不存在或改变")
                    current = await audit_dataset(db, dataset, json.loads(value), set(tables))
                    for field in ("ids", "links", "counts", "base_date", "prefix"):
                        if canonical(current[field]) != canonical(batch[field]):
                            raise DeploymentError("CLEANUP_SCOPE_CHANGED", f"清理范围已变化：{field}")
                    marker_ids = list((await db.scalars(select(params.c.id).where(params.c.config_key == f"zhicang_init_org_demo-{dataset}"))).all())
                    if current["external_references"] or current["warnings"] or sorted(marker_ids) != sorted(batch["organization_manifest_ids"]):
                        raise DeploymentError("CLEANUP_SCOPE_CHANGED", "引用或批次标记已变化，须重新审核")
                    users = tables["sys_user"]
                    accounts = list((await db.scalars(select(users.c.username).where(users.c.id.in_(batch["ids"]["sys_user"])))).all())
                    if await db.scalar(select(users.c.id).where(users.c.id.in_(batch["ids"]["sys_user"]), users.c.is_superuser.is_(True)).limit(1)):
                        raise DeploymentError("CLEANUP_SCOPE_CHANGED", "目标账号已变更为超管，停止清理")
                    for name in ("ims_receivable", "ims_payable"):
                        table = tables[name]
                        if await db.scalar(select(table.c.id).where(table.c.id.in_(batch["ids"][name]), table.c.allocated_amount != 0).limit(1)):
                            raise DeploymentError("CLEANUP_SCOPE_CHANGED", "目标往来账已有核销，停止清理")
                    # 非模型AI表以用户名关联，不能让历史会话成为未审查的附带删除。
                    for name, table in tables.items():
                        if name.startswith("agno_") and "user_id" in table.c:
                            if await db.scalar(select(func.count()).select_from(table).where(table.c.user_id.in_([*accounts, *map(str, batch["ids"]["sys_user"])]))):
                                raise DeploymentError("CLEANUP_SCOPE_CHANGED", "发现旧账号AI数据，须另行审核")
                    selected, before = await snapshot(db, tables, batch)
                    if not apply:
                        return {"mode": "dry-run", "database": identity, "dataset": dataset, "counts": {name: len(rows) for name, rows in selected.items()}, "deleted": False}
                    dump = mysql_dump(directory) if settings.DATABASE_TYPE == "mysql" else None
                    backup_sha = save_private(directory / "target-rows.json", {"database": identity, "dataset": dataset, "rows": selected, "retained": before})
                    sessions: list[dict[str, Any]] = []
                    if redis:
                        async for key in redis.scan_iter(match="user_session:*"):
                            raw = await redis.get(key)
                            session = json.loads(raw) if raw else {}
                            if session.get("user_id") in batch["ids"]["sys_user"]:
                                if session.get("user_name") not in accounts:
                                    raise DeploymentError("CLEANUP_SCOPE_CHANGED", "缓存账号身份不一致，停止清理")
                                suffix = key.decode().split(":", 1)[1]
                                for prefix in ("user_session", "access_token", "refresh_token"):
                                    token_key = f"{prefix}:{suffix}"
                                    data = await redis.get(token_key)
                                    if data is not None:
                                        sessions.append({"key": token_key, "value": base64.b64encode(data).decode(), "ttl": await redis.ttl(token_key)})
                    save_private(directory / "sessions.json", sessions)
                    save_private(
                        directory / "prepared.json",
                        {"database": identity, "dataset": dataset, "dump": dump, "target_sha256": backup_sha, "counts": {name: len(rows) for name, rows in selected.items()}},
                    )
                    if redis and sessions:
                        await redis.delete(*(row["key"] for row in sessions))
                    deleted: dict[str, int] = {}
                    for name in DELETE_ORDER:
                        rows = selected.get(name, [])
                        if not rows:
                            continue
                        result = await db.execute(delete(tables[name]).where(target_predicate(tables[name], batch)))
                        if result.rowcount != len(rows):
                            raise DeploymentError("CLEANUP_SCOPE_CHANGED", f"{name} 删除数量不一致，事务回滚")
                        deleted[name] = result.rowcount
                    remaining, after = await snapshot(db, tables, batch)
                    if any(remaining.values()) or before != after:
                        raise DeploymentError("CLEANUP_VERIFICATION_FAILED", "目标残留或非目标数据变化，事务回滚")
                # 离开事务才可记录已提交，文件写失败时以数据库复查为准，不盲目重跑。
                result = {
                    "mode": "apply",
                    "database": identity,
                    "dataset": dataset,
                    "deleted": deleted,
                    "retained_verified": True,
                    "session_keys_revoked": len(sessions),
                    "backup_dir": str(directory),
                    "committed": True,
                }
                save_private(directory / "completed.json", result)
                return result
        finally:
            if redis:
                await redis.aclose()
