import { request } from "@utils";

/** 报表领域与展示维度。 */
export type ReportKind = "purchase" | "sale" | "stock" | "profit";
export type ReportView = "documents" | "goods" | "balance" | "movement";
/** 报表十进制数由后端返回定点字符串，前端不汇总浮点数。 */
export type ReportDecimal = string;
/** 业务来源仅在明细视图返回，汇总行不伪造来源 ID。 */
export interface ReportSource {
  business_type:
    | "purchase_in"
    | "purchase_return"
    | "sale_out"
    | "sale_return"
    | "opening_balance"
    | "stock_check_gain"
    | "stock_check_loss";
  business_id: number;
}
/** 后端为每行返回稳定唯一 ID，商品数量必须按商品及单位分组。 */
export interface ReportDimensions {
  id: string | number;
  business_no?: string;
  business_date?: string;
  supplier_name?: string;
  customer_name?: string;
  warehouse_name?: string;
  goods_code?: string;
  goods_name?: string;
  spec?: string | null;
  unit?: string;
  source?: ReportSource | null;
}
/** 采购与退货金额分别统计，净采购金额为两者差额，不代表资金付款。 */
export interface PurchaseReportRow extends ReportDimensions {
  purchase_amount: ReportDecimal;
  return_amount: ReportDecimal;
  net_purchase_amount: ReportDecimal;
  purchase_quantity?: ReportDecimal;
  return_quantity?: ReportDecimal;
  net_quantity?: ReportDecimal;
}
/** 销售金额为优惠后的应计收入，不代表现金收款。 */
export interface SaleReportRow extends ReportDimensions {
  sale_amount: ReportDecimal;
  return_amount: ReportDecimal;
  net_sale_amount: ReportDecimal;
  sale_quantity?: ReportDecimal;
  return_quantity?: ReportDecimal;
  net_quantity?: ReportDecimal;
}
/** 当前库存快照不接收期间日期条件。 */
export interface StockBalanceReportRow extends ReportDimensions {
  quantity: ReportDecimal;
  avg_cost: ReportDecimal;
  stock_amount: ReportDecimal;
  warning: "normal" | "low" | "high";
}
/** 按业务日期汇总确认与反向流水，净变动不是期末库存，金额为库存成本。 */
export interface StockMovementReportRow extends ReportDimensions {
  in_quantity: ReportDecimal;
  out_quantity: ReportDecimal;
  net_quantity: ReportDecimal;
  in_amount: ReportDecimal;
  out_amount: ReportDecimal;
  net_amount: ReportDecimal;
}
/** 毛利采用优惠后收入及固化成本，非正净收入的毛利率为空，其余返回两位百分数。 */
export interface ProfitReportRow extends ReportDimensions {
  net_sale_amount: ReportDecimal;
  net_cost_amount: ReportDecimal;
  gross_profit: ReportDecimal;
  gross_margin: ReportDecimal | null;
}
/** 领域响应映射，保留各报表独立金额字段。 */
export interface ReportRowMap {
  purchase: PurchaseReportRow;
  sale: SaleReportRow;
  stock: StockBalanceReportRow | StockMovementReportRow;
  profit: ProfitReportRow;
}
export type ReportRow = ReportRowMap[ReportKind];
/** 完整筛选结果汇总，不受分页影响，不跨计量单位相加数量。 */
export interface ReportSummaryMap {
  purchase: {
    document_count: number;
    purchase_amount: ReportDecimal;
    return_amount: ReportDecimal;
    net_purchase_amount: ReportDecimal;
  };
  sale: {
    document_count: number;
    sale_amount: ReportDecimal;
    return_amount: ReportDecimal;
    net_sale_amount: ReportDecimal;
  };
  stock: {
    goods_count: number;
    stock_amount?: ReportDecimal;
    in_amount?: ReportDecimal;
    out_amount?: ReportDecimal;
    net_amount?: ReportDecimal;
  };
  profit: {
    net_sale_amount: ReportDecimal;
    net_cost_amount: ReportDecimal;
    gross_profit: ReportDecimal;
    gross_margin: ReportDecimal | null;
  };
}
export type ReportSummary = ReportSummaryMap[ReportKind];
/** 查询字段由视图白名单清洗；后端需独立校验视图及权限。 */
export interface ReportQuery extends Partial<PageQuery> {
  view: ReportView;
  business_date?: string[];
  business_no?: string;
  supplier_name?: string;
  customer_name?: string;
  warehouse_id?: number;
  category_id?: number;
  warehouse_name?: string;
  category_name?: string;
  goods_code?: string;
  goods_name?: string;
  warning?: "normal" | "low" | "high";
}
/** 全量导出与列表使用相同筛选和字段顺序。 */
export interface ReportExportBody {
  query: ReportQuery;
  fields: string[];
  format: "xlsx" | "csv";
  sheet_name: string;
  filename?: string;
}
/** 每个领域独立控制接入，后端上线并联调完成后再启用。 */
export const reportApiReady: Record<ReportKind, boolean> = {
  purchase: true,
  sale: true,
  stock: true,
  profit: true,
};
/** 各领域统一只读报表接口，不提供创建、编辑或删除报表记录能力。 */
export function createReportClient<K extends ReportKind>(kind: K) {
  const path = "/inventory/report/" + kind;
  /** 报表列表筛选及分页参数。 */
  type ListQuery = ReportQuery;
  /** 读取当前维度的分页报表。 */
  function list(query: ListQuery) {
    return request<ApiResponse<PageResult<ReportRowMap[K]>>>({
      url: path + "/list",
      method: "get",
      params: query,
    });
  }
  /** 汇总只传筛选条件，前端调用时清除分页参数。 */
  type SummaryQuery = Omit<ReportQuery, "page_no" | "page_size" | "order_by">;
  /** 读取整个筛选结果的汇总，不使用当前页合计。 */
  function summary(query: SummaryQuery) {
    return request<ApiResponse<ReportSummaryMap[K]>>({
      url: path + "/summary",
      method: "get",
      params: query,
    });
  }
  /** 服务端文件生成所需筛选及文件选项。 */
  type ExportBody = ReportExportBody;
  /** 下载包含选定字段的全量文件。 */
  function exportDocument(body: ExportBody) {
    return request<Blob>({
      url: path + "/export",
      method: "post",
      data: body,
      responseType: "blob",
    });
  }
  return { list, summary, exportDocument };
}
