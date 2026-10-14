import { request } from "@utils";
import type { AxiosPromise } from "axios";

/** 首页金额和数量使用服务端定点字符串，不在浏览器累计业务金额。 */
export interface TradeMetric {
  net_amount: string;
  return_amount: string;
}
/** 往来余额按对象净额汇总，负向余额不抵消其他对象待收待付。 */
export interface FinanceMetric {
  positive_balance: string;
  negative_balance: string;
}
/** 未授权指标为空，已授权但无业务才为零。 */
export interface DashboardSummary {
  as_of: string;
  today: string;
  sale_today: TradeMetric | null;
  sale_month: TradeMetric | null;
  purchase_today: TradeMetric | null;
  purchase_month: TradeMetric | null;
  stock_amount: string | null;
  warning_count: number | null;
  receivable: FinanceMetric | null;
  payable: FinanceMetric | null;
}
/** 预置经营趋势期间。 */
export type TrendPeriod = "7d" | "30d" | "month";
/** 趋势绘图可转数值，但提示金额仍取原始定点字符串。 */
export interface TrendPoint {
  business_date: string;
  sale_amount: string | null;
  purchase_amount: string | null;
}
/** 服务端日期范围含首尾，缺失业务日期补零。 */
export interface DashboardTrend {
  start_date: string;
  end_date: string;
  points: TrendPoint[];
}
/** 当前仓库实际库存金额。 */
export interface WarehouseStock {
  warehouse_id: number;
  warehouse_name: string;
  stock_amount: string;
}
/** 一条预警对应一个已建账商品仓库组合。 */
export interface StockWarning {
  id: string;
  warehouse_id: number;
  warehouse_name: string;
  goods_id: number;
  goods_code: string;
  goods_name: string;
  unit: string;
  quantity: string;
  stock_min: string;
  stock_max: string;
  warning: "low" | "high";
}
/** 首页库存预警分页响应。 */
export type DashboardWarningPage = PageResult<StockWarning>;
/** 最近单据仅包含当前用户原业务查询权限和数据范围内记录。 */
export interface RecentDocument {
  id: string;
  business_type: "purchase_in" | "purchase_return" | "sale_out" | "sale_return";
  business_id: number;
  business_no: string;
  business_date: string;
  created_time: string;
  amount: string;
  status: 0 | 1 | 2;
}

/** 获取登录用户可查看的经营及当前余额指标。 */
export function getDashboardSummary(): AxiosPromise<ApiResponse<DashboardSummary>> {
  return request<ApiResponse<DashboardSummary>>({
    url: "/inventory/dashboard/summary",
    method: "get",
  });
}

/** 仅趋势接受期间，当前库存和往来余额不使用该条件。 */
export interface TrendQuery {
  period: TrendPeriod;
}
/** 获取逐日净采购与净销售。 */
export function getDashboardTrend(params: TrendQuery): AxiosPromise<ApiResponse<DashboardTrend>> {
  return request<ApiResponse<DashboardTrend>>({
    url: "/inventory/dashboard/trend",
    method: "get",
    params,
  });
}

/** 获取已有库存记录的仓库金额分布。 */
export function getWarehouseStock(): AxiosPromise<ApiResponse<WarehouseStock[]>> {
  return request<ApiResponse<WarehouseStock[]>>({
    url: "/inventory/dashboard/warehouse-stock",
    method: "get",
  });
}

/** 预警有界分页，默认每页五条。 */
export interface WarningQuery {
  page_no: number;
  page_size: number;
}
/** 获取当前库存上下限预警。 */
export function getStockWarnings(
  params: WarningQuery
): AxiosPromise<ApiResponse<DashboardWarningPage>> {
  return request<ApiResponse<PageResult<StockWarning>>>({
    url: "/inventory/dashboard/stock-warnings",
    method: "get",
    params,
  });
}

/** 最近单据数量上限为二十条。 */
export interface RecentQuery {
  limit: number;
}
/** 获取权限范围内最近创建的业务单据。 */
export function getRecentDocuments(
  params: RecentQuery
): AxiosPromise<ApiResponse<RecentDocument[]>> {
  return request<ApiResponse<RecentDocument[]>>({
    url: "/inventory/dashboard/recent-documents",
    method: "get",
    params,
  });
}
