<script setup lang="ts">
import BalanceAPI from "@/api/module_inventory/stock/balance";
import LogAPI from "@/api/module_inventory/stock/log";
import type { StockRecord, StockQuery } from "@/api/module_inventory/stock/client";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import type { ColumnOption } from "@/types/component";
import type { ExportBlobOptions, IObject } from "@/components/modal/types";
import {
  renderTableOperationCell,
  toCrudCols,
  cleanEmptyArrayParams,
  stripPaginationParams,
  type TableOperationAction,
} from "@utils";
import { Download, Refresh } from "@element-plus/icons-vue";
import { useStockOptions } from "../composables/useStockOptions";
import StockSourceDetail from "./StockSourceDetail.vue";
/** 当前库存与流水保持只读，入口固定查询种类。 */
const props = defineProps<{ kind: "balance" | "log" }>();
/** 库存详情加载状态。 */
interface DetailState {
  visible: boolean;
  loading: boolean;
  failed: boolean;
  id?: number;
  record?: StockRecord;
}
const detail = reactive<DetailState>({ visible: false, loading: false, failed: false });
const sourceVisible = ref(false);
const sourceRecord = ref<StockRecord>();
const api = props.kind === "balance" ? BalanceAPI : LogAPI;
const prefix = "module_inventory:stock_" + props.kind;
const label = props.kind === "balance" ? "当前库存" : "库存流水";
const { hasAuth } = useAuth();
const route = useRoute();
const router = useRouter();
const searchForm = ref<StockQuery>({});
const showSearch = ref(true);
const {
  warehouses,
  categories,
  loading: warehouseLoading,
  searchWarehouses,
  loadCategories,
} = useStockOptions();
const businessLabels: Record<string, string> = {
  opening_balance: "期初库存",
  purchase_in: "采购入库",
  purchase_return: "采购退货",
  sale_out: "销售出库",
  sale_return: "销售退货",
  stock_check_gain: "盘盈",
  stock_check_loss: "盘亏",
};
const warningLabels: Record<string, string> = { normal: "正常", low: "低于下限", high: "高于上限" };
/** 来源读取仍使用该业务模块的独立详情权限与数据范围。 */
function sourcePermission(row: StockRecord): string {
  const names: Record<string, string> = {
    opening_balance: "stock_opening",
    stock_check_gain: "stock_check",
    stock_check_loss: "stock_check",
  };
  return "module_inventory:" + (names[row.business_type ?? ""] ?? row.business_type) + ":detail";
}
/** 打开原业务单据只读弹窗。 */
function openSource(row: StockRecord): void {
  if (hasAuth(sourcePermission(row))) {
    sourceRecord.value = row;
    sourceVisible.value = true;
  }
}
/** 从仓库商品余额跳转到对应流水，刷新后查询参数仍可恢复。 */
function viewLogs(row: StockRecord): void {
  void router.push({
    path: "/inventory/stock/log",
    query: { warehouse_id: row.warehouse_id, goods_id: row.goods_id },
  });
}
/** 当前页和全量导出保持一致的业务标签。 */
function exportValues(rows: StockRecord[]): IObject[] {
  return rows.map((row) => ({
    ...row,
    business_type: businessLabels[row.business_type ?? ""] ?? row.business_type,
    operation_type: row.operation_type === "void" ? "冲销" : "确认",
    warning: warningLabels[row.warning ?? ""] ?? row.warning,
    created_name: row.created_by?.name ?? "",
  }));
}
const items = computed<SearchFormItem[]>(() => [
  { label: "商品编码", key: "goods_code", type: "input", clearable: true, span: 6 },
  { label: "商品名称", key: "goods_name", type: "input", clearable: true, span: 6 },
  {
    label: "分类",
    key: "category_id",
    type: "select",
    span: 6,
    props: { options: categories.value, filterable: true, clearable: true },
  },
  {
    label: "仓库",
    key: "warehouse_id",
    type: "select",
    span: 6,
    props: {
      options: warehouses.value,
      remote: true,
      filterable: true,
      remoteMethod: searchWarehouses,
      loading: warehouseLoading.value,
      clearable: true,
    },
  },
  ...(props.kind === "balance"
    ? [
        {
          label: "库存数量",
          key: "quantity_state",
          type: "select" as const,
          span: 6,
          props: {
            options: [
              { value: "positive", label: "有库存" },
              { value: "zero", label: "零库存" },
            ],
            clearable: true,
          },
        },
        {
          label: "库存预警",
          key: "warning",
          type: "select" as const,
          span: 6,
          props: {
            options: [
              { value: "low", label: "低于下限" },
              { value: "high", label: "高于上限" },
            ],
            clearable: true,
          },
        },
      ]
    : [
        {
          label: "业务类型",
          key: "business_type",
          type: "select" as const,
          span: 6,
          props: {
            options: Object.entries(businessLabels).map(([value, text]) => ({
              value,
              label: text,
            })),
            clearable: true,
          },
        },
        {
          label: "操作类型",
          key: "operation_type",
          type: "select" as const,
          span: 6,
          props: {
            options: [
              { value: "confirm", label: "确认" },
              { value: "void", label: "冲销" },
            ],
            clearable: true,
          },
        },
        { label: "来源单号", key: "business_no", type: "input" as const, clearable: true, span: 6 },
        {
          label: "业务日期",
          key: "business_date",
          type: "date" as const,
          span: 6,
          props: { type: "daterange", valueFormat: "YYYY-MM-DD" },
        },
        {
          label: "入账时间",
          key: "posted_time",
          type: "date" as const,
          span: 12,
          props: { type: "datetimerange", valueFormat: "YYYY-MM-DD HH:mm:ss" },
        },
      ]),
]);
/** 仅按详情权限请求具体库存记录，关闭或切换详情时丢弃过期响应。 */
async function showDetail(row: StockRecord): Promise<void> {
  detail.id = row.id;
  detail.record = undefined;
  detail.visible = true;
  detail.loading = true;
  detail.failed = false;
  try {
    const response = await api.detail(row.id);
    if (detail.visible && detail.id === row.id) detail.record = response.data.data;
  } catch {
    if (detail.id === row.id) detail.failed = true;
  } finally {
    if (detail.id === row.id) detail.loading = false;
  }
}
/** 只读查询不提供余额修改或流水删除操作。 */
function actions(row: StockRecord): TableOperationAction[] {
  const result: TableOperationAction[] = [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: prefix + ":detail",
      run: () => void showDetail(row),
    },
  ];
  if (props.kind === "balance")
    result.push({
      key: "logs",
      label: "流水",
      artType: "more",
      icon: "ri:file-list-3-line",
      perm: "module_inventory:stock_log:query",
      run: () => viewLogs(row),
    });
  else
    result.push({
      key: "source",
      label: "来源单据",
      artType: "more",
      icon: "ri:external-link-line",
      perm: sourcePermission(row),
      run: () => openSource(row),
    });
  return result;
}
const businessColumns: ColumnOption<StockRecord>[] = [
  { prop: "goods_code", label: "商品编码", minWidth: 140 },
  { prop: "goods_name", label: "商品名称", minWidth: 180 },
  { prop: "warehouse_name", label: "仓库", minWidth: 140 },
  ...(props.kind === "balance"
    ? [
        { prop: "spec", label: "规格", minWidth: 110 },
        { prop: "unit", label: "单位", width: 80 },
        { prop: "quantity", label: "库存数量", width: 140 },
        { prop: "avg_cost", label: "平均成本", width: 140 },
        { prop: "stock_amount", label: "库存金额", width: 150 },
        {
          prop: "warning",
          label: "预警",
          width: 110,
          formatter: (row: StockRecord) => warningLabels[row.warning ?? ""] ?? "-",
        },
        { prop: "last_business_time", label: "最近变动时间", width: 175 },
      ]
    : [
        { prop: "business_no", label: "来源单号", minWidth: 200, showOverflowTooltip: true },
        {
          prop: "business_type",
          label: "业务类型",
          width: 120,
          formatter: (row: StockRecord) => businessLabels[row.business_type ?? ""] ?? "-",
        },
        {
          prop: "operation_type",
          label: "操作类型",
          width: 100,
          formatter: (row: StockRecord) => (row.operation_type === "void" ? "冲销" : "确认"),
        },
        { prop: "business_date", label: "业务日期", width: 120 },
        { prop: "before_quantity", label: "变动前数量", width: 140 },
        { prop: "change_quantity", label: "变动数量", width: 140 },
        { prop: "after_quantity", label: "变动后数量", width: 140 },
        { prop: "unit_cost", label: "单位成本", width: 140 },
        { prop: "cost_amount", label: "成本金额", width: 140 },
        { prop: "posted_time", label: "入账时间", width: 175 },
        {
          prop: "created_name",
          label: "操作人",
          width: 110,
          formatter: (row: StockRecord) => row.created_by?.name ?? "",
        },
        { prop: "remark", label: "备注", minWidth: 150, showOverflowTooltip: true },
      ]),
];
const {
  data,
  columns,
  columnChecks,
  loading,
  pagination,
  searchParams,
  replaceSearchParams,
  getData,
  resetSearchParams,
  refreshData,
  handleSizeChange,
  handleCurrentChange,
  error,
} = useTable({
  core: {
    apiFn: api.list,
    immediate: false,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "selection", width: 48 },
      ...businessColumns,
      {
        prop: "operation",
        label: "操作",
        width: 180,
        fixed: "right",
        formatter: (row) => renderTableOperationCell(actions(row)),
      },
    ],
  },
});
const { selectedRows, onTableSelectionChange } = useTableSelection<StockRecord>();
const { exportVisible, openExport } = useImportExport();
const crudColumns = toCrudCols(columns);
const fields = businessColumns.map((col) => String(col.prop)).filter(Boolean);
const exportConfig = computed(() => ({
  permPrefix: prefix,
  defaultExportFileName: label + "列表",
  cols: crudColumns.value.filter((col) => col.prop && fields.includes(col.prop)),
  /** 全量导出保留当前业务筛选和字段顺序。 */
  exportsBlobAction: async (query: IObject, options?: ExportBlobOptions): Promise<Blob> =>
    (
      await api.exportDocument({
        query: cleanEmptyArrayParams(stripPaginationParams(query)) as StockQuery,
        fields: options?.fields ?? fields,
        format: options?.format ?? "xlsx",
        sheet_name: options?.sheetName || label,
        filename: options?.fileName,
      })
    ).data,
}));
const pageRows = computed(() => exportValues(data.value));
const selectionRows = computed(() => exportValues(selectedRows.value));
const detailValues = computed(() => {
  const row = detail.record;
  if (!row) return [];
  const value = exportValues([row])[0]!;
  return businessColumns.map((col) => ({
    key: String(col.prop),
    label: col.label,
    value: value[String(col.prop)] ?? "-",
  }));
});
/** 应用查询筛选并处理失败状态。 */
async function search(params: StockQuery): Promise<void> {
  searchForm.value = { ...params };
  replaceSearchParams(cleanEmptyArrayParams({ ...params }));
  await getData().catch(() => undefined);
}
/** 清除来源跳转的商品限制并恢复第一页。 */
async function reset(): Promise<void> {
  searchForm.value = {};
  await resetSearchParams().catch(() => undefined);
}
/** 刷新列表，失败状态可由用户重试。 */
function reload(): void {
  void refreshData().catch(() => undefined);
}
/** 调整分页数量。 */
function changeSize(size: number): void {
  void handleSizeChange(size).catch(() => undefined);
}
/** 切换列表页码。 */
function changePage(page: number): void {
  void handleCurrentChange(page).catch(() => undefined);
}
/** 从 URL 恢复仓库和商品条件，不在离开页面时覆盖缓存查询。 */
function restoreRoute(): void {
  if (props.kind !== "log" || route.path !== "/inventory/stock/log") return;
  const goods = Number(route.query.goods_id);
  const warehouse = Number(route.query.warehouse_id);
  if (
    Number.isSafeInteger(goods) &&
    goods > 0 &&
    Number.isSafeInteger(warehouse) &&
    warehouse > 0
  ) {
    searchForm.value = { goods_id: goods, warehouse_id: warehouse };
    replaceSearchParams({ ...searchForm.value });
  }
}
watch(
  () => [route.query.goods_id, route.query.warehouse_id],
  () => {
    if (props.kind === "log" && route.path === "/inventory/stock/log") {
      restoreRoute();
      reload();
    }
  }
);
onMounted(() => {
  if (!hasAuth(prefix + ":query")) return;
  restoreRoute();
  reload();
  if (hasAuth("module_inventory:warehouse:query")) void searchWarehouses();
  if (hasAuth("module_inventory:category:query")) void loadCategories();
});
</script>
<template>
  <div class="fa-full-height">
    <ElResult v-if="!hasAuth(prefix + ':query')" icon="warning" title="暂无库存查询权限" />
    <template v-else>
      <FaSearchBar
        v-show="showSearch"
        v-model="searchForm"
        :items="items"
        include-audit
        @search="search"
        @reset="reset"
      />
      <ElCard class="fa-table-card" :style="{ marginTop: showSearch ? '12px' : '0' }">
        <FaTableHeader
          v-model:columns="columnChecks"
          v-model:showSearchBar="showSearch"
          :loading="loading"
          @refresh="reload"
          ><template #left
            ><ElButton
              v-if="hasAuth(prefix + ':export')"
              type="warning"
              plain
              :icon="Download"
              @click="openExport"
              >导出</ElButton
            ></template
          ></FaTableHeader
        >
        <ElResult v-if="error" icon="error" title="库存数据加载失败"
          ><template #extra
            ><ElButton :icon="Refresh" @click="reload">重试</ElButton></template
          ></ElResult
        >
        <FaTable
          v-else
          :data="data"
          :columns="columns"
          :loading="loading"
          :pagination="pagination"
          @selection-change="onTableSelectionChange"
          @pagination:size-change="changeSize"
          @pagination:current-change="changePage"
        />
      </ElCard>
      <FaExportDialog
        v-model="exportVisible"
        :content-config="exportConfig"
        :query-params="stripPaginationParams(searchParams)"
        :page-data="pageRows"
        :selection-data="selectionRows"
      />
      <FaDialog
        v-model="detail.visible"
        :title="label + '详情'"
        width="min(900px, 96vw)"
        form-mode="detail"
        @close="detail.visible = false"
      >
        <div v-loading="detail.loading">
          <ElResult v-if="detail.failed" icon="error" title="详情加载失败"
            ><template #extra
              ><ElButton
                v-if="detail.id"
                :icon="Refresh"
                @click="showDetail({ id: detail.id } as StockRecord)"
                >重试</ElButton
              ></template
            ></ElResult
          >
          <ElDescriptions v-else-if="detail.record" :column="2" border
            ><ElDescriptionsItem v-for="item in detailValues" :key="item.key" :label="item.label">{{
              item.value
            }}</ElDescriptionsItem
            ><ElDescriptionsItem v-if="kind === 'log'" label="被冲销流水">{{
              detail.record.reversal_log_id ?? "-"
            }}</ElDescriptionsItem></ElDescriptions
          >
        </div>
      </FaDialog>
      <StockSourceDetail v-model="sourceVisible" :record="sourceRecord" />
    </template>
  </div>
</template>
