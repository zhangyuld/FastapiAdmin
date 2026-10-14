import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, KeepAlive, nextTick, ref } from "vue";
import { mount, flushPromises } from "@vue/test-utils";
import { useInventoryDashboard } from "./useInventoryDashboard";

const mocks = vi.hoisted(() => ({
  allowed: true,
  summary: vi.fn(),
  trend: vi.fn(),
  warehouses: vi.fn(),
  warnings: vi.fn(),
  recent: vi.fn(),
}));
vi.mock("@/utils/checkPerm", () => ({ checkPerm: () => mocks.allowed }));
vi.mock("@/api/module_inventory/dashboard", () => ({
  getDashboardSummary: mocks.summary,
  getDashboardTrend: mocks.trend,
  getWarehouseStock: mocks.warehouses,
  getStockWarnings: mocks.warnings,
  getRecentDocuments: mocks.recent,
}));
let subject: ReturnType<typeof useInventoryDashboard>;
const Subject = defineComponent({
  setup() {
    subject = useInventoryDashboard();
    return () => h("div");
  },
});
const wrappers: ReturnType<typeof mount>[] = [];
/** 包装框架标准响应。 */
function response<T>(data: T) {
  return { data: { data } };
}
/** 建立测试宿主，确保生命周期清理真实触发。 */
function createSubject() {
  const wrapper = mount(Subject);
  wrappers.push(wrapper);
  return wrapper;
}
beforeEach(() => {
  vi.clearAllMocks();
  mocks.allowed = true;
  mocks.summary.mockResolvedValue(response({ today: "2026-10-14" }));
  mocks.trend.mockResolvedValue(
    response({ points: [], start_date: "2026-10-01", end_date: "2026-10-14" })
  );
  mocks.warehouses.mockResolvedValue(response([]));
  mocks.warnings.mockResolvedValue(response({ total: 0, items: [] }));
  mocks.recent.mockResolvedValue(response([]));
});
afterEach(() => {
  wrappers.forEach((wrapper) => wrapper.unmount());
  wrappers.length = 0;
});
describe("首页请求编排", () => {
  it("初次进入各接口只请求一次，分页仅请求预警", async () => {
    createSubject();
    await flushPromises();
    expect(mocks.summary).toHaveBeenCalledTimes(1);
    expect(mocks.trend).toHaveBeenCalledTimes(1);
    subject.changeWarningPage(2);
    await flushPromises();
    expect(mocks.warnings).toHaveBeenLastCalledWith({ page_no: 2, page_size: 5 });
    expect(mocks.summary).toHaveBeenCalledTimes(1);
  });
  it("无权限面板不发请求，空数据不标记失败", async () => {
    mocks.allowed = false;
    createSubject();
    await flushPromises();
    expect(mocks.trend).not.toHaveBeenCalled();
    expect(mocks.warehouses).not.toHaveBeenCalled();
    expect(mocks.recent).not.toHaveBeenCalled();
    expect(subject.trend.forbidden).toBe(true);
    expect(subject.summary.error).toBe(false);
  });
  it("一个接口失败不阻塞其余面板，并可独立重试", async () => {
    mocks.trend.mockRejectedValueOnce(new Error("offline"));
    createSubject();
    await flushPromises();
    expect(subject.trend.error).toBe(true);
    expect(subject.summary.data).toBeDefined();
    expect(subject.recent.data).toEqual([]);
    await subject.loadTrend();
    expect(subject.trend.error).toBe(false);
  });
  it.each([{ response: { status: 403 } }, { code: 403 }])(
    "403不能显示成空业务或通用错误: %j",
    async (failure) => {
      mocks.warehouses.mockRejectedValueOnce(failure);
      createSubject();
      await flushPromises();
      expect(subject.warehouses.forbidden).toBe(true);
      expect(subject.warehouses.error).toBe(false);
      expect(subject.warehouses.data).toBeUndefined();
    }
  );
  it("切换期间后旧回包不能覆盖新趋势", async () => {
    let resolveOld!: (value: unknown) => void;
    mocks.trend.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveOld = resolve;
      })
    );
    createSubject();
    await flushPromises();
    subject.changePeriod("7d");
    await flushPromises();
    resolveOld(response({ points: [], start_date: "old" }));
    await flushPromises();
    expect(subject.trend.data?.start_date).toBe("2026-10-01");
  });
  it("缓存切换重新加载，不重复首次请求", async () => {
    const visible = ref(true);
    const Host = defineComponent({
      setup: () => () => h(KeepAlive, {}, () => (visible.value ? h(Subject) : h("div"))),
    });
    const wrapper = mount(Host);
    wrappers.push(wrapper);
    await flushPromises();
    expect(mocks.summary).toHaveBeenCalledTimes(1);
    visible.value = false;
    await nextTick();
    visible.value = true;
    await nextTick();
    await flushPromises();
    expect(mocks.summary).toHaveBeenCalledTimes(2);
  });
});
