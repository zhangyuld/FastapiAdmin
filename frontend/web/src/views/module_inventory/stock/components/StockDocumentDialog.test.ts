import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { computed, defineComponent, reactive, ref, watch } from "vue";
import CheckAPI from "@/api/module_inventory/stock/check";
import OpeningAPI from "@/api/module_inventory/stock/opening";
import type { StockDocument, StockLine } from "@/api/module_inventory/stock/client";
import StockDocumentDialog from "./StockDocumentDialog.vue";

vi.mock("@utils", () => ({ request: vi.fn() }));
vi.mock("@/api/module_inventory/stock/opening", () => ({
  default: { detail: vi.fn(), create: vi.fn(), update: vi.fn() },
}));
vi.mock("@/api/module_inventory/stock/check", () => ({
  default: { detail: vi.fn(), create: vi.fn(), update: vi.fn(), refresh: vi.fn() },
}));
vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), warning: vi.fn() },
  ElMessageBox: { confirm: vi.fn().mockResolvedValue(undefined) },
}));
vi.mock("../composables/useStockOptions", () => ({
  useStockOptions: () => ({
    warehouses: ref([]),
    loading: ref(false),
    searchWarehouses: vi.fn().mockResolvedValue(undefined),
    retainWarehouse: vi.fn(),
  }),
}));
const document: StockDocument = {
  id: 1,
  doc_no: "SC1",
  warehouse_id: 2,
  warehouse_name: "仓库",
  business_date: "2026-10-12",
  status: 0,
  version: 0,
  items: [
    {
      goods_id: 3,
      goods_code: "G3",
      goods_name: "商品",
      unit: "件",
      actual_quantity: "2.000",
      system_quantity: "0.000",
      system_stock_amount: "0.00",
      balance_version: 0,
      unit_cost: "2.0000",
      cost_amount: "4.00",
    },
  ],
};
const FormStub = defineComponent({
  props: ["disabled", "model"],
  setup(_props, { expose }) {
    expose({ validate: () => Promise.resolve(true) });
  },
  template: "<div><slot /></div>",
});
const LinesStub = defineComponent({
  props: ["modelValue", "readonly", "disabled"],
  emits: ["update:modelValue", "loading"],
  template: "<div />",
});
/** 隔离全局插件，仅检查库存弹窗的状态和提交契约。 */
function render(mode: "create" | "update" | "detail", kind: "opening" | "check" = "check") {
  return mount(StockDocumentDialog, {
    props: { modelValue: true, mode, kind, documentId: mode === "create" ? undefined : 1 },
    global: {
      directives: { loading: () => undefined },
      stubs: {
        FaDialog: { template: "<div><slot /><slot name='footer' /></div>" },
        ElForm: FormStub,
        StockLines: LinesStub,
        ElFormItem: { template: "<div><slot /></div>" },
        ElRow: { template: "<div><slot /></div>" },
        ElCol: { template: "<div><slot /></div>" },
        ElSelect: { template: "<div><slot /></div>" },
        ElOption: true,
        ElInput: true,
        ElDatePicker: true,
        ElButton: {
          props: ["disabled"],
          emits: ["click"],
          template: "<button :disabled='disabled' @click='$emit(\"click\")'><slot /></button>",
        },
        ElResult: { props: ["title"], template: "<div>{{title}}<slot name='extra' /></div>" },
        ElDescriptions: { template: "<div><slot /></div>" },
        ElDescriptionsItem: { template: "<span><slot /></span>" },
      },
    },
  });
}
describe("库存单据弹窗", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("ref", ref);
    vi.stubGlobal("reactive", reactive);
    vi.stubGlobal("computed", computed);
    vi.stubGlobal("watch", watch);
    vi.stubGlobal("useAuth", () => ({ hasAuth: () => true }));
    vi.mocked(CheckAPI.detail).mockResolvedValue({ data: { data: document } } as never);
    vi.mocked(CheckAPI.update).mockResolvedValue({ data: { data: document } } as never);
    vi.mocked(CheckAPI.refresh).mockResolvedValue({
      data: { data: { ...document, version: 1 } },
    } as never);
    vi.mocked(OpeningAPI.detail).mockResolvedValue({
      data: { data: { ...document, status: 1 } },
    } as never);
  });
  afterEach(() => vi.unstubAllGlobals());
  it("详情和已确认单据的仓库、明细及业务字段只读", async () => {
    for (const [mode, kind] of [
      ["detail", "check"],
      ["update", "opening"],
    ] as const) {
      const wrapper = render(mode, kind);
      await flushPromises();
      expect(wrapper.getComponent(FormStub).props("disabled")).toBe(true);
      expect(wrapper.getComponent(LinesStub).props("readonly")).toBe(true);
      expect(wrapper.text()).not.toContain("保存草稿");
      wrapper.unmount();
    }
  });
  it("详情请求失败可重试且不允许保存", async () => {
    vi.mocked(CheckAPI.detail).mockRejectedValueOnce(new Error("加载失败"));
    const wrapper = render("update");
    await flushPromises();
    expect(wrapper.text()).toContain("单据加载失败");
    const save = wrapper.findAll("button").find((x) => x.text() === "保存草稿")!;
    expect(save.attributes("disabled")).toBeDefined();
    await wrapper
      .findAll("button")
      .find((x) => x.text() === "重试")!
      .trigger("click");
    await flushPromises();
    expect(wrapper.getComponent(LinesStub).props("modelValue")).toEqual(document.items);
    wrapper.unmount();
  });
  it("盘点保存仅提交实盘、成本和版本，不提交账面快照", async () => {
    const wrapper = render("update");
    await flushPromises();
    await wrapper
      .findAll("button")
      .find((x) => x.text() === "保存草稿")!
      .trigger("click");
    await flushPromises();
    expect(CheckAPI.update).toHaveBeenCalledWith(1, {
      warehouse_id: 2,
      business_date: "2026-10-12",
      remark: "",
      version: 0,
      items: [{ goods_id: 3, actual_quantity: "2.000", unit_cost: "2.0000" }],
    });
    wrapper.unmount();
  });
  it("显式刷新采用已保存版本，商品快照加载期间禁止保存", async () => {
    const wrapper = render("update");
    await flushPromises();
    wrapper.getComponent(LinesStub).vm.$emit("loading", true);
    await flushPromises();
    expect(
      wrapper
        .findAll("button")
        .find((x) => x.text() === "保存草稿")!
        .attributes("disabled")
    ).toBeDefined();
    wrapper.getComponent(LinesStub).vm.$emit("loading", false);
    await flushPromises();
    await wrapper
      .findAll("button")
      .find((x) => x.text() === "刷新账面快照")!
      .trigger("click");
    await flushPromises();
    expect(CheckAPI.refresh).toHaveBeenCalledWith(1, { version: 0 });
    expect(
      (wrapper.getComponent(LinesStub).props("modelValue") as StockLine[])[0]?.actual_quantity
    ).toBe("2.000");
    wrapper.unmount();
  });
});
