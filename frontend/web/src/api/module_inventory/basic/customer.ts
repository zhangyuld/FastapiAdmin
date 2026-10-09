import { request } from "@utils";

const API_PATH = "/inventory/basic/customer";

/** 客户启停状态。 */
export type CustomerStatus = 0 | 1;

/** 客户分页查询参数。 */
export interface CustomerPageQuery extends PageQuery, UserByQueryParams {
  customer_code?: string;
  customer_name?: string;
  contact?: string;
  phone?: string;
  status?: CustomerStatus;
}

/** 客户列表及详情数据。 */
export interface CustomerItem extends BaseType {
  customer_code: string;
  customer_name: string;
  contact?: string | null;
  phone?: string | null;
  address?: string | null;
  remark?: string | null;
  status: CustomerStatus;
}

/** 客户新增和修改表单。 */
export interface CustomerForm extends BaseFormType {
  customer_code: string;
  customer_name: string;
  contact?: string;
  phone?: string;
  address?: string;
  remark?: string;
  status: CustomerStatus;
}

/** 客户批量删除参数。 */
export interface CustomerDeleteBody {
  ids: number[];
}

/** 客户批量状态参数。 */
export interface CustomerStatusBody extends CustomerDeleteBody {
  status: CustomerStatus;
}

/** 客户允许导出的字段。 */
export const CUSTOMER_EXPORT_FIELDS = [
  "customer_code",
  "customer_name",
  "contact",
  "phone",
  "address",
  "status",
  "remark",
  "created_time",
  "updated_time",
] as const;

/** 客户导出字段。 */
export type CustomerExportField = (typeof CUSTOMER_EXPORT_FIELDS)[number];

/** 客户全量导出参数。 */
export interface CustomerExportBody {
  query: CustomerPageQuery;
  fields: CustomerExportField[];
  format: "xlsx" | "csv";
  sheet_name: string;
  filename?: string;
}

const CustomerAPI = {
  /** 分页查询客户。 */
  listCustomer(query: CustomerPageQuery) {
    return request<ApiResponse<PageResult<CustomerItem>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  /** 查询客户详情。 */
  getCustomerDetail(id: number) {
    return request<ApiResponse<CustomerItem>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  /** 创建客户。 */
  createCustomer(body: CustomerForm) {
    return request<ApiResponse<CustomerItem>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: body,
    });
  },

  /** 修改客户。 */
  updateCustomer(id: number, body: CustomerForm) {
    return request<ApiResponse<CustomerItem>>({
      url: `${API_PATH}/update/${id}`,
      method: "post",
      data: body,
    });
  },

  /** 批量删除客户。 */
  deleteCustomer(body: CustomerDeleteBody) {
    return request<ApiResponse>({
      url: `${API_PATH}/delete`,
      method: "post",
      data: body,
    });
  },

  /** 批量修改客户状态。 */
  batchCustomerStatus(body: CustomerStatusBody) {
    return request<ApiResponse>({
      url: `${API_PATH}/status/batch`,
      method: "post",
      data: body,
    });
  },

  /** 导出客户。 */
  exportCustomer(body: CustomerExportBody) {
    return request<Blob>({
      url: `${API_PATH}/export`,
      method: "post",
      data: body,
      responseType: "blob",
    });
  },
};

export default CustomerAPI;
