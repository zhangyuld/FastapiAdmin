from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.core.exceptions import CustomException


def allocate_receivable(amounts: Sequence[Decimal], discount: Decimal) -> list[Decimal]:
    """按行金额累计分摊整单优惠，确保每行非负且合计精确等于应收。"""
    with localcontext() as context:
        context.prec = 40
        total = sum(amounts, Decimal("0.00"))
        if discount < 0 or discount > total or any(amount < 0 for amount in amounts):
            raise CustomException(msg="优惠金额不能超过原价合计", status_code=400)
        if total == 0:
            return [Decimal("0.00") for _ in amounts]
        net = total - discount
        cumulative = Decimal("0.00")
        allocated = Decimal("0.00")
        result: list[Decimal] = []
        for amount in amounts:
            cumulative += amount
            target = (cumulative * net / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            result.append(target - allocated)
            allocated = target
        return result
