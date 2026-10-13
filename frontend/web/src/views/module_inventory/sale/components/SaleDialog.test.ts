import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { computed, defineAsyncComponent, defineComponent, reactive, ref, watch } from "vue";
import SaleOutAPI from "@/api/module_inventory/sale/out";
import SaleReturnAPI from "@/api/module_inventory/sale/return";
import SaleDialog from "./SaleDialog.vue";
import type { SaleDocument } from "@/api/module_inventory/sale/client";

vi.mock("@utils", () => ({ request: vi.fn() }));

vi.mock("@/api/module_inventory/sale/out", () => ({
  default: {
    detail: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    returnable: vi.fn(),
  },
}));
vi.mock("@/api/module_inventory/sale/return", () => ({
  default: {
    detail: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));
vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), error: vi.fn() },
  ElMessageBox: { confirm: vi.fn().mockResolvedValue(undefined) },
}));
vi.mock("../composables/useSaleOptions", () => ({
  useSaleOptions: () => ({
    customers: ref([{ value: 2, label: "客户甲" }]),
    warehouses: ref([{ value: 1, label: "仓库甲" }]),
    customerLoading: ref(false),
    warehouseLoading: ref(false),
    searchCustomers: vi.fn().mockResolvedValue(undefined),
    searchWarehouses: vi.fn().mockResolvedValue(undefined),
    retainOptions: vi.fn(),
  }),
}));
const document: SaleDocument = {
  id: 9,
  order_no: "SO009",
  customer_id: 2,
  customer_name: "客户甲",
  warehouse_id: 1,
  warehouse_name: "仓库甲",
  business_date: "2026-10-12",
  original_amount: "20.00",
  discount_amount: "4.00",
  receivable_amount: "16.00",
  status: 1,
  version: 1,
  items: [
    {
      id: 3,
      line_no: 1,
      goods_id: 4,
      goods_code: "G4",
      goods_name: "商品",
      unit: "件",
      quantity: "2.000",
      unit_price: "10.0000",
      line_amount: "20.00",
      returnable_quantity: "2.000",
      returnable_amount: "16.00",
    },
  ],
};
const SelectStub = defineComponent({
  name: "SelectStub",
  props: ["modelValue", "disabled"],
  emits: ["update:modelValue"],
  template: "<div><slot /></div>",
});
const LinesStub = defineComponent({
  name: "LinesStub",
  props: ["modelValue", "readonly", "sourced"],
  emits: ["update:modelValue"],
  template: "<div />",
});
const SourceStub = defineComponent({
  name: "SourceStub",
  props: ["modelValue"],
  emits: ["select", "update:modelValue"],
  template: "<div />",
});
const FormStub = defineComponent({
  props: ["disabled", "model"],
  setup(_props, { expose }) {
    expose({ validate: () => Promise.resolve(true) });
  },
  template: "<div><slot /></div>",
});
/** 挂载销售弹窗，验证业务请求与只读控制而不依赖全局插件。 */
function render(kind: "out" | "return", mode: "create" | "detail" = "create") {
  return mount(SaleDialog, {
    props: { kind, mode, modelValue: true, documentId: mode === "detail" ? 9 : undefined },
    global: {
      directives: { loading: () => undefined },
      stubs: {
        FaDialog: { template: "<div><slot /><slot name='footer' /></div>" },
        ElForm: FormStub,
        ElFormItem: { template: "<div><slot /></div>" },
        ElRow: { template: "<div><slot /></div>" },
        ElCol: { template: "<div><slot /></div>" },
        ElSelect: SelectStub,
        ElOption: true,
        ElDatePicker: true,
        ElInput: {
          props: ["modelValue", "readonly"],
          template: "<input :value='modelValue' :readonly='readonly' />",
        },
        ElButton: {
          props: ["disabled"],
          emits: ["click"],
          template: "<button :disabled='disabled' @click='$emit(\"click\")'><slot /></button>",
        },
        ElDescriptions: { template: "<div><slot /></div>" },
        ElDescriptionsItem: { template: "<span><slot /></span>" },
        ElResult: { props: ["title"], template: "<div>{{ title }}<slot name='extra' /></div>" },
        SaleLines: LinesStub,
        SaleSourcePicker: SourceStub,
        SaleReturnHistory: true,
      },
    },
  });
}
describe("销售单据弹窗", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("ref", ref);
    vi.stubGlobal("reactive", reactive);
    vi.stubGlobal("computed", computed);
    vi.stubGlobal("watch", watch);
    vi.stubGlobal("defineAsyncComponent", defineAsyncComponent);
    vi.mocked(SaleOutAPI.detail).mockResolvedValue({ data: { data: document } } as never);
    vi.mocked(SaleOutAPI.create).mockResolvedValue({ data: { data: document } } as never);
    vi.mocked(SaleReturnAPI.create).mockResolvedValue({ data: { data: document } } as never);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });
  it("确认单详情客户、仓库和商品只读，并展示服务端金额", async () => {
    const wrapper = render("out", "detail");
    await flushPromises();
    expect(wrapper.findAllComponents(SelectStub).every((select) => select.props("disabled"))).toBe(
      true
    );
    expect(wrapper.getComponent(LinesStub).props("readonly")).toBe(true);
    expect(wrapper.text()).toContain("16.00");
    expect(wrapper.text()).not.toContain("保存草稿");
    wrapper.unmount();
  });
  it("详情失败禁止保存并支持重试", async () => {
    vi.mocked(SaleOutAPI.detail).mockRejectedValueOnce(new Error("接口未实现"));
    const wrapper = render("out", "detail");
    await flushPromises();
    expect(wrapper.text()).toContain("单据加载失败");
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "重试")!
      .trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("16.00");
    wrapper.unmount();
  });
  it("原单退货客户仓库只读，并提交来源行而不是优惠或合计", async () => {
    const wrapper = render("return");
    await flushPromises();
    expect(wrapper.findAllComponents(SelectStub)).toHaveLength(0);
    wrapper.getComponent(SourceStub).vm.$emit("select", document);
    await flushPromises();
    const form = wrapper.getComponent(FormStub).props("model") as { return_reason: string };
    form.return_reason = "质量问题";
    expect(wrapper.text()).toContain("16.00");
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "保存草稿")!
      .trigger("click");
    await flushPromises();
    expect(SaleReturnAPI.create).toHaveBeenCalledWith({
      customer_id: 2,
      warehouse_id: 1,
      business_date: expect.any(String),
      remark: "",
      source_sale_out_id: 9,
      return_reason: "质量问题",
      items: [
        { goods_id: 4, quantity: "2.000", unit_price: "10.0000", source_sale_out_item_id: 3 },
      ],
    });
    expect(wrapper.emitted("success")).toHaveLength(1);
    wrapper.unmount();
  });
  it("没有原单的退货不能提交", async () => {
    const wrapper = render("return");
    await flushPromises();
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "保存草稿")!
      .trigger("click");
    await flushPromises();
    expect(SaleReturnAPI.create).not.toHaveBeenCalled();
    wrapper.unmount();
  });
  it("优惠超过原价时不能提交", async () => {
    const wrapper = render("out");
    await flushPromises();
    wrapper.getComponent(LinesStub).vm.$emit("update:modelValue", document.items);
    const form = wrapper.getComponent(FormStub).props("model") as { discount_amount: string };
    form.discount_amount = "20.01";
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "保存草稿")!
      .trigger("click");
    await flushPromises();
    expect(SaleOutAPI.create).not.toHaveBeenCalled();
    wrapper.unmount();
  });
  it("校验和保存期间重复点击只发送一次请求", async () => {
    const wrapper = render("out");
    await flushPromises();
    const selects = wrapper.findAllComponents(SelectStub);
    selects[0]!.vm.$emit("update:modelValue", 2);
    selects[1]!.vm.$emit("update:modelValue", 1);
    wrapper.getComponent(LinesStub).vm.$emit("update:modelValue", document.items);
    const save = wrapper.findAll("button").find((button) => button.text() === "保存草稿")!;
    await Promise.all([save.trigger("click"), save.trigger("click")]);
    await flushPromises();
    expect(SaleOutAPI.create).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });
  it("出库草稿提交优惠金额，失败不发出保存成功事件", async () => {
    vi.mocked(SaleOutAPI.create).mockRejectedValueOnce(new Error("接口未实现"));
    const wrapper = render("out");
    await flushPromises();
    const selects = wrapper.findAllComponents(SelectStub);
    selects[0]!.vm.$emit("update:modelValue", 2);
    selects[1]!.vm.$emit("update:modelValue", 1);
    wrapper.getComponent(LinesStub).vm.$emit("update:modelValue", document.items);
    const form = wrapper.getComponent(FormStub).props("model") as { discount_amount: string };
    form.discount_amount = "4.00";
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "保存草稿")!
      .trigger("click");
    await flushPromises();
    expect(SaleOutAPI.create).toHaveBeenCalledWith({
      customer_id: 2,
      warehouse_id: 1,
      business_date: expect.any(String),
      remark: "",
      discount_amount: "4.00",
      items: [{ goods_id: 4, quantity: "2.000", unit_price: "10.0000" }],
    });
    expect(wrapper.emitted("success")).toBeUndefined();
    wrapper.unmount();
  });
});
