import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "@utils";
import ReceivableAPI, { BalanceAPI as ReceivableBalance } from "./receivable";
import PayableAPI, { BalanceAPI as PayableBalance } from "./payable";
vi.mock("@utils", () => ({ request: vi.fn() }));
beforeEach(() => vi.mocked(request).mockClear());
describe.each([
  { kind: "receivable", api: ReceivableAPI, balance: ReceivableBalance },
  { kind: "payable", api: PayableAPI, balance: PayableBalance },
])("$kind 往来接口", ({ kind, api, balance }) => {
  const path = "/inventory/finance/" + kind;
  it("账单查询为 GET，导出为 POST 并保留字段、文件名", () => {
    api.list({ party_id: 3, status: 0 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/list",
      method: "get",
      params: { party_id: 3, status: 0 },
    });
    api.detail(4);
    expect(request).toHaveBeenLastCalledWith({ url: path + "/detail/4", method: "get" });
    const body = {
      query: { party_id: 3 },
      fields: ["business_no", "amount"],
      format: "csv" as const,
      sheet_name: "往来",
      filename: "核对",
    };
    api.exportDocument(body);
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/export",
      method: "post",
      data: body,
      responseType: "blob",
    });
    expect(api).not.toHaveProperty("create");
    expect(api).not.toHaveProperty("remove");
  });
  it("余额列表、汇总与导出使用独立路径", () => {
    balance.list({ party_name: "公司", balance_state: "negative", page_no: 2 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/balance/list",
      method: "get",
      params: { party_name: "公司", balance_state: "negative", page_no: 2 },
    });
    balance.summary({ party_id: 3 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/summary",
      method: "get",
      params: { party_id: 3 },
    });
    const body = {
      query: { party_id: 3 },
      fields: ["party_name", "unsettled_net_amount"],
      format: "xlsx" as const,
      sheet_name: "余额",
    };
    balance.exportDocument(body);
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/balance/export",
      method: "post",
      data: body,
      responseType: "blob",
    });
  });
});
