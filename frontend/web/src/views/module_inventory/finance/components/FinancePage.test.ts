import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { computed, reactive, watch, nextTick } from "vue";
import FinancePage from "./FinancePage.vue";
vi.mock("./FinanceList.vue", () => ({
  default: {
    name: "FinanceList",
    props: ["kind", "balance", "partyId"],
    emits: ["selectParty"],
    template: "<div />",
  },
}));
const replace = vi.fn();
const route = reactive<{ path: string; query: Record<string, string> }>({
  path: "/inventory/finance/receivable",
  query: {},
});
/** 隔离列表请求，只检查缓存页与路由恢复契约。 */
function render() {
  return mount(FinancePage, {
    props: { kind: "receivable" },
    global: {
      stubs: {
        ElRadioGroup: {
          name: "ElRadioGroup",
          props: ["modelValue"],
          emits: ["change"],
          template: "<div><slot /></div>",
        },
        ElRadioButton: true,
      },
    },
  });
}
beforeEach(() => {
  route.path = "/inventory/finance/receivable";
  route.query = {};
  replace.mockClear();
  vi.stubGlobal("reactive", reactive);
  vi.stubGlobal("computed", computed);
  vi.stubGlobal("watch", watch);
  vi.stubGlobal("useRoute", () => route);
  vi.stubGlobal("useRouter", () => ({ replace }));
});
afterEach(() => vi.unstubAllGlobals());
describe("往来页面状态", () => {
  it("刷新恢复余额视图，缓存页不响应其他领域的对象参数", async () => {
    route.query = { view: "balance" };
    const wrapper = render();
    expect(wrapper.getComponent({ name: "FinanceList" }).props("balance")).toBe(true);
    route.path = "/inventory/finance/payable";
    route.query = { view: "bills", party_id: "123" };
    await nextTick();
    expect(wrapper.getComponent({ name: "FinanceList" }).props("balance")).toBe(true);
    expect(wrapper.getComponent({ name: "FinanceList" }).props("partyId")).toBeUndefined();
    route.path = "/inventory/finance/receivable";
    route.query = { view: "bills", party_id: "6" };
    await nextTick();
    expect(wrapper.getComponent({ name: "FinanceList" }).props("partyId")).toBe(6);
    wrapper.unmount();
  });
  it("余额跳转携带对象，主动切换视图清除旧对象限制", () => {
    const wrapper = render();
    wrapper.getComponent({ name: "FinanceList" }).vm.$emit("selectParty", 11);
    expect(replace).toHaveBeenLastCalledWith({ query: { view: "bills", party_id: 11 } });
    wrapper.getComponent({ name: "ElRadioGroup" }).vm.$emit("change", "balance");
    expect(replace).toHaveBeenLastCalledWith({ query: { view: "balance" } });
    wrapper.unmount();
  });
  it("忽略非法对象 ID", () => {
    route.query = { party_id: "-1" };
    const wrapper = render();
    expect(wrapper.getComponent({ name: "FinanceList" }).props("partyId")).toBeUndefined();
    wrapper.unmount();
  });
});
