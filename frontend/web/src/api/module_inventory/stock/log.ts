import { createStockReadClient } from "./client";
/** 不可变库存流水查询接口。 */
export default createStockReadClient({ path: "/inventory/stock/log" });
