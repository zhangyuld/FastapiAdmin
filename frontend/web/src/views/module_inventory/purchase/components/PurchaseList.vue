<script setup lang="ts">
import PurchaseInAPI from "@/api/module_inventory/purchase/in";
import PurchaseReturnAPI from "@/api/module_inventory/purchase/return";
import type {
  PurchaseDocument,
  PurchaseKind,
  PurchaseQuery,
} from "@/api/module_inventory/purchase/types";
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
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Download, Delete } from "@element-plus/icons-vue";
import { usePurchaseOptions } from "../composables/usePurchaseOptions";
import { displayAmount } from "../utils/amount";
import PurchaseDialog from "./PurchaseDialog.vue";
defineOptions({ name: "PurchaseDocumentList" });
/** 列表种类由独立路由入口指定。 */
const props = defineProps<{ kind: PurchaseKind }>();
/** 列表查询状态。 */
type SearchState = PurchaseQuery;
/** 当前单据弹窗状态。 */
interface DialogState {
  visible: boolean;
  mode: DialogType;
  id?: number;
}
const api = props.kind === "in" ? PurchaseInAPI : PurchaseReturnAPI;
const label = props.kind === "in" ? "采购入库" : "采购退货";
const prefix =
  props.kind === "in" ? "module_inventory:purchase_in" : "module_inventory:purchase_return";
const { hasAuth } = useAuth();
const searchForm = ref<SearchState>({});
const showSearch = ref(true);
const dialog = reactive<DialogState>({ visible: false, mode: "create" });
const busy = ref(false);
const tableRef = ref<{ elTableRef?: { clearSelection: () => void } }>();
const {
  suppliers,
  warehouses,
  supplierLoading,
  warehouseLoading,
  searchSuppliers,
  searchWarehouses,
} = usePurchaseOptions();
const items = computed<SearchFormItem[]>(() => [
  { label: "单据编号", key: "order_no", type: "input", clearable: true, span: 6 },
  {
    label: "供应商",
    key: "supplier_id",
    type: "select",
    props: {
      options: suppliers.value,
      filterable: true,
      remote: true,
      remoteMethod: searchSuppliers,
      loading: supplierLoading.value,
      clearable: true,
    },
    span: 6,
  },
  {
    label: "仓库",
    key: "warehouse_id",
    type: "select",
    props: {
      options: warehouses.value,
      filterable: true,
      remote: true,
      remoteMethod: searchWarehouses,
      loading: warehouseLoading.value,
      clearable: true,
    },
    span: 6,
  },
  {
    label: "状态",
    key: "status",
    type: "select",
    props: {
      options: [
        { label: "草稿", value: 0 },
        { label: "已确认", value: 1 },
        { label: "已作废", value: 2 },
      ],
      clearable: true,
    },
    span: 6,
  },
  {
    label: "业务日期",
    key: "business_date",
    type: "date",
    props: { type: "daterange", valueFormat: "YYYY-MM-DD" },
    span: 6,
  },
  ...(props.kind === "return"
    ? [
        {
          label: "原入库单号",
          key: "source_order_no",
          type: "input" as const,
          clearable: true,
          span: 6,
        },
      ]
    : []),
]);
/** 打开单据编辑或详情。 */
function open(mode: DialogType, row?: PurchaseDocument): void {
  dialog.mode = mode;
  dialog.id = row?.id;
  dialog.visible = true;
}
/** 按状态构建操作；后端仍须执行状态和版本校验。 */
function actions(row: PurchaseDocument): TableOperationAction[] {
  const result: TableOperationAction[] = [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: prefix + ":detail",
      run: () => open("detail", row),
    },
  ];
  if (row.status === 0) {
    result.push({
      key: "update",
      label: "编辑",
      artType: "edit",
      perm: prefix + ":update",
      run: () => open("update", row),
    });
    result.push({
      key: "delete",
      label: "删除",
      artType: "delete",
      perm: prefix + ":delete",
      run: () => void deleteRows([row]),
    });
    result.push({
      key: "confirm",
      label: "确认",
      artType: "more",
      icon: "ri:check-line",
      perm: prefix + ":confirm",
      run: () => void confirmRow(row),
    });
  }
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
  refreshCreate,
  refreshUpdate,
  refreshRemove,
  handleSizeChange,
  handleCurrentChange,
} = useTable({
  core: {
    apiFn: api.list,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: resolveStatusColumns<PurchaseDocument>(() => [
      { type: "selection", width: 48, selectable: (row: PurchaseDocument) => row.status === 0 },
      { prop: "order_no", label: "单据编号", minWidth: 190, showOverflowTooltip: true },
      { prop: "supplier_name", label: "供应商", minWidth: 180, showOverflowTooltip: true },
      {
        prop: "warehouse_name",
        label: props.kind === "in" ? "入库仓库" : "退货仓库",
        minWidth: 130,
      },
      { prop: "business_date", label: "业务日期", width: 120 },
      ...(props.kind === "return"
        ? [
            { prop: "source_order_no", label: "入库单号", minWidth: 180 },
            { prop: "return_reason", label: "退货原因", minWidth: 160, showOverflowTooltip: true },
          ]
        : []),
      {
        prop: "total_amount",
        label: "总金额",
        width: 140,
        align: "right",
        formatter: (row) => displayAmount(row.total_amount),
      },
      {
        prop: "status",
        label: "状态",
        width: 95,
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
      {
        prop: "operation",
        label: "操作",
        width: 200,
        fixed: "right",
        formatter: (row) => renderTableOperationCell(actions(row)),
      },
    ]),
  },
});
const { selectedRows, selectedIds, onTableSelectionChange } = useTableSelection<PurchaseDocument>();
const { exportVisible, openExport } = useImportExport();
const crudColumns = toCrudCols(columns);
const exportFields = [
  "order_no",
  "supplier_name",
  "warehouse_name",
  "business_date",
  "total_amount",
  "status",
  "created_name",
  "confirmed_time",
  ...(props.kind === "return" ? ["source_order_no", "return_reason"] : []),
];
const exportRows = computed(() =>
  data.value.map((row) => ({
    ...row,
    created_name: row.created_by?.name ?? "",
    status: ["草稿", "已确认", "已作废"][row.status],
  }))
);
const exportSelection = computed(() =>
  selectedRows.value.map((row) => ({
    ...row,
    created_name: row.created_by?.name ?? "",
    status: ["草稿", "已确认", "已作废"][row.status],
  }))
);
const exportConfig = computed(() => ({
  permPrefix: prefix,
  defaultExportFileName: label + "列表",
  cols: crudColumns.value.filter((col) => col.prop && exportFields.includes(col.prop)),
  /** 全量文件导出沿用当前筛选和字段选择。 */
  exportsBlobAction: async (query: IObject, options?: ExportBlobOptions): Promise<Blob> => {
    const response = await api.exportDocument({
      query: cleanEmptyArrayParams(stripPaginationParams(query)) as PurchaseQuery,
      fields: (options?.fields ?? exportFields).filter((field) => exportFields.includes(field)),
      format: options?.format ?? "xlsx",
      sheet_name: options?.sheetName || label,
      filename: options?.fileName,
    });
    return response.data;
  },
}));
/** 应用业务及审计查询。 */
async function search(params: SearchState): Promise<void> {
  searchForm.value = { ...params };
  replaceSearchParams(cleanEmptyArrayParams({ ...params }));
  await getData();
}
/** 清空筛选恢复第一页。 */
async function reset(): Promise<void> {
  searchForm.value = {};
  await resetSearchParams();
}
/** 草稿删除前核对选择状态。 */
async function deleteRows(rows: PurchaseDocument[]): Promise<void> {
  if (busy.value || !rows.length) return;
  if (rows.some((row) => row.status !== 0)) {
    ElMessage.warning("只能删除草稿");
    return;
  }
  try {
    await ElMessageBox.confirm("确定删除选中的 " + rows.length + " 张草稿？", "删除草稿", {
      type: "warning",
    });
  } catch {
    return;
  }
  busy.value = true;
  try {
    await api.remove({
      ids: rows.map((row) => row.id),
      versions: Object.fromEntries(rows.map((row) => [row.id, row.version])),
    });
    tableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    /* 请求层显示失败原因。 */
  } finally {
    busy.value = false;
  }
}
/** 确认单据生效。 */
async function confirmRow(row: PurchaseDocument): Promise<void> {
  if (busy.value || row.status !== 0) return;
  try {
    await ElMessageBox.confirm(
      "确认单据 " + row.order_no + "？确认后将影响库存及应付。",
      "确认单据",
      { type: "warning" }
    );
  } catch {
    return;
  }
  busy.value = true;
  try {
    await api.confirm(row.id, { version: row.version });
    await refreshData();
  } catch {
    /* 请求层显示失败原因。 */
  } finally {
    busy.value = false;
  }
}
/** 作废必须填写原因并携带版本。 */
async function voidRow(row: PurchaseDocument): Promise<void> {
  if (busy.value || row.status !== 1) return;
  let reason: string;
  try {
    const result = await ElMessageBox.prompt("请输入作废原因", "作废 " + row.order_no, {
      inputType: "textarea",
      inputValidator: (value) =>
        (!!value?.trim() && value.trim().length <= 500) || "请输入1至500字符的作废原因",
      type: "warning",
    });
    reason = result.value.trim();
  } catch {
    return;
  }
  busy.value = true;
  try {
    await api.voidDocument(row.id, { version: row.version, void_reason: reason });
    await refreshData();
  } catch {
    /* 请求层显示失败原因。 */
  } finally {
    busy.value = false;
  }
}
/** 保存后刷新正确的分页位置。 */
async function saved(): Promise<void> {
  if (dialog.mode === "create") await refreshCreate();
  else await refreshUpdate();
}
onMounted(() => {
  void searchSuppliers();
  void searchWarehouses();
});
</script>
<template>
  <div class="fa-full-height">
    <FaSearchBar
      v-show="showSearch"
      v-model="searchForm"
      :items="items"
      include-audit
      :is-expand="false"
      :show-expand="true"
      @search="search"
      @reset="reset"
    />
    <ElCard class="fa-table-card" :style="{ marginTop: showSearch ? '12px' : '0' }">
      <FaTableHeader
        v-model:columns="columnChecks"
        v-model:showSearchBar="showSearch"
        :loading="loading"
        @refresh="refreshData"
      >
        <template #left>
          <ElSpace>
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
              @click="deleteRows(selectedRows)"
              >批量删除</ElButton
            >
          </ElSpace>
        </template>
      </FaTableHeader>
      <FaTable
        ref="tableRef"
        :data="data"
        :columns="columns"
        :loading="loading || busy"
        :pagination="pagination"
        @selection-change="onTableSelectionChange"
        @pagination:size-change="handleSizeChange"
        @pagination:current-change="handleCurrentChange"
      />
    </ElCard>
    <PurchaseDialog
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
      :page-data="exportRows"
      :selection-data="exportSelection"
    />
  </div>
</template>
