import { createSaleClient } from "./client";
import { request } from "@utils";
import type { SaleDocument, SaleSaveBody, SaleStatus, SaleDecimal } from "./client";

/** 原单可退额度查询，编辑时仅传同来源已保存草稿 ID。 */
interface ReturnableQuery {
  exclude_return_id?: number;
}
/** 获取已确认原销售单及优惠分摊后的可退数量、金额。 */
function returnable(id: number, query: ReturnableQuery = {}) {
  return request<ApiResponse<SaleDocument>>({
    url: "/inventory/sale/out/returnable/" + id,
    method: "get",
    params: query,
  });
}

/** 当前用户可见的关联销售退货摘要。 */
export interface RelatedSaleReturn {
  id: number;
  order_no: string;
  business_date: string;
  status: SaleStatus;
  return_amount: SaleDecimal;
  return_reason: string;
  confirmed_time?: string | null;
}

/** 原出库单关联退货的分页参数。 */
type RelatedReturnsQuery = Pick<PageQuery, "page_no" | "page_size">;
/** 分页读取有权限的关联退货，包含草稿、已确认和作废记录。 */
function relatedReturns(id: number, query: RelatedReturnsQuery) {
  return request<ApiResponse<PageResult<RelatedSaleReturn>>>({
    url: "/inventory/sale/out/returns/" + id,
    method: "get",
    params: query,
  });
}

/** 销售出库输入，优惠为金额而非折扣率。 */
export type SaleOutSaveBody = Extract<SaleSaveBody, { discount_amount: string }>;

/** 销售出库接口。 */
const SaleOutAPI = {
  ...createSaleClient({ path: "/inventory/sale/out" }),
  relatedReturns,
  returnable,
};
export default SaleOutAPI;
