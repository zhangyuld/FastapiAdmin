import type { SaleDecimal, SaleLine } from "@/api/module_inventory/sale/client";

/** 数据库 decimal(18, scale) 的缩放整数上限。 */
const MAX_DECIMAL = 999999999999999999n;
/** 非负十进制转缩放整数，拒绝精度丢失、科学计数和超出数据库范围。 */
export function scaledDecimal(value: SaleDecimal, precision: number): bigint {
  const text = String(value);
  if (!/^\d+(\.\d+)?$/.test(text)) throw new Error("请输入有效的非负数");
  const [whole = "0", fraction = ""] = text.split(".");
  if (fraction.length > precision && /[1-9]/.test(fraction.slice(precision)))
    throw new Error("数值超过允许的小数精度");
  const result = BigInt(whole + fraction.slice(0, precision).padEnd(precision, "0"));
  if (result > MAX_DECIMAL) throw new Error("数值超过允许范围");
  return result;
}
/** 缩放整数转非负固定精度字符串。 */
export function decimalText(value: bigint, precision: number): string {
  if (value < 0n || value > MAX_DECIMAL) throw new Error("数值超过允许范围");
  const text = value.toString().padStart(precision + 1, "0");
  return precision ? text.slice(0, -precision) + "." + text.slice(-precision) : text;
}
/** 行金额按数量三位、单价四位相乘后按分四舍五入。 */
export function lineAmount(quantity: SaleDecimal, price: SaleDecimal): string {
  return decimalText((scaledDecimal(quantity, 3) * scaledDecimal(price, 4) + 50000n) / 100000n, 2);
}
/** 汇总各行已舍入的原价金额。 */
export function totalAmount(lines: SaleLine[]): string {
  return decimalText(
    lines.reduce(
      (sum, line) => sum + scaledDecimal(lineAmount(line.quantity, line.unit_price), 2),
      0n
    ),
    2
  );
}
/** 校验整单优惠并计算预计应收，不使用浮点减法。 */
export function receivableAmount(lines: SaleLine[], discount: SaleDecimal): string {
  const original = scaledDecimal(totalAmount(lines), 2);
  const reduction = scaledDecimal(discount, 2);
  if (reduction > original) throw new Error("优惠金额不能超过原价合计");
  return decimalText(original - reduction, 2);
}
/** 从剩余可退金额按本次数量估算退款，不以原单价忽略整单优惠。 */
export function returnLineAmount(line: SaleLine): string {
  if (line.returnable_quantity === undefined || line.returnable_amount === undefined)
    throw new Error("来源接口缺少可退数量或优惠分摊后的可退金额");
  const available = scaledDecimal(line.returnable_quantity, 3);
  const quantity = scaledDecimal(line.quantity, 3);
  if (available <= 0n || quantity > available) throw new Error("退货数量超过可退数量");
  const amount = scaledDecimal(line.returnable_amount, 2);
  return decimalText((amount * quantity + available / 2n) / available, 2);
}
/** 汇总退款预估，最终金额及尾差由后端确认时固化。 */
export function returnTotalAmount(lines: SaleLine[]): string {
  return decimalText(
    lines.reduce((sum, line) => sum + scaledDecimal(returnLineAmount(line), 2), 0n),
    2
  );
}
/** 汇总后端固化的金额，保留优惠和尾差结果。 */
export function storedTotalAmount(lines: SaleLine[]): string {
  return decimalText(
    lines.reduce((sum, line) => sum + scaledDecimal(line.line_amount, 2), 0n),
    2
  );
}
/** 展示金额时保留大整数精度，缺失值不冒充零。 */
export function displayAmount(value: SaleDecimal | null | undefined): string {
  if (value === undefined || value === null) return "-";
  try {
    const [whole, fraction] = decimalText(scaledDecimal(value, 2), 2).split(".");
    return whole!.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + "." + fraction;
  } catch {
    return "-";
  }
}
