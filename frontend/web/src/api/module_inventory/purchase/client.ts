import { request } from "@utils";
import type { PurchaseDocument, PurchaseQuery, PurchaseSaveBody } from "./types";

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
