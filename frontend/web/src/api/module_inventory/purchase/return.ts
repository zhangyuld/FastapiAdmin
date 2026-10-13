import { createPurchaseClient } from "./client";

/** 采购退货接口。 */
const PurchaseReturnAPI = createPurchaseClient({ path: "/inventory/purchase/return_order" });
export default PurchaseReturnAPI;
