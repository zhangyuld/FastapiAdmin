import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { computed, reactive, watch, nextTick } from "vue";
import ReportPage from "./ReportPage.vue";
vi.mock("./ReportContent.vue", () => ({
  default: { name: "ReportContent", props: ["kind", "view"], template: "<div />" },
}));
const route = reactive<{ path: string; query: Record<string, string> }>({
  path: "/inventory/report/stock",
  query: {},
});
const replace = vi.fn();
/** 隔离实际表格，只验证页面维度和缓存恢复。 */
function render() {
  return mount(ReportPage, {
    props: { kind: "stock" },
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
  route.path = "/inventory/report/stock";
  route.query = {};
  replace.mockClear();
  vi.stubGlobal("reactive", reactive);
  vi.stubGlobal("computed", computed);
  vi.stubGlobal("watch", watch);
  vi.stubGlobal("useRoute", () => route);
  vi.stubGlobal("useRouter", () => ({ replace }));
});
afterEach(() => vi.unstubAllGlobals());
it("URL 恢复期间视图，缓存页不响应其他报表参数", async () => {
  route.query = { view: "movement" };
  const wrapper = render();
  expect(wrapper.getComponent({ name: "ReportContent" }).props("view")).toBe("movement");
  route.path = "/inventory/report/sale";
  route.query = { view: "goods" };
  await nextTick();
  expect(wrapper.getComponent({ name: "ReportContent" }).props("view")).toBe("movement");
  wrapper.unmount();
});
it("切换库存视图清除旧日期和对象筛选", () => {
  route.query = { view: "movement", warehouse_id: "2" };
  const wrapper = render();
  wrapper.getComponent({ name: "ElRadioGroup" }).vm.$emit("change", "balance");
  expect(replace).toHaveBeenLastCalledWith({
    path: "/inventory/report/stock",
    query: { view: "balance" },
  });
  wrapper.unmount();
});
it("错误维度恢复当前库存", () => {
  route.query = { view: "documents" };
  const wrapper = render();
  expect(wrapper.getComponent({ name: "ReportContent" }).props("view")).toBe("balance");
  wrapper.unmount();
});
