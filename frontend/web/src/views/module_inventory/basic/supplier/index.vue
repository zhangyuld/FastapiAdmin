<script setup lang="ts">
import SupplierAPI, {
  SUPPLIER_EXPORT_FIELDS,
  type SupplierExportField,
  type SupplierItem,
  type SupplierPageQuery,
  type SupplierStatus,
} from "@/api/module_inventory/basic/supplier";
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
import SupplierDialog from "./components/SupplierDialog.vue";

defineOptions({
  name: "InventorySupplier",
  inheritAttrs: false,
});

/** 供应商页面查询状态。 */
interface SupplierSearchForm {
  supplier_code?: string;
  supplier_name?: string;
  contact?: string;
  phone?: string;
  status?: SupplierStatus;
  created_id?: number;
  updated_id?: number;
  created_time?: string[];
  updated_time?: string[];
}

/** 供应商弹窗页面状态。 */
interface SupplierDialogState {
  visible: boolean;
  mode: DialogType;
  supplierId?: number;
}

/** 供应商表格实例能力。 */
interface SupplierTableRef {
  elTableRef?: {
    clearSelection: () => void;
  };
}

const STATUS_OPTIONS = [
  { label: "启用", value: 0 },
  { label: "停用", value: 1 },
] as const;

const searchForm = ref<SupplierSearchForm>({});
const searchBarRef = ref<InstanceType<typeof FaSearchBar> | null>(null);
const searchBarRules: Record<string, unknown> = {};
const showSearchBar = ref(true);
const tableRef = ref<SupplierTableRef | null>(null);
const createLoading = ref(false);
const moreLoading = ref(false);

const dialogState = reactive<SupplierDialogState>({
  visible: false,
  mode: "create",
  supplierId: undefined,
});

const searchItems = computed<SearchFormItem[]>(() => [
  {
    label: "供应商编码",
    labelWidth: "90px",
    key: "supplier_code",
    type: "input",
    placeholder: "请输入供应商编码",
    clearable: true,
    span: 6,
  },
  {
    label: "供应商名称",
    labelWidth: "90px",
    key: "supplier_name",
    type: "input",
    placeholder: "请输入供应商名称",
    clearable: true,
    span: 6,
  },
  {
    label: "联系人",
    key: "contact",
    type: "input",
    placeholder: "请输入联系人",
    clearable: true,
    span: 6,
  },
  {
    label: "联系电话",
    key: "phone",
    type: "input",
    placeholder: "请输入联系电话",
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

/** 规范供应商分页查询参数。 */
function normalizeSupplierQuery(params: Record<string, unknown>): SupplierPageQuery {
  return cleanEmptyArrayParams({ ...params }) as unknown as SupplierPageQuery;
}

/** 将供应商查询表单转换为表格查询条件。 */
function buildSearchParams(params: SupplierSearchForm): Record<string, unknown> {
  return {
    supplier_code: params.supplier_code,
    supplier_name: params.supplier_name,
    contact: params.contact,
    phone: params.phone,
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

/** 打开供应商新增、编辑或详情弹窗。 */
function openSupplierDialog(mode: DialogType, supplierId?: number) {
  dialogState.mode = mode;
  dialogState.supplierId = supplierId;
  dialogState.visible = true;
}

/** 构建供应商行操作。 */
function buildSupplierRowActions(row: SupplierItem): TableOperationAction[] {
  return [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: "module_inventory:supplier:detail",
      run: () => openSupplierDialog("detail", row.id),
    },
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_inventory:supplier:update",
      run: () => openSupplierDialog("update", row.id),
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      perm: "module_inventory:supplier:delete",
      run: () => void deleteSupplierRow(row),
    },
  ];
}

/** 渲染供应商行操作单元格。 */
function formatSupplierOperationCell(row: SupplierItem) {
  return renderTableOperationCell(buildSupplierRowActions(row), {
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
    apiFn: SupplierAPI.listSupplier,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: resolveStatusColumns<SupplierItem>(() => [
      { type: "selection", width: 48, fixed: "left" },
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "supplier_code", label: "供应商编码", minWidth: 140, showOverflowTooltip: true },
      { prop: "supplier_name", label: "供应商名称", minWidth: 200, showOverflowTooltip: true },
      { prop: "contact", label: "联系人", minWidth: 110, showOverflowTooltip: true },
      { prop: "phone", label: "联系电话", minWidth: 140, showOverflowTooltip: true },
      { prop: "address", label: "联系地址", minWidth: 220, showOverflowTooltip: true },
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
        formatter: (row: SupplierItem) => row.created_by?.name ?? "—",
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
        formatter: formatSupplierOperationCell,
      },
    ]),
  },
});

const { selectedRows, selectedIds, batchDeleting, onTableSelectionChange } =
  useTableSelection<SupplierItem>();
const { exportVisible, openExport } = useImportExport();
const supplierCrudCols = toCrudCols(columns);
const supplierExportFieldSet = new Set<string>(SUPPLIER_EXPORT_FIELDS);
const supplierExportCols = computed(() =>
  supplierCrudCols.value.filter(
    (column) => typeof column.prop === "string" && supplierExportFieldSet.has(column.prop)
  )
);

const exportQueryParams = computed(() =>
  normalizeSupplierQuery(stripPaginationParams(searchParams) as Record<string, unknown>)
);

/** 过滤供应商远程导出的字段白名单。 */
function normalizeSupplierExportFields(fields: string[]): SupplierExportField[] {
  return fields.filter((field): field is SupplierExportField => supplierExportFieldSet.has(field));
}

const supplierExportContentConfig = computed(() => ({
  permPrefix: "module_inventory:supplier",
  defaultExportFileName: "供应商列表",
  cols: supplierExportCols.value,
  exportsBlobAction: async (params: IObject, options?: ExportBlobOptions) => {
    const response = await SupplierAPI.exportSupplier({
      query: normalizeSupplierQuery({ ...exportQueryParams.value, ...params }),
      fields: normalizeSupplierExportFields(options?.fields ?? [...SUPPLIER_EXPORT_FIELDS]),
      format: options?.format ?? "xlsx",
      sheet_name: options?.sheetName || "供应商档案",
      filename: options?.fileName,
    });
    return response.data as Blob;
  },
}));

/** 执行供应商查询。 */
async function handleSearch(params: SupplierSearchForm) {
  await searchBarRef.value?.validate?.();
  searchForm.value = { ...params };
  replaceSearchParams(buildSearchParams(params));
  await getData();
}

/** 重置供应商查询条件。 */
async function handleReset() {
  searchForm.value = {};
  await resetSearchParams();
}

/** 打开新增供应商弹窗。 */
function handleAdd() {
  createLoading.value = true;
  openSupplierDialog("create");
  nextTick(() => {
    createLoading.value = false;
  });
}

/** 删除单个供应商。 */
async function deleteSupplierRow(row: SupplierItem) {
  try {
    await confirmDelete(`确定删除「${row.supplier_name}」吗？`);
    await SupplierAPI.deleteSupplier({ ids: [row.id!] });
    tableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    // 用户取消或接口已统一提示失败原因
  }
}

/** 批量删除选中供应商。 */
async function handleBatchDelete() {
  const ids = selectedIds.value;
  if (!ids.length) return;
  try {
    await confirmBatchDelete(
      ids.length,
      selectedRows.value.map((row) => row.supplier_name)
    );
    batchDeleting.value = true;
    await SupplierAPI.deleteSupplier({ ids });
    tableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    // 用户取消或接口已统一提示失败原因
  } finally {
    batchDeleting.value = false;
  }
}

/** 批量启用或停用选中供应商。 */
async function handleMoreClick(action: "enable" | "disable") {
  const ids = selectedIds.value;
  if (!ids.length) {
    ElMessage.warning("请先选择要操作的数据");
    return;
  }
  try {
    await confirmToggleStatus(action);
    moreLoading.value = true;
    await SupplierAPI.batchSupplierStatus({ ids, status: action === "enable" ? 0 : 1 });
    await refreshData();
  } catch {
    // 用户取消或接口已统一提示失败原因
  } finally {
    moreLoading.value = false;
  }
}

/** 供应商保存后刷新对应分页位置。 */
async function handleSupplierSaved() {
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
            :perm-create="['module_inventory:supplier:create']"
            :perm-export="['module_inventory:supplier:export']"
            :perm-delete="['module_inventory:supplier:delete']"
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

    <SupplierDialog
      v-model="dialogState.visible"
      :mode="dialogState.mode"
      :supplier-id="dialogState.supplierId"
      @success="handleSupplierSaved"
    />

    <FaExportDialog
      v-model="exportVisible"
      :content-config="supplierExportContentConfig"
      :query-params="exportQueryParams"
      :page-data="data"
      :selection-data="selectedRows"
    />
  </div>
</template>
