import { beforeEach, expect, it, vi } from "vitest";
import type { AxiosRequestConfig } from "axios";
import {
  getCategoryOptions,
  getCustomerOptions,
  getSupplierOptions,
  getWarehouseOptions,
} from "./options";

const request = vi.hoisted(() => vi.fn<(config: AxiosRequestConfig) => void>());
vi.mock("@utils", () => ({ request }));
beforeEach(() => vi.clearAllMocks());
it("业务选项只调用四个GET轻量接口，不复用管理列表", () => {
  getCategoryOptions({ status: 0 });
  getCustomerOptions({ keyword: "C01", page_no: 2, page_size: 50 });
  getSupplierOptions({ status: 0 });
  getWarehouseOptions({});
  expect(vi.mocked(request).mock.calls.map(([config]) => [config.url, config.method])).toEqual(
    ["category", "customer", "supplier", "warehouse"].map((kind) => [
      `/inventory/basic/${kind}/options`,
      "get",
    ])
  );
  expect(vi.mocked(request).mock.calls[1]?.[0].params).toEqual({
    keyword: "C01",
    page_no: 2,
    page_size: 50,
  });
});
