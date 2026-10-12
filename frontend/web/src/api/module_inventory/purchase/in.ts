import { createPurchaseClient } from "./client";
import { request } from "@utils";
import type { RelatedPurchaseReturn } from "./types";

/** 原入库单关联退货的分页参数。 */
type RelatedReturnsQuery = Pick<PageQuery, "page_no" | "page_size">;
/** 分页读取有权限的关联退货，包含草稿、已确认和作废记录。 */
function relatedReturns(id: number, query: RelatedReturnsQuery) {
  return request<ApiResponse<PageResult<RelatedPurchaseReturn>>>({
    url: "/inventory/purchase/in/returns/" + id,
    method: "get",
    params: query,
  });
}

/** 采购入库接口。 */
const PurchaseInAPI = {
  ...createPurchaseClient({ path: "/inventory/purchase/in" }),
  relatedReturns,
};
export default PurchaseInAPI;
