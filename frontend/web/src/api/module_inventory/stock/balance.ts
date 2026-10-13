import { createStockReadClient } from "./client";
/** 当前库存只读接口。 */
export default createStockReadClient({ path: "/inventory/stock/balance" });
