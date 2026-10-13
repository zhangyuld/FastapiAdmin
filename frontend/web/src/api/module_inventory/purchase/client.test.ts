import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "@utils";
import PurchaseInAPI from "./in";
import PurchaseReturnAPI from "./return";
import type { PurchaseSaveBody } from "./client";

vi.mock("@utils", () => ({ request: vi.fn() }));

it("入库关联退货使用独立 GET 分页接口", () => {
  PurchaseInAPI.relatedReturns(3, { page_no: 2, page_size: 10 });
  expect(request).toHaveBeenLastCalledWith({
    url: "/inventory/purchase/inbound/returns/3",
    method: "get",
    params: { page_no: 2, page_size: 10 },
  });
});

describe.each([
  { path: "/inventory/purchase/inbound", api: PurchaseInAPI },
  { path: "/inventory/purchase/return_order", api: PurchaseReturnAPI },
])("$path 接口契约", ({ path, api }) => {
  beforeEach(() => vi.mocked(request).mockClear());

  it("查询使用 GET，创建和状态操作使用 POST", () => {
    api.list({ page_no: 1, page_size: 10, status: 0 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/list",
      method: "get",
      params: { page_no: 1, page_size: 10, status: 0 },
    });
    api.detail(3);
    expect(request).toHaveBeenLastCalledWith({ url: path + "/detail/3", method: "get" });
    const body: PurchaseSaveBody = {
      supplier_id: 1,
      warehouse_id: 2,
      business_date: "2026-10-10",
      remark: "",
      items: [{ goods_id: 4, quantity: "1.000", unit_price: "2.0000" }],
    };
    api.create(body);
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/create",
      method: "post",
      data: body,
    });
    api.update(3, { ...body, version: 2 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/update/3",
      method: "post",
      data: { ...body, version: 2 },
    });
    api.remove({ ids: [3], versions: { 3: 2 } });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/delete",
      method: "post",
      data: { ids: [3], versions: { 3: 2 } },
    });
    api.confirm(3, { version: 2 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/confirm/3",
      method: "post",
      data: { version: 2 },
    });
    api.voidDocument(3, { version: 3, void_reason: "录入错误" });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/void/3",
      method: "post",
      data: { version: 3, void_reason: "录入错误" },
    });
  });

  it("导出保留筛选、字段选择及文件参数", () => {
    const body = {
      query: { status: 1 as const },
      fields: ["order_no", "total_amount"],
      format: "xlsx" as const,
      sheet_name: "采购列表",
      filename: "采购记录",
    };
    api.exportDocument(body);
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/export",
      method: "post",
      data: body,
      responseType: "blob",
    });
  });

  it("编辑来源退货时携带排除自身的 ID", () => {
    api.returnable(3, { exclude_return_id: 7 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/returnable/3",
      method: "get",
      params: { exclude_return_id: 7 },
    });
  });
});
