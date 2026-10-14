import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "@utils";
import PurchaseAPI from "./purchase";
import SaleAPI from "./sale";
import StockAPI from "./stock";
import ProfitAPI from "./profit";
import { reportApiReady } from "./client";
vi.mock("@utils", () => ({ request: vi.fn() }));
beforeEach(() => vi.mocked(request).mockClear());
describe.each([
  { kind: "purchase", api: PurchaseAPI },
  { kind: "sale", api: SaleAPI },
  { kind: "stock", api: StockAPI },
  { kind: "profit", api: ProfitAPI },
])("$kind 报表契约", ({ kind, api }) => {
  it("仅提供 GET 查询和 POST 文件流导出", () => {
    const query = {
      view: kind === "stock" ? ("balance" as const) : ("documents" as const),
      goods_name: "商品",
      page_no: 2,
    };
    api.list(query);
    expect(request).toHaveBeenLastCalledWith({
      url: "/inventory/report/" + kind + "/list",
      method: "get",
      params: query,
    });
    api.summary({ view: query.view, goods_name: "商品" });
    expect(request).toHaveBeenLastCalledWith({
      url: "/inventory/report/" + kind + "/summary",
      method: "get",
      params: { view: query.view, goods_name: "商品" },
    });
    const body = {
      query,
      fields: ["goods_name", "net_amount"],
      format: "csv" as const,
      sheet_name: "报表",
      filename: "经营核对",
    };
    api.exportDocument(body);
    expect(request).toHaveBeenLastCalledWith({
      url: "/inventory/report/" + kind + "/export",
      method: "post",
      data: body,
      responseType: "blob",
    });
    expect(api).not.toHaveProperty("create");
    expect(api).not.toHaveProperty("remove");
  });
  it("四个报表领域均已接入后端", () => {
    expect(reportApiReady[kind as keyof typeof reportApiReady]).toBe(true);
  });
});
