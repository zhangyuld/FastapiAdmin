import { request } from "@utils";

const API_PATH = "/inventory/basic/supplier";

/** 供应商启停状态。 */
export type SupplierStatus = 0 | 1;

/** 供应商分页查询参数。 */
export interface SupplierPageQuery extends PageQuery, UserByQueryParams {
  supplier_code?: string;
  supplier_name?: string;
  contact?: string;
  phone?: string;
  status?: SupplierStatus;
}

/** 供应商列表及详情数据。 */
export interface SupplierItem extends BaseType {
  supplier_code: string;
  supplier_name: string;
  contact?: string | null;
  phone?: string | null;
  address?: string | null;
  remark?: string | null;
  status: SupplierStatus;
}

/** 供应商新增和修改表单。 */
export interface SupplierForm extends BaseFormType {
  supplier_code: string;
  supplier_name: string;
  contact?: string;
  phone?: string;
  address?: string;
  remark?: string;
  status: SupplierStatus;
}

/** 供应商批量删除参数。 */
export interface SupplierDeleteBody {
  ids: number[];
}

/** 供应商批量状态参数。 */
export interface SupplierStatusBody extends SupplierDeleteBody {
  status: SupplierStatus;
}

/** 供应商允许导出的字段。 */
export const SUPPLIER_EXPORT_FIELDS = [
  "supplier_code",
  "supplier_name",
  "contact",
  "phone",
  "address",
  "status",
  "remark",
  "created_time",
  "updated_time",
] as const;

/** 供应商导出字段。 */
export type SupplierExportField = (typeof SUPPLIER_EXPORT_FIELDS)[number];

/** 供应商全量导出参数。 */
export interface SupplierExportBody {
  query: SupplierPageQuery;
  fields: SupplierExportField[];
  format: "xlsx" | "csv";
  sheet_name: string;
  filename?: string;
}

const SupplierAPI = {
  /** 分页查询供应商。 */
  listSupplier(query: SupplierPageQuery) {
    return request<ApiResponse<PageResult<SupplierItem>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  /** 查询供应商详情。 */
  getSupplierDetail(id: number) {
    return request<ApiResponse<SupplierItem>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  /** 创建供应商。 */
  createSupplier(body: SupplierForm) {
    return request<ApiResponse<SupplierItem>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: body,
    });
  },

  /** 修改供应商。 */
  updateSupplier(id: number, body: SupplierForm) {
    return request<ApiResponse<SupplierItem>>({
      url: `${API_PATH}/update/${id}`,
      method: "post",
      data: body,
    });
  },

  /** 批量删除供应商。 */
  deleteSupplier(body: SupplierDeleteBody) {
    return request<ApiResponse>({
      url: `${API_PATH}/delete`,
      method: "post",
      data: body,
    });
  },

  /** 批量修改供应商状态。 */
  batchSupplierStatus(body: SupplierStatusBody) {
    return request<ApiResponse>({
      url: `${API_PATH}/status/batch`,
      method: "post",
      data: body,
    });
  },

  /** 导出供应商。 */
  exportSupplier(body: SupplierExportBody) {
    return request<Blob>({
      url: `${API_PATH}/export`,
      method: "post",
      data: body,
      responseType: "blob",
    });
  },
};

export default SupplierAPI;
