import type { DashboardSummary, RecentDocument } from "@/api/module_inventory/dashboard";

/** 指标视图保留未授权和未加载区别。 */
export interface DashboardMetric {
  key: string;
  title: string;
  icon: string;
  tone: "sale" | "purchase" | "stock" | "finance";
  value?: string | number | null;
  detail?: string;
  count?: boolean;
}
/** 定点字符串直接分组，避免大额金额转浮点导致精度丢失。 */
export function formatAmount(value?: string | number | null): string {
  if (value === undefined || value === null) return "—";
  const [integer = "0", decimal] = String(value).split(".");
  return integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + "." + (decimal ?? "").padEnd(2, "0");
}
/** 构建八项经营指标，不将当前余额受趋势筛选影响。 */
export function dashboardMetrics(data?: DashboardSummary): DashboardMetric[] {
  const trades = [
    ["sale_today", "今日销售净额", "ri:shopping-bag-3-line", "sale"],
    ["purchase_today", "今日采购净额", "ri:truck-line", "purchase"],
    ["sale_month", "本月销售净额", "ri:line-chart-line", "sale"],
    ["purchase_month", "本月采购净额", "ri:shopping-cart-line", "purchase"],
  ] as const;
  const items: DashboardMetric[] = trades.map(([key, title, icon, tone]) => ({
    key,
    title,
    icon,
    tone,
    value: data ? (data[key]?.net_amount ?? null) : undefined,
    detail: data?.[key] ? `退货 ¥${formatAmount(data[key].return_amount)}` : undefined,
  }));
  items.push(
    {
      key: "stock",
      title: "库存总金额",
      icon: "ri:archive-line",
      tone: "stock",
      value: data?.stock_amount,
    },
    {
      key: "receivable",
      title: "待收金额",
      icon: "ri:wallet-3-line",
      tone: "finance",
      value: data ? (data.receivable?.positive_balance ?? null) : undefined,
      detail: data?.receivable
        ? `冲减余额 ¥${formatAmount(data.receivable.negative_balance)}`
        : undefined,
    },
    {
      key: "payable",
      title: "待付金额",
      icon: "ri:bank-card-line",
      tone: "finance",
      value: data ? (data.payable?.positive_balance ?? null) : undefined,
      detail: data?.payable
        ? `冲减余额 ¥${formatAmount(data.payable.negative_balance)}`
        : undefined,
    },
    {
      key: "warning",
      title: "库存预警",
      icon: "ri:alarm-warning-line",
      tone: "stock",
      value: data?.warning_count,
      count: true,
    }
  );
  return items;
}
/** 原业务名称与权限类型保持一致。 */
export const documentLabels: Record<RecentDocument["business_type"], string> = {
  purchase_in: "采购入库",
  purchase_return: "采购退货",
  sale_out: "销售出库",
  sale_return: "销售退货",
};
