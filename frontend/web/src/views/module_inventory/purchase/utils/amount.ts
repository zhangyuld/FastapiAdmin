import type { PurchaseDecimal, PurchaseLine } from "@/api/module_inventory/purchase/types";

/** 将非负十进制数转换为固定精度整数，超出精度或非法输入直接拒绝。 */
export function scaledDecimal(value: PurchaseDecimal, precision: number): bigint {
  const text = String(value);
  if (!/^\d+(\.\d+)?$/.test(text)) throw new Error("请输入有效的非负数");
  const [whole = "0", fraction = ""] = text.split(".");
  if (fraction.length > precision && /[1-9]/.test(fraction.slice(precision)))
    throw new Error("数值超过允许的小数精度");
  return BigInt(whole + fraction.slice(0, precision).padEnd(precision, "0"));
}
/** 将缩放整数格式化为十进制字符串。 */
export function decimalText(value: bigint, precision: number): string {
  const text = value.toString().padStart(precision + 1, "0");
  return precision ? text.slice(0, -precision) + "." + text.slice(-precision) : text;
}
/** 使用数量三位、单价四位精度相乘，行金额按分四舍五入。 */
export function lineAmount(quantity: PurchaseDecimal, price: PurchaseDecimal): string {
  const product = scaledDecimal(quantity, 3) * scaledDecimal(price, 4);
  return decimalText((product + 50000n) / 100000n, 2);
}
/** 汇总已按分舍入的行金额。 */
export function totalAmount(lines: PurchaseLine[]): string {
  return decimalText(
    lines.reduce(
      (sum, line) => sum + scaledDecimal(lineAmount(line.quantity, line.unit_price), 2),
      0n
    ),
    2
  );
}
/** 汇总后端已固化的行金额，保留多次退货的尾差分摊结果。 */
export function storedTotalAmount(lines: PurchaseLine[]): string {
  return decimalText(
    lines.reduce((sum, line) => sum + scaledDecimal(line.line_amount, 2), 0n),
    2
  );
}
/** 非编辑场景格式化金额，保留缺失值。 */
export function displayAmount(value: PurchaseDecimal | null | undefined): string {
  if (value === undefined || value === null) return "-";
  return Number(value).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
