import { request } from "@utils";

/** 采购单据种类。 */
export type PurchaseKind = "in" | "return";
/** 草稿、已确认、已作废。 */
export type PurchaseStatus = 0 | 1 | 2;
/** 十进制数据以字符串传输。 */
export type PurchaseDecimal = string | number;
/** 采购列表查询参数。 */
export interface PurchaseQuery extends Partial<PageQuery>, UserByQueryParams {
  order_no?: string;
  supplier_id?: number;
  warehouse_id?: number;
  business_date?: string[];
  source_order_no?: string;
  status?: PurchaseStatus;
}
/** 商品明细及来源入库快照。 */
export interface PurchaseLine {
  id?: number;
  line_no: number;
  goods_id: number;
  goods_code: string;
  goods_name: string;
  spec?: string | null;
  unit: string;
  quantity: PurchaseDecimal;
  unit_price: PurchaseDecimal;
  line_amount: PurchaseDecimal;
  source_purchase_in_item_id?: number;
  /** 后端计算的可退数量，编辑时须包含本单原有数量。 */
  returnable_quantity?: PurchaseDecimal;
  unit_cost?: PurchaseDecimal;
  cost_amount?: PurchaseDecimal;
  /** 原入库明细累计已确认且未作废的退货数量。 */
  returned_quantity?: PurchaseDecimal;
}
/** 原入库单实际退货汇总，统计不受下游单据数据范围影响。 */
export interface PurchaseReturnSummary {
  return_status: "none" | "partial" | "full";
  confirmed_count: number;
  returned_amount: PurchaseDecimal;
}
/** 采购列表记录；详情同时返回 items。 */
export interface PurchaseDocument extends BaseType {
  id: number;
  order_no: string;
  supplier_id: number;
  supplier_name: string;
  warehouse_id: number;
  warehouse_name: string;
  business_date: string;
  total_amount: PurchaseDecimal;
  status: PurchaseStatus;
  version: number;
  remark?: string | null;
  source_purchase_in_id?: number;
  source_order_no?: string | null;
  return_reason?: string;
  confirmed_name?: string;
  confirmed_time?: string;
  voided_name?: string;
  voided_time?: string;
  void_reason?: string;
  items?: PurchaseLine[];
  return_summary?: PurchaseReturnSummary;
}
/** 保存明细输入，金额、成本与快照由后端生成。 */
export interface PurchaseLineInput {
  goods_id: number;
  quantity: string;
  unit_price: string;
  source_purchase_in_item_id?: number;
}
/** 单据保存参数，编辑必须携带 version。 */
export interface PurchaseSaveBody {
  supplier_id: number;
  warehouse_id: number;
  business_date: string;
  remark: string;
  version?: number;
  source_purchase_in_id?: number;
  return_reason?: string;
  items: PurchaseLineInput[];
}

/** 采购单据接口配置。 */
interface PurchaseClientOptions {
  path: string;
}
/** 创建采购模块内使用的 GET/POST 单据客户端。 */
export function createPurchaseClient(options: PurchaseClientOptions) {
  const path = options.path;
  /** 单据列表的查询参数。 */
  type ListQuery = PurchaseQuery;
  /** 分页读取单据。 */
  function list(query: ListQuery) {
    return request<ApiResponse<PageResult<PurchaseDocument>>>({
      url: path + "/list",
      method: "get",
      params: query,
    });
  }
  /** 读取完整单据及明细。 */
  function detail(id: number) {
    return request<ApiResponse<PurchaseDocument>>({ url: path + "/detail/" + id, method: "get" });
  }
  /** 创建草稿的请求体。 */
  type CreateBody = PurchaseSaveBody;
  /** 保存新草稿，单号由后端生成。 */
  function create(body: CreateBody) {
    return request<ApiResponse<PurchaseDocument>>({
      url: path + "/create",
      method: "post",
      data: body,
    });
  }
  /** 更新草稿必须携带当前版本。 */
  type UpdateBody = PurchaseSaveBody & { version: number };
  /** 按版本更新草稿。 */
  function update(id: number, body: UpdateBody) {
    return request<ApiResponse<PurchaseDocument>>({
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
  /** 确认单据，库存和应付由后端事务处理。 */
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
    query: PurchaseQuery;
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
  /** 查询可退来源参数，编辑退货单时传自身 ID。 */
  interface ReturnableQuery {
    exclude_return_id?: number;
  }
  /** 读取已确认入库单及各行实时可退数量。 */
  function returnable(id: number, query: ReturnableQuery = {}) {
    return request<ApiResponse<PurchaseDocument>>({
      url: path + "/returnable/" + id,
      method: "get",
      params: query,
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
    returnable,
  };
}
