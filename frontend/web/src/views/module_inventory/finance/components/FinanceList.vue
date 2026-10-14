<script setup lang="ts">
import {
  createFinanceClient,
  businessLabels,
  statusLabels,
  reversalLabels,
} from "@/api/module_inventory/finance/client";
import type {
  FinanceKind,
  FinanceQuery,
  FinanceRecord,
  FinanceSummary,
} from "@/api/module_inventory/finance/client";
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
import FinanceSourceDetail from "./FinanceSourceDetail.vue";
/** 模块内账单与余额只读列表配置。 */
const props = defineProps<{ kind: FinanceKind; balance: boolean; partyId?: number }>();
/** 点击对象余额，切换到对应账单明细。 */
const emit = defineEmits<{ selectParty: [id: number] }>();
/** 账单详情请求状态，关闭后不应用过期响应。 */
interface DetailState {
  visible: boolean;
  loading: boolean;
  failed: boolean;
  id?: number;
  record?: FinanceRecord;
}
const detail = reactive<DetailState>({ visible: false, loading: false, failed: false });
const api = createFinanceClient({ kind: props.kind, balance: props.balance });
const prefix = "module_inventory:" + props.kind;
const label = props.kind === "receivable" ? "应收账款" : "应付账款";
const partyLabel = props.kind === "receivable" ? "客户" : "供应商";
const { hasAuth } = useAuth();
const sourceVisible = ref(false);
const sourceRecord = ref<FinanceRecord>();
const searchForm = ref<FinanceQuery>({ party_id: props.partyId });
const showSearch = ref(true);
const summary = ref<FinanceSummary>();
const summaryLoading = ref(false);
const summaryFailed = ref(false);
let summaryRequest = 0;
let detailRequest = 0;
/** 当前余额只发送对象筛选，不把日期与核销状态当余额条件。 */
function balanceQuery(query: FinanceQuery): FinanceQuery {
  return {
    party_id: query.party_id,
    party_code: query.party_code,
    party_name: query.party_name,
    balance_state: query.balance_state,
  };
}
/** 请求完整筛选集的余额汇总，失败时不保留旧数字。 */
async function loadSummary(): Promise<void> {
  if (!props.balance || !hasAuth(prefix + ":query")) return;
  const sequence = ++summaryRequest;
  summaryLoading.value = true;
  summaryFailed.value = false;
  summary.value = undefined;
  try {
    const response = await api.summary(balanceQuery(searchForm.value));
    if (sequence === summaryRequest) summary.value = response.data.data;
  } catch {
    if (sequence === summaryRequest) summaryFailed.value = true;
  } finally {
    if (sequence === summaryRequest) summaryLoading.value = false;
  }
}
/** 来源单据仍以业务模块自己的详情权限和数据范围读取。 */
function sourcePermission(row: FinanceRecord): string {
  return "module_inventory:" + row.business_type + ":detail";
}
/** 只读查看原业务单据。 */
function openSource(row: FinanceRecord): void {
  if (!hasAuth(sourcePermission(row))) return;
  sourceRecord.value = row;
  sourceVisible.value = true;
}
/** 读取账单详情及冲销关联，切换或关闭时丢弃旧响应。 */
async function showDetail(row: FinanceRecord): Promise<void> {
  const sequence = ++detailRequest;
  detail.id = row.id;
  detail.visible = true;
  detail.loading = true;
  detail.failed = false;
  detail.record = undefined;
  try {
    const response = await api.detail(row.id);
    if (sequence === detailRequest && detail.visible) detail.record = response.data.data;
  } catch {
    if (sequence === detailRequest && detail.visible) detail.failed = true;
  } finally {
    if (sequence === detailRequest) detail.loading = false;
  }
}
/** 明细提供详情和来源追溯，余额仅跳转对象账单。 */
function actions(row: FinanceRecord): TableOperationAction[] {
  if (props.balance)
    return [
      {
        key: "bills",
        label: "账单",
        artType: "view",
        perm: prefix + ":query",
        run: () => emit("selectParty", row.party_id),
      },
    ];
  return [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: prefix + ":detail",
      run: () => void showDetail(row),
    },
    {
      key: "source",
      label: "来源单据",
      artType: "more",
      icon: "ri:external-link-line",
      perm: sourcePermission(row),
      run: () => openSource(row),
    },
  ];
}
/** 本地导出与服务端导出使用同一业务标签。 */
function exportValues(rows: FinanceRecord[]): IObject[] {
  return rows.map((row) => ({
    ...row,
    business_type: businessLabels[row.business_type ?? ""] ?? row.business_type,
    operation_type: row.operation_type === "void" ? "冲销" : "确认",
    status: statusLabels[row.status ?? -1] ?? "-",
    reversal_state: reversalLabels[row.reversal_state ?? ""] ?? "-",
    created_name: row.created_by?.name ?? "",
  }));
}
const items = computed<SearchFormItem[]>(() => [
  { label: partyLabel + "编码", key: "party_code", type: "input", clearable: true, span: 6 },
  { label: partyLabel + "名称", key: "party_name", type: "input", clearable: true, span: 6 },
  ...(props.balance
    ? [
        {
          label: "余额方向",
          key: "balance_state",
          type: "select" as const,
          span: 6,
          props: {
            clearable: true,
            options: [
              { value: "positive", label: "正余额" },
              { value: "negative", label: "负余额" },
              { value: "zero", label: "零余额" },
            ],
          },
        },
      ]
    : [
        { label: "来源单号", key: "business_no", type: "input" as const, clearable: true, span: 6 },
        {
          label: "业务类型",
          key: "business_type",
          type: "select" as const,
          span: 6,
          props: {
            clearable: true,
            options: Object.entries(businessLabels)
              .filter(([value]) =>
                value.startsWith(props.kind === "receivable" ? "sale" : "purchase")
              )
              .map(([value, text]) => ({ value, label: text })),
          },
        },
        {
          label: "操作类型",
          key: "operation_type",
          type: "select" as const,
          span: 6,
          props: {
            clearable: true,
            options: [
              { value: "confirm", label: "确认" },
              { value: "void", label: "冲销" },
            ],
          },
        },
        {
          label: "核销状态",
          key: "status",
          type: "select" as const,
          span: 6,
          props: {
            clearable: true,
            options: Object.entries(statusLabels).map(([value, text]) => ({
              value: Number(value),
              label: text,
            })),
          },
        },
        {
          label: "冲销状态",
          key: "reversal_state",
          type: "select" as const,
          span: 6,
          props: {
            clearable: true,
            options: Object.entries(reversalLabels).map(([value, text]) => ({
              value,
              label: text,
            })),
          },
        },
        {
          label: "账单日期",
          key: "bill_date",
          type: "date" as const,
          span: 12,
          props: { type: "daterange", valueFormat: "YYYY-MM-DD" },
        },
      ]),
]);
const businessColumns: ColumnOption<FinanceRecord>[] = [
  { prop: "party_code", label: partyLabel + "编码", minWidth: 145 },
  { prop: "party_name", label: partyLabel + "名称", minWidth: 160 },
  ...(props.balance
    ? [
        { prop: "business_net_amount", label: "业务净额", width: 150 },
        { prop: "allocated_net_amount", label: "已核销净额", width: 150 },
        { prop: "unsettled_net_amount", label: "未核销净额", width: 150 },
        { prop: "bill_count", label: "账单数", width: 100 },
      ]
    : [
        { prop: "business_no", label: "来源单号", minWidth: 200 },
        {
          prop: "business_type",
          label: "业务类型",
          width: 120,
          formatter: (row: FinanceRecord) => businessLabels[row.business_type ?? ""] ?? "-",
        },
        {
          prop: "operation_type",
          label: "操作类型",
          width: 110,
          formatter: (row: FinanceRecord) => (row.operation_type === "void" ? "冲销" : "确认"),
        },
        { prop: "amount", label: "变动金额", width: 145 },
        { prop: "allocated_amount", label: "已核销金额", width: 145 },
        { prop: "unallocated_amount", label: "未核销金额", width: 145 },
        { prop: "bill_date", label: "账单日期", width: 130 },
        {
          prop: "status",
          label: "核销状态",
          width: 120,
          formatter: (row: FinanceRecord) => statusLabels[row.status ?? -1] ?? "-",
        },
        {
          prop: "reversal_state",
          label: "冲销状态",
          width: 120,
          formatter: (row: FinanceRecord) => reversalLabels[row.reversal_state ?? ""] ?? "-",
        },
        {
          prop: "created_name",
          label: "记账人",
          width: 120,
          formatter: (row: FinanceRecord) => row.created_by?.name ?? "-",
        },
        { prop: "created_time", label: "记账时间", width: 175 },
        { prop: "remark", label: "备注", minWidth: 160 },
      ]),
];
const {
  data,
  columns,
  columnChecks,
  loading,
  pagination,
  searchParams,
  getData,
  replaceSearchParams,
  refreshData,
  handleSizeChange,
  handleCurrentChange,
  error,
} = useTable({
  core: {
    apiFn: api.list,
    immediate: false,
    apiParams: { page_no: 1, page_size: 10, party_id: props.partyId },
    columnsFactory: () => [
      { type: "selection", width: 48 },
      ...businessColumns,
      {
        prop: "operation",
        label: "操作",
        width: props.balance ? 90 : 180,
        fixed: "right",
        formatter: (row: FinanceRecord) => renderTableOperationCell(actions(row)),
      },
    ],
  },
});
const { selectedRows, onTableSelectionChange } = useTableSelection<FinanceRecord>();
const { exportVisible, openExport } = useImportExport();
const crudColumns = toCrudCols(columns);
const fields = businessColumns.map((col) => String(col.prop));
const exportConfig = computed(() => ({
  permPrefix: prefix,
  defaultExportFileName: label + (props.balance ? "余额" : "列表"),
  cols: crudColumns.value.filter((col) => col.prop && fields.includes(col.prop)),
  /** 全量导出保留当前筛选、字段顺序和文件选项。 */
  exportsBlobAction: async (query: IObject, options?: ExportBlobOptions): Promise<Blob> =>
    (
      await api.exportDocument({
        query: cleanEmptyArrayParams(stripPaginationParams(query)) as FinanceQuery,
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
  if (!detail.record) return [];
  const values = exportValues([detail.record])[0]!;
  return businessColumns.map((col) => ({
    key: String(col.prop),
    label: col.label,
    value: values[String(col.prop)] ?? "-",
  }));
});
/** 应用筛选并重置到第一页。 */
async function search(params: FinanceQuery): Promise<void> {
  searchForm.value = {
    ...(props.balance ? balanceQuery(params) : params),
    party_id: props.partyId,
  };
  replaceSearchParams(cleanEmptyArrayParams({ ...searchForm.value }));
  await Promise.all([getData().catch(() => undefined), loadSummary()]);
}
/** 清空筛选；对象跳转限制由页面入口显式保留。 */
async function reset(): Promise<void> {
  await search({});
}
/** 刷新列表与同一筛选条件的余额汇总。 */
function reload(): void {
  void refreshData().catch(() => undefined);
  void loadSummary();
}
/** 调整每页数量。 */
function changeSize(size: number): void {
  void handleSizeChange(size).catch(() => undefined);
}
/** 切换页码，余额汇总不随分页变化。 */
function changePage(page: number): void {
  void handleCurrentChange(page).catch(() => undefined);
}
onMounted(() => {
  if (hasAuth(prefix + ":query")) reload();
});
onBeforeUnmount(() => {
  summaryRequest++;
  detailRequest++;
});
</script>
<template>
  <div class="fa-full-height">
    <ElResult v-if="!hasAuth(prefix + ':query')" icon="warning" title="暂无往来查询权限" />
    <template v-else>
      <div v-if="balance" v-loading="summaryLoading" class="finance-summary">
        <ElAlert v-if="summaryFailed" title="余额汇总加载失败" type="error" :closable="false"
          ><ElButton :icon="Refresh" @click="loadSummary">重试</ElButton></ElAlert
        >
        <template v-else-if="summary">
          <div>
            业务净额<strong>{{ summary.business_net_amount }}</strong>
          </div>
          <div>
            未核销净额<strong>{{ summary.unsettled_net_amount }}</strong>
          </div>
          <div>
            {{ kind === "receivable" ? "待收余额" : "待付余额"
            }}<strong>{{ summary.positive_balance }}</strong>
          </div>
          <div>
            负向余额<strong>{{ summary.negative_balance }}</strong>
          </div>
        </template>
      </div>
      <ElTag v-if="partyId" class="mb-3">{{ partyLabel }} ID：{{ partyId }}</ElTag>
      <FaSearchBar
        v-show="showSearch"
        v-model="searchForm"
        :items="items"
        label-width="100px"
        :include-audit="!balance"
        @search="search"
        @reset="reset"
      />
      <ElCard class="fa-table-card" :style="{ marginTop: showSearch ? '12px' : '0' }">
        <FaTableHeader
          v-model:columns="columnChecks"
          v-model:showSearchBar="showSearch"
          :loading="loading"
          @refresh="reload"
        >
          <template #left
            ><ElButton
              v-if="hasAuth(prefix + ':export')"
              type="warning"
              plain
              :icon="Download"
              @click="openExport"
              >导出</ElButton
            ></template
          >
        </FaTableHeader>
        <ElResult v-if="error" icon="error" title="往来数据加载失败"
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
        width="min(960px, 96vw)"
        form-mode="detail"
        confirm-text="关闭"
        @close="detail.visible = false"
      >
        <div v-loading="detail.loading" class="finance-detail">
          <ElResult v-if="detail.failed" icon="error" title="账单详情加载失败"
            ><template #extra
              ><ElButton
                v-if="detail.id"
                :icon="Refresh"
                @click="showDetail({ id: detail.id } as FinanceRecord)"
                >重试</ElButton
              ></template
            ></ElResult
          >
          <template v-else-if="detail.record">
            <ElDescriptions :column="1" border
              ><ElDescriptionsItem
                v-for="item in detailValues"
                :key="item.key"
                :label="item.label"
                >{{ item.value }}</ElDescriptionsItem
              ></ElDescriptions
            >
            <h3 class="my-3 text-base font-medium">关联账单</h3>
            <ElTable :data="detail.record.related_bills ?? []" border>
              <ElTableColumn prop="id" label="账单 ID" width="100" />
              <ElTableColumn prop="business_no" label="来源单号" min-width="180" />
              <ElTableColumn prop="amount" label="变动金额" width="140" />
              <ElTableColumn label="冲销状态" width="120"
                ><template #default="{ row }">{{
                  reversalLabels[row.reversal_state]
                }}</template></ElTableColumn
              >
              <ElTableColumn label="操作" width="90"
                ><template #default="{ row }"
                  ><ElButton link type="primary" @click="showDetail(row as FinanceRecord)"
                    >详情</ElButton
                  ></template
                ></ElTableColumn
              >
            </ElTable>
          </template>
        </div>
      </FaDialog>
      <FinanceSourceDetail v-model="sourceVisible" :record="sourceRecord" />
    </template>
  </div>
</template>
<style scoped lang="scss">
.finance-detail {
  :deep(.el-descriptions__content) {
    overflow-wrap: anywhere;
  }
}

.finance-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  min-height: 76px;
  padding: 12px 0;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color);

  strong {
    display: block;
    margin-top: 6px;
    font-size: 20px;
    overflow-wrap: anywhere;
  }
  @media (width <= 768px) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
