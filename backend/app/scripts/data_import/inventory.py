"""按需导入标准业务样例，组织与单据同事务写入，不参与系统初始化。"""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import MappedBase
from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.database import async_db_session
from app.modules.inventory.basic.goods.schema import GoodsCreateSchema
from app.modules.inventory.basic.model import CustomerModel, GoodsCategoryModel, GoodsModel, SupplierModel, WarehouseModel
from app.modules.inventory.purchase.inbound.schema import PurchaseInConfirmSchema, PurchaseInCreateSchema, PurchaseInVoidSchema
from app.modules.inventory.purchase.inbound.service import PurchaseInService
from app.modules.inventory.purchase.return_order.schema import PurchaseReturnConfirmSchema, PurchaseReturnCreateSchema
from app.modules.inventory.purchase.return_order.service import PurchaseReturnService
from app.modules.inventory.sale.out.schema import SaleOutConfirmSchema, SaleOutCreateSchema, SaleOutVoidSchema
from app.modules.inventory.sale.out.service import SaleOutService
from app.modules.inventory.sale.return_order.schema import SaleReturnConfirmSchema, SaleReturnCreateSchema
from app.modules.inventory.sale.return_order.service import SaleReturnService
from app.modules.inventory.stock.document_schema import CheckCreateSchema, OpeningCreateSchema, VersionBody
from app.modules.inventory.stock.document_service import StockDocumentService
from app.modules.system.dept.model import DeptModel
from app.modules.system.menu.model import MenuModel
from app.modules.system.position.model import PositionModel
from app.modules.system.role.model import RoleModel
from app.modules.system.user.model import UserModel
from app.scripts.deployment.check import check_installation
from app.scripts.deployment.common import MANIFEST_PREFIX, DeploymentError, initialization_lock
from app.scripts.deployment.organization import OrganizationInput, add_manifest, import_organization, manifest


async def check_conflicts(db: AsyncSession, spec: OrganizationInput) -> None:
    """业务编码、用户名及分类名冲突时拒绝，不复用档案或自动改名。"""
    checks = [
        (DeptModel, "code", [row.code for row in spec.departments]),
        (DeptModel, "name", [row.name for row in spec.departments]),
        (PositionModel, "code", [row.code for row in spec.positions]),
        (PositionModel, "name", [row.name for row in spec.positions]),
        (RoleModel, "code", [row.code for row in spec.roles]),
        (RoleModel, "name", [row.name for row in spec.roles]),
        (UserModel, "username", [row.username for row in spec.users]),
        (GoodsCategoryModel, "name", ["办公耗材", "包装材料", "仓储用品", "电子配件", "清洁用品", "劳保用品"]),
        (GoodsModel, "goods_code", [f"G{index:03}" for index in range(1, 31)]),
        (CustomerModel, "customer_code", [f"C{index:02}" for index in range(1, 11)]),
        (SupplierModel, "supplier_code", [f"S{index:02}" for index in range(1, 9)]),
        (WarehouseModel, "warehouse_code", [f"W{index:02}" for index in range(1, 4)]),
    ]
    conflicts: dict[str, list[str]] = {}
    for model, field, values in checks:
        column = getattr(model, field)
        existing = list((await db.scalars(select(column).where(column.in_(values)))).all())
        if existing:
            conflicts[f"{model.__tablename__}.{field}"] = existing
    if conflicts:
        import json

        raise DeploymentError("IMPORT_DATA_CONFLICT", f"既有业务编码/名称冲突：{json.dumps(conflicts, ensure_ascii=False)}")


async def import_records(db: AsyncSession, spec: OrganizationInput) -> dict[str, list[int]]:
    """仅记录本事务新建组织与新账号创建的业务行，不标记业务字段。"""
    records: dict[str, list[int]] = {}
    for model, field, values in (
        (DeptModel, "code", [row.code for row in spec.departments]),
        (PositionModel, "code", [row.code for row in spec.positions]),
        (RoleModel, "code", [row.code for row in spec.roles]),
        (UserModel, "username", [row.username for row in spec.users]),
    ):
        records[model.__tablename__] = sorted((await db.scalars(select(model.id).where(getattr(model, field).in_(values)))).all())
    actor = await db.scalar(select(UserModel.id).where(UserModel.username == spec.users[0].username))
    for table in MappedBase.metadata.tables.values():
        if table.name.startswith("ims_") and table.name != "ims_document_sequence" and "id" in table.c and "created_id" in table.c:
            ids = sorted((await db.scalars(select(table.c.id).where(table.c.created_id == actor))).all())
            if ids:
                records[table.name] = ids
    return records


def business_organization(dataset: str, permissions: list[str]) -> OrganizationInput:
    """使用正常组织编码与人员姓名，不通过业务字段标记数据来源。"""
    groups = [("HQ", "公司总部"), ("BUY", "采购部"), ("SALE", "销售部"), ("STOCK", "仓储部"), ("FIN", "财务部"), ("OPS", "运营部")]
    jobs = [
        ("manager", "业务管理员", "HQ", None),
        ("buyer", "采购员", "BUY", "purchase"),
        ("seller", "销售员", "SALE", "sale"),
        ("keeper", "仓管员", "STOCK", "stock"),
        ("finance", "财务", "FIN", "finance"),
        ("viewer", "经营查看", "OPS", "report"),
    ]
    roles = []
    for key, label, _, domain in jobs:
        allowed = (
            permissions
            if domain is None
            else [
                permission
                for permission in permissions
                if (domain == "purchase" and ":purchase_" in permission)
                or (domain == "sale" and ":sale_" in permission)
                or (domain == "stock" and any(f":{name}:" in permission for name in ("stock_balance", "stock_log", "stock_opening", "stock_check")))
                or (domain == "finance" and any(f":{name}:" in permission for name in ("receivable", "payable")))
                or (domain == "report" and "_report:" in permission)
            ]
        )
        roles.append({"code": key.upper(), "name": label, "data_scope": 3 if key in {"manager", "viewer", "finance"} else 2, "permissions": allowed})
    people = [("zhangming", "张明"), ("liwei", "李伟"), ("wangfang", "王芳"), ("chenqiang", "陈强"), ("liumin", "刘敏"), ("zhoujing", "周静")]
    users = [
        {
            "username": people[index][0],
            "name": people[index][1],
            "dept_code": group,
            "role_codes": [key.upper()],
            "position_codes": [key.upper()],
            "password_env": "INVENTORY_DATA_PASSWORD",
        }
        for index, (key, label, group, _) in enumerate(jobs)
    ]
    for index, (username, name) in enumerate((("zhaolei", "赵磊"), ("sunli", "孙丽"), ("zhenghao", "郑浩"), ("wuyue", "吴越")), start=1):
        users.append({**users[index], "username": username, "name": name})
    return OrganizationInput.model_validate(
        {
            "dataset": f"import-{dataset}",
            "departments": [{"code": key, "name": name, "parent_code": None if key == "HQ" else "HQ"} for key, name in groups],
            "positions": [{"code": key.upper(), "name": name} for key, name, _, _ in jobs],
            "roles": roles,
            "users": users,
        }
    )


async def create_business_data(db: AsyncSession, base: date, spec: OrganizationInput) -> dict[str, Any]:
    """只使用真实单据服务记账，不直接写库存余额或应收应付。"""
    actor = await db.scalar(select(UserModel).where(UserModel.username == spec.users[0].username))
    if actor is None:
        raise DeploymentError("INIT_DATA_INVALID", "业务管理员不存在")
    auth = AuthSchema(user=CoreUserSchema.model_validate(actor), permissions=["module_inventory:goods:query"])
    tag = None
    category_names = ["办公耗材", "包装材料", "仓储用品", "电子配件", "清洁用品", "劳保用品"]
    categories = [GoodsCategoryModel(name=name, sort=index, status=0, created_id=actor.id, updated_id=actor.id) for index, name in enumerate(category_names)]
    db.add_all(categories)
    await db.flush()
    products = [
        "打印纸",
        "文件夹",
        "签字笔",
        "标签纸",
        "订书机",
        "封箱胶带",
        "包装纸箱",
        "气泡膜",
        "打包带",
        "缠绕膜",
        "收纳箱",
        "货架隔板",
        "周转筐",
        "托盘垫板",
        "标签夹",
        "数据线",
        "电源适配器",
        "网线",
        "插座",
        "鼠标",
        "清洁布",
        "拖把",
        "垃圾袋",
        "清洁剂",
        "扫把",
        "手套",
        "防尘口罩",
        "安全帽",
        "反光背心",
        "护目镜",
    ]
    goods: list[GoodsModel] = []
    for index, name in enumerate(products):
        cost = Decimal(5 + index * 2)
        values = GoodsCreateSchema(
            goods_code=f"G{index + 1:03}",
            goods_name=name,
            category_id=categories[index // 5].id,
            spec="标准装",
            unit="件",
            reference_cost_price=cost,
            sale_price=cost + 8,
            stock_min=150 if index == 0 else 10,
            stock_max=50 if index == 1 else 0,
            status=0,
            remark=tag,
        )
        goods.append(GoodsModel(**values.model_dump(), created_id=actor.id, updated_id=actor.id))
    customer_names = ["华星商贸", "远航办公", "新源科技", "启航物流", "博文文具", "东辰实业", "明达电子", "恒丰百货", "嘉禾包装", "兴业建材"]
    supplier_names = ["恒信纸业", "联创包装", "宏达仓储", "锐通电子", "洁新日化", "安信劳保", "益丰办公", "华联供应链"]
    customers = [CustomerModel(customer_code=f"C{index + 1:02}", customer_name=name, status=0, remark=tag, created_id=actor.id, updated_id=actor.id) for index, name in enumerate(customer_names)]
    suppliers = [SupplierModel(supplier_code=f"S{index + 1:02}", supplier_name=name, status=0, remark=tag, created_id=actor.id, updated_id=actor.id) for index, name in enumerate(supplier_names)]
    warehouses = [
        WarehouseModel(warehouse_code=f"W{index + 1:02}", warehouse_name=name, status=0, is_default=False, remark=tag, created_id=actor.id, updated_id=actor.id)
        for index, name in enumerate(("中心仓", "华东仓", "华南仓"))
    ]
    for rows in (goods, customers, suppliers, warehouses):
        db.add_all(rows)
    await db.flush()
    opening = StockDocumentService(auth, db, "opening")
    for warehouse in warehouses:
        document = await opening.create(
            OpeningCreateSchema(
                warehouse_id=warehouse.id,
                business_date=base - timedelta(days=90),
                remark=tag,
                items=[{"goods_id": good.id, "quantity": "1.000" if index == 29 else "100.000", "unit_cost": good.reference_cost_price} for index, good in enumerate(goods)],
            )
        )
        await opening.confirm(document.id, VersionBody(version=document.version))
    purchase, sale = PurchaseInService(auth, db), SaleOutService(auth, db)
    purchase_return, sale_return = PurchaseReturnService(auth, db), SaleReturnService(auth, db)
    for index in range(30):
        day = base - timedelta(days=(29 - index) * 3)
        warehouse = warehouses[index % 3]
        selected = [goods[(index + offset) % len(goods)] for offset in range(3)]
        inbound = await purchase.create(
            PurchaseInCreateSchema(
                supplier_id=suppliers[index % 8].id,
                warehouse_id=warehouse.id,
                business_date=day,
                remark=tag,
                items=[{"goods_id": good.id, "quantity": "8.000", "unit_price": good.reference_cost_price} for good in selected],
            )
        )
        inbound = await purchase.confirm(inbound.id, PurchaseInConfirmSchema(version=inbound.version))
        outbound = await sale.create(
            SaleOutCreateSchema(
                customer_id=customers[index % 10].id,
                warehouse_id=warehouse.id,
                business_date=day,
                discount_amount="1.00",
                remark=tag,
                items=[{"goods_id": good.id, "quantity": "3.000", "unit_price": good.sale_price} for good in selected],
            )
        )
        outbound = await sale.confirm(outbound.id, SaleOutConfirmSchema(version=outbound.version))
        if index % 10 == 0:
            item = inbound.items[0]
            returned = await purchase_return.create(
                PurchaseReturnCreateSchema(
                    supplier_id=inbound.supplier_id,
                    warehouse_id=warehouse.id,
                    source_purchase_in_id=inbound.id,
                    business_date=day + timedelta(days=1),
                    return_reason="商品质量问题",
                    remark=tag,
                    items=[{"goods_id": item.goods_id, "source_purchase_in_item_id": item.id, "quantity": "1.000", "unit_price": item.unit_price}],
                )
            )
            await purchase_return.confirm(returned.id, PurchaseReturnConfirmSchema(version=returned.version))
            item = outbound.items[0]
            returned_sale = await sale_return.create(
                SaleReturnCreateSchema(
                    customer_id=outbound.customer_id,
                    warehouse_id=warehouse.id,
                    source_sale_out_id=outbound.id,
                    business_date=day + timedelta(days=1),
                    return_reason="商品质量问题",
                    remark=tag,
                    items=[{"goods_id": item.goods_id, "source_sale_out_item_id": item.id, "quantity": "1.000", "unit_price": item.unit_price}],
                )
            )
            await sale_return.confirm(returned_sale.id, SaleReturnConfirmSchema(version=returned_sale.version))
    check = StockDocumentService(auth, db, "check")
    for warehouse in warehouses:
        snapshots = await check.snapshot(warehouse.id, [goods[0].id, goods[1].id])
        document = await check.create(
            CheckCreateSchema(
                warehouse_id=warehouse.id,
                business_date=base,
                remark=tag,
                items=[{"goods_id": row["goods_id"], "actual_quantity": Decimal(row["system_quantity"]) + (1 if index == 0 else -1)} for index, row in enumerate(snapshots)],
            )
        )
        await check.confirm(document.id, VersionBody(version=document.version))
        buying = PurchaseInCreateSchema(
            supplier_id=suppliers[0].id, warehouse_id=warehouse.id, business_date=base, remark=tag, items=[{"goods_id": goods[0].id, "quantity": "2.000", "unit_price": goods[0].reference_cost_price}]
        )
        await purchase.create(buying)
        voided = await purchase.create(buying)
        voided = await purchase.confirm(voided.id, PurchaseInConfirmSchema(version=voided.version))
        await purchase.void(voided.id, PurchaseInVoidSchema(version=voided.version, void_reason="单据录入有误"))
        selling = SaleOutCreateSchema(
            customer_id=customers[0].id, warehouse_id=warehouse.id, business_date=base, remark=tag, items=[{"goods_id": goods[0].id, "quantity": "1.000", "unit_price": goods[0].sale_price}]
        )
        await sale.create(selling)
        voided_sale = await sale.create(selling)
        voided_sale = await sale.confirm(voided_sale.id, SaleOutConfirmSchema(version=voided_sale.version))
        await sale.void(voided_sale.id, SaleOutVoidSchema(version=voided_sale.version, void_reason="单据录入有误"))
    return {
        "categories": 6,
        "goods": 30,
        "customers": 10,
        "suppliers": 8,
        "warehouses": 3,
        "purchase_in": 36,
        "sale_out": 36,
        "purchase_return": 3,
        "sale_return": 3,
        "stock_opening": 3,
        "stock_check": 3,
        "accounts": [row.username for row in spec.users],
    }


async def import_inventory_data(apply: bool = False, dataset: str = "standard-v1", base_date: date | None = None) -> dict[str, Any]:
    """相同数据集保留首次基准日期，重跑不重复创建或确认单据。"""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,19}", dataset):
        raise DeploymentError("INIT_DATA_INVALID", "数据集须为1至20位字母、数字、下划线或短横线", 2)
    await check_installation()
    key = f"{MANIFEST_PREFIX}import_inventory_{dataset}"

    async def process(db: AsyncSession) -> dict[str, Any]:
        """标记与业务同事务提交，失败不会留下已完成标记。"""
        previous = await manifest(db, key)
        if previous:
            if base_date is not None and base_date.isoformat() != previous.get("base_date"):
                raise DeploymentError("INIT_DATA_CONFLICT", "同一数据集不能更换基准日期")
            return {"mode": "apply" if apply else "dry-run", "dataset": dataset, "skipped": True, "base_date": previous["base_date"], "created": {}}
        base = base_date or datetime.now(ZoneInfo("Asia/Shanghai")).date()
        if base > datetime.now(ZoneInfo("Asia/Shanghai")).date():
            raise DeploymentError("INIT_DATA_INVALID", "业务基准日期不能晚于今天", 2)
        permissions = sorted(
            set((await db.scalars(select(MenuModel.permission).where(MenuModel.permission.startswith("module_inventory:"), MenuModel.status == 0, MenuModel.is_deleted.is_(False)))).all())
        )
        spec = business_organization(dataset, permissions)
        await check_conflicts(db, spec)
        organization = await import_organization(db, spec, apply)
        if not apply:
            return {
                "mode": "dry-run",
                "dataset": dataset,
                "base_date": base,
                "organization": organization,
                "planned": {"goods": 30, "warehouses": 3, "business_documents": 84},
                "password_env": "INVENTORY_DATA_PASSWORD",
            }
        counts = await create_business_data(db, base, spec)
        created_rows = await import_records(db, spec)
        add_manifest(db, key, {"dataset": dataset, "base_date": base.isoformat(), "counts": counts, "records": created_rows, "accounts": counts["accounts"]})
        return {"mode": "apply", "dataset": dataset, "base_date": base, "organization": organization, "created": counts}

    if not apply:
        async with async_db_session() as db:
            return await process(db)
    async with initialization_lock(), async_db_session() as db, db.begin():
        return await process(db)
