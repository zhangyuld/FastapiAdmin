import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { computed, defineComponent, h, onUnmounted, reactive, watch } from "vue";
import PurchaseInAPI from "@/api/module_inventory/purchase/in";
import PurchaseReturnHistory from "./PurchaseReturnHistory.vue";
import type { RelatedPurchaseReturn } from "@/api/module_inventory/purchase/types";

vi.mock("@/api/module_inventory/purchase/in", () => ({
  default: { relatedReturns: vi.fn() },
}));
const summary = { return_status: "partial" as const, confirmed_count: 1, returned_amount: "8.00" };
const row: RelatedPurchaseReturn = {
  id: 7,
  order_no: "PR007",
  business_date: "2026-10-12",
  status: 1,
  total_amount: "8.00",
  return_reason: "质量问题",
};
/** 构建分页响应，仅模拟关联记录接口。 */
function response(items: RelatedPurchaseReturn[] = [row]) {
  return { data: { data: { items, total: items.length, page_no: 1, page_size: 10 } } };
}
const TableStub = defineComponent({
  props: ["data"],
  setup(props, { slots }) {
    return () =>
      h(
        "div",
        (props.data as RelatedPurchaseReturn[]).map((item) =>
          h("div", [slots.order_no?.({ row: item }), slots.status?.({ row: item })])
        )
      );
  },
});
/** 用轻量控件验证业务权限和请求，不依赖全局自动导入插件。 */
function render() {
  return mount(PurchaseReturnHistory, {
    props: { sourceId: 3, summary },
    global: {
      stubs: {
        FaTable: TableStub,
        ElButton: {
          emits: ["click"],
          template: "<button @click='$emit(\"click\")'><slot /></button>",
        },
        ElDescriptions: { template: "<div><slot /></div>" },
        ElDescriptionsItem: { template: "<span><slot /></span>" },
        ElTag: { template: "<span><slot /></span>" },
        ElResult: { props: ["title"], template: "<div>{{ title }}<slot name='extra' /></div>" },
        ElEmpty: { props: ["description"], template: "<div>{{ description }}</div>" },
        ElPagination: true,
      },
    },
  });
}
describe("入库关联退货", () => {
  let permissions: string[];
  beforeEach(() => {
    vi.clearAllMocks();
    permissions = [
      "module_inventory:purchase_return:query",
      "module_inventory:purchase_return:detail",
    ];
    vi.stubGlobal("reactive", reactive);
    vi.stubGlobal("computed", computed);
    vi.stubGlobal("watch", watch);
    vi.stubGlobal("onUnmounted", onUnmounted);
    vi.stubGlobal("useAuth", () => ({
      hasAuth: (permission: string) => permissions.includes(permission),
    }));
    vi.mocked(PurchaseInAPI.relatedReturns).mockResolvedValue(response() as never);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });
  it("展示汇总、单据状态并打开退货详情", async () => {
    const wrapper = render();
    await flushPromises();
    expect(wrapper.text()).toContain("部分退货");
    expect(wrapper.text()).toContain("8.00");
    expect(wrapper.text()).toContain("已确认");
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "PR007")!
      .trigger("click");
    expect(wrapper.emitted("detail")).toEqual([[7]]);
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "刷新")!
      .trigger("click");
    expect(wrapper.emitted("refresh")).toHaveLength(1);
    wrapper.unmount();
  });
  it("无查询权限仍展示实际汇总，不请求退货记录", async () => {
    permissions = [];
    const wrapper = render();
    await flushPromises();
    expect(wrapper.text()).toContain("部分退货");
    expect(wrapper.text()).toContain("暂无退货查询权限");
    expect(PurchaseInAPI.relatedReturns).not.toHaveBeenCalled();
    wrapper.unmount();
  });
  it("无详情权限只展示单号", async () => {
    permissions = ["module_inventory:purchase_return:query"];
    const wrapper = render();
    await flushPromises();
    expect(wrapper.text()).toContain("PR007");
    expect(wrapper.findAll("button").some((button) => button.text() === "PR007")).toBe(false);
    wrapper.unmount();
  });
  it("查询失败可重试，恢复后展示记录", async () => {
    vi.mocked(PurchaseInAPI.relatedReturns).mockRejectedValueOnce(new Error("失败"));
    const wrapper = render();
    await flushPromises();
    expect(wrapper.text()).toContain("关联退货加载失败");
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "重试")!
      .trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("PR007");
    wrapper.unmount();
  });
  it("切换原单后忽略过期响应并重置分页", async () => {
    let resolveOld!: (value: unknown) => void;
    vi.mocked(PurchaseInAPI.relatedReturns).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve as (value: unknown) => void;
        }) as never
    );
    const wrapper = render();
    await wrapper.setProps({ sourceId: 4 });
    await flushPromises();
    resolveOld(response([{ ...row, order_no: "旧单" }]));
    await flushPromises();
    expect(wrapper.text()).not.toContain("旧单");
    expect(PurchaseInAPI.relatedReturns).toHaveBeenLastCalledWith(4, { page_no: 1, page_size: 10 });
    wrapper.unmount();
  });
});
