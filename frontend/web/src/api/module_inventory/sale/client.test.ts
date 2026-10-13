import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "@utils";
import SaleOutAPI from "./out";
import SaleReturnAPI from "./return";
import type { SaleSaveBody } from "./client";

vi.mock("@utils", () => ({ request: vi.fn() }));
describe.each([
  { path: "/inventory/sale/out", api: SaleOutAPI, extra: { discount_amount: "1.00" } },
  {
    path: "/inventory/sale/return_order",
    api: SaleReturnAPI,
    extra: { source_sale_out_id: 3, return_reason: "质量问题" },
  },
])("$path 接口契约", ({ path, api, extra }) => {
  beforeEach(() => vi.mocked(request).mockClear());
  it("查询使用 GET，业务输入不混入成本和合计", () => {
    api.list({ page_no: 1, page_size: 10, customer_id: 2 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/list",
      method: "get",
      params: { page_no: 1, page_size: 10, customer_id: 2 },
    });
    api.detail(3);
    expect(request).toHaveBeenLastCalledWith({ url: path + "/detail/3", method: "get" });
    const body: SaleSaveBody = {
      customer_id: 2,
      warehouse_id: 1,
      business_date: "2026-10-12",
      remark: "",
      items: [{ goods_id: 4, quantity: "1.000", unit_price: "2.0000" }],
      ...extra,
    };
    api.create(body);
    expect(request).toHaveBeenLastCalledWith({ url: path + "/create", method: "post", data: body });
    api.update(3, { ...body, version: 1 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/update/3",
      method: "post",
      data: { ...body, version: 1 },
    });
  });
  it("确认作废删除均使用 POST 并携带版本", () => {
    api.confirm(3, { version: 0 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/confirm/3",
      method: "post",
      data: { version: 0 },
    });
    api.voidDocument(3, { version: 1, void_reason: "作废" });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/void/3",
      method: "post",
      data: { version: 1, void_reason: "作废" },
    });
    api.remove({ ids: [3], versions: { 3: 0 } });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/delete",
      method: "post",
      data: { ids: [3], versions: { 3: 0 } },
    });
  });
  it("全量导出传递筛选、字段顺序、文件名和格式", () => {
    const body = {
      query: { customer_id: 2 },
      fields: ["order_no", "customer_name"],
      format: "csv" as const,
      sheet_name: "销售",
      filename: "销售数据",
    };
    api.exportDocument(body);
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/export",
      method: "post",
      data: body,
      responseType: "blob",
    });
  });
});
it("原单可退额度和关联退货分别预留 GET 接口", () => {
  SaleOutAPI.returnable(3, { exclude_return_id: 7 });
  expect(request).toHaveBeenLastCalledWith({
    url: "/inventory/sale/out/returnable/3",
    method: "get",
    params: { exclude_return_id: 7 },
  });
  SaleOutAPI.relatedReturns(3, { page_no: 2, page_size: 10 });
  expect(request).toHaveBeenLastCalledWith({
    url: "/inventory/sale/out/returns/3",
    method: "get",
    params: { page_no: 2, page_size: 10 },
  });
});
