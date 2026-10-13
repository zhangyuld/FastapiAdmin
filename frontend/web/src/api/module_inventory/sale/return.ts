import { createSaleClient } from "./client";
import type { SaleSaveBody } from "./client";

/** 原单销售退货输入，不接受自定义成本或合计。 */
export type SaleReturnSaveBody = Extract<SaleSaveBody, { source_sale_out_id: number }>;

/** 销售退货接口。 */
const SaleReturnAPI = createSaleClient({ path: "/inventory/sale/return_order" });
export default SaleReturnAPI;
