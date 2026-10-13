import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "@utils";
import BalanceAPI from "./balance";
import LogAPI from "./log";
import OpeningAPI from "./opening";
import CheckAPI from "./check";

vi.mock("@utils", () => ({ request: vi.fn() }));
beforeEach(() => vi.mocked(request).mockClear());

describe.each([
  { path: "/inventory/stock/balance", api: BalanceAPI },
  { path: "/inventory/stock/log", api: LogAPI },
])("$path 只读契约", ({ path, api }) => {
  it("查询使用 GET，导出保留筛选和字段", () => {
    api.list({ warehouse_id: 2, goods_id: 3 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/list",
      method: "get",
      params: { warehouse_id: 2, goods_id: 3 },
    });
    api.detail(1);
    expect(request).toHaveBeenLastCalledWith({ url: path + "/detail/1", method: "get" });
    const body = {
      query: { warehouse_id: 2 },
      fields: ["goods_name", "warehouse_name"],
      format: "csv" as const,
      sheet_name: "库存",
      filename: "库存核对",
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
});
describe.each([
  {
    path: "/inventory/stock/opening",
    api: OpeningAPI,
    item: { goods_id: 3, quantity: "1.000", unit_cost: "2.0000" },
  },
  {
    path: "/inventory/stock/check",
    api: CheckAPI,
    item: { goods_id: 3, actual_quantity: "1.000" },
  },
])("$path 单据契约", ({ path, api, item }) => {
  it("保存使用 POST，版本随生命周期请求传递", () => {
    const body = { warehouse_id: 2, business_date: "2026-10-12", remark: "", items: [item] };
    api.create(body);
    expect(request).toHaveBeenLastCalledWith({ url: path + "/create", method: "post", data: body });
    api.update(1, { ...body, version: 2 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/update/1",
      method: "post",
      data: { ...body, version: 2 },
    });
    api.confirm(1, { version: 2 });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/confirm/1",
      method: "post",
      data: { version: 2 },
    });
    api.voidDocument(1, { version: 3, void_reason: "复核" });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/void/1",
      method: "post",
      data: { version: 3, void_reason: "复核" },
    });
    api.remove({ ids: [1], versions: { 1: 2 } });
    expect(request).toHaveBeenLastCalledWith({
      url: path + "/delete",
      method: "post",
      data: { ids: [1], versions: { 1: 2 } },
    });
  });
});
it("读取与显式刷新账面快照使用不同接口", () => {
  CheckAPI.snapshot({ warehouse_id: 2, goods_ids: [3, 4] });
  expect(request).toHaveBeenLastCalledWith({
    url: "/inventory/stock/check/snapshot",
    method: "get",
    params: { warehouse_id: 2, goods_ids: [3, 4] },
  });
  CheckAPI.refresh(1, { version: 2 });
  expect(request).toHaveBeenLastCalledWith({
    url: "/inventory/stock/check/refresh/1",
    method: "post",
    data: { version: 2 },
  });
});
