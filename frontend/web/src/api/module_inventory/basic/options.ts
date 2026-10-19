import type { AxiosPromise } from "axios";
import { request } from "@utils";

/** 商品分类轻量树，不包含审计或管理详情字段。 */
export interface CategoryOptionItem {
  id: number;
  name: string;
  parent_id: number | null;
  status: 0 | 1;
  children: CategoryOptionItem[];
}
/** 客户轻量选项。 */
export interface CustomerOptionItem {
  id: number;
  customer_code: string;
  customer_name: string;
  status: 0 | 1;
}
/** 供应商轻量选项。 */
export interface SupplierOptionItem {
  id: number;
  supplier_code: string;
  supplier_name: string;
  status: 0 | 1;
}
/** 仓库轻量选项，保留默认仓库标识。 */
export interface WarehouseOptionItem {
  id: number;
  warehouse_code: string;
  warehouse_name: string;
  status: 0 | 1;
  is_default: boolean;
}
/** 选项分页查询，省略状态包含停用档案，仅供历史查询。 */
export interface ArchiveOptionsQuery {
  keyword?: string;
  status?: 0 | 1;
  page_no?: number;
  page_size?: number;
}

/** 分类树状态筛选，省略状态返回全部未删除分类。 */
export interface CategoryOptionsQuery {
  status?: 0 | 1;
}
/** 获取登录用户可用的轻量分类树，不依赖分类管理权限。 */
export function getCategoryOptions(
  query?: CategoryOptionsQuery
): AxiosPromise<ApiResponse<CategoryOptionItem[]>> {
  return request({ url: "/inventory/basic/category/options", method: "get", params: query });
}

/** 客户选项按编码或名称搜索。 */
export type CustomerOptionsQuery = ArchiveOptionsQuery;
/** 获取轻量客户选项，不请求联系人、电话和地址。 */
export function getCustomerOptions(
  query: CustomerOptionsQuery
): AxiosPromise<ApiResponse<PageResult<CustomerOptionItem>>> {
  return request({ url: "/inventory/basic/customer/options", method: "get", params: query });
}

/** 供应商选项按编码或名称搜索。 */
export type SupplierOptionsQuery = ArchiveOptionsQuery;
/** 获取轻量供应商选项，不依赖供应商管理权限。 */
export function getSupplierOptions(
  query: SupplierOptionsQuery
): AxiosPromise<ApiResponse<PageResult<SupplierOptionItem>>> {
  return request({ url: "/inventory/basic/supplier/options", method: "get", params: query });
}

/** 仓库选项按编码或名称搜索。 */
export type WarehouseOptionsQuery = ArchiveOptionsQuery;
/** 获取轻量仓库选项，服务端按默认仓库及ID稳定排序。 */
export function getWarehouseOptions(
  query: WarehouseOptionsQuery
): AxiosPromise<ApiResponse<PageResult<WarehouseOptionItem>>> {
  return request({ url: "/inventory/basic/warehouse/options", method: "get", params: query });
}
