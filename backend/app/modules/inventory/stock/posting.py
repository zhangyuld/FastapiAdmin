from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException

from .model import StockBalanceModel, StockLogModel


@dataclass(frozen=True)
class StockPostingLine:
    """库存入账参数，金额采用原业务金额，不由四位单位成本反算。"""

    goods_id: int
    business_item_id: int
    quantity: Decimal
    unit_cost: Decimal
    cost_amount: Decimal
    reversal_log_id: int | None = None


@dataclass(frozen=True)
class StockOutLine:
    """销售出库数量输入，成本只从已锁定库存余额计算。"""

    goods_id: int
    business_item_id: int
    quantity: Decimal


class StockPostingService:
    """进销存模块内部库存记账，复用请求事务，不单独提交。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """绑定审计用户及业务会话。"""
        self.auth = auth
        self.db = db

    async def post_sale_out(
        self,
        *,
        warehouse_id: int,
        business_id: int,
        business_no: str,
        business_date: date,
        posted_time: datetime,
        lines: Sequence[StockOutLine],
        remark: str | None = None,
    ) -> dict[int, tuple[Decimal, Decimal]]:
        """顺序锁定余额后固化移动平均成本，全部出库时结清库存金额尾差。"""
        if not lines or len({line.goods_id for line in lines}) != len(lines):
            raise CustomException(msg="销售明细为空或包含重复商品", status_code=409)
        postings: list[StockPostingLine] = []
        costs: dict[int, tuple[Decimal, Decimal]] = {}
        for line in sorted(lines, key=lambda item: item.goods_id):
            balance = await self._lock_balance(warehouse_id, line.goods_id, create=False)
            if line.quantity <= 0 or line.quantity > balance.quantity:
                raise CustomException(msg=f"商品库存不足，无法出库：{line.goods_id}", status_code=409)
            with localcontext() as context:
                context.prec = 40
                unit_cost = (balance.stock_amount / balance.quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                cost = balance.stock_amount if line.quantity == balance.quantity else (balance.stock_amount * line.quantity / balance.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if cost < 0 or cost > balance.stock_amount or unit_cost > Decimal("99999999999999.9999"):
                    raise CustomException(msg="库存成本异常，不能确认销售出库", status_code=409)
            costs[line.business_item_id] = (unit_cost, cost)
            postings.append(StockPostingLine(line.goods_id, line.business_item_id, -line.quantity, unit_cost, -cost))
        await self.post(
            warehouse_id=warehouse_id, business_type="sale_out", operation_type="confirm",
            business_id=business_id, business_no=business_no, business_date=business_date,
            posted_time=posted_time, lines=postings, remark=remark,
        )
        return costs

    async def confirmed_logs(self, business_type: str, business_id: int) -> Sequence[StockLogModel]:
        """锁定原确认流水供冲销校验，不隐藏异常删除的历史记录。"""
        statement = (
            select(StockLogModel)
            .where(
                StockLogModel.business_type == business_type,
                StockLogModel.business_id == business_id,
                StockLogModel.operation_type == "confirm",
            )
            .with_for_update()
        )
        return (await self.db.execute(statement)).scalars().all()

    async def post(
        self,
        *,
        warehouse_id: int,
        business_type: str,
        operation_type: str,
        business_id: int,
        business_no: str,
        business_date: date,
        posted_time: datetime,
        lines: Sequence[StockPostingLine],
        remark: str | None = None,
    ) -> None:
        """按商品排序加锁，原子更新余额并保留每次变动的不可变流水。"""
        for line in sorted(lines, key=lambda item: item.goods_id):
            balance = await self._lock_balance(warehouse_id, line.goods_id, create=line.quantity > 0 and line.reversal_log_id is None)
            before = balance.quantity
            with localcontext() as context:
                context.prec = 40
                quantity = before + line.quantity
                amount = balance.stock_amount + line.cost_amount
                if quantity < 0 or amount < 0:
                    raise CustomException(msg="库存数量或库存金额不足，无法记账", status_code=409)
                if quantity == 0 and amount != 0:
                    raise CustomException(msg="冲销后库存数量为零但金额不为零，请先处理后续库存业务", status_code=409)
                average = (amount / quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if quantity else Decimal("0.0000")
                if quantity > Decimal("999999999999999.999") or amount > Decimal("9999999999999999.99") or average > Decimal("99999999999999.9999"):
                    raise CustomException(msg="库存数量、金额或平均成本超过允许范围", status_code=400)
            result = await self.db.execute(
                update(StockBalanceModel)
                .where(StockBalanceModel.id == balance.id, StockBalanceModel.version == balance.version, StockBalanceModel.is_deleted.is_(False))
                .values(
                    quantity=quantity,
                    stock_amount=amount,
                    avg_cost=average,
                    version=balance.version + 1,
                    last_business_time=posted_time,
                    updated_id=self.auth.user.id,
                    updated_time=posted_time,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise CustomException(msg="库存版本发生变化，请刷新后重试", status_code=409)
            self.db.add(
                StockLogModel(
                    warehouse_id=warehouse_id,
                    goods_id=line.goods_id,
                    business_type=business_type,
                    operation_type=operation_type,
                    business_id=business_id,
                    business_item_id=line.business_item_id,
                    business_no=business_no,
                    business_date=business_date,
                    change_quantity=line.quantity,
                    before_quantity=before,
                    after_quantity=quantity,
                    unit_cost=line.unit_cost,
                    cost_amount=line.cost_amount,
                    reversal_log_id=line.reversal_log_id,
                    posted_time=posted_time,
                    remark=remark,
                    created_id=self.auth.user.id,
                    updated_id=self.auth.user.id,
                )
            )
            await self.db.flush()

    async def _lock_balance(self, warehouse_id: int, goods_id: int, *, create: bool) -> StockBalanceModel:
        """先幂等插入再行锁读取，避免首次入库并发创建同一余额的唯一键竞争。"""
        if create:
            values = {"warehouse_id": warehouse_id, "goods_id": goods_id, "created_id": self.auth.user.id, "updated_id": self.auth.user.id}
            dialect = self.db.get_bind().dialect.name
            if dialect == "mysql":
                statement = mysql_insert(StockBalanceModel).values(**values)
                statement = statement.on_duplicate_key_update(id=StockBalanceModel.id, updated_time=StockBalanceModel.updated_time)
            elif dialect == "postgresql":
                statement = postgres_insert(StockBalanceModel).values(**values).on_conflict_do_nothing(index_elements=["warehouse_id", "goods_id"])
            elif dialect == "sqlite":
                statement = sqlite_insert(StockBalanceModel).values(**values).on_conflict_do_nothing(index_elements=["warehouse_id", "goods_id"])
            else:
                raise CustomException(msg="当前数据库不支持库存并发入账", status_code=400)
            await self.db.execute(statement)
        statement = select(StockBalanceModel).where(StockBalanceModel.warehouse_id == warehouse_id, StockBalanceModel.goods_id == goods_id).with_for_update().execution_options(populate_existing=True)
        balance = (await self.db.execute(statement)).scalar_one_or_none()
        if balance is None or balance.is_deleted:
            raise CustomException(msg="库存余额不存在或已删除，不能入账", status_code=409)
        return balance
