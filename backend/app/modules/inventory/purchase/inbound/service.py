from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any
from uuid import uuid4

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.inventory.basic.goods.crud import GoodsCRUD
from app.modules.inventory.basic.supplier.crud import SupplierCRUD
from app.modules.inventory.basic.warehouse.crud import WarehouseCRUD
from app.modules.inventory.common.business_log import BusinessLogService
from app.modules.inventory.enums import BusinessOperationType, DocumentStatus, EnableStatus, StockBusinessType
from app.modules.inventory.finance.payable import PayableService
from app.modules.inventory.stock.posting import StockPostingLine, StockPostingService
from app.utils.common_util import search_to_dict
from app.utils.excel_util import ExcelUtil

from ..model import PurchaseInModel
from .crud import PurchaseInCRUD, PurchaseInItemValues
from .schema import (
    PurchaseInConfirmSchema,
    PurchaseInCreateSchema,
    PurchaseInDeleteSchema,
    PurchaseInDetailItemOutSchema,
    PurchaseInDetailOutSchema,
    PurchaseInExportSchema,
    PurchaseInItemOutSchema,
    PurchaseInOutSchema,
    PurchaseInQueryParam,
    PurchaseInRelatedReturnOutSchema,
    PurchaseInReturnableItemOutSchema,
    PurchaseInReturnableOutSchema,
    PurchaseInReturnableQueryParam,
    PurchaseInReturnSummarySchema,
    PurchaseInUpdateSchema,
    PurchaseInVoidSchema,
)

PURCHASE_IN_EXPORT_COLUMNS: dict[str, str] = {
    "order_no": "单据编号",
    "supplier_name": "供应商",
    "warehouse_name": "入库仓库",
    "business_date": "业务日期",
    "total_amount": "总金额",
    "status": "状态",
    "created_name": "创建人",
    "confirmed_time": "确认时间",
}
MAX_PURCHASE_AMOUNT = Decimal("9999999999999999.99")


class PurchaseInService:
    """采购入库草稿、确认入账、作废冲销及退货来源查询。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """复用同一请求会话访问主单及共享基础档案。"""
        self.auth = auth
        self.db = db
        self.crud = PurchaseInCRUD(auth, db)
        self.goods_crud = GoodsCRUD(auth, db)
        self.supplier_crud = SupplierCRUD(auth, db)
        self.warehouse_crud = WarehouseCRUD(auth, db)
        self.stock = StockPostingService(auth, db)
        self.payable = PayableService(auth, db)
        self.business_log = BusinessLogService(auth, db)

    async def confirm(self, id: int, data: PurchaseInConfirmSchema) -> PurchaseInDetailOutSchema:
        """锁定草稿并完成库存、应付和业务审计的事务入账。"""
        document = await self._get_document(id, lock=True)
        self._validate_draft(document, data.version)
        items = await self.crud.get_items(id, lock=True)
        if not items:
            raise CustomException(msg="采购明细为空，不能确认", status_code=409)
        check_data = PurchaseInCreateSchema(
            supplier_id=document.supplier_id,
            warehouse_id=document.warehouse_id,
            business_date=document.business_date,
            items=[{"goods_id": item.goods_id, "quantity": item.quantity, "unit_price": item.unit_price} for item in items],
        )
        computed, total = await self._build_items(check_data)
        if total != document.total_amount or any(row["line_amount"] != item.line_amount for row, item in zip(computed, items, strict=True)):
            raise CustomException(msg="草稿金额与明细不一致，请重新保存后确认", status_code=409)
        now = datetime.now(UTC)
        await self.crud.transition(document, DocumentStatus.CONFIRMED, now)
        await self.stock.post(
            warehouse_id=document.warehouse_id,
            business_type=StockBusinessType.PURCHASE_IN,
            operation_type=BusinessOperationType.CONFIRM,
            business_id=id,
            business_no=document.order_no,
            business_date=document.business_date,
            posted_time=now,
            remark=document.remark,
            lines=[StockPostingLine(item.goods_id, item.id, item.quantity, item.unit_price, item.line_amount) for item in items],
        )
        await self.payable.create(
            supplier_id=document.supplier_id,
            business_type=StockBusinessType.PURCHASE_IN,
            business_id=id,
            business_no=document.order_no,
            amount=document.total_amount,
            bill_date=document.business_date,
        )
        await self.business_log.record(
            business_type=StockBusinessType.PURCHASE_IN,
            business_id=id,
            business_no=document.order_no,
            action=BusinessOperationType.CONFIRM,
            before_status=DocumentStatus.DRAFT,
            after_status=DocumentStatus.CONFIRMED,
            operated_time=now,
        )
        return await self.detail(id, lock=True)

    async def void(self, id: int, data: PurchaseInVoidSchema) -> PurchaseInDetailOutSchema:
        """阻断退货和核销后，按原流水金额完整冲销，不修改历史流水。"""
        document = await self._get_document(id, lock=True)
        self._validate_confirmed(document, data.version)
        if await self.crud.has_active_returns(id):
            raise CustomException(msg="存在未作废的关联采购退货单，请先处理退货单", status_code=409)
        original_payable = await self.payable.lock_reversible(StockBusinessType.PURCHASE_IN, id)
        logs = await self.stock.confirmed_logs(StockBusinessType.PURCHASE_IN, id)
        items = await self.crud.get_items(id, lock=True)
        log_map = {log.business_item_id: log for log in logs}
        if (
            set(log_map) != {item.id for item in items}
            or not items
            or original_payable.amount != document.total_amount
            or original_payable.supplier_id != document.supplier_id
            or any(
                log_map[item.id].is_deleted
                or log_map[item.id].warehouse_id != document.warehouse_id
                or log_map[item.id].goods_id != item.goods_id
                or log_map[item.id].change_quantity != item.quantity
                or log_map[item.id].cost_amount != item.line_amount
                for item in items
            )
        ):
            raise CustomException(msg="原入账记录不完整或不一致，不能作废", status_code=409)
        now = datetime.now(UTC)
        await self.crud.transition(document, DocumentStatus.VOIDED, now, data.void_reason)
        await self.stock.post(
            warehouse_id=document.warehouse_id,
            business_type=StockBusinessType.PURCHASE_IN,
            operation_type=BusinessOperationType.VOID,
            business_id=id,
            business_no=document.order_no,
            business_date=document.business_date,
            posted_time=now,
            remark=data.void_reason,
            lines=[StockPostingLine(log.goods_id, log.business_item_id, -log.change_quantity, log.unit_cost, -log.cost_amount, log.id) for log in logs],
        )
        await self.payable.reverse(original_payable, data.void_reason)
        await self.business_log.record(
            business_type=StockBusinessType.PURCHASE_IN,
            business_id=id,
            business_no=document.order_no,
            action=BusinessOperationType.VOID,
            before_status=DocumentStatus.CONFIRMED,
            after_status=DocumentStatus.VOIDED,
            operated_time=now,
            content=data.void_reason,
        )
        return await self.detail(id, lock=True)

    async def returnable(self, id: int, query: PurchaseInReturnableQueryParam) -> PurchaseInReturnableOutSchema:
        """返回已确认来源的可退数量；只扣已确认退货，草稿不预占。"""
        document = await self._get_document(id, lock=True)
        self._validate_confirmed(document)
        if query.exclude_return_id is not None and not await self.crud.validate_return_draft(id, query.exclude_return_id):
            raise CustomException(msg="当前退货草稿不存在、无权访问或不属于该入库单", status_code=404)
        quantities = await self.crud.returned_quantities(id)
        detail = await self.detail(id, lock=True)
        items: list[PurchaseInReturnableItemOutSchema] = []
        for item in detail.items:
            quantity = item.quantity - quantities.get(item.id, Decimal("0.000"))
            if quantity < 0:
                raise CustomException(msg="关联退货数量超过原入库数量，请检查退货记录", status_code=409)
            items.append(PurchaseInReturnableItemOutSchema(**item.model_dump(exclude={"returnable_quantity"}), returnable_quantity=quantity))
        return PurchaseInReturnableOutSchema(**detail.model_dump(exclude={"items"}), items=items)

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: PurchaseInQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[PurchaseInOutSchema]:
        """分页筛选主单，批量补齐关联名称，不加载商品明细。"""
        result = await self.crud.page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            search=search_to_dict(search),
            order_by=self._validate_order_by(order_by),
        )
        items = await self._serialize_documents(result.items)
        return PageResultSchema[PurchaseInOutSchema](
            page_no=page_no,
            page_size=page_size,
            total=result.total,
            has_next=result.has_next,
            items=items,
        )

    async def detail(self, id: int, *, lock: bool = False) -> PurchaseInDetailOutSchema:
        """读取有权限的主单及有效明细，返回商品历史快照。"""
        document = await self._get_document(id, lock=lock)
        output = (await self._serialize_documents([document]))[0]
        items = await self.crud.get_items(document.id, lock=lock)
        quantities = await self.crud.returned_quantities(id, lock=lock)
        count, amount = await self.crud.return_totals(id, lock=lock)
        output_items: list[PurchaseInDetailItemOutSchema] = []
        for item in items:
            returned = quantities.get(item.id, Decimal("0.000"))
            remaining = item.quantity - returned
            if remaining < 0:
                raise CustomException(msg="关联退货数量超过原入库数量，请检查退货记录", status_code=409)
            output_items.append(PurchaseInDetailItemOutSchema(
                **PurchaseInItemOutSchema.model_validate(item).model_dump(),
                returned_quantity=returned,
                returnable_quantity=remaining if document.status == DocumentStatus.CONFIRMED else Decimal("0.000"),
            ))
        return_status = "none"
        if any(item.returned_quantity > 0 for item in output_items):
            return_status = "full" if all(item.returned_quantity == item.quantity for item in output_items) else "partial"
        return PurchaseInDetailOutSchema(
            **output.model_dump(),
            items=output_items,
            return_summary=PurchaseInReturnSummarySchema(return_status=return_status, confirmed_count=count, returned_amount=amount),
        )

    async def related_returns(self, id: int, page_no: int, page_size: int) -> PageResultSchema[PurchaseInRelatedReturnOutSchema]:
        """先授权原入库单，再分页读取退货数据范围内的关联记录。"""
        await self._get_document(id)
        result = await self.crud.related_returns(id, page_no, page_size)
        return PageResultSchema[PurchaseInRelatedReturnOutSchema](
            page_no=result.page_no, page_size=result.page_size, total=result.total, has_next=result.has_next,
            items=[PurchaseInRelatedReturnOutSchema.model_validate(item) for item in result.items],
        )

    async def create(self, data: PurchaseInCreateSchema) -> PurchaseInDetailOutSchema:
        """校验档案、计算金额并保存草稿；不影响库存或应付。"""
        items, total_amount = await self._build_items(data)
        values = data.model_dump(exclude={"items"})
        values.update(order_no=self._generate_order_no(), status=DocumentStatus.DRAFT, version=0, total_amount=total_amount)
        document = await self.crud.create_draft(values, items)
        return await self.detail(document.id)

    async def update(self, id: int, data: PurchaseInUpdateSchema) -> PurchaseInDetailOutSchema:
        """完整更新草稿，单号不变；原子版本校验防止覆盖他人修改。"""
        document = await self._get_document(id)
        self._validate_draft(document, data.version)
        items, total_amount = await self._build_items(data)
        values = data.model_dump(exclude={"items", "version"})
        values["total_amount"] = total_amount
        if not await self.crud.update_draft(id, data.version, values, items):
            raise CustomException(msg="单据已被修改或状态发生变化，请刷新后重试", status_code=status.HTTP_409_CONFLICT)
        return await self.detail(id)

    async def delete(self, data: PurchaseInDeleteSchema) -> list[int]:
        """校验全部草稿后按固定顺序删除，任一版本冲突则整批回滚。"""
        documents = await self.crud.get_list(search={"id": ("in", data.ids)})
        document_map = {document.id: document for document in documents}
        if set(document_map) != set(data.ids):
            raise CustomException(msg="部分采购入库单不存在或无权访问", status_code=status.HTTP_404_NOT_FOUND)
        for id in data.ids:
            self._validate_draft(document_map[id], data.versions[id])
        for id in sorted(data.ids):
            if not await self.crud.delete_draft(id, data.versions[id]):
                raise CustomException(msg="单据已被修改或状态发生变化，批量删除已取消", status_code=status.HTTP_409_CONFLICT)
        return data.ids

    async def export(self, data: PurchaseInExportSchema) -> bytes:
        """按筛选条件和字段顺序导出全部有权限的主单。"""
        documents = await self.crud.get_list(search=search_to_dict(data.query), order_by=[{"id": "asc"}])
        outputs = await self._serialize_documents(documents)
        rows: list[dict[str, Any]] = []
        for output in outputs:
            row = output.model_dump(mode="json")
            row["status"] = {0: "草稿", 1: "已确认", 2: "已作废"}[output.status]
            row["created_name"] = output.created_by.name if output.created_by else ""
            rows.append(row)
        mapping = {field: PURCHASE_IN_EXPORT_COLUMNS[field] for field in data.fields}
        if data.format == "csv":
            return await ExcelUtil.aexport_list2csv(list_data=rows, mapping_dict=mapping)
        return await ExcelUtil.aexport_list2excel(list_data=rows, mapping_dict=mapping, sheet_name=data.sheet_name)

    async def _get_document(self, id: int, *, lock: bool = False) -> PurchaseInModel:
        """不存在和无数据权限使用相同响应，不泄露其他人的单据。"""
        document = await self.crud.get_document(id, lock=lock)
        if document is None:
            raise CustomException(msg="采购入库单不存在或无权访问", status_code=status.HTTP_404_NOT_FOUND)
        return document

    async def _serialize_documents(self, documents: Sequence[PurchaseInModel]) -> list[PurchaseInOutSchema]:
        """批量组装名称和审计信息，避免关联字段的异步懒加载。"""
        names = await self.crud.get_name_maps(documents)
        outputs: list[PurchaseInOutSchema] = []
        for document in documents:
            values = {column.key: getattr(document, column.key) for column in PurchaseInModel.__table__.columns}
            values.update(
                supplier_name=names.suppliers.get(document.supplier_id, "-"),
                warehouse_name=names.warehouses.get(document.warehouse_id, "-"),
                confirmed_name=names.users.get(document.confirmed_id),
                voided_name=names.users.get(document.voided_id),
                created_by=document.created_by,
                updated_by=document.updated_by,
            )
            outputs.append(PurchaseInOutSchema.model_validate(values))
        return outputs

    async def _build_items(self, data: PurchaseInCreateSchema) -> tuple[list[PurchaseInItemValues], Decimal]:
        """校验启用档案，按行生成快照及四舍五入金额，并检查数据库金额上限。"""
        supplier = await self.supplier_crud.get(id=data.supplier_id)
        if supplier is None:
            raise CustomException(msg="供应商不存在", status_code=status.HTTP_404_NOT_FOUND)
        if supplier.status != EnableStatus.ENABLED:
            raise CustomException(msg="供应商已停用", status_code=status.HTTP_400_BAD_REQUEST)
        warehouse = await self.warehouse_crud.get(id=data.warehouse_id)
        if warehouse is None:
            raise CustomException(msg="仓库不存在", status_code=status.HTTP_404_NOT_FOUND)
        if warehouse.status != EnableStatus.ENABLED:
            raise CustomException(msg="仓库已停用", status_code=status.HTTP_400_BAD_REQUEST)
        goods = await self.goods_crud.get_list(search={"id": ("in", [item.goods_id for item in data.items])})
        goods_map = {item.id: item for item in goods}
        items: list[PurchaseInItemValues] = []
        total = Decimal("0.00")
        with localcontext() as context:
            context.prec = 40
            for index, item in enumerate(data.items, start=1):
                goods = goods_map.get(item.goods_id)
                if goods is None:
                    raise CustomException(msg=f"商品不存在：{item.goods_id}", status_code=status.HTTP_404_NOT_FOUND)
                if goods.status != EnableStatus.ENABLED:
                    raise CustomException(msg=f"商品已停用：{goods.goods_name}", status_code=status.HTTP_400_BAD_REQUEST)
                quantity = item.quantity.quantize(Decimal("0.001"))
                price = item.unit_price.quantize(Decimal("0.0001"))
                amount = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total += amount
                if amount > MAX_PURCHASE_AMOUNT or total > MAX_PURCHASE_AMOUNT:
                    raise CustomException(msg="采购金额超过允许范围", status_code=status.HTTP_400_BAD_REQUEST)
                items.append(
                    PurchaseInItemValues(
                        line_no=index,
                        goods_id=goods.id,
                        goods_code=goods.goods_code,
                        goods_name=goods.goods_name,
                        spec=goods.spec,
                        unit=goods.unit,
                        quantity=quantity,
                        unit_price=price,
                        line_amount=amount,
                    )
                )
        return items, total

    @staticmethod
    def _validate_draft(document: PurchaseInModel, version: int) -> None:
        """已确认、已作废单据不可编辑删除，旧版本不能继续提交。"""
        if document.status != DocumentStatus.DRAFT:
            raise CustomException(msg="只能编辑或删除草稿", status_code=status.HTTP_409_CONFLICT)
        if document.version != version:
            raise CustomException(msg="单据版本已变化，请刷新后重试", status_code=status.HTTP_409_CONFLICT)

    @staticmethod
    def _validate_confirmed(document: PurchaseInModel, version: int | None = None) -> None:
        """仅已确认单据可以冲销或作为退货来源，提交时必须匹配当前版本。"""
        if document.status != DocumentStatus.CONFIRMED:
            raise CustomException(msg="仅已确认的采购入库单可以执行此操作", status_code=409)
        if version is not None and document.version != version:
            raise CustomException(msg="单据版本已变化，请刷新后重试", status_code=409)

    @staticmethod
    def _generate_order_no() -> str:
        """生成带 UTC 创建时间及完整 UUID 的单号，数据库唯一约束作最终保证。"""
        return f"PI{datetime.now(UTC):%Y%m%d%H%M%S}{uuid4().hex}"

    @staticmethod
    def _validate_order_by(order_by: list[dict[str, str]] | None) -> list[dict[str, str]]:
        """仅允许主单列和升降序排序，并追加 ID 保证分页顺序稳定。"""
        order = order_by or [{"id": "desc"}]
        columns = set(PurchaseInModel.__table__.columns.keys())
        if not isinstance(order, list):
            raise CustomException(msg="排序条件格式错误", status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
        result: list[dict[str, str]] = []
        for item in order:
            if not isinstance(item, dict) or not item:
                raise CustomException(msg="排序条件格式错误", status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
            for field, direction in item.items():
                if field not in columns or not isinstance(direction, str) or direction.lower() not in {"asc", "desc"}:
                    raise CustomException(msg="排序字段或方向无效", status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
                result.append({field: direction.lower()})
        if not any("id" in item for item in result):
            result.append({"id": "desc"})
        return result
