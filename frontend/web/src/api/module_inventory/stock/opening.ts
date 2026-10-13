import { createStockDocumentClient } from "./client";
/** 期初库存业务接口。 */
export default createStockDocumentClient({ path: "/inventory/stock/opening" });
