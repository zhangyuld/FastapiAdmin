import { request } from "@utils";

/** 往来业务类型。 */
export type FinanceKind = "receivable" | "payable";
/** 账单及余额筛选，余额只提交对象和余额方向。 */
export interface FinanceQuery extends Partial<PageQuery>, UserByQueryParams {
  party_id?: number;
  party_code?: string;
  party_name?: string;
  business_no?: string;
  business_type?: string;
  operation_type?: "confirm" | "void";
  bill_date?: string[];
  status?: 0 | 1 | 2;
  reversal_state?: "original" | "reversed" | "reversal";
  balance_state?: "positive" | "negative" | "zero";
}
/** 往来账单或余额，金额以服务端精度字符串展示。 */
export interface FinanceRecord extends BaseType {
  id: number;
  party_id: number;
  party_code: string;
  party_name: string;
  business_type?: string;
  business_id?: number;
  business_no?: string;
  operation_type?: "confirm" | "void";
  amount?: string;
  allocated_amount?: string;
  unallocated_amount?: string;
  bill_date?: string;
  status?: 0 | 1 | 2;
  reversal_id?: number | null;
  reversal_state?: "original" | "reversed" | "reversal";
  related_bills?: FinanceRecord[];
  business_net_amount?: string;
  allocated_net_amount?: string;
  unsettled_net_amount?: string;
  bill_count?: number;
  remark?: string | null;
}
/** 对象分组后计算的净额及正负余额。 */
export interface FinanceSummary {
  party_count: number;
  business_net_amount: string;
  unsettled_net_amount: string;
  positive_balance: string;
  negative_balance: string;
}
/** 全量导出的字段、筛选及文件选项。 */
export interface FinanceExportBody {
  query: FinanceQuery;
  fields: string[];
  format: "xlsx" | "csv";
  sheet_name: string;
  filename?: string;
}
/** 往来模块内只读客户端配置。 */
interface ClientOptions {
  kind: FinanceKind;
  balance?: boolean;
}
/** 创建应收应付的查询客户端，不提供账单写入功能。 */
export function createFinanceClient(options: ClientOptions) {
  const path = "/inventory/finance/" + options.kind;
  const listPath = options.balance ? "/balance/list" : "/list";
  /** 账单或余额的分页筛选。 */
  type ListQuery = FinanceQuery;
  /** 查询账单明细或按对象汇总的当前余额。 */
  function list(query: ListQuery) {
    return request<ApiResponse<PageResult<FinanceRecord>>>({
      url: path + listPath,
      method: "get",
      params: query,
    });
  }
  /** 查询账单及关联冲销记录。 */
  function detail(id: number) {
    return request<ApiResponse<FinanceRecord>>({ url: path + "/detail/" + id, method: "get" });
  }
  /** 当前余额汇总仅支持往来对象和余额方向筛选。 */
  type SummaryQuery = Pick<
    FinanceQuery,
    "party_id" | "party_code" | "party_name" | "balance_state"
  >;
  /** 分别汇总正余额和负余额，不按分页汇总。 */
  function summary(query: SummaryQuery) {
    return request<ApiResponse<FinanceSummary>>({
      url: path + "/summary",
      method: "get",
      params: query,
    });
  }
  /** 文件流导出请求参数。 */
  type ExportBody = FinanceExportBody;
  /** 根据用户选择的字段和格式导出全部筛选结果。 */
  function exportDocument(body: ExportBody) {
    return request<Blob>({
      url: path + (options.balance ? "/balance/export" : "/export"),
      method: "post",
      data: body,
      responseType: "blob",
    });
  }
  return { list, detail, summary, exportDocument };
}
/** 账单业务类型标签。 */
export const businessLabels: Record<string, string> = {
  sale_out: "销售出库",
  sale_return: "销售退货",
  purchase_in: "采购入库",
  purchase_return: "采购退货",
};
/** 核销状态与业务冲销状态分开展示。 */
export const statusLabels: Record<number, string> = { 0: "未结清", 1: "部分结清", 2: "已结清" };
export const reversalLabels: Record<string, string> = {
  original: "未冲销",
  reversed: "已冲销",
  reversal: "反向账单",
};
