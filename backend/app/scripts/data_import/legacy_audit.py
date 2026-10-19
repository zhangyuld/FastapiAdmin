"""旧D前缀数据只读核查：按完成标记及精确编码定位，不提供删除入口。"""

import hashlib
import json
from typing import Any

from sqlalchemy import and_, inspect, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.setting import settings
from app.core.base_model import MappedBase
from app.core.database import async_db_session, async_engine
from app.scripts.deployment.common import DeploymentError
from app.utils.import_util import ImportUtil

DOCUMENTS = {
    "purchase_in": "ims_purchase_in",
    "purchase_return": "ims_purchase_return",
    "sale_out": "ims_sale_out",
    "sale_return": "ims_sale_return",
    "opening_balance": "ims_stock_opening",
    "stock_check": "ims_stock_check",
    "stock_check_gain": "ims_stock_check",
    "stock_check_loss": "ims_stock_check",
}


async def audit_dataset(db: AsyncSession, dataset: str, value: dict[str, Any], available: set[str]) -> dict[str, Any]:
    """完成标记、精确编码和创建人共同限定候选范围，引用另行报告。"""
    tables = MappedBase.metadata.tables
    prefix = "D" + hashlib.sha256(dataset.encode()).hexdigest()[:10]
    targets: dict[str, set[int]] = {}
    warnings: list[str] = []
    job_names = ("manager", "buyer", "seller", "keeper", "finance", "viewer")
    accounts = value.get("counts", {}).get("accounts", [])
    expected_accounts = [f"{prefix.lower()}_{key}" for key in job_names] + [f"{prefix.lower()}_{key}2" for key in ("buyer", "seller", "keeper", "finance")]
    if sorted(accounts) != sorted(expected_accounts):
        raise DeploymentError("LEGACY_AUDIT_CONFLICT", "旧数据集账号清单与原生成规则不一致，不能自动推断范围")

    async def collect(name: str, predicate: Any) -> None:
        """仅保留主键，报告不读取密码、连接密钥或完整个人资料。"""
        if name not in available:
            warnings.append(f"缺少表 {name}，核查不完整")
            targets[name] = set()
            return
        targets[name] = set((await db.scalars(select(tables[name].c.id).where(predicate))).all())

    await collect("sys_user", tables["sys_user"].c.username.in_(expected_accounts))
    users = targets["sys_user"]
    for name, values in (
        ("sys_dept", [f"{prefix}_{key}" for key in ("HQ", "BUY", "SALE", "STOCK", "FIN", "OPS")]),
        ("sys_position", [f"{prefix}_{key}" for key in job_names]),
        ("sys_role", [f"{prefix}_{key}" for key in job_names]),
    ):
        await collect(name, tables[name].c.code.in_(values))
    categories = [f"{prefix}_{name}" for name in ("办公耗材", "包装材料", "仓储用品", "电子配件", "清洁用品", "劳保用品")]
    await collect("ims_goods_category", and_(tables["ims_goods_category"].c.name.in_(categories), tables["ims_goods_category"].c.created_id.in_(users)))
    for name, field, letter, count, width in (
        ("ims_goods", "goods_code", "G", 30, 3),
        ("ims_customer", "customer_code", "C", 10, 2),
        ("ims_supplier", "supplier_code", "S", 8, 2),
        ("ims_warehouse", "warehouse_code", "W", 3, 2),
    ):
        codes = [f"{prefix}_{letter}{index:0{width}d}" for index in range(1, count + 1)]
        await collect(name, and_(tables[name].c[field].in_(codes), tables[name].c.created_id.in_(users)))
    for name in set(DOCUMENTS.values()):
        table = tables[name]
        await collect(name, and_(table.c.remark == f"演示数据集 {dataset}", table.c.created_id.in_(users), table.c.warehouse_id.in_(targets["ims_warehouse"])))
    for name, parent, field in (
        ("ims_purchase_in_item", "ims_purchase_in", "purchase_in_id"),
        ("ims_purchase_return_item", "ims_purchase_return", "purchase_return_id"),
        ("ims_sale_out_item", "ims_sale_out", "sale_out_id"),
        ("ims_sale_return_item", "ims_sale_return", "sale_return_id"),
        ("ims_stock_opening_item", "ims_stock_opening", "stock_opening_id"),
        ("ims_stock_check_item", "ims_stock_check", "stock_check_id"),
    ):
        await collect(name, tables[name].c[field].in_(targets[parent]))
    for name in ("ims_stock_log", "ims_receivable", "ims_payable", "ims_business_log"):
        table = tables[name]
        sources = or_(*(and_(table.c.business_type == kind, table.c.business_id.in_(targets[parent])) for kind, parent in DOCUMENTS.items()))
        await collect(name, and_(sources, table.c.created_id.in_(users)))
    balance = tables["ims_stock_balance"]
    await collect("ims_stock_balance", and_(balance.c.warehouse_id.in_(targets["ims_warehouse"]), balance.c.goods_id.in_(targets["ims_goods"])))

    links: dict[str, list[dict[str, Any]]] = {}
    for name, field, owner in (
        ("sys_user_roles", "user_id", "sys_user"),
        ("sys_user_positions", "user_id", "sys_user"),
        ("sys_role_menus", "role_id", "sys_role"),
        ("sys_role_depts", "role_id", "sys_role"),
    ):
        if name in available:
            table = tables[name]
            links[name] = [dict(row) for row in (await db.execute(select(*table.primary_key.columns).where(table.c[field].in_(targets[owner])))).mappings()]

    external: list[dict[str, Any]] = []
    for name in ("ims_stock_log", "ims_receivable", "ims_payable", "ims_business_log"):
        if name in available:
            table = tables[name]
            source = or_(*(and_(table.c.business_type == kind, table.c.business_id.in_(targets[parent])) for kind, parent in DOCUMENTS.items()))
            ids = list((await db.scalars(select(table.c.id).where(source, ~table.c.id.in_(targets[name])))).all())
            if ids:
                external.append({"table": name, "field": "business_id", "count": len(ids), "ids": ids})
    for table in tables.values():
        if table.name not in available:
            continue
        for column in table.c:
            for foreign in column.foreign_keys:
                parent = foreign.column.table.name
                if not targets.get(parent):
                    continue
                statement = select(*table.primary_key.columns).where(column.in_(targets[parent]))
                if table.name in targets:
                    statement = statement.where(~table.c.id.in_(targets[table.name]))
                rows = [dict(row) for row in (await db.execute(statement)).mappings()]
                if table.name in links:
                    rows = [row for row in rows if row not in links[table.name]]
                if rows:
                    external.append({"table": table.name, "field": column.name, "target": parent, "count": len(rows), "keys": rows})
    # V2资金和核销使用多态ID，不在数据库外键中，须单独核对。
    for name, kind_field, id_field, kinds in (
        ("ims_fund_transaction", "party_type", "party_id", {"customer": "ims_customer", "supplier": "ims_supplier"}),
        ("ims_fund_allocation", "bill_type", "bill_id", {"receivable": "ims_receivable", "payable": "ims_payable"}),
    ):
        if name in available:
            table = tables[name]
            condition = or_(*(and_(table.c[kind_field] == kind, table.c[id_field].in_(targets[parent])) for kind, parent in kinds.items()))
            ids = list((await db.scalars(select(table.c.id).where(condition))).all())
            if ids:
                external.append({"table": name, "field": id_field, "count": len(ids), "ids": ids})
    expected_counts = {
        "sys_user": 10,
        "sys_dept": 6,
        "sys_position": 6,
        "sys_role": 6,
        "ims_goods_category": 6,
        "ims_goods": 30,
        "ims_customer": 10,
        "ims_supplier": 8,
        "ims_warehouse": 3,
        "ims_purchase_in": 36,
        "ims_sale_out": 36,
        "ims_purchase_return": 3,
        "ims_sale_return": 3,
        "ims_stock_opening": 3,
        "ims_stock_check": 3,
    }
    for name, count in expected_counts.items():
        if len(targets.get(name, set())) != count:
            warnings.append(f"{name} 候选{len(targets.get(name, set()))}条，与原批次预期{count}条不一致")
    return {
        "dataset": dataset,
        "prefix": prefix,
        "base_date": value.get("base_date"),
        "counts": {name: len(ids) for name, ids in targets.items()},
        "ids": {name: sorted(ids) for name, ids in targets.items()},
        "links": links,
        "external_references": external,
        "warnings": warnings,
        "requires_approval": True,
        "deleted": False,
    }


async def audit_legacy_data() -> dict[str, Any]:
    """只读列出所有旧完成批次；无标记时不以D开头做模糊删除推断。"""
    ImportUtil.find_models(MappedBase)
    async with async_engine.connect() as connection:
        available = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
    table = MappedBase.metadata.tables["sys_param"]
    if "sys_param" not in available:
        raise DeploymentError("APP_NOT_INITIALIZED", "系统参数表不存在，无法核对旧导入记录")
    async with async_db_session() as db:
        rows = (await db.execute(select(table.c.id, table.c.config_key, table.c.config_value).where(table.c.config_key.startswith("zhicang_init_demo_")))).mappings().all()
        batches = []
        for row in rows:
            dataset = row["config_key"].removeprefix("zhicang_init_demo_")
            try:
                value = json.loads(row["config_value"])
                if value["dataset"] != dataset:
                    raise ValueError("dataset")
            except (ValueError, TypeError, KeyError) as error:
                raise DeploymentError("LEGACY_AUDIT_CONFLICT", "旧数据集完成标记损坏，不能推断清理范围") from error
            result = await audit_dataset(db, dataset, value, available)
            result["manifest_id"] = row["id"]
            result["organization_manifest_ids"] = list((await db.scalars(select(table.c.id).where(table.c.config_key == f"zhicang_init_org_demo-{dataset}"))).all())
            batches.append(result)
    return {
        "mode": "read-only",
        "environment": settings.ENVIRONMENT.value,
        "database": {"type": settings.DATABASE_TYPE, "host": settings.DATABASE_HOST, "name": settings.DATABASE_NAME},
        "batches": batches,
        "deleted": False,
        "notes": ["未执行删除，须审核清单并备份后另行确认", "全局单据流水号不回退；辅助表、文件及缓存会话需在清理前进一步核对"],
    }
