import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import {
  ref,
  reactive,
  computed,
  watch,
  defineComponent,
  h,
  onMounted,
  onActivated,
  onDeactivated,
  onBeforeUnmount,
} from "vue";
import type { ColumnOption } from "@/types/component";
import type { TableOperationAction } from "@utils";
import type { ReportQuery, ReportRow } from "@/api/module_inventory/report/client";
import { useReportTable, reportSourcePermission } from "./useReportTable";
const mocks = vi.hoisted(() => ({
  ready: { purchase: false, sale: false, stock: false, profit: false },
  api: { list: vi.fn(), summary: vi.fn(), exportDocument: vi.fn() },
}));
vi.mock("@/api/module_inventory/report/client", () => ({
  createReportClient: () => mocks.api,
  reportApiReady: mocks.ready,
}));
vi.mock("@utils", () => ({
  toCrudCols: (columns: { value: ColumnOption<ReportRow>[] }) => computed(() => columns.value),
  renderTableOperationCell: (actions: TableOperationAction[]) => actions,
}));
const row: ReportRow = {
  id: 1,
  supplier_name: "供应商",
  business_no: "PI1",
  purchase_amount: "100.00",
  return_amount: "30.00",
  net_purchase_amount: "70.00",
  source: { business_type: "purchase_in", business_id: 5 },
};
const summary = {
  document_count: 100,
  purchase_amount: "1200.00",
  return_amount: "200.00",
  net_purchase_amount: "1000.00",
};
const route = reactive<{
  path: string;
  fullPath: string;
  query: Record<string, string | string[]>;
}>({ path: "/inventory/report/purchase", fullPath: "/inventory/report/purchase", query: {} });
const replace = vi.fn();
let hasAuth: (permission: string) => boolean = () => true;
let subject: ReturnType<typeof useReportTable>;
/** 以框架公开方法模拟表格，检查报表编排而非重复测试框架内部实现。 */
function fakeTable(config: {
  core: {
    apiParams: ReportQuery;
    apiFn: (query: ReportQuery) => Promise<unknown>;
    columnsFactory: () => ColumnOption<ReportRow>[];
  };
}) {
  const params = reactive<ReportQuery>({ ...config.core.apiParams });
  const data = ref<ReportRow[]>([]);
  const loading = ref(false);
  const error = ref<Error | null>(null);
  const pagination = reactive({
    current: params.page_no ?? 1,
    size: params.page_size ?? 10,
    total: 0,
  });
  const columns = ref(config.core.columnsFactory());
  /** 模拟统一响应和失败状态，便于验证接入开关及汇总失效。 */
  async function fetch(): Promise<void> {
    loading.value = true;
    try {
      const response = (await config.core.apiFn({ ...params })) as {
        data: { data: { items: ReportRow[]; total: number } };
      };
      data.value = response.data.data.items;
      pagination.total = response.data.data.total;
      error.value = null;
    } catch (reason) {
      error.value = reason as Error;
    } finally {
      loading.value = false;
    }
  }
  return {
    data,
    loading,
    error,
    pagination,
    columns,
    columnChecks: ref([]),
    searchParams: params,
    refreshData: fetch,
    getData: fetch,
    /** 清空旧筛选并回到第一页。 */
    replaceSearchParams(query: ReportQuery) {
      Object.keys(params).forEach(
        (key) => delete (params as unknown as Record<string, unknown>)[key]
      );
      Object.assign(params, query);
      pagination.current = 1;
    },
    /** 失败和新查询不能保留旧行。 */
    clearData() {
      data.value = [];
      error.value = null;
    },
    /** 分页只请求列表。 */
    async handleCurrentChange(page: number) {
      params.page_no = page;
      pagination.current = page;
      await fetch();
    },
    /** 容量改变重置第一页。 */
    async handleSizeChange(size: number) {
      params.page_no = 1;
      params.page_size = size;
      pagination.current = 1;
      pagination.size = size;
      await fetch();
    },
  };
}
/** 挂载组合逻辑以注册真实生命周期。 */
function render() {
  return mount(
    defineComponent({
      setup() {
        subject = useReportTable({ kind: "purchase", view: "documents" });
        return () => h("div");
      },
    })
  );
}
beforeEach(() => {
  Object.assign(mocks.ready, { purchase: false, sale: false, stock: false, profit: false });
  route.path = "/inventory/report/purchase";
  route.fullPath = route.path;
  route.query = {};
  hasAuth = () => true;
  mocks.api.list.mockReset().mockResolvedValue({ data: { data: { items: [row], total: 100 } } });
  mocks.api.summary.mockReset().mockResolvedValue({ data: { data: summary } });
  mocks.api.exportDocument.mockReset().mockResolvedValue({ data: new Blob(["test"]) });
  replace
    .mockReset()
    .mockImplementation(async (location: { query: Record<string, string | string[]> }) => {
      route.query = location.query;
      route.fullPath = route.path + JSON.stringify(location.query);
    });
  Object.entries({
    ref,
    reactive,
    computed,
    watch,
    onMounted,
    onActivated,
    onDeactivated,
    onBeforeUnmount,
  }).forEach(([name, value]) => vi.stubGlobal(name, value));
  vi.stubGlobal("useRoute", () => route);
  vi.stubGlobal("useRouter", () => ({ replace }));
  vi.stubGlobal("useAuth", () => ({ hasAuth: (permission: string) => hasAuth(permission) }));
  vi.stubGlobal("useTable", fakeTable);
  vi.stubGlobal("useTableSelection", () => {
    const selectedRows = ref<ReportRow[]>([]);
    return {
      selectedRows,
      onTableSelectionChange: (rows: ReportRow[]) => {
        selectedRows.value = rows;
      },
      clearSelection: () => {
        selectedRows.value = [];
      },
    };
  });
  vi.stubGlobal("useImportExport", () => {
    const exportVisible = ref(false);
    return {
      exportVisible,
      openExport: () => {
        exportVisible.value = true;
      },
    };
  });
});
afterEach(() => vi.unstubAllGlobals());
describe("报表接入及请求状态", () => {
  it("待接入仍可保存筛选，但不请求列表、汇总或导出", async () => {
    const wrapper = render();
    await flushPromises();
    await subject.search({ view: "documents", supplier_name: "供应商" });
    await subject.reload();
    subject.showExport();
    expect(mocks.api.list).not.toHaveBeenCalled();
    expect(mocks.api.summary).not.toHaveBeenCalled();
    expect(mocks.api.exportDocument).not.toHaveBeenCalled();
    expect(subject.summary.value).toBeUndefined();
    expect(subject.exportDisabled.value).toBe(true);
    expect(subject.exportVisible.value).toBe(false);
    expect(replace).toHaveBeenLastCalledWith({
      path: route.path,
      query: { view: "documents", supplier_name: "供应商" },
    });
    wrapper.unmount();
  });
  it("接入后汇总使用完整筛选，不随分页重新计算", async () => {
    mocks.ready.purchase = true;
    const wrapper = render();
    await flushPromises();
    expect(subject.summary.value).toEqual(summary);
    expect(mocks.api.summary).toHaveBeenCalledWith({ view: "documents" });
    await subject.changePage(2);
    expect(mocks.api.summary).toHaveBeenCalledTimes(1);
    expect(mocks.api.list).toHaveBeenLastCalledWith({
      view: "documents",
      page_no: 2,
      page_size: 10,
    });
    wrapper.unmount();
  });
  it("加载失败清空汇总并允许重试，不开放旧数据导出", async () => {
    mocks.ready.purchase = true;
    mocks.api.list.mockRejectedValueOnce(new Error("list"));
    mocks.api.summary.mockRejectedValueOnce(new Error("summary"));
    const wrapper = render();
    await flushPromises();
    expect(subject.summaryFailed.value).toBe(true);
    expect(subject.summary.value).toBeUndefined();
    expect(subject.exportDisabled.value).toBe(true);
    await subject.reload();
    expect(subject.summaryFailed.value).toBe(false);
    expect(subject.summary.value).toEqual(summary);
    expect(subject.exportDisabled.value).toBe(false);
    wrapper.unmount();
  });
  it("旧汇总响应不能覆盖新筛选的指标", async () => {
    mocks.ready.purchase = true;
    const wrapper = render();
    await flushPromises();
    let finish: (value: unknown) => void = () => undefined;
    mocks.api.summary.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    );
    const old = subject.loadSummary();
    await subject.search({ view: "documents", supplier_name: "新供应商" });
    finish({ data: { data: { ...summary, net_purchase_amount: "999999.00" } } });
    await old;
    expect(subject.summary.value).toEqual(summary);
    wrapper.unmount();
  });
  it("没有报表权限即使接口启用也不发送请求", async () => {
    mocks.ready.purchase = true;
    hasAuth = () => false;
    const wrapper = render();
    await flushPromises();
    await subject.reload();
    expect(mocks.api.list).not.toHaveBeenCalled();
    expect(mocks.api.summary).not.toHaveBeenCalled();
    wrapper.unmount();
  });
  it("来源动作检查采购详情权限，不能用报表权限替代", async () => {
    mocks.ready.purchase = true;
    hasAuth = (permission) => permission === "module_inventory:purchase_report:query";
    const wrapper = render();
    await flushPromises();
    expect(reportSourcePermission(row)).toBe("module_inventory:purchase_in:detail");
    const actions = subject.columns!.value.at(-1)!.formatter!(row) as TableOperationAction[];
    actions[0]!.run();
    expect(subject.source.visible).toBe(false);
    wrapper.unmount();
  });
  it("服务端导出保留字段顺序和文件选项，本地金额不转浮点", async () => {
    mocks.ready.purchase = true;
    const wrapper = render();
    await flushPromises();
    await subject.exportConfig.value.exportsBlobAction(
      { view: "documents", supplier_name: "供应商", page_no: 30 },
      {
        fields: ["net_purchase_amount", "supplier_name"],
        format: "csv",
        fileName: "核对",
        sheetName: "采购",
      }
    );
    expect(mocks.api.exportDocument).toHaveBeenLastCalledWith({
      query: { view: "documents", supplier_name: "供应商" },
      fields: ["net_purchase_amount", "supplier_name"],
      format: "csv",
      filename: "核对",
      sheet_name: "采购",
    });
    expect(subject.pageRows.value[0]!.net_purchase_amount).toBe("70.00");
    wrapper.unmount();
  });
});
