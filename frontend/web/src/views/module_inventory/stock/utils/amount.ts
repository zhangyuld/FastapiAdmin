import type { StockDecimal, StockLine } from "@/api/module_inventory/stock/client";
const MAX = 999999999999999999n;
/** 非负十进制转定点整数，拒绝科学计数与精度丢失。 */
export function scaled(value: StockDecimal, precision: number): bigint {
  const text = String(value);
  if (!/^\d+(\.\d+)?$/.test(text)) throw new Error("请输入有效非负数");
  const [whole = "0", fraction = ""] = text.split(".");
  if (fraction.length > precision && /[1-9]/.test(fraction.slice(precision)))
    throw new Error("小数精度超限");
  const result = BigInt(whole + fraction.slice(0, precision).padEnd(precision, "0"));
  if (result > MAX) throw new Error("数值超过允许范围");
  return result;
}
/** 带方向定点整数转固定精度十进制字符串。 */
export function decimal(value: bigint, precision: number): string {
  const absolute = value < 0n ? -value : value;
  if (absolute > MAX) throw new Error("数值超过允许范围");
  const text = absolute.toString().padStart(precision + 1, "0");
  return (
    (value < 0n ? "-" : "") +
    (precision ? text.slice(0, -precision) + "." + text.slice(-precision) : text)
  );
}
/** 期初按数量与成本预估金额，盘点按库存原金额比例保留尾差。 */
export function preview(
  line: StockLine,
  kind: "opening" | "check"
): { difference: string; amount: string } {
  if (kind === "opening") {
    const quantity = scaled(line.quantity ?? "", 3);
    if (quantity <= 0n) throw new Error("期初数量必须大于零");
    return {
      difference: decimal(quantity, 3),
      amount: decimal((quantity * scaled(line.unit_cost, 4) + 50000n) / 100000n, 2),
    };
  }
  const actual = scaled(line.actual_quantity ?? "", 3);
  const quantity = scaled(line.system_quantity ?? "", 3);
  const difference = actual - quantity;
  const absolute = difference < 0n ? -difference : difference;
  const cost =
    quantity > 0n
      ? (scaled(line.system_stock_amount ?? "", 2) * absolute + quantity / 2n) / quantity
      : (absolute * scaled(line.unit_cost || "0", 4) + 50000n) / 100000n;
  if (quantity === 0n && actual > 0n && line.unit_cost === "")
    throw new Error("零库存盘盈须填写单位成本");
  return { difference: decimal(difference, 3), amount: decimal(difference < 0n ? -cost : cost, 2) };
}
