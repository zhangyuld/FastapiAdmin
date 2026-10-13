import { request } from "@utils";

/** 销售单据种类及状态。 */
export type SaleKind = "out" | "return";
export type SaleStatus = 0 | 1 | 2;
/** 十进制业务数优先使用固定精度字符串。 */
export type SaleDecimal = string | number;
/** 销售分页及审计筛选。 */
export interface SaleQuery extends Partial<PageQuery>, UserByQueryParams {
  order_no?: string;
  customer_id?: number;
  warehouse_id?: number;
  business_date?: string[];
  source_order_no?: string;
  status?: SaleStatus;
}
/** 商品快照、固化金额及原销售明细可退额度。 */
export interface SaleLine {
  id?: number;
  line_no: number;
  goods_id: number;
  goods_code: string;
  goods_name: string;
  spec?: string | null;
  unit: string;
  quantity: SaleDecimal;
  unit_price: SaleDecimal;
  line_amount: SaleDecimal;
  source_sale_out_item_id?: number;
  returned_quantity?: SaleDecimal;
  returnable_quantity?: SaleDecimal;
  /** 后端分摊原单优惠并扣除有效退货后的剩余可退金额。 */
  returnable_amount?: SaleDecimal;
  unit_cost?: SaleDecimal | null;
  cost_amount?: SaleDecimal | null;
}
/** 销售出库详情预留的有效退货汇总。 */
export interface SaleReturnSummary {
  return_status: "none" | "partial" | "full";
  confirmed_count: number;
  returned_amount: SaleDecimal;
}
/** 销售列表与详情，金额字段按单据种类返回。 */
export interface SaleDocument extends BaseType {
  id: number;
  order_no: string;
  customer_id: number;
  customer_name: string;
  warehouse_id: number;
  warehouse_name: string;
  business_date: string;
  original_amount?: SaleDecimal;
  discount_amount?: SaleDecimal;
  receivable_amount?: SaleDecimal;
  return_amount?: SaleDecimal;
  status: SaleStatus;
  version: number;
  remark?: string | null;
  source_sale_out_id?: number;
  source_order_no?: string | null;
  return_reason?: string;
  confirmed_name?: string | null;
  confirmed_time?: string | null;
  voided_name?: string | null;
  voided_time?: string | null;
  void_reason?: string | null;
  items?: SaleLine[];
  return_summary?: SaleReturnSummary;
}
/** 保存明细只传业务输入，金额、成本和快照由后端生成。 */
export interface SaleLineInput {
  goods_id: number;
  quantity: string;
  unit_price: string;
  source_sale_out_item_id?: number;
}
/** 销售草稿通用输入。 */
export interface SaleSaveBase {
  customer_id: number;
  warehouse_id: number;
  business_date: string;
  remark: string;
  items: SaleLineInput[];
}
/** 出库与原单退货共用的草稿保存输入。 */
export type SaleSaveBody = SaleSaveBase &
  ({ discount_amount: string } | { source_sale_out_id: number; return_reason: string });

/** 销售单据接口配置。 */
interface SaleClientOptions {
  path: string;
}
/** 创建销售模块内使用的 GET/POST 单据客户端。 */
export function createSaleClient(options: SaleClientOptions) {
  const path = options.path;
  /** 单据列表的查询参数。 */
  type ListQuery = SaleQuery;
  /** 分页读取单据。 */
  function list(query: ListQuery) {
    return request<ApiResponse<PageResult<SaleDocument>>>({
      url: path + "/list",
      method: "get",
      params: query,
    });
  }
  /** 读取完整单据及明细。 */
  function detail(id: number) {
    return request<ApiResponse<SaleDocument>>({ url: path + "/detail/" + id, method: "get" });
  }
  /** 创建草稿的请求体。 */
  type CreateBody = SaleSaveBody;
  /** 保存新草稿，单号由后端生成。 */
  function create(body: CreateBody) {
    return request<ApiResponse<SaleDocument>>({
      url: path + "/create",
      method: "post",
      data: body,
    });
  }
  /** 更新草稿必须携带当前版本。 */
  type UpdateBody = SaleSaveBody & { version: number };
  /** 按版本更新草稿。 */
  function update(id: number, body: UpdateBody) {
    return request<ApiResponse<SaleDocument>>({
      url: path + "/update/" + id,
      method: "post",
      data: body,
    });
  }
  /** 草稿删除参数，版本映射防止删除已被其他用户修改的单据。 */
  interface DeleteBody {
    ids: number[];
    versions: Record<number, number>;
  }
  /** 删除草稿。 */
  function remove(body: DeleteBody) {
    return request<ApiResponse>({ url: path + "/delete", method: "post", data: body });
  }
  /** 确认单据的并发控制参数。 */
  interface ConfirmBody {
    version: number;
  }
  /** 确认单据，库存和应收由后端事务处理。 */
  function confirm(id: number, body: ConfirmBody) {
    return request<ApiResponse>({ url: path + "/confirm/" + id, method: "post", data: body });
  }
  /** 作废单据参数。 */
  interface VoidBody {
    version: number;
    void_reason: string;
  }
  /** 作废单据，冲销由后端处理。 */
  function voidDocument(id: number, body: VoidBody) {
    return request<ApiResponse>({ url: path + "/void/" + id, method: "post", data: body });
  }
  /** 导出字段、查询及文件参数。 */
  interface ExportBody {
    query: SaleQuery;
    fields: string[];
    format: "xlsx" | "csv";
    sheet_name: string;
    filename?: string;
  }
  /** 下载服务端生成的导出文件。 */
  function exportDocument(body: ExportBody) {
    return request<Blob>({
      url: path + "/export",
      method: "post",
      data: body,
      responseType: "blob",
    });
  }
  return {
    list,
    detail,
    create,
    update,
    remove,
    confirm,
    voidDocument,
    exportDocument,
  };
}
