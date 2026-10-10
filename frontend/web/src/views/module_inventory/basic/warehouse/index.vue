<script setup lang="ts">
import WarehouseAPI, {
  WAREHOUSE_EXPORT_FIELDS,
  type WarehouseExportField,
  type WarehouseItem,
  type WarehousePageQuery,
  type WarehouseStatus,
} from "@/api/module_inventory/basic/warehouse";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import type FaSearchBar from "@/components/forms/fa-search-bar/index.vue";
import type { ExportBlobOptions, IObject } from "@/components/modal/types";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import type { DialogType } from "@/hooks/core/useCrudDialog";
import {
  cleanEmptyArrayParams,
  renderTableOperationCell,
  resolveStatusColumns,
  stripPaginationParams,
  toCrudCols,
  type TableOperationAction,
} from "@utils";
import { ElMessage } from "element-plus";
import WarehouseDialog from "./components/WarehouseDialog.vue";

defineOptions({
  name: "InventoryWarehouse",
  inheritAttrs: false,
});

/** 仓库页面查询状态。 */
interface WarehouseSearchForm {
  warehouse_code?: string;
  warehouse_name?: string;
  status?: WarehouseStatus;
  created_id?: number;
  updated_id?: number;
  created_time?: string[];
  updated_time?: string[];
}

/** 仓库弹窗页面状态。 */
interface WarehouseDialogState {
  visible: boolean;
  mode: DialogType;
  warehouseId?: number;
}

/** 仓库表格实例能力。 */
interface WarehouseTableRef {
  elTableRef?: {
    clearSelection: () => void;
  };
}

const STATUS_OPTIONS = [
  { label: "启用", value: 0 },
  { label: "停用", value: 1 },
] as const;

const searchForm = ref<WarehouseSearchForm>({});
const searchBarRef = ref<InstanceType<typeof FaSearchBar> | null>(null);
const searchBarRules: Record<string, unknown> = {};
const showSearchBar = ref(true);
const tableRef = ref<WarehouseTableRef | null>(null);
const createLoading = ref(false);
const moreLoading = ref(false);

const dialogState = reactive<WarehouseDialogState>({
  visible: false,
  mode: "create",
  warehouseId: undefined,
});

const searchItems = computed<SearchFormItem[]>(() => [
  {
    label: "仓库编码",
    labelWidth: "90px",
    key: "warehouse_code",
    type: "input",
    placeholder: "请输入仓库编码",
    clearable: true,
    span: 6,
  },
  {
    label: "仓库名称",
    labelWidth: "90px",
    key: "warehouse_name",
    type: "input",
    placeholder: "请输入仓库名称",
    clearable: true,
    span: 6,
  },
  {
    label: "状态",
    key: "status",
    type: "select",
    props: { placeholder: "请选择状态", options: STATUS_OPTIONS, clearable: true },
    span: 6,
  },
]);

/** 规范仓库分页查询参数。 */
function normalizeWarehouseQuery(params: Record<string, unknown>): WarehousePageQuery {
  return cleanEmptyArrayParams({ ...params }) as unknown as WarehousePageQuery;
}

/** 将仓库查询表单转换为表格查询条件。 */
function buildSearchParams(params: WarehouseSearchForm): Record<string, unknown> {
  return {
    warehouse_code: params.warehouse_code,
    warehouse_name: params.warehouse_name,
    status: params.status,
    created_id: params.created_id,
    updated_id: params.updated_id,
    created_time:
      Array.isArray(params.created_time) && params.created_time.length === 2
        ? params.created_time
        : undefined,
    updated_time:
      Array.isArray(params.updated_time) && params.updated_time.length === 2
        ? params.updated_time
        : undefined,
  };
}

/** 打开仓库新增、编辑或详情弹窗。 */
function openWarehouseDialog(mode: DialogType, warehouseId?: number) {
  dialogState.mode = mode;
  dialogState.warehouseId = warehouseId;
  dialogState.visible = true;
}

/** 构建仓库行操作。 */
function buildWarehouseRowActions(row: WarehouseItem): TableOperationAction[] {
  return [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: "module_inventory:warehouse:detail",
      run: () => openWarehouseDialog("detail", row.id),
    },
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_inventory:warehouse:update",
      run: () => openWarehouseDialog("update", row.id),
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      perm: "module_inventory:warehouse:delete",
      run: () => void deleteWarehouseRow(row),
    },
  ];
}

/** 渲染仓库行操作单元格。 */
function formatWarehouseOperationCell(row: WarehouseItem) {
  return renderTableOperationCell(buildWarehouseRowActions(row), {
    wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1",
  });
}

const {
  columns,
  columnChecks,
  data,
  loading,
  pagination,
  searchParams,
  getData,
  replaceSearchParams,
  resetSearchParams,
  handleSizeChange,
  handleCurrentChange,
  refreshData,
  refreshCreate,
  refreshUpdate,
  refreshRemove,
} = useTable({
  core: {
    apiFn: WarehouseAPI.listWarehouse,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: resolveStatusColumns<WarehouseItem>(() => [
      { type: "selection", width: 48, fixed: "left" },
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "warehouse_code", label: "仓库编码", minWidth: 140, showOverflowTooltip: true },
      { prop: "warehouse_name", label: "仓库名称", minWidth: 200, showOverflowTooltip: true },
      { prop: "address", label: "仓库地址", minWidth: 220, showOverflowTooltip: true },
      {
        prop: "status",
        label: "状态",
        width: 88,
        status: {
          0: { type: "success", text: "启用" },
          1: { type: "danger", text: "停用" },
        },
      },
      {
        prop: "created_id",
        label: "创建人",
        minWidth: 100,
        formatter: (row: WarehouseItem) => row.created_by?.name ?? "—",
      },
      {
        prop: "updated_time",
        label: "更新时间",
        width: 168,
        sortable: true,
        showOverflowTooltip: true,
      },
      {
        prop: "operation",
        label: "操作",
        width: 200,
        fixed: "right",
        align: "center",
        formatter: formatWarehouseOperationCell,
      },
    ]),
  },
});

const { selectedRows, selectedIds, batchDeleting, onTableSelectionChange } =
  useTableSelection<WarehouseItem>();
const { exportVisible, openExport } = useImportExport();
const warehouseCrudCols = toCrudCols(columns);
const warehouseExportFieldSet = new Set<string>(WAREHOUSE_EXPORT_FIELDS);
const warehouseExportCols = computed(() =>
  warehouseCrudCols.value.filter(
    (column) => typeof column.prop === "string" && warehouseExportFieldSet.has(column.prop)
  )
);

const exportQueryParams = computed(() =>
  normalizeWarehouseQuery(stripPaginationParams(searchParams) as Record<string, unknown>)
);

/** 过滤仓库远程导出的字段白名单。 */
function normalizeWarehouseExportFields(fields: string[]): WarehouseExportField[] {
  return fields.filter((field): field is WarehouseExportField =>
    warehouseExportFieldSet.has(field)
  );
}

const warehouseExportContentConfig = computed(() => ({
  permPrefix: "module_inventory:warehouse",
  defaultExportFileName: "仓库列表",
  cols: warehouseExportCols.value,
  exportsBlobAction: async (params: IObject, options?: ExportBlobOptions) => {
    const response = await WarehouseAPI.exportWarehouse({
      query: normalizeWarehouseQuery({ ...exportQueryParams.value, ...params }),
      fields: normalizeWarehouseExportFields(options?.fields ?? [...WAREHOUSE_EXPORT_FIELDS]),
      format: options?.format ?? "xlsx",
      sheet_name: options?.sheetName || "仓库档案",
      filename: options?.fileName,
    });
    return response.data as Blob;
  },
}));

/** 执行仓库查询。 */
async function handleSearch(params: WarehouseSearchForm) {
  await searchBarRef.value?.validate?.();
  searchForm.value = { ...params };
  replaceSearchParams(buildSearchParams(params));
  await getData();
}

/** 重置仓库查询条件。 */
async function handleReset() {
  searchForm.value = {};
  await resetSearchParams();
}

/** 打开新增仓库弹窗。 */
function handleAdd() {
  createLoading.value = true;
  openWarehouseDialog("create");
  nextTick(() => {
    createLoading.value = false;
  });
}

/** 删除单个仓库。 */
async function deleteWarehouseRow(row: WarehouseItem) {
  try {
    await confirmDelete(`确定删除「${row.warehouse_name}」吗？`);
    await WarehouseAPI.deleteWarehouse({ ids: [row.id!] });
    tableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    // 用户取消或接口已统一提示失败原因
  }
}

/** 批量删除选中仓库。 */
async function handleBatchDelete() {
  const ids = selectedIds.value;
  if (!ids.length) return;
  try {
    await confirmBatchDelete(
      ids.length,
      selectedRows.value.map((row) => row.warehouse_name)
    );
    batchDeleting.value = true;
    await WarehouseAPI.deleteWarehouse({ ids });
    tableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    // 用户取消或接口已统一提示失败原因
  } finally {
    batchDeleting.value = false;
  }
}

/** 批量启用或停用选中仓库。 */
async function handleMoreClick(action: "enable" | "disable") {
  const ids = selectedIds.value;
  if (!ids.length) {
    ElMessage.warning("请先选择要操作的数据");
    return;
  }
  try {
    await confirmToggleStatus(action);
    moreLoading.value = true;
    await WarehouseAPI.batchWarehouseStatus({ ids, status: action === "enable" ? 0 : 1 });
    await refreshData();
  } catch {
    // 用户取消或接口已统一提示失败原因
  } finally {
    moreLoading.value = false;
  }
}

/** 仓库保存后刷新对应分页位置。 */
async function handleWarehouseSaved() {
  if (dialogState.mode === "create") {
    await refreshCreate();
  } else {
    await refreshUpdate();
  }
}
</script>

<template>
  <div class="fa-full-height">
    <FaSearchBar
      v-show="showSearchBar"
      ref="searchBarRef"
      v-model="searchForm"
      :items="searchItems"
      :rules="searchBarRules"
      :is-expand="false"
      :show-expand="true"
      :show-reset="true"
      :show-search="true"
      :disabled-search="false"
      :default-expanded="false"
      include-audit
      @search="handleSearch"
      @reset="handleReset"
    />

    <ElCard class="fa-table-card" :style="{ marginTop: showSearchBar ? '12px' : '0' }">
      <FaTableHeader
        v-model:columns="columnChecks"
        v-model:showSearchBar="showSearchBar"
        :loading="loading"
        @refresh="refreshData"
      >
        <template #left>
          <FaTableHeaderLeft
            :remove-ids="selectedIds"
            :perm-create="['module_inventory:warehouse:create']"
            :perm-export="['module_inventory:warehouse:export']"
            :perm-delete="['module_inventory:warehouse:delete']"
            :perm-patch="['module_inventory:warehouse:patch']"
            :delete-loading="batchDeleting"
            :create-loading="createLoading"
            :more-loading="moreLoading"
            @add="handleAdd"
            @export="openExport"
            @delete="handleBatchDelete"
            @more="handleMoreClick"
          />
        </template>
      </FaTableHeader>

      <FaTable
        ref="tableRef"
        :loading="loading"
        :data="data"
        :columns="columns"
        :pagination="pagination"
        @selection-change="onTableSelectionChange"
        @pagination:size-change="handleSizeChange"
        @pagination:current-change="handleCurrentChange"
      />
    </ElCard>

    <WarehouseDialog
      v-model="dialogState.visible"
      :mode="dialogState.mode"
      :warehouse-id="dialogState.warehouseId"
      @success="handleWarehouseSaved"
    />

    <FaExportDialog
      v-model="exportVisible"
      :content-config="warehouseExportContentConfig"
      :query-params="exportQueryParams"
      :page-data="data"
      :selection-data="selectedRows"
    />
  </div>
</template>
