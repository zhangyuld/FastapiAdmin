<script setup lang="ts">
import CustomerAPI, {
  CUSTOMER_EXPORT_FIELDS,
  type CustomerExportField,
  type CustomerItem,
  type CustomerPageQuery,
  type CustomerStatus,
} from "@/api/module_inventory/basic/customer";
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
import CustomerDialog from "./components/CustomerDialog.vue";

defineOptions({
  name: "InventoryCustomer",
  inheritAttrs: false,
});

/** 客户页面查询状态。 */
interface CustomerSearchForm {
  customer_code?: string;
  customer_name?: string;
  contact?: string;
  phone?: string;
  status?: CustomerStatus;
  created_id?: number;
  updated_id?: number;
  created_time?: string[];
  updated_time?: string[];
}

/** 客户弹窗页面状态。 */
interface CustomerDialogState {
  visible: boolean;
  mode: DialogType;
  customerId?: number;
}

/** 客户表格实例能力。 */
interface CustomerTableRef {
  elTableRef?: {
    clearSelection: () => void;
  };
}

const STATUS_OPTIONS = [
  { label: "启用", value: 0 },
  { label: "停用", value: 1 },
] as const;

const searchForm = ref<CustomerSearchForm>({});
const searchBarRef = ref<InstanceType<typeof FaSearchBar> | null>(null);
const searchBarRules: Record<string, unknown> = {};
const showSearchBar = ref(true);
const tableRef = ref<CustomerTableRef | null>(null);
const createLoading = ref(false);
const moreLoading = ref(false);

const dialogState = reactive<CustomerDialogState>({
  visible: false,
  mode: "create",
  customerId: undefined,
});

const searchItems = computed<SearchFormItem[]>(() => [
  {
    label: "客户编码",
    key: "customer_code",
    type: "input",
    placeholder: "请输入客户编码",
    clearable: true,
    span: 6,
  },
  {
    label: "客户名称",
    key: "customer_name",
    type: "input",
    placeholder: "请输入客户名称",
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

/** 规范客户分页查询参数。 */
function normalizeCustomerQuery(params: Record<string, unknown>): CustomerPageQuery {
  return cleanEmptyArrayParams({ ...params }) as unknown as CustomerPageQuery;
}

/** 将客户查询表单转换为表格查询条件。 */
function buildSearchParams(params: CustomerSearchForm): Record<string, unknown> {
  return {
    customer_code: params.customer_code,
    customer_name: params.customer_name,
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

/** 打开客户新增、编辑或详情弹窗。 */
function openCustomerDialog(mode: DialogType, customerId?: number) {
  dialogState.mode = mode;
  dialogState.customerId = customerId;
  dialogState.visible = true;
}

/** 构建客户行操作。 */
function buildCustomerRowActions(row: CustomerItem): TableOperationAction[] {
  return [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: "module_inventory:customer:detail",
      run: () => openCustomerDialog("detail", row.id),
    },
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_inventory:customer:update",
      run: () => openCustomerDialog("update", row.id),
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      perm: "module_inventory:customer:delete",
      run: () => void deleteCustomerRow(row),
    },
  ];
}

/** 渲染客户行操作单元格。 */
function formatCustomerOperationCell(row: CustomerItem) {
  return renderTableOperationCell(buildCustomerRowActions(row), {
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
    apiFn: CustomerAPI.listCustomer,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: resolveStatusColumns<CustomerItem>(() => [
      { type: "selection", width: 48, fixed: "left" },
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "customer_code", label: "客户编码", minWidth: 140, showOverflowTooltip: true },
      { prop: "customer_name", label: "客户名称", minWidth: 200, showOverflowTooltip: true },
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
        formatter: (row: CustomerItem) => row.created_by?.name ?? "—",
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
        formatter: formatCustomerOperationCell,
      },
    ]),
  },
});

const { selectedRows, selectedIds, batchDeleting, onTableSelectionChange } =
  useTableSelection<CustomerItem>();
const { exportVisible, openExport } = useImportExport();
const customerCrudCols = toCrudCols(columns);
const customerExportFieldSet = new Set<string>(CUSTOMER_EXPORT_FIELDS);
const customerExportCols = computed(() =>
  customerCrudCols.value.filter(
    (column) => typeof column.prop === "string" && customerExportFieldSet.has(column.prop)
  )
);

const exportQueryParams = computed(() =>
  normalizeCustomerQuery(stripPaginationParams(searchParams) as Record<string, unknown>)
);

/** 过滤客户远程导出的字段白名单。 */
function normalizeCustomerExportFields(fields: string[]): CustomerExportField[] {
  return fields.filter((field): field is CustomerExportField => customerExportFieldSet.has(field));
}

const customerExportContentConfig = computed(() => ({
  permPrefix: "module_inventory:customer",
  defaultExportFileName: "客户列表",
  cols: customerExportCols.value,
  exportsBlobAction: async (params: IObject, options?: ExportBlobOptions) => {
    const response = await CustomerAPI.exportCustomer({
      query: normalizeCustomerQuery({ ...exportQueryParams.value, ...params }),
      fields: normalizeCustomerExportFields(options?.fields ?? [...CUSTOMER_EXPORT_FIELDS]),
      format: options?.format ?? "xlsx",
      sheet_name: options?.sheetName || "客户档案",
      filename: options?.fileName,
    });
    return response.data as Blob;
  },
}));

/** 执行客户查询。 */
async function handleSearch(params: CustomerSearchForm) {
  await searchBarRef.value?.validate?.();
  searchForm.value = { ...params };
  replaceSearchParams(buildSearchParams(params));
  await getData();
}

/** 重置客户查询条件。 */
async function handleReset() {
  searchForm.value = {};
  await resetSearchParams();
}

/** 打开新增客户弹窗。 */
function handleAdd() {
  createLoading.value = true;
  openCustomerDialog("create");
  nextTick(() => {
    createLoading.value = false;
  });
}

/** 删除单个客户。 */
async function deleteCustomerRow(row: CustomerItem) {
  try {
    await confirmDelete(`确定删除「${row.customer_name}」吗？`);
    await CustomerAPI.deleteCustomer({ ids: [row.id!] });
    tableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    // 用户取消或接口已统一提示失败原因
  }
}

/** 批量删除选中客户。 */
async function handleBatchDelete() {
  const ids = selectedIds.value;
  if (!ids.length) return;
  try {
    await confirmBatchDelete(
      ids.length,
      selectedRows.value.map((row) => row.customer_name)
    );
    batchDeleting.value = true;
    await CustomerAPI.deleteCustomer({ ids });
    tableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    // 用户取消或接口已统一提示失败原因
  } finally {
    batchDeleting.value = false;
  }
}

/** 批量启用或停用选中客户。 */
async function handleMoreClick(action: "enable" | "disable") {
  const ids = selectedIds.value;
  if (!ids.length) {
    ElMessage.warning("请先选择要操作的数据");
    return;
  }
  try {
    await confirmToggleStatus(action);
    moreLoading.value = true;
    await CustomerAPI.batchCustomerStatus({ ids, status: action === "enable" ? 0 : 1 });
    await refreshData();
  } catch {
    // 用户取消或接口已统一提示失败原因
  } finally {
    moreLoading.value = false;
  }
}

/** 客户保存后刷新对应分页位置。 */
async function handleCustomerSaved() {
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
            :perm-create="['module_inventory:customer:create']"
            :perm-export="['module_inventory:customer:export']"
            :perm-delete="['module_inventory:customer:delete']"
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

    <CustomerDialog
      v-model="dialogState.visible"
      :mode="dialogState.mode"
      :customer-id="dialogState.customerId"
      @success="handleCustomerSaved"
    />

    <FaExportDialog
      v-model="exportVisible"
      :content-config="customerExportContentConfig"
      :query-params="exportQueryParams"
      :page-data="data"
      :selection-data="selectedRows"
    />
  </div>
</template>
