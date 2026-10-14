import { createFinanceClient } from "./client";
/** 应付账单和对象余额接口。 */
export default createFinanceClient({ kind: "payable" });
export const BalanceAPI = createFinanceClient({ kind: "payable", balance: true });
