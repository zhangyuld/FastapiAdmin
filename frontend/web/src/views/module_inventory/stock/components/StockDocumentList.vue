<script setup lang="ts">
import OpeningAPI from "@/api/module_inventory/stock/opening";
import CheckAPI from "@/api/module_inventory/stock/check";
import type { StockDocument, StockQuery } from "@/api/module_inventory/stock/client";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import type { DialogType } from "@/hooks/core/useCrudDialog";
import type { ExportBlobOptions, IObject } from "@/components/modal/types";
import {
  renderTableOperationCell,
  resolveStatusColumns,
  toCrudCols,
  stripPaginationParams,
  cleanEmptyArrayParams,
  type TableOperationAction,
} from "@utils";
import { Plus, Delete, Download, Refresh } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useStockOptions } from "../composables/useStockOptions";
import StockDocumentDialog from "./StockDocumentDialog.vue";
/** 路由入口固定单据种类，避免期初与盘点互相污染状态。 */
const props = defineProps<{ kind: "opening" | "check" }>();
/** 列表单据弹窗状态。 */
interface DialogState {
  visible: boolean;
  mode: DialogType;
  id?: number;
}
const dialog = reactive<DialogState>({ visible: false, mode: "create" });
const searchForm = ref<StockQuery>({});
const showSearch = ref(true);
const busy = ref(false);
const tableRef = ref<{ elTableRef?: { clearSelection: () => void } }>();
const api = props.kind === "opening" ? OpeningAPI : CheckAPI;
const label = props.kind === "opening" ? "期初库存" : "库存盘点";
const prefix = "module_inventory:stock_" + props.kind;
const { hasAuth } = useAuth();
const { warehouseSelectProps, searchWarehouses } = useStockOptions();
const items = computed<SearchFormItem[]>(() => [
  { label: "单据编号", key: "doc_no", type: "input", clearable: true, span: 6 },
  {
    label: "仓库",
    key: "warehouse_id",
    type: "select",
    span: 6,
    props: warehouseSelectProps.value,
  },
  {
    label: "状态",
    key: "status",
    type: "select",
    span: 6,
    props: {
      clearable: true,
      options: [
        { label: "草稿", value: 0 },
        { label: "已确认", value: 1 },
        { label: "已作废", value: 2 },
      ],
    },
  },
  {
    label: "业务日期",
    key: "business_date",
    type: "date",
    span: 6,
    props: { type: "daterange", valueFormat: "YYYY-MM-DD" },
  },
]);
/** 按权限和单据状态打开表单或只读详情。 */
function open(mode: DialogType, row?: StockDocument): void {
  if (
    !hasAuth(prefix + (mode === "detail" ? ":detail" : mode === "create" ? ":create" : ":update"))
  )
    return;
  Object.assign(dialog, { visible: true, mode, id: row?.id });
}
/** 删除草稿前逐单提交版本映射。 */
async function remove(rows: StockDocument[]): Promise<void> {
  if (busy.value || !rows.length) return;
  if (rows.some((row) => row.status !== 0)) {
    ElMessage.warning("只能删除草稿");
    return;
  }
  busy.value = true;
  try {
    await ElMessageBox.confirm("确定删除选中的草稿？", "删除草稿", { type: "warning" });
    await api.remove({
      ids: rows.map((row) => row.id),
      versions: Object.fromEntries(rows.map((row) => [row.id, row.version])),
    });
    tableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    /* 取消操作或接口错误不提示成功。 */
  } finally {
    busy.value = false;
  }
}
/** 确认会影响库存，重复操作交由服务端版本保护。 */
async function confirmRow(row: StockDocument): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  try {
    await ElMessageBox.confirm("确认单据 " + row.doc_no + "？确认后将影响库存。", "确认单据", {
      type: "warning",
    });
    await api.confirm(row.id, { version: row.version });
    await refreshData();
  } catch {
    /* 快照冲突由请求层提示，打开编辑后显式刷新。 */
  } finally {
    busy.value = false;
  }
}
/** 已确认单据按原因生成原流水冲销。 */
async function voidRow(row: StockDocument): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  try {
    const result = await ElMessageBox.prompt("请输入作废原因", "作废单据", {
      inputType: "textarea",
      inputValidator: (value) =>
        (!!value?.trim() && value.trim().length <= 500) || "请输入1至500字符的原因",
      type: "warning",
    });
    await api.voidDocument(row.id, { version: row.version, void_reason: result.value.trim() });
    await refreshData();
  } catch {
    /* 库存不足或后续业务拦截不会显示成功。 */
  } finally {
    busy.value = false;
  }
}
/** 只展示状态允许且用户有权执行的操作。 */
function actions(row: StockDocument): TableOperationAction[] {
  const result: TableOperationAction[] = [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: prefix + ":detail",
      run: () => open("detail", row),
    },
  ];
  if (row.status === 0)
    result.push(
      {
        key: "update",
        label: "编辑",
        artType: "edit",
        perm: prefix + ":update",
        run: () => open("update", row),
      },
      {
        key: "delete",
        label: "删除",
        artType: "delete",
        perm: prefix + ":delete",
        run: () => void remove([row]),
      },
      {
        key: "confirm",
        label: "确认",
        artType: "more",
        icon: "ri:check-line",
        perm: prefix + ":confirm",
        run: () => void confirmRow(row),
      }
    );
  if (row.status === 1)
    result.push({
      key: "void",
      label: "作废",
      artType: "more",
      icon: "ri:close-circle-line",
      perm: prefix + ":void",
      run: () => void voidRow(row),
    });
  return result;
}
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
  refreshRemove,
  refreshCreate,
  refreshUpdate,
  handleSizeChange,
  handleCurrentChange,
  error,
} = useTable({
  core: {
    apiFn: api.list,
    immediate: false,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: resolveStatusColumns<StockDocument>(() => [
      { type: "selection", width: 48 },
      { prop: "doc_no", label: "单据编号", minWidth: 200, showOverflowTooltip: true },
      { prop: "warehouse_name", label: "仓库", minWidth: 150 },
      { prop: "business_date", label: "业务日期", width: 120 },
      {
        prop: "status",
        label: "状态",
        width: 100,
        status: {
          0: { type: "info", text: "草稿" },
          1: { type: "success", text: "已确认" },
          2: { type: "danger", text: "已作废" },
        },
      },
      {
        prop: "created_name",
        label: "创建人",
        width: 110,
        formatter: (row) => row.created_by?.name ?? "-",
      },
      { prop: "confirmed_time", label: "确认时间", width: 170 },
      { prop: "voided_time", label: "作废时间", width: 170 },
      { prop: "remark", label: "备注", minWidth: 150, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 210,
        fixed: "right",
        formatter: (row) => renderTableOperationCell(actions(row)),
      },
    ]),
  },
});
const { selectedRows, selectedIds, onTableSelectionChange } = useTableSelection<StockDocument>();
const { exportVisible, openExport } = useImportExport();
const crudColumns = toCrudCols(columns);
const fields = [
  "doc_no",
  "warehouse_name",
  "business_date",
  "status",
  "created_name",
  "confirmed_time",
  "voided_time",
  "remark",
];
/** 导出使用可读状态和创建人，保留服务器实际值。 */
function exportValues(rows: StockDocument[]): IObject[] {
  return rows.map((row) => ({
    ...row,
    status: ["草稿", "已确认", "已作废"][row.status],
    created_name: row.created_by?.name ?? "",
  }));
}
const pageRows = computed(() => exportValues(data.value));
const selectionRows = computed(() => exportValues(selectedRows.value));
const exportConfig = computed(() => ({
  permPrefix: prefix,
  defaultExportFileName: label + "列表",
  cols: crudColumns.value.filter((col) => col.prop && fields.includes(col.prop)),
  /** 全量导出提交当前筛选与用户选择字段。 */
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
/** 查询失败保留错误状态供重试。 */
async function search(params: StockQuery): Promise<void> {
  searchForm.value = { ...params };
  replaceSearchParams(cleanEmptyArrayParams({ ...params }));
  await getData().catch(() => undefined);
}
/** 重置筛选并恢复第一页。 */
async function reset(): Promise<void> {
  searchForm.value = {};
  await resetSearchParams().catch(() => undefined);
}
/** 保存后刷新对应分页位置。 */
async function saved(): Promise<void> {
  await (dialog.mode === "create" ? refreshCreate() : refreshUpdate()).catch(() => undefined);
}
/** 主动刷新并保留表格异常状态。 */
function reload(): void {
  void refreshData().catch(() => undefined);
}
/** 切换分页数量。 */
function changeSize(size: number): void {
  void handleSizeChange(size).catch(() => undefined);
}
/** 切换当前页码。 */
function changePage(page: number): void {
  void handleCurrentChange(page).catch(() => undefined);
}
onMounted(() => {
  if (hasAuth(prefix + ":query")) {
    reload();
    void searchWarehouses();
  }
});
</script>
<template>
  <div class="fa-full-height">
    <ElResult v-if="!hasAuth(prefix + ':query')" icon="warning" title="暂无查询权限" />
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
            ><ElSpace>
              <ElButton
                v-if="hasAuth(prefix + ':create')"
                type="primary"
                plain
                :icon="Plus"
                @click="open('create')"
                >新增</ElButton
              >
              <ElButton
                v-if="hasAuth(prefix + ':export')"
                type="warning"
                plain
                :icon="Download"
                @click="openExport"
                >导出</ElButton
              >
              <ElButton
                v-if="hasAuth(prefix + ':delete')"
                type="danger"
                plain
                :icon="Delete"
                :loading="busy"
                :disabled="!selectedIds.length"
                @click="remove(selectedRows)"
                >批量删除</ElButton
              >
            </ElSpace></template
          ></FaTableHeader
        >
        <ElResult v-if="error" icon="error" title="库存单据加载失败"
          ><template #extra
            ><ElButton :icon="Refresh" @click="reload">重试</ElButton></template
          ></ElResult
        >
        <FaTable
          v-else
          ref="tableRef"
          :data="data"
          :columns="columns"
          :loading="loading || busy"
          :pagination="pagination"
          @selection-change="onTableSelectionChange"
          @pagination:size-change="changeSize"
          @pagination:current-change="changePage"
        />
      </ElCard>
      <StockDocumentDialog
        v-model="dialog.visible"
        :kind="kind"
        :mode="dialog.mode"
        :document-id="dialog.id"
        @success="saved"
      />
      <FaExportDialog
        v-model="exportVisible"
        :content-config="exportConfig"
        :query-params="stripPaginationParams(searchParams)"
        :page-data="pageRows"
        :selection-data="selectionRows"
      />
    </template>
  </div>
</template>
