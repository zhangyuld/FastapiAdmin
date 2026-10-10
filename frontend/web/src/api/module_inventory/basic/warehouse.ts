import { request } from "@utils";

const API_PATH = "/inventory/basic/warehouse";

/** 仓库启停状态。 */
export type WarehouseStatus = 0 | 1;

/** 仓库分页查询参数。 */
export interface WarehousePageQuery extends PageQuery, UserByQueryParams {
  warehouse_code?: string;
  warehouse_name?: string;
  status?: WarehouseStatus;
}

/** 仓库列表及详情数据。 */
export interface WarehouseItem extends BaseType {
  warehouse_code: string;
  warehouse_name: string;
  address?: string | null;
  remark?: string | null;
  status: WarehouseStatus;
}

/** 仓库新增和修改表单。 */
export interface WarehouseForm extends BaseFormType {
  warehouse_code: string;
  warehouse_name: string;
  address?: string;
  remark?: string;
  status: WarehouseStatus;
}

/** 仓库批量删除参数。 */
export interface WarehouseDeleteBody {
  ids: number[];
}

/** 仓库批量状态参数。 */
export interface WarehouseStatusBody extends WarehouseDeleteBody {
  status: WarehouseStatus;
}

/** 仓库允许导出的字段。 */
export const WAREHOUSE_EXPORT_FIELDS = [
  "warehouse_code",
  "warehouse_name",
  "address",
  "status",
  "remark",
  "created_time",
  "updated_time",
] as const;

/** 仓库导出字段。 */
export type WarehouseExportField = (typeof WAREHOUSE_EXPORT_FIELDS)[number];

/** 仓库全量导出参数。 */
export interface WarehouseExportBody {
  query: WarehousePageQuery;
  fields: WarehouseExportField[];
  format: "xlsx" | "csv";
  sheet_name: string;
  filename?: string;
}

const WarehouseAPI = {
  /** 分页查询仓库。 */
  listWarehouse(query: WarehousePageQuery) {
    return request<ApiResponse<PageResult<WarehouseItem>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  /** 查询仓库详情。 */
  getWarehouseDetail(id: number) {
    return request<ApiResponse<WarehouseItem>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  /** 创建仓库。 */
  createWarehouse(body: WarehouseForm) {
    return request<ApiResponse<WarehouseItem>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: body,
    });
  },

  /** 修改仓库。 */
  updateWarehouse(id: number, body: WarehouseForm) {
    return request<ApiResponse<WarehouseItem>>({
      url: `${API_PATH}/update/${id}`,
      method: "post",
      data: body,
    });
  },

  /** 批量删除仓库。 */
  deleteWarehouse(body: WarehouseDeleteBody) {
    return request<ApiResponse>({
      url: `${API_PATH}/delete`,
      method: "post",
      data: body,
    });
  },

  /** 批量修改仓库状态。 */
  batchWarehouseStatus(body: WarehouseStatusBody) {
    return request<ApiResponse>({
      url: `${API_PATH}/status/batch`,
      method: "post",
      data: body,
    });
  },

  /** 导出仓库。 */
  exportWarehouse(body: WarehouseExportBody) {
    return request<Blob>({
      url: `${API_PATH}/export`,
      method: "post",
      data: body,
      responseType: "blob",
    });
  },
};

export default WarehouseAPI;
