import { createFinanceClient } from "./client";
/** 应收账单和对象余额接口。 */
export default createFinanceClient({ kind: "receivable" });
export const BalanceAPI = createFinanceClient({ kind: "receivable", balance: true });
