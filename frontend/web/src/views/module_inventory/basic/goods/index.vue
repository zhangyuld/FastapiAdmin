<script setup lang="ts">
import GoodsCategoryAPI, { type GoodsCategoryItem } from "@/api/module_inventory/basic/category";
import GoodsAPI, {
  GOODS_EXPORT_FIELDS,
  type GoodsExportField,
  type GoodsItem,
  type GoodsPageQuery,
  type GoodsStatus,
} from "@/api/module_inventory/basic/goods";
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
import GoodsDialog from "./components/GoodsDialog.vue";

defineOptions({
  name: "InventoryGoods",
  inheritAttrs: false,
});

/** 商品页面查询状态。 */
interface GoodsSearchForm {
  goods_code?: string;
  goods_name?: string;
  category_id?: number;
  status?: GoodsStatus;
  created_id?: number;
  updated_id?: number;
  created_time?: string[];
  updated_time?: string[];
}

/** 商品弹窗页面状态。 */
interface GoodsDialogState {
  visible: boolean;
  mode: DialogType;
  goodsId?: number;
}

/** 商品表格实例能力。 */
interface GoodsTableRef {
  elTableRef?: {
    clearSelection: () => void;
  };
}

const STATUS_OPTIONS = [
  { label: "启用", value: 0 },
  { label: "停用", value: 1 },
] as const;

const searchForm = ref<GoodsSearchForm>({});
const searchBarRef = ref<InstanceType<typeof FaSearchBar> | null>(null);
const searchBarRules: Record<string, unknown> = {};
const showSearchBar = ref(true);
const tableRef = ref<GoodsTableRef | null>(null);
const categoryOptions = ref<OptionType[]>([]);
const categoryLoading = ref(false);
const createLoading = ref(false);
const moreLoading = ref(false);

const dialogState = reactive<GoodsDialogState>({
  visible: false,
  mode: "create",
  goodsId: undefined,
});

const searchItems = computed<SearchFormItem[]>(() => [
  {
    label: "商品编码",
    key: "goods_code",
    type: "input",
    placeholder: "请输入商品编码",
    clearable: true,
    span: 6,
  },
  {
    label: "商品名称",
    key: "goods_name",
    type: "input",
    placeholder: "请输入商品名称",
    clearable: true,
    span: 6,
  },
  {
    label: "商品分类",
    key: "category_id",
    type: "treeselect",
    props: {
      placeholder: "请选择商品分类",
      data: categoryOptions.value,
      filterable: true,
      clearable: true,
      checkStrictly: true,
      renderAfterExpand: false,
      loading: categoryLoading.value,
    },
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

/** 将商品分类树转换为表单选项。 */
function buildCategoryOptions(rows: GoodsCategoryItem[]): OptionType[] {
  return rows
    .filter((item) => item.id)
    .map((item) => ({
      value: item.id!,
      label: item.name,
      children: item.children?.length ? buildCategoryOptions(item.children) : undefined,
    }));
}

/** 加载商品分类筛选和表单选项。 */
async function loadCategoryOptions() {
  categoryLoading.value = true;
  try {
    const response = await GoodsCategoryAPI.listCategoryTree();
    categoryOptions.value = buildCategoryOptions(response.data.data ?? []);
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error(error);
    categoryOptions.value = [];
  } finally {
    categoryLoading.value = false;
  }
}

/** 规范商品分页查询参数。 */
function normalizeGoodsQuery(params: Record<string, unknown>): GoodsPageQuery {
  return cleanEmptyArrayParams({ ...params }) as unknown as GoodsPageQuery;
}

/** 将商品查询表单转换为表格查询条件。 */
function buildSearchParams(params: GoodsSearchForm): Record<string, unknown> {
  return {
    goods_code: params.goods_code,
    goods_name: params.goods_name,
    category_id: params.category_id,
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

/** 格式化价格或库存精度。 */
function formatDecimal(value: number | string | null | undefined, precision: number) {
  if (value === null || value === undefined || value === "") return "—";
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return String(value);
  return numberValue.toFixed(precision).replace(/\.?0+$/, "");
}

/** 打开商品新增、编辑或详情弹窗。 */
function openGoodsDialog(mode: DialogType, goodsId?: number) {
  dialogState.mode = mode;
  dialogState.goodsId = goodsId;
  dialogState.visible = true;
}

/** 构建商品行操作。 */
function buildGoodsRowActions(row: GoodsItem): TableOperationAction[] {
  return [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: "module_inventory:goods:detail",
      run: () => openGoodsDialog("detail", row.id),
    },
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_inventory:goods:update",
      run: () => openGoodsDialog("update", row.id),
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      perm: "module_inventory:goods:delete",
      run: () => void deleteGoodsRow(row),
    },
  ];
}

/** 渲染商品行操作单元格。 */
function formatGoodsOperationCell(row: GoodsItem) {
  return renderTableOperationCell(buildGoodsRowActions(row), {
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
    apiFn: GoodsAPI.listGoods,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: resolveStatusColumns<GoodsItem>(() => [
      { type: "selection", width: 48, fixed: "left" },
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "goods_code", label: "商品编码", minWidth: 140, showOverflowTooltip: true },
      { prop: "goods_name", label: "商品名称", minWidth: 180, showOverflowTooltip: true },
      {
        prop: "category_name",
        label: "商品分类",
        minWidth: 130,
        showOverflowTooltip: true,
      },
      { prop: "spec", label: "规格型号", minWidth: 140, showOverflowTooltip: true },
      { prop: "unit", label: "单位", width: 86, showOverflowTooltip: true },
      {
        prop: "reference_cost_price",
        label: "参考进价",
        width: 120,
        align: "right",
        formatter: (row: GoodsItem) => formatDecimal(row.reference_cost_price, 4),
      },
      {
        prop: "sale_price",
        label: "默认销售价",
        width: 120,
        align: "right",
        formatter: (row: GoodsItem) => formatDecimal(row.sale_price, 4),
      },
      {
        prop: "stock_min",
        label: "最低库存",
        width: 110,
        align: "right",
        formatter: (row: GoodsItem) => formatDecimal(row.stock_min, 3),
      },
      {
        prop: "stock_max",
        label: "最高库存",
        width: 110,
        align: "right",
        formatter: (row: GoodsItem) =>
          Number(row.stock_max) === 0 ? "不限" : formatDecimal(row.stock_max, 3),
      },
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
        formatter: formatGoodsOperationCell,
      },
    ]),
  },
});

const { selectedRows, selectedIds, batchDeleting, onTableSelectionChange } =
  useTableSelection<GoodsItem>();
const { exportVisible, openExport } = useImportExport();
const goodsCrudCols = toCrudCols(columns);
const goodsExportFieldSet = new Set<string>(GOODS_EXPORT_FIELDS);
const goodsExportCols = computed(() =>
  goodsCrudCols.value.filter(
    (column) => typeof column.prop === "string" && goodsExportFieldSet.has(column.prop)
  )
);

const exportQueryParams = computed(() =>
  normalizeGoodsQuery(stripPaginationParams(searchParams) as Record<string, unknown>)
);

/** 过滤商品远程导出的字段白名单。 */
function normalizeGoodsExportFields(fields: string[]): GoodsExportField[] {
  return fields.filter((field): field is GoodsExportField => goodsExportFieldSet.has(field));
}

const goodsExportContentConfig = computed(() => ({
  permPrefix: "module_inventory:goods",
  cols: goodsExportCols.value,
  exportsBlobAction: async (params: IObject, options?: ExportBlobOptions) => {
    const response = await GoodsAPI.exportGoods({
      query: normalizeGoodsQuery({ ...exportQueryParams.value, ...params }),
      fields: normalizeGoodsExportFields(options?.fields ?? [...GOODS_EXPORT_FIELDS]),
      format: options?.format ?? "xlsx",
      sheet_name: options?.sheetName || "商品档案",
    });
    return response.data as Blob;
  },
}));

/** 执行商品查询。 */
async function handleSearch(params: GoodsSearchForm) {
  await searchBarRef.value?.validate?.();
  searchForm.value = { ...params };
  replaceSearchParams(buildSearchParams(params));
  await getData();
}

/** 重置商品查询条件。 */
async function handleReset() {
  searchForm.value = {};
  await resetSearchParams();
}

/** 打开新增商品弹窗。 */
function handleAdd() {
  createLoading.value = true;
  openGoodsDialog("create");
  nextTick(() => {
    createLoading.value = false;
  });
}

/** 删除单个商品。 */
async function deleteGoodsRow(row: GoodsItem) {
  try {
    await confirmDelete(`确定删除「${row.goods_name}」吗？`);
    await GoodsAPI.deleteGoods({ ids: [row.id!] });
    tableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    // 用户取消或接口已统一提示失败原因
  }
}

/** 批量删除选中商品。 */
async function handleBatchDelete() {
  const ids = selectedIds.value;
  if (!ids.length) return;
  try {
    await confirmBatchDelete(
      ids.length,
      selectedRows.value.map((row) => row.goods_name)
    );
    batchDeleting.value = true;
    await GoodsAPI.deleteGoods({ ids });
    tableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    // 用户取消或接口已统一提示失败原因
  } finally {
    batchDeleting.value = false;
  }
}

/** 批量启用或停用选中商品。 */
async function handleMoreClick(action: "enable" | "disable") {
  const ids = selectedIds.value;
  if (!ids.length) {
    ElMessage.warning("请先选择要操作的数据");
    return;
  }
  try {
    await confirmToggleStatus(action);
    moreLoading.value = true;
    await GoodsAPI.batchGoodsStatus({ ids, status: action === "enable" ? 0 : 1 });
    await refreshData();
  } catch {
    // 用户取消或接口已统一提示失败原因
  } finally {
    moreLoading.value = false;
  }
}

/** 商品保存后刷新对应分页位置。 */
async function handleGoodsSaved() {
  if (dialogState.mode === "create") {
    await refreshCreate();
  } else {
    await refreshUpdate();
  }
}

onMounted(() => {
  void loadCategoryOptions();
});
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
            :perm-create="['module_inventory:goods:create']"
            :perm-export="['module_inventory:goods:export']"
            :perm-delete="['module_inventory:goods:delete']"
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

    <GoodsDialog
      v-model="dialogState.visible"
      :mode="dialogState.mode"
      :goods-id="dialogState.goodsId"
      :category-options="categoryOptions"
      @success="handleGoodsSaved"
    />

    <FaExportDialog
      v-model="exportVisible"
      :content-config="goodsExportContentConfig"
      :query-params="exportQueryParams"
      :page-data="data"
      :selection-data="selectedRows"
    />
  </div>
</template>
