import { request } from "@utils";

/** 库存业务单据与查询页面种类。 */
export type StockKind = "balance" | "log" | "opening" | "check";
/** 固定精度库存业务数，不经过浮点转换。 */
export type StockDecimal = string | number;
/** 模块内库存与业务单据筛选。 */
export interface StockQuery extends Partial<PageQuery>, UserByQueryParams {
  goods_id?: number;
  goods_code?: string;
  goods_name?: string;
  category_id?: number;
  warehouse_id?: number;
  warehouse_name?: string;
  quantity_state?: "positive" | "zero";
  warning?: "low" | "high";
  business_type?: string;
  operation_type?: "confirm" | "void";
  business_no?: string;
  doc_no?: string;
  business_date?: string[];
  posted_time?: string[];
  status?: 0 | 1 | 2;
}
/** 库存只读列表记录，来源标识只在流水中返回。 */
export interface StockRecord extends BaseType {
  id: number;
  warehouse_id: number;
  warehouse_name: string;
  goods_id: number;
  goods_code: string;
  goods_name: string;
  spec?: string | null;
  unit: string;
  quantity?: StockDecimal;
  avg_cost?: StockDecimal;
  stock_amount?: StockDecimal;
  stock_min?: StockDecimal;
  stock_max?: StockDecimal;
  warning?: "normal" | "low" | "high";
  last_business_time?: string | null;
  business_type?: string;
  operation_type?: "confirm" | "void";
  business_id?: number;
  business_no?: string;
  business_date?: string;
  before_quantity?: StockDecimal;
  change_quantity?: StockDecimal;
  after_quantity?: StockDecimal;
  unit_cost?: StockDecimal;
  cost_amount?: StockDecimal;
  reversal_log_id?: number | null;
  posted_time?: string;
  remark?: string | null;
}
/** 期初与盘点的明细快照及服务端固化成本。 */
export interface StockLine {
  id?: number;
  goods_id: number;
  goods_code: string;
  goods_name: string;
  spec?: string | null;
  unit: string;
  quantity?: StockDecimal | null;
  actual_quantity?: StockDecimal | null;
  system_quantity?: StockDecimal | null;
  system_stock_amount?: StockDecimal | null;
  balance_version?: number | null;
  difference_quantity?: StockDecimal | null;
  unit_cost: StockDecimal;
  cost_amount?: StockDecimal | null;
}
/** 期初与盘点主单，列表不加载明细。 */
export interface StockDocument extends BaseType {
  id: number;
  doc_no: string;
  warehouse_id: number;
  warehouse_name: string;
  business_date: string;
  status: 0 | 1 | 2;
  version: number;
  remark?: string | null;
  confirmed_time?: string | null;
  voided_time?: string | null;
  confirmed_name?: string | null;
  voided_name?: string | null;
  void_reason?: string | null;
  items?: StockLine[] | null;
}
/** 库存单据保存输入，不接收客户端金额或账面快照。 */
export interface StockSaveBody {
  warehouse_id: number;
  business_date: string;
  remark: string;
  items: { goods_id: number; quantity?: string; actual_quantity?: string; unit_cost?: string }[];
}
/** 库存模块内导出字段与文件选项。 */
export interface StockExportBody {
  query: StockQuery;
  fields: string[];
  format: "xlsx" | "csv";
  sheet_name: string;
  filename?: string;
}
/** 库存只读 API 配置。 */
interface ReadClientOptions {
  path: string;
}
/** 创建库存模块内的只读客户端。 */
export function createStockReadClient(options: ReadClientOptions) {
  /** 列表筛选与分页入参。 */
  type ListQuery = StockQuery;
  /** 分页读取库存余额或流水。 */
  function list(query: ListQuery) {
    return request<ApiResponse<PageResult<StockRecord>>>({
      url: options.path + "/list",
      method: "get",
      params: query,
    });
  }
  /** 读取库存记录详情。 */
  function detail(id: number) {
    return request<ApiResponse<StockRecord>>({
      url: options.path + "/detail/" + id,
      method: "get",
    });
  }
  /** 文件流导出的筛选和字段参数。 */
  type ExportBody = StockExportBody;
  /** 按选择字段下载服务端文件。 */
  function exportDocument(body: ExportBody) {
    return request<Blob>({
      url: options.path + "/export",
      method: "post",
      data: body,
      responseType: "blob",
    });
  }
  return { list, detail, exportDocument };
}
/** 库存业务单据 API 配置。 */
interface DocumentClientOptions {
  path: string;
}
/** 创建模块内期初和盘点客户端，只使用 GET/POST。 */
export function createStockDocumentClient(options: DocumentClientOptions) {
  /** 主单列表查询参数。 */
  type ListQuery = StockQuery;
  /** 读取有数据权限的库存业务列表。 */
  function list(query: ListQuery) {
    return request<ApiResponse<PageResult<StockDocument>>>({
      url: options.path + "/list",
      method: "get",
      params: query,
    });
  }
  /** 读取库存业务单据及商品快照。 */
  function detail(id: number) {
    return request<ApiResponse<StockDocument>>({
      url: options.path + "/detail/" + id,
      method: "get",
    });
  }
  /** 新建期初或盘点的业务输入。 */
  type CreateBody = StockSaveBody;
  /** 保存新草稿，不直接改变库存。 */
  function create(body: CreateBody) {
    return request<ApiResponse<StockDocument>>({
      url: options.path + "/create",
      method: "post",
      data: body,
    });
  }
  /** 更新须完整提交明细及版本。 */
  type UpdateBody = StockSaveBody & { version: number };
  /** 按版本更新草稿，不静默刷新盘点快照。 */
  function update(id: number, body: UpdateBody) {
    return request<ApiResponse<StockDocument>>({
      url: options.path + "/update/" + id,
      method: "post",
      data: body,
    });
  }
  /** 批量删除的单据及对应版本。 */
  interface DeleteBody {
    ids: number[];
    versions: Record<number, number>;
  }
  /** 按版本删除草稿。 */
  function remove(body: DeleteBody) {
    return request<ApiResponse<number[]>>({
      url: options.path + "/delete",
      method: "post",
      data: body,
    });
  }
  /** 确认时提交当前单据版本。 */
  interface ConfirmBody {
    version: number;
  }
  /** 由服务端事务确认单据。 */
  function confirm(id: number, body: ConfirmBody) {
    return request<ApiResponse<StockDocument>>({
      url: options.path + "/confirm/" + id,
      method: "post",
      data: body,
    });
  }
  /** 冲销须提交版本及原因。 */
  interface VoidBody {
    version: number;
    void_reason: string;
  }
  /** 按原流水冲销库存单据。 */
  function voidDocument(id: number, body: VoidBody) {
    return request<ApiResponse<StockDocument>>({
      url: options.path + "/void/" + id,
      method: "post",
      data: body,
    });
  }
  /** 导出的筛选及文件参数。 */
  type ExportBody = StockExportBody;
  /** 下载全量有权限的单据文件。 */
  function exportDocument(body: ExportBody) {
    return request<Blob>({
      url: options.path + "/export",
      method: "post",
      data: body,
      responseType: "blob",
    });
  }
  return { list, detail, create, update, remove, confirm, voidDocument, exportDocument };
}
