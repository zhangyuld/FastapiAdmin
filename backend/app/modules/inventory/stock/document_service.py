from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.inventory.basic.model import GoodsModel, WarehouseModel
from app.modules.inventory.common.business_log import BusinessLogService
from app.modules.system.user.model import UserModel
from app.utils.common_util import search_to_dict

from .document_crud import Document, StockDocumentCRUD
from .document_schema import (
    CheckCreateSchema,
    CheckUpdateSchema,
    DeleteBody,
    DocumentExport,
    DocumentQuery,
    OpeningCreateSchema,
    OpeningUpdateSchema,
    StockDocumentOut,
    StockItemOut,
    VersionBody,
    VoidBody,
)
from .export import export_rows
from .model import StockBalanceModel, StockLogModel
from .posting import StockPostingLine, StockPostingService

DOCUMENT_COLUMNS = {
    "doc_no": "单据编号",
    "warehouse_name": "仓库",
    "business_date": "业务日期",
    "status": "状态",
    "created_name": "创建人",
    "confirmed_time": "确认时间",
    "voided_time": "作废时间",
    "remark": "备注",
}
MAX_AMOUNT = Decimal("9999999999999999.99")


class StockDocumentService:
    """库存模块内期初和盘点业务编排，所有更新使用同一请求事务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession, kind: Literal["opening", "check"]) -> None:
        """配置单据类型，不向采购销售扩散库存专有规则。"""
        self.auth, self.db, self.kind = auth, db, kind
        self.crud = StockDocumentCRUD(auth, db, kind)
        self.stock = StockPostingService(auth, db)
        self.audit = BusinessLogService(auth, db)

    async def _output(self, document: Document, include_items: bool = False) -> StockDocumentOut:
        """组装历史名称与审计字段，禁止异步关系隐式加载。"""
        warehouse_name = await self.db.scalar(select(WarehouseModel.warehouse_name).where(WarehouseModel.id == document.warehouse_id))
        users = dict((await self.db.execute(select(UserModel.id, UserModel.name).where(UserModel.id.in_([value for value in (document.confirmed_id, document.voided_id) if value is not None])))).all())
        values = {column.key: getattr(document, column.key) for column in document.__table__.columns}
        values.update(
            doc_no=getattr(document, self.crud.number_field),
            warehouse_name=warehouse_name or "-",
            confirmed_name=users.get(document.confirmed_id),
            voided_name=users.get(document.voided_id),
            created_by=document.created_by,
            updated_by=document.updated_by,
        )
        if include_items:
            values["items"] = [StockItemOut.model_validate(item) for item in await self.crud.items(document.id)]
        return StockDocumentOut.model_validate(values)

    async def detail(self, id: int) -> StockDocumentOut:
        """授权主单后读取不可变业务明细或草稿快照。"""
        return await self._output(await self.crud.document(id), True)

    def _search(self, query: DocumentQuery) -> dict[str, Any]:
        """前端统一单号字段映射到期初或盘点的真实数据库列。"""
        search = search_to_dict(query)
        search.pop("doc_no", None)
        if query.doc_no and query.doc_no.strip():
            search[self.crud.number_field] = ("like", query.doc_no.strip())
        return search

    async def page(self, page_no: int, page_size: int, search: DocumentQuery, order_by: list[dict[str, str]] | None = None) -> PageResultSchema:
        """按单据数据范围分页，不加载商品明细。"""
        order = order_by or [{"id": "desc"}]
        for mapping in order:
            if not isinstance(mapping, dict):
                raise CustomException(msg="排序格式无效", status_code=422)
            for field, direction in mapping.items():
                if field not in self.crud.model.__table__.columns or not isinstance(direction, str) or direction.lower() not in {"asc", "desc"}:
                    raise CustomException(msg="排序字段或方向无效", status_code=422)
        result = await self.crud.page((page_no - 1) * page_size, page_size, order + [{"id": "desc"}], self._search(search))
        return PageResultSchema(page_no=page_no, page_size=page_size, total=result.total, has_next=result.has_next, items=[await self._output(row) for row in result.items])

    async def _archives(self, warehouse_id: int, ids: list[int]) -> dict[int, GoodsModel]:
        """按固定顺序共享锁校验启用档案，避免确认与停用并发。"""
        warehouse = (await self.db.execute(select(WarehouseModel).where(WarehouseModel.id == warehouse_id).with_for_update(read=True))).scalar_one_or_none()
        if warehouse is None or warehouse.is_deleted or warehouse.status != 0:
            raise CustomException(msg="仓库不存在或已停用", status_code=400)
        goods = (await self.db.execute(select(GoodsModel).where(GoodsModel.id.in_(ids)).order_by(GoodsModel.id).with_for_update(read=True))).scalars().all()
        result = {row.id: row for row in goods if not row.is_deleted and row.status == 0}
        if set(result) != set(ids):
            raise CustomException(msg="存在无效或已停用商品", status_code=400)
        return result

    async def snapshot(self, warehouse_id: int, ids: list[int]) -> list[dict[str, Any]]:
        """读取实盘录入所需快照，无余额商品返回零数量与零版本。"""
        goods = await self._archives(warehouse_id, ids)
        result = []
        for id in sorted(ids):
            balance = (
                await self.db.execute(
                    select(StockBalanceModel)
                    .where(StockBalanceModel.warehouse_id == warehouse_id, StockBalanceModel.goods_id == id)
                    .with_for_update(read=True)
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if balance is not None and balance.is_deleted:
                raise CustomException(msg="库存余额已删除，不能盘点", status_code=409)
            item = goods[id]
            result.append(
                {
                    "goods_id": id,
                    "goods_code": item.goods_code,
                    "goods_name": item.goods_name,
                    "spec": item.spec,
                    "unit": item.unit,
                    "system_quantity": format(balance.quantity if balance else Decimal(0), ".3f"),
                    "system_stock_amount": format(balance.stock_amount if balance else Decimal(0), ".2f"),
                    "balance_version": balance.version if balance else 0,
                    "unit_cost": format(balance.avg_cost if balance else Decimal(0), ".4f"),
                }
            )
        return result

    @staticmethod
    def _check_cost(quantity: Decimal, amount: Decimal, actual: Decimal, input_cost: Decimal | None) -> tuple[Decimal, Decimal]:
        """盘亏按未舍入库存比例计价，全亏结清尾差；零库存盘盈须显式填成本。"""
        difference = actual - quantity
        with localcontext() as ctx:
            ctx.prec = 40
            if quantity > 0:
                price = (amount / quantity).quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)
                cost = -amount if actual == 0 else (amount * difference / quantity).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
            else:
                if difference > 0 and input_cost is None:
                    raise CustomException(msg="零库存盘盈必须填写单位成本", status_code=400)
                price = input_cost or Decimal("0.0000")
                cost = (difference * price).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
            if abs(cost) > MAX_AMOUNT or price > Decimal("99999999999999.9999"):
                raise CustomException(msg="盘点成本超过允许范围", status_code=400)
        return price, cost

    async def _build(self, data: OpeningCreateSchema | CheckCreateSchema, previous: dict[int, Any] | None = None) -> list[dict[str, Any]]:
        """期初生成金额；盘点保留原快照，仅新行或显式刷新读取新快照。"""
        goods = await self._archives(data.warehouse_id, [row.goods_id for row in data.items])
        snapshots = (
            {row["goods_id"]: row for row in await self.snapshot(data.warehouse_id, [item.goods_id for item in data.items if previous is None or item.goods_id not in previous])}
            if self.kind == "check"
            else {}
        )
        result = []
        for index, row in enumerate(data.items, 1):
            good = goods[row.goods_id]
            values = {"goods_id": good.id, "goods_code": good.goods_code, "goods_name": good.goods_name, "spec": good.spec, "unit": good.unit}
            with localcontext() as ctx:
                ctx.prec = 40
                if self.kind == "opening":
                    cost = (row.quantity * row.unit_cost).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
                    if cost > MAX_AMOUNT:
                        raise CustomException(msg="期初金额超过允许范围", status_code=400)
                    values.update(line_no=index, quantity=row.quantity, unit_cost=row.unit_cost, cost_amount=cost)
                else:
                    old = previous.get(row.goods_id) if previous else None
                    if old is not None:
                        if old.balance_version is None or old.system_stock_amount is None:
                            raise CustomException(msg="旧盘点草稿缺少库存快照，请先刷新快照", status_code=409)
                        quantity, amount, version = old.system_quantity, old.system_stock_amount, old.balance_version
                    else:
                        snapshot = snapshots[row.goods_id]
                        quantity, amount, version = Decimal(snapshot["system_quantity"]), Decimal(snapshot["system_stock_amount"]), snapshot["balance_version"]
                    price, cost = self._check_cost(quantity, amount, row.actual_quantity, row.unit_cost)
                    values.update(
                        system_quantity=quantity,
                        system_stock_amount=amount,
                        balance_version=version,
                        actual_quantity=row.actual_quantity,
                        difference_quantity=row.actual_quantity - quantity,
                        unit_cost=price,
                        cost_amount=cost,
                    )
            result.append(values)
        return result

    @staticmethod
    def _validate(document: Document, version: int, expected: int) -> None:
        """只允许目标状态及当前版本执行生命周期操作。"""
        if document.status != expected or document.version != version:
            raise CustomException(msg="单据状态或版本已变化，请刷新重试", status_code=409)

    async def create(self, data: OpeningCreateSchema | CheckCreateSchema) -> StockDocumentOut:
        """保存草稿快照不产生库存流水。"""
        rows = await self._build(data)
        document = await self.crud.create(
            {
                self.crud.number_field: f"{'OP' if self.kind == 'opening' else 'SC'}{datetime.now(UTC):%Y%m%d%H%M%S}{uuid4().hex}",
                "warehouse_id": data.warehouse_id,
                "business_date": data.business_date,
                "remark": data.remark,
                "status": 0,
                "version": 0,
            }
        )
        await self.crud.add_items(document.id, rows)
        return await self.detail(document.id)

    async def update(self, id: int, data: OpeningUpdateSchema | CheckUpdateSchema) -> StockDocumentOut:
        """完整保存草稿；同仓库已有盘点行不静默刷新快照。"""
        document = await self.crud.document(id, True)
        self._validate(document, data.version, 0)
        previous = {row.goods_id: row for row in await self.crud.items(id, True)} if self.kind == "check" and document.warehouse_id == data.warehouse_id else None
        rows = await self._build(data, previous)
        await self.crud.replace(document, data.model_dump(exclude={"items", "version"}), rows)
        return await self.detail(id)

    async def refresh(self, id: int, data: VersionBody) -> StockDocumentOut:
        """显式刷新草稿快照并递增版本，保留实盘数供用户重新核对。"""
        document = await self.crud.document(id, True)
        self._validate(document, data.version, 0)
        items = await self.crud.items(id, True)
        body = CheckCreateSchema(
            warehouse_id=document.warehouse_id,
            business_date=document.business_date,
            remark=document.remark,
            items=[{"goods_id": row.goods_id, "actual_quantity": row.actual_quantity, "unit_cost": row.unit_cost} for row in items],
        )
        await self.crud.replace(document, {}, await self._build(body))
        return await self.detail(id)

    async def delete(self, data: DeleteBody) -> list[int]:
        """按 ID 固定顺序逐单软删除，任一冲突整体回滚。"""
        for id in sorted(data.ids):
            document = await self.crud.document(id, True)
            self._validate(document, data.versions[id], 0)
            await self.crud.cas(document, self.crud._soft_delete_values(), 0)
        return data.ids

    async def _pair_logs(self, warehouse: int, goods: int) -> list[StockLogModel]:
        """在持有商品余额锁后读取全部历史流水，不能依赖旧事务快照。"""
        return list(
            (await self.db.execute(select(StockLogModel).where(StockLogModel.warehouse_id == warehouse, StockLogModel.goods_id == goods).order_by(StockLogModel.id).with_for_update())).scalars().all()
        )

    async def confirm(self, id: int, data: VersionBody) -> StockDocumentOut:
        """确认按商品顺序持有全部余额锁，再写状态、流水和日志。"""
        document = await self.crud.document(id, True)
        self._validate(document, data.version, 0)
        items = await self.crud.items(id, True)
        if not items:
            raise CustomException(msg="单据明细为空", status_code=409)
        await self._archives(document.warehouse_id, [row.goods_id for row in items])
        postings: dict[str, list[StockPostingLine]] = {}
        for row in items:
            balance = await self.stock._lock_balance(document.warehouse_id, row.goods_id, create=True)
            if self.kind == "opening":
                logs = await self._pair_logs(document.warehouse_id, row.goods_id)
                reversed_ids = {log.reversal_log_id for log in logs if log.operation_type == "void" and not log.is_deleted}
                if (
                    balance.quantity != 0
                    or balance.stock_amount != 0
                    or any(log.is_deleted or log.business_type != "opening_balance" or (log.operation_type == "confirm" and log.id not in reversed_ids) for log in logs)
                ):
                    raise CustomException(msg="商品已有有效期初或其他库存业务，不能重复初始化", status_code=409)
                with localcontext() as ctx:
                    ctx.prec = 40
                    expected = (row.quantity * row.unit_cost).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
                if row.quantity <= 0 or row.cost_amount != expected:
                    raise CustomException(msg="期初草稿金额异常，请重新保存", status_code=409)
                quantity, price, cost, business = row.quantity, row.unit_cost, row.cost_amount, "opening_balance"
            else:
                if (
                    row.balance_version is None
                    or row.system_stock_amount is None
                    or (row.balance_version, row.system_quantity, row.system_stock_amount) != (balance.version, balance.quantity, balance.stock_amount)
                ):
                    raise CustomException(msg="盘点期间库存发生变化，请刷新账面快照并重新核对实盘数量", status_code=409)
                price, cost = self._check_cost(balance.quantity, balance.stock_amount, row.actual_quantity, row.unit_cost)
                quantity = row.actual_quantity - balance.quantity
                row.unit_cost, row.cost_amount, row.difference_quantity = price, cost, quantity
                row.updated_id = self.auth.user.id
                if quantity == 0:
                    continue
                business = "stock_check_gain" if quantity > 0 else "stock_check_loss"
            postings.setdefault(business, []).append(StockPostingLine(row.goods_id, row.id, quantity, price, cost))
        now = datetime.now(UTC)
        await self.crud.cas(document, {"status": 1, "confirmed_id": self.auth.user.id, "confirmed_time": now}, 0)
        for business, lines in postings.items():
            await self.stock.post(
                warehouse_id=document.warehouse_id,
                business_type=business,
                operation_type="confirm",
                business_id=id,
                business_no=getattr(document, self.crud.number_field),
                business_date=document.business_date,
                posted_time=now,
                lines=lines,
                remark=document.remark,
            )
        await self.audit.record(
            business_type="opening_balance" if self.kind == "opening" else "stock_check",
            business_id=id,
            business_no=getattr(document, self.crud.number_field),
            action="confirm",
            before_status=0,
            after_status=1,
            operated_time=now,
        )
        return await self.detail(id)

    async def void(self, id: int, data: VoidBody) -> StockDocumentOut:
        """校验原确认流水后逐行冲销；期初有后续业务时禁止作废。"""
        document = await self.crud.document(id, True)
        self._validate(document, data.version, 1)
        items = await self.crud.items(id, True)
        for row in items:
            await self.stock._lock_balance(document.warehouse_id, row.goods_id, create=False)
        types = ["opening_balance"] if self.kind == "opening" else ["stock_check_gain", "stock_check_loss"]
        logs = list(
            (await self.db.execute(select(StockLogModel).where(StockLogModel.business_id == id, StockLogModel.business_type.in_(types), StockLogModel.operation_type == "confirm").with_for_update()))
            .scalars()
            .all()
        )
        expected_items = {row.id: row for row in items if self.kind == "opening" or row.difference_quantity != 0}
        if len(logs) != len(expected_items) or {log.business_item_id for log in logs} != set(expected_items):
            raise CustomException(msg="原确认流水不完整，不能作废", status_code=409)
        postings: dict[str, list[StockPostingLine]] = {}
        for log in logs:
            row = expected_items[log.business_item_id]
            quantity = row.quantity if self.kind == "opening" else row.difference_quantity
            if (
                log.is_deleted
                or log.goods_id != row.goods_id
                or log.warehouse_id != document.warehouse_id
                or log.change_quantity != quantity
                or log.cost_amount != row.cost_amount
                or log.unit_cost != row.unit_cost
            ):
                raise CustomException(msg="原流水与单据不一致，不能作废", status_code=409)
            if self.kind == "opening" and any(later.id > log.id for later in await self._pair_logs(document.warehouse_id, row.goods_id)):
                raise CustomException(msg="期初已发生后续库存业务，不能作废", status_code=409)
            postings.setdefault(log.business_type, []).append(StockPostingLine(log.goods_id, log.business_item_id, -log.change_quantity, log.unit_cost, -log.cost_amount, log.id))
        now = datetime.now(UTC)
        await self.crud.cas(document, {"status": 2, "voided_id": self.auth.user.id, "voided_time": now, "void_reason": data.void_reason}, 1)
        for business, lines in postings.items():
            await self.stock.post(
                warehouse_id=document.warehouse_id,
                business_type=business,
                operation_type="void",
                business_id=id,
                business_no=getattr(document, self.crud.number_field),
                business_date=document.business_date,
                posted_time=now,
                lines=lines,
                remark=data.void_reason,
            )
        await self.audit.record(
            business_type="opening_balance" if self.kind == "opening" else "stock_check",
            business_id=id,
            business_no=getattr(document, self.crud.number_field),
            action="void",
            before_status=1,
            after_status=2,
            operated_time=now,
            content=data.void_reason,
        )
        return await self.detail(id)

    async def export(self, data: DocumentExport) -> bytes:
        """导出全部有数据权限的主单，保留字段顺序与文件选项。"""
        documents = await self.crud.get_list(search=self._search(data.query), order_by=[{"id": "desc"}])
        rows = []
        for document in documents:
            output = await self._output(document)
            values = output.model_dump(mode="json")
            values["status"] = ["草稿", "已确认", "已作废"][output.status]
            values["created_name"] = output.created_by.name if output.created_by else ""
            rows.append(values)
        return await export_rows(rows, data, DOCUMENT_COLUMNS)
