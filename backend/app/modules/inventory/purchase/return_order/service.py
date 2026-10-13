from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.inventory.common.business_log import BusinessLogService
from app.modules.inventory.enums import BusinessOperationType, DocumentStatus, StockBusinessType
from app.modules.inventory.finance.payable import PayableService
from app.modules.inventory.stock.posting import StockPostingLine, StockPostingService
from app.utils.common_util import search_to_dict
from app.utils.excel_util import ExcelUtil

from ..inbound.crud import PurchaseInCRUD
from ..model import PurchaseInModel, PurchaseReturnModel
from .crud import PurchaseReturnCRUD, PurchaseReturnItemValues, ReturnedTotals
from .schema import (
    PurchaseReturnConfirmSchema,
    PurchaseReturnCreateSchema,
    PurchaseReturnDeleteSchema,
    PurchaseReturnDetailOutSchema,
    PurchaseReturnExportSchema,
    PurchaseReturnItemOutSchema,
    PurchaseReturnOutSchema,
    PurchaseReturnQueryParam,
    PurchaseReturnUpdateSchema,
    PurchaseReturnVoidSchema,
)

EXPORT_COLUMNS = {
    "order_no": "单据编号",
    "supplier_name": "供应商",
    "warehouse_name": "退货仓库",
    "business_date": "业务日期",
    "source_order_no": "原入库单号",
    "return_reason": "退货原因",
    "total_amount": "总金额",
    "status": "状态",
    "created_name": "创建人",
    "confirmed_time": "确认时间",
}
MAX_AMOUNT = Decimal("9999999999999999.99")


class PurchaseReturnService:
    """原单退货编排，来源锁统一保护数量和金额分摊，所有写入沿用请求事务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """绑定单据、来源、库存及应付服务，不创建独立事务。"""
        self.auth = auth
        self.db = db
        self.crud = PurchaseReturnCRUD(auth, db)
        self.source_crud = PurchaseInCRUD(auth, db)
        self.stock = StockPostingService(auth, db)
        self.payable = PayableService(auth, db)
        self.business_log = BusinessLogService(auth, db)

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: PurchaseReturnQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[PurchaseReturnOutSchema]:
        """分页筛选有权限的退货，来源单号由数据层子查询处理。"""
        result = await self.crud.page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            search=search_to_dict(search),
            order_by=self._validate_order_by(order_by),
        )
        return PageResultSchema[PurchaseReturnOutSchema](
            page_no=page_no,
            page_size=page_size,
            total=result.total,
            has_next=result.has_next,
            items=await self._serialize_documents(result.items),
        )

    async def detail(self, id: int, *, lock: bool = False) -> PurchaseReturnDetailOutSchema:
        """历史详情读取已保存快照，不按当前商品资料重新计算价格和金额。"""
        document = await self._get_document(id, lock=lock)
        output = (await self._serialize_documents([document]))[0]
        items = await self.crud.get_items(id, lock=lock)
        return PurchaseReturnDetailOutSchema(
            **output.model_dump(),
            items=[PurchaseReturnItemOutSchema.model_validate(item) for item in items],
        )

    async def create(self, data: PurchaseReturnCreateSchema) -> PurchaseReturnDetailOutSchema:
        """锁来源后创建退货草稿，校验可退数量但不预占库存或额度。"""
        source = await self._lock_source(data.source_purchase_in_id)
        items, total = await self._build_items(data, source)
        values = data.model_dump(exclude={"items"})
        values.update(order_no=self._generate_order_no(), status=DocumentStatus.DRAFT, version=0, total_amount=total)
        document = await self.crud.create_draft(values, items)
        return await self.detail(document.id, lock=True)

    async def update(self, id: int, data: PurchaseReturnUpdateSchema) -> PurchaseReturnDetailOutSchema:
        """切换来源时按来源 ID 排序锁新旧来源，再按版本完整更新草稿。"""
        document, sources = await self._lock_document(id, extra_source_id=data.source_purchase_in_id)
        self._validate_state(document, DocumentStatus.DRAFT, data.version)
        items, total = await self._build_items(data, sources[data.source_purchase_in_id])
        values = data.model_dump(exclude={"items", "version"})
        values["total_amount"] = total
        await self.crud.update_draft(id, data.version, values, items)
        return await self.detail(id, lock=True)

    async def delete(self, data: PurchaseReturnDeleteSchema) -> list[int]:
        """先锁全部来源，再按退货 ID 加锁删除，任一冲突则整批回滚。"""
        documents = await self.crud.get_list(search={"id": ("in", data.ids)})
        expected_sources = {document.id: document.source_purchase_in_id for document in documents}
        if set(expected_sources) != set(data.ids):
            raise CustomException(msg="部分退货单不存在或无权访问", status_code=404)
        for source_id in sorted({id for id in expected_sources.values() if id is not None}):
            await self._lock_source(source_id)
        for id in sorted(data.ids):
            document = await self._get_document(id, lock=True)
            if document.source_purchase_in_id != expected_sources[id]:
                raise CustomException(msg="退货来源已变化，请刷新后重试", status_code=409)
            self._validate_state(document, DocumentStatus.DRAFT, data.versions[id])
            await self.crud.delete_draft(id, data.versions[id])
        return data.ids

    async def confirm(self, id: int, data: PurchaseReturnConfirmSchema) -> PurchaseReturnDetailOutSchema:
        """实时重校来源、累计数量和成本，扣库存并生成负向应付。"""
        document, sources = await self._lock_document(id)
        self._validate_state(document, DocumentStatus.DRAFT, data.version)
        saved = await self.crud.get_items(id, lock=True)
        if not saved:
            raise CustomException(msg="退货明细为空，不能确认", status_code=409)
        check = PurchaseReturnCreateSchema(
            supplier_id=document.supplier_id,
            warehouse_id=document.warehouse_id,
            source_purchase_in_id=document.source_purchase_in_id,
            business_date=document.business_date,
            return_reason=document.return_reason,
            items=[
                {
                    "goods_id": item.goods_id,
                    "source_purchase_in_item_id": item.source_purchase_in_item_id,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                }
                for item in saved
            ],
        )
        items, total = await self._build_items(check, sources[document.source_purchase_in_id])
        for item, values in zip(saved, items, strict=True):
            if any(getattr(item, field) != values[field] for field in ("goods_code", "goods_name", "spec", "unit", "unit_cost")):
                raise CustomException(msg="退货商品快照或成本与原入库记录不一致", status_code=409)
        now = datetime.now(UTC)
        await self.crud.confirm(document, now, total, items)
        posted = await self.crud.get_items(id, lock=True)
        await self.stock.post(
            warehouse_id=document.warehouse_id,
            business_type=StockBusinessType.PURCHASE_RETURN,
            operation_type=BusinessOperationType.CONFIRM,
            business_id=id,
            business_no=document.order_no,
            business_date=document.business_date,
            posted_time=now,
            remark=document.return_reason,
            lines=[StockPostingLine(item.goods_id, item.id, -item.quantity, item.unit_cost, -item.cost_amount) for item in posted],
        )
        await self.payable.create(
            supplier_id=document.supplier_id,
            business_type=StockBusinessType.PURCHASE_RETURN,
            business_id=id,
            business_no=document.order_no,
            amount=-total,
            bill_date=document.business_date,
        )
        await self._record(document, BusinessOperationType.CONFIRM, DocumentStatus.DRAFT, DocumentStatus.CONFIRMED, now)
        return await self.detail(id, lock=True)

    async def void(self, id: int, data: PurchaseReturnVoidSchema) -> PurchaseReturnDetailOutSchema:
        """按原退货流水恢复库存、成本和应付，同时释放已退数量。"""
        document, _ = await self._lock_document(id)
        self._validate_state(document, DocumentStatus.CONFIRMED, data.version)
        payable = await self.payable.lock_reversible(StockBusinessType.PURCHASE_RETURN, id)
        logs = await self.stock.confirmed_logs(StockBusinessType.PURCHASE_RETURN, id)
        items = await self.crud.get_items(id, lock=True)
        log_map = {log.business_item_id: log for log in logs}
        if (
            not items
            or set(log_map) != {item.id for item in items}
            or payable.amount != -document.total_amount
            or payable.supplier_id != document.supplier_id
            or any(
                log_map[item.id].is_deleted
                or log_map[item.id].warehouse_id != document.warehouse_id
                or log_map[item.id].goods_id != item.goods_id
                or log_map[item.id].change_quantity != -item.quantity
                or log_map[item.id].cost_amount != -item.cost_amount
                or log_map[item.id].unit_cost != item.unit_cost
                for item in items
            )
        ):
            raise CustomException(msg="原退货入账记录不完整或不一致，不能作废", status_code=409)
        now = datetime.now(UTC)
        await self.crud.void(document, now, data.void_reason)
        await self.stock.post(
            warehouse_id=document.warehouse_id,
            business_type=StockBusinessType.PURCHASE_RETURN,
            operation_type=BusinessOperationType.VOID,
            business_id=id,
            business_no=document.order_no,
            business_date=document.business_date,
            posted_time=now,
            remark=data.void_reason,
            lines=[StockPostingLine(log.goods_id, log.business_item_id, -log.change_quantity, log.unit_cost, -log.cost_amount, log.id) for log in logs],
        )
        await self.payable.reverse(payable, data.void_reason)
        await self._record(document, BusinessOperationType.VOID, DocumentStatus.CONFIRMED, DocumentStatus.VOIDED, now, data.void_reason)
        return await self.detail(id, lock=True)

    async def export(self, data: PurchaseReturnExportSchema) -> bytes:
        """筛选全部有权限退货，仅输出用户选择的字段并保留列顺序。"""
        documents = await self.crud.get_list(search=search_to_dict(data.query), order_by=[{"id": "asc"}])
        rows: list[dict[str, Any]] = []
        for output in await self._serialize_documents(documents):
            row = output.model_dump(mode="json")
            row["status"] = {0: "草稿", 1: "已确认", 2: "已作废"}[output.status]
            row["created_name"] = output.created_by.name if output.created_by else ""
            rows.append(row)
        mapping = {field: EXPORT_COLUMNS[field] for field in data.fields}
        if data.format == "csv":
            return await ExcelUtil.aexport_list2csv(list_data=rows, mapping_dict=mapping)
        return await ExcelUtil.aexport_list2excel(list_data=rows, mapping_dict=mapping, sheet_name=data.sheet_name)

    async def _get_document(self, id: int, *, lock: bool = False) -> PurchaseReturnModel:
        """不存在和无数据权限返回相同错误，不泄露其他单据。"""
        document = await self.crud.get_document(id, lock=lock)
        if document is None:
            raise CustomException(msg="采购退货单不存在或无权访问", status_code=404)
        return document

    async def _lock_source(self, id: int) -> PurchaseInModel:
        """来源主单是退货数量、尾差和入库作废的共同串行化锁。"""
        source = await self.source_crud.get_document(id, lock=True)
        if source is None:
            raise CustomException(msg="原采购入库单不存在或无权访问", status_code=404)
        if source.status != DocumentStatus.CONFIRMED:
            raise CustomException(msg="原采购入库单必须是已确认状态", status_code=409)
        return source

    async def _lock_document(self, id: int, extra_source_id: int | None = None) -> tuple[PurchaseReturnModel, dict[int, PurchaseInModel]]:
        """先授权读取来源 ID，再锁来源和退货，来源被并发切换时要求重试。"""
        preview = await self._get_document(id)
        expected_source = preview.source_purchase_in_id
        if expected_source is None:
            raise CustomException(msg="本阶段只支持原单采购退货", status_code=409)
        source_ids = {expected_source}
        if extra_source_id is not None:
            source_ids.add(extra_source_id)
        sources = {source_id: await self._lock_source(source_id) for source_id in sorted(source_ids)}
        document = await self._get_document(id, lock=True)
        if document.source_purchase_in_id != expected_source:
            raise CustomException(msg="退货来源已变化，请刷新后重试", status_code=409)
        return document, sources

    async def _build_items(self, data: PurchaseReturnCreateSchema, source: PurchaseInModel) -> tuple[list[PurchaseReturnItemValues], Decimal]:
        """核对来源归属、启用档案和累计退货数量，按原金额分摊尾差。"""
        if data.supplier_id != source.supplier_id or data.warehouse_id != source.warehouse_id:
            raise CustomException(msg="供应商和仓库必须与原入库单一致", status_code=400)
        original_items = await self.source_crud.get_items(source.id, lock=True)
        source_map = {item.id: item for item in original_items}
        logs = await self.stock.confirmed_logs(StockBusinessType.PURCHASE_IN, source.id)
        log_map = {log.business_item_id: log for log in logs}
        await self.crud.validate_archives(data.supplier_id, data.warehouse_id, {item.goods_id for item in data.items})
        totals = await self.crud.returned_totals(source.id)
        values: list[PurchaseReturnItemValues] = []
        total_amount = Decimal("0.00")
        with localcontext() as context:
            context.prec = 40
            for index, item in enumerate(data.items, start=1):
                original = source_map.get(item.source_purchase_in_item_id)
                if original is None or original.goods_id != item.goods_id:
                    raise CustomException(msg="退货商品或来源行不属于原入库单", status_code=400)
                if item.unit_price != original.unit_price:
                    raise CustomException(msg="退货单价必须与原入库单一致", status_code=400)
                log = log_map.get(original.id)
                if (
                    log is None
                    or log.is_deleted
                    or log.goods_id != original.goods_id
                    or log.warehouse_id != source.warehouse_id
                    or log.change_quantity != original.quantity
                    or log.cost_amount != original.line_amount
                    or log.unit_cost != original.unit_price
                ):
                    raise CustomException(msg="原入库成本流水不完整或不一致", status_code=409)
                returned = totals.get(original.id, ReturnedTotals())
                quantity = item.quantity.quantize(Decimal("0.001"))
                if returned.quantity + quantity > original.quantity:
                    raise CustomException(msg=f"退货数量超过可退数量：{original.goods_name}", status_code=409)
                if returned.quantity < 0 or not 0 <= returned.amount <= original.line_amount or not 0 <= returned.cost <= log.cost_amount:
                    raise CustomException(msg="历史退货金额或成本超出原入账范围", status_code=409)
                amount = self._allocate(original.line_amount, original.quantity, returned.quantity, quantity, returned.amount)
                cost = self._allocate(log.cost_amount, original.quantity, returned.quantity, quantity, returned.cost)
                total_amount += amount
                if total_amount > MAX_AMOUNT:
                    raise CustomException(msg="退货总金额超过允许范围", status_code=400)
                values.append(
                    PurchaseReturnItemValues(
                        line_no=index,
                        source_purchase_in_item_id=original.id,
                        goods_id=original.goods_id,
                        goods_code=original.goods_code,
                        goods_name=original.goods_name,
                        spec=original.spec,
                        unit=original.unit,
                        quantity=quantity,
                        unit_price=original.unit_price,
                        line_amount=amount,
                        unit_cost=log.unit_cost,
                        cost_amount=cost,
                    )
                )
        return values, total_amount

    @staticmethod
    def _allocate(original_amount: Decimal, original_quantity: Decimal, returned_quantity: Decimal, quantity: Decimal, allocated_amount: Decimal) -> Decimal:
        """累计比例舍入减已退金额；作废改变累计分摊时不产生负额，全部退完补齐尾差。"""
        target = (original_amount * (returned_quantity + quantity) / original_quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return max(Decimal("0.00"), target - allocated_amount)

    async def _serialize_documents(self, documents: Sequence[PurchaseReturnModel]) -> list[PurchaseReturnOutSchema]:
        """批量装配来源和审计名称，不触发异步懒加载。"""
        names = await self.crud.get_name_maps(documents)
        outputs: list[PurchaseReturnOutSchema] = []
        for document in documents:
            values = {column.key: getattr(document, column.key) for column in PurchaseReturnModel.__table__.columns}
            values.update(
                supplier_name=names.suppliers.get(document.supplier_id, "-"),
                warehouse_name=names.warehouses.get(document.warehouse_id, "-"),
                source_order_no=names.sources.get(document.source_purchase_in_id),
                confirmed_name=names.users.get(document.confirmed_id),
                voided_name=names.users.get(document.voided_id),
                created_by=document.created_by,
                updated_by=document.updated_by,
            )
            outputs.append(PurchaseReturnOutSchema.model_validate(values))
        return outputs

    async def _record(self, document: PurchaseReturnModel, action: str, before: DocumentStatus, after: DocumentStatus, now: datetime, content: str | None = None) -> None:
        """业务日志与库存、应付一同提交或回滚。"""
        await self.business_log.record(
            business_type=StockBusinessType.PURCHASE_RETURN,
            business_id=document.id,
            business_no=document.order_no,
            action=action,
            before_status=before,
            after_status=after,
            operated_time=now,
            content=content,
        )

    @staticmethod
    def _validate_state(document: PurchaseReturnModel, state: DocumentStatus, version: int) -> None:
        """服务层先拒绝错误状态及版本，数据层 CAS 作最终并发保护。"""
        if document.status != state or document.version != version:
            raise CustomException(msg="退货单版本或状态不符，请刷新后重试", status_code=409)

    @staticmethod
    def _generate_order_no() -> str:
        """沿用采购入库的时间与 UUID 编号方式，数据库唯一约束兜底。"""
        return f"PR{datetime.now(UTC):%Y%m%d%H%M%S}{uuid4().hex}"

    @staticmethod
    def _validate_order_by(order_by: list[dict[str, str]] | None) -> list[dict[str, str]]:
        """只允许主单列排序并增加 ID 保证分页稳定。"""
        order = order_by or [{"id": "desc"}]
        if not isinstance(order, list):
            raise CustomException(msg="排序条件格式错误", status_code=422)
        result: list[dict[str, str]] = []
        for row in order:
            if not isinstance(row, dict) or not row:
                raise CustomException(msg="排序条件格式错误", status_code=422)
            for field, direction in row.items():
                if field not in PurchaseReturnModel.__table__.columns or not isinstance(direction, str) or direction.lower() not in {"asc", "desc"}:
                    raise CustomException(msg="排序字段或方向无效", status_code=422)
                result.append({field: direction.lower()})
        if not any("id" in row for row in result):
            result.append({"id": "desc"})
        return result
