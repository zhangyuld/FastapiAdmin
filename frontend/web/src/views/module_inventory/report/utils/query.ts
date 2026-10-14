import type { ReportKind, ReportView, ReportQuery } from "@/api/module_inventory/report/client";
import { reportView } from "./config";
/** 确认日期是实际存在的年月日，拒绝 URL 中的无效日期。 */
function validDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value + "T00:00:00Z");
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
/** 仅接受完整正整数，不将小数、空串或多值 URL 参数作为 ID。 */
function positiveInteger(value: unknown): number | undefined {
  if (typeof value !== "number" && (typeof value !== "string" || !/^\d+$/.test(value)))
    return undefined;
  const result = Number(value);
  return Number.isSafeInteger(result) && result > 0 ? result : undefined;
}
/** 筛选输入白名单，当前库存主动剔除期间日期及其他领域条件。 */
export function normalizeReportQuery(
  kind: ReportKind,
  view: ReportView,
  input: object
): ReportQuery {
  const source = input as Record<string, unknown>;
  view = reportView(kind, view);
  const result: ReportQuery = {
    view: reportView(kind, view),
    page_no: positiveInteger(source.page_no) ?? 1,
    page_size: Math.min(positiveInteger(source.page_size) ?? 10, 100),
  };
  const strings = [
    "goods_code",
    "goods_name",
    "warehouse_name",
    "category_name",
    ...(kind === "purchase" ? ["supplier_name"] : kind === "stock" ? [] : ["customer_name"]),
    ...(view === "documents" ? ["business_no"] : []),
  ];
  for (const key of strings) {
    if (typeof source[key] === "string" && source[key].trim())
      Object.assign(result, { [key]: source[key].trim().slice(0, 200) });
  }
  for (const key of ["warehouse_id", "category_id"]) {
    const value = positiveInteger(source[key]);
    if (value) Object.assign(result, { [key]: value });
  }
  const dates = source.business_date;
  if (
    !(kind === "stock" && view === "balance") &&
    Array.isArray(dates) &&
    dates.length === 2 &&
    dates.every(validDate) &&
    dates[0]! <= dates[1]!
  )
    result.business_date = [...dates];
  if (
    kind === "stock" &&
    view === "balance" &&
    ["normal", "low", "high"].includes(String(source.warning))
  )
    result.warning = source.warning as ReportQuery["warning"];
  return result;
}
/** URL 仅持久化报表查询字段，不串入来源弹窗或其他模块状态。 */
export function reportRouteQuery(query: ReportQuery): Record<string, string | string[]> {
  return Object.fromEntries(
    Object.entries(query)
      .filter(([, value]) => value !== undefined)
      .map(([key, value]) => [key, Array.isArray(value) ? value : String(value)])
  );
}
/** 汇总和导出剔除分页及排序字段。 */
export function reportFilterQuery(
  query: ReportQuery
): Omit<ReportQuery, "page_no" | "page_size" | "order_by"> {
  const filters = { ...query };
  delete filters.page_no;
  delete filters.page_size;
  return filters;
}
