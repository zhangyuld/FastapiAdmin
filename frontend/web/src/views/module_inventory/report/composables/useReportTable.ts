import type {
  ReportKind,
  ReportView,
  ReportQuery,
  ReportRow,
  ReportSummary,
} from "@/api/module_inventory/report/client";
import { createReportClient, reportApiReady } from "@/api/module_inventory/report/client";
import type { ColumnOption } from "@/types/component";
import type { ExportBlobOptions, IObject } from "@/components/modal/types";
import { toCrudCols, renderTableOperationCell } from "@utils";
import { reportFields, reportLabels, fieldValue, exportFieldValue } from "../utils/config";
import { normalizeReportQuery, reportRouteQuery, reportFilterQuery } from "../utils/query";
/** 来源详情权限不由报表查询权限替代。 */
export function reportSourcePermission(row: ReportRow): string | undefined {
  if (!row.source || !Number.isSafeInteger(row.source.business_id) || row.source.business_id <= 0)
    return undefined;
  const sourceType = row.source.business_type;
  const domain =
    sourceType === "opening_balance"
      ? "stock_opening"
      : sourceType.startsWith("stock_check_")
        ? "stock_check"
        : sourceType;
  return "module_inventory:" + domain + ":detail";
}
/** 报表查询组合配置，固定领域与维度避免缓存串用。 */
interface ReportTableOptions {
  kind: ReportKind;
  view: ReportView;
}
/** 页面局部来源状态，不提供任何单据修改入口。 */
interface SourceState {
  visible: boolean;
  row?: ReportRow;
}
/** 复用框架表格，同时独立管理全部筛选结果的汇总与请求失效。 */
export function useReportTable(options: ReportTableOptions) {
  const { kind, view } = options;
  const route = useRoute();
  const router = useRouter();
  const { hasAuth } = useAuth();
  const prefix = "module_inventory:" + kind + "_report";
  const ready = computed(() => reportApiReady[kind]);
  const authorized = computed(() => hasAuth(prefix + ":query"));
  const api = createReportClient(kind);
  const routePath = "/inventory/report/" + kind;
  const initial = normalizeReportQuery(kind, view, route.path === routePath ? route.query : {});
  const form = ref<ReportQuery>({ ...initial });
  const applied = ref<ReportQuery>({ ...initial });
  const summary = ref<ReportSummary>();
  const summaryLoading = ref(false);
  const summaryFailed = ref(false);
  const source = reactive<SourceState>({ visible: false });
  let active = true;
  let summarySequence = 0;
  const fields = reportFields(kind, view);
  const businessColumns: ColumnOption<ReportRow>[] = fields.map((field) => ({
    prop: field.key,
    label: field.label,
    minWidth: field.width ?? 150,
    showOverflowTooltip: true,
    formatter: (row) => fieldValue(row, field),
  }));
  /** 原单保持独立详情权限，商品汇总及库存汇总没有来源按钮。 */
  function openSource(row: ReportRow): void {
    const permission = reportSourcePermission(row);
    if (permission && hasAuth(permission)) {
      source.row = row;
      source.visible = true;
    }
  }
  /** 即使表格内部误触发请求，未接入或无权限时也不发送 HTTP。 */
  async function list(query: ReportQuery): ReturnType<typeof api.list> {
    if (!ready.value || !authorized.value || !active)
      throw new Error("报表接口尚未接入或无查询权限");
    return api.list(normalizeReportQuery(kind, view, query));
  }
  const table = useTable({
    core: {
      apiFn: list,
      immediate: false,
      apiParams: initial,
      paginationKey: { current: "page_no", size: "page_size" },
      columnsFactory: () => [
        { type: "selection", width: 48 },
        ...businessColumns,
        ...(view === "documents"
          ? [
              {
                prop: "operation",
                label: "来源单据",
                width: 110,
                fixed: "right" as const,
                formatter: (row: ReportRow) => {
                  const permission = reportSourcePermission(row);
                  return permission
                    ? renderTableOperationCell([
                        {
                          key: "source",
                          label: "来源单据",
                          artType: "view",
                          perm: permission,
                          run: () => openSource(row),
                        },
                      ])
                    : "-";
                },
              },
            ]
          : []),
      ],
    },
  });
  const { selectedRows, onTableSelectionChange, clearSelection } = useTableSelection<ReportRow>();
  const { exportVisible, openExport } = useImportExport();
  const crudColumns = toCrudCols(table.columns);
  const exportConfig = computed(() => ({
    permPrefix: prefix,
    defaultExportFileName:
      reportLabels[kind] + (view === "goods" ? "商品汇总" : view === "movement" ? "期间变动" : ""),
    cols: crudColumns.value.filter(
      (col) => col.prop && fields.some((field) => field.key === col.prop)
    ),
    /** 文件流仅在接口接入及授权后调用，字段顺序与页面一致。 */
    exportsBlobAction: async (query: IObject, exportOptions?: ExportBlobOptions): Promise<Blob> => {
      if (!ready.value || !hasAuth(prefix + ":export") || !active)
        throw new Error("报表导出暂不可用");
      return (
        await api.exportDocument({
          query: reportFilterQuery(normalizeReportQuery(kind, view, query)),
          fields: exportOptions?.fields ?? fields.map((field) => field.key),
          format: exportOptions?.format ?? "xlsx",
          sheet_name: exportOptions?.sheetName || reportLabels[kind],
          filename: exportOptions?.fileName,
        })
      ).data;
    },
  }));
  /** 将标签及百分数字符串用于本地导出，保留金额精度。 */
  function exportRows(rows: ReportRow[]): IObject[] {
    return rows.map((row) =>
      Object.fromEntries(fields.map((field) => [field.key, exportFieldValue(row, field)]))
    );
  }
  const pageRows = computed(() => exportRows(table.data.value));
  const selectionRows = computed(() => exportRows(selectedRows.value));
  const exportDisabled = computed(
    () =>
      !ready.value || table.loading.value || !!table.error.value || table.data.value.length === 0
  );
  /** 汇总始终基于已提交筛选，分页和未提交输入不会改变指标。 */
  async function loadSummary(): Promise<void> {
    const sequence = ++summarySequence;
    summary.value = undefined;
    summaryFailed.value = false;
    summaryLoading.value = false;
    if (!ready.value || !authorized.value || !active) return;
    summaryLoading.value = true;
    try {
      const response = await api.summary(reportFilterQuery(applied.value));
      if (sequence === summarySequence && active) summary.value = response.data.data;
    } catch {
      if (sequence === summarySequence && active) summaryFailed.value = true;
    } finally {
      if (sequence === summarySequence && active) summaryLoading.value = false;
    }
  }
  /** 同步白名单参数，不允许旧视图的筛选遗留到新报表。 */
  function applyQuery(query: ReportQuery): void {
    applied.value = { ...query, page_no: 1, page_size: table.pagination.size };
    form.value = {
      ...query,
      business_date: query.business_date ? [...query.business_date] : undefined,
    };
    table.replaceSearchParams(applied.value);
    clearSelection();
    table.clearData();
  }
  /** URL 只写当前业务页面，缓存页失活时不覆盖其他页面查询。 */
  async function persistQuery(): Promise<void> {
    if (active && route.path === routePath)
      await router.replace({
        path: routePath,
        query: reportRouteQuery(reportFilterQuery(applied.value)),
      });
  }
  /** 刷新当前页和完整筛选集汇总，待接入状态不会发请求。 */
  async function reload(): Promise<void> {
    if (!ready.value || !authorized.value || !active) return;
    clearSelection();
    await Promise.all([table.refreshData(), loadSummary()]);
  }
  /** 提交查询后回到第一页，并保存筛选以支持刷新恢复。 */
  async function search(params: ReportQuery): Promise<void> {
    applyQuery(
      normalizeReportQuery(kind, view, { ...params, page_no: 1, page_size: table.pagination.size })
    );
    await persistQuery();
    await reload();
  }
  /** 恢复当前视图的空筛选。 */
  async function reset(): Promise<void> {
    await search({ view });
  }
  /** 切换分页不重复请求汇总，避免把分页合计误当报表总计。 */
  async function changePage(page: number): Promise<void> {
    if (!ready.value || !authorized.value) return;
    applied.value = { ...applied.value, page_no: page };
    clearSelection();
    await persistQuery();
    await table.handleCurrentChange(page);
  }
  /** 更改分页容量，保留当前已提交筛选。 */
  async function changeSize(size: number): Promise<void> {
    if (!ready.value || !authorized.value) return;
    applied.value = { ...applied.value, page_no: 1, page_size: size };
    clearSelection();
    await persistQuery();
    await table.handleSizeChange(size);
  }
  /** 接口接入且有查询结果时才打开导出弹窗。 */
  function showExport(): void {
    if (!exportDisabled.value && hasAuth(prefix + ":export")) openExport();
  }
  watch(
    () => route.fullPath,
    () => {
      if (
        !active ||
        route.path !== routePath ||
        normalizeReportQuery(kind, view, route.query).view !== view ||
        (route.query.view && route.query.view !== view)
      )
        return;
      const next = normalizeReportQuery(kind, view, route.query);
      if (
        JSON.stringify(reportFilterQuery(next)) !== JSON.stringify(reportFilterQuery(applied.value))
      ) {
        applyQuery(next);
        void reload();
      }
    }
  );
  onMounted(() => {
    void reload();
  });
  onActivated(() => {
    active = true;
  });
  onDeactivated(() => {
    active = false;
    summarySequence++;
    summaryLoading.value = false;
    source.visible = false;
    exportVisible.value = false;
  });
  onBeforeUnmount(() => {
    active = false;
    summarySequence++;
  });
  return {
    ...table,
    kind,
    view,
    prefix,
    ready,
    authorized,
    form,
    fields,
    summary,
    summaryLoading,
    summaryFailed,
    source,
    selectedRows,
    onTableSelectionChange,
    exportConfig,
    exportVisible,
    exportDisabled,
    pageRows,
    selectionRows,
    loadSummary,
    search,
    reset,
    reload,
    changePage,
    changeSize,
    showExport,
  };
}
