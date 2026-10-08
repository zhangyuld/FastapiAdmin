<script setup lang="ts">
import GoodsCategoryAPI, {
  type GoodsCategoryForm,
  type GoodsCategoryItem,
  type GoodsCategoryQuery,
} from "@/api/module_inventory/basic/category";
import type { AuditSearchFormParams } from "@/components/forms/fa-search-bar/auditSearchFormItems";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import type FaSearchBar from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { DescriptionsItem } from "@/components/display/fa-descriptions/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, resolveStatusColumns, type TableOperationAction } from "@utils";
import { ElMessage } from "element-plus";

defineOptions({
  name: "InventoryGoodsCategory",
  inheritAttrs: false,
});

/** 商品分类页面查询状态。 */
type GoodsCategorySearchForm = {
  name?: string;
  status?: 0 | 1;
} & AuditSearchFormParams;

/** 商品分类树形表格实例能力。 */
interface CategoryTableRef {
  elTableRef?: {
    toggleRowExpansion: (row: GoodsCategoryItem, expanded?: boolean) => void;
    clearSelection: () => void;
  };
}

const STATUS_OPTIONS = [
  { label: "启用", value: 0 },
  { label: "停用", value: 1 },
] as const;

const searchForm = ref<GoodsCategorySearchForm>({
  name: undefined,
  status: undefined,
  created_time: undefined,
  created_id: undefined,
  updated_id: undefined,
  updated_time: undefined,
});
const showSearchBar = ref(true);
const searchBarRef = ref<InstanceType<typeof FaSearchBar> | null>(null);
const searchBarRules: Record<string, unknown> = {};
const tableRef = ref<CategoryTableRef | null>(null);
const tableData = ref<GoodsCategoryItem[]>([]);
const categoryOptionData = ref<GoodsCategoryItem[]>([]);
const loading = ref(false);
const isExpanded = ref(false);
const createLoading = ref(false);
const moreLoading = ref(false);

const categorySearchItems = computed<SearchFormItem[]>(() => [
  {
    label: "分类名称",
    key: "name",
    type: "input",
    placeholder: "请输入分类名称",
    clearable: true,
    span: 6,
  },
  {
    label: "状态",
    key: "status",
    type: "select",
    props: {
      placeholder: "请选择状态",
      options: STATUS_OPTIONS,
      clearable: true,
    },
    span: 6,
  },
]);

/** 将页面查询状态转换为后端查询参数。 */
function buildCategoryQuery(params: GoodsCategorySearchForm): GoodsCategoryQuery {
  return {
    name: params.name,
    status: params.status,
    created_time:
      Array.isArray(params.created_time) && params.created_time.length === 2
        ? params.created_time
        : undefined,
    created_id: params.created_id ?? undefined,
    updated_id: params.updated_id ?? undefined,
    updated_time:
      Array.isArray(params.updated_time) && params.updated_time.length === 2
        ? params.updated_time
        : undefined,
  };
}

/** 收集当前分类及全部子分类 ID，避免选择成自己的上级。 */
function collectCategoryBranchIds(rows: GoodsCategoryItem[], categoryId?: number): Set<number> {
  const excludedIds = new Set<number>();
  if (!categoryId) return excludedIds;

  const visit = (items: GoodsCategoryItem[]): boolean => {
    for (const item of items) {
      if (item.id === categoryId) {
        const collect = (nodes: GoodsCategoryItem[]) => {
          nodes.forEach((node) => {
            if (node.id) excludedIds.add(node.id);
            if (node.children?.length) collect(node.children);
          });
        };
        collect([item]);
        return true;
      }
      if (item.children?.length && visit(item.children)) return true;
    }
    return false;
  };

  visit(rows);
  return excludedIds;
}

/** 将分类树转换为上级分类选择项。 */
function buildCategoryOptions(rows: GoodsCategoryItem[], excludedIds: Set<number>): OptionType[] {
  return rows
    .filter((item) => item.id && !excludedIds.has(item.id))
    .map((item) => {
      const children = item.children?.length
        ? buildCategoryOptions(item.children, excludedIds)
        : undefined;
      return {
        value: item.id!,
        label: item.name,
        children: children?.length ? children : undefined,
      };
    });
}

/** 加载商品分类树并刷新父分类选项来源。 */
async function loadCategoryData() {
  loading.value = true;
  try {
    const [tableResponse, optionResponse] = await Promise.all([
      GoodsCategoryAPI.listCategoryTree(buildCategoryQuery(searchForm.value)),
      GoodsCategoryAPI.listCategoryTree(),
    ]);
    tableData.value = tableResponse.data.data ?? [];
    categoryOptionData.value = optionResponse.data.data ?? [];
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error(error);
    tableData.value = [];
    categoryOptionData.value = [];
  } finally {
    loading.value = false;
  }
}

const { selectedRows, selectedIds, batchDeleting, onTableSelectionChange } =
  useTableSelection<GoodsCategoryItem>();
const { dialogVisible } = useCrudDialog();

const detailFormData = ref<GoodsCategoryItem>({
  name: "",
  sort: 0,
  status: 0,
});
const formData = ref<GoodsCategoryForm>({
  id: undefined,
  name: "",
  parent_id: null,
  sort: 0,
  status: 0,
});
const initialFormData: GoodsCategoryForm = {
  id: undefined,
  name: "",
  parent_id: null,
  sort: 0,
  status: 0,
};
const dataFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const categoryFormRenderKey = ref(0);

const parentCategoryOptions = computed<OptionType[]>(() => {
  const excludedIds = collectCategoryBranchIds(categoryOptionData.value, formData.value.id);
  return buildCategoryOptions(categoryOptionData.value, excludedIds);
});

const rules = reactive({
  name: [
    { required: true, message: "请输入分类名称", trigger: "blur" },
    { min: 1, max: 100, message: "分类名称长度应为1至100个字符", trigger: "blur" },
  ],
  sort: [{ required: true, message: "请输入显示排序", trigger: "blur" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
});

const categoryDetailItems: DescriptionsItem[] = [
  { label: "分类名称", prop: "name" },
  { label: "上级分类", prop: "parent_name" },
  {
    label: "状态",
    prop: "status",
    tag: {
      map: {
        "0": { type: "success", text: "启用" },
        "1": { type: "danger", text: "停用" },
      },
    },
  },
  { label: "排序", prop: "sort" },
  { label: "创建时间", prop: "created_time" },
  { label: "更新时间", prop: "updated_time" },
  { label: "创建人", prop: "created_by.name" },
  { label: "更新人", prop: "updated_by.name" },
];

const categoryDialogFormItems = computed<FormItem[]>(() => [
  {
    label: "分类名称",
    key: "name",
    type: "input",
    props: {
      placeholder: "请输入分类名称",
      maxlength: 100,
      showWordLimit: true,
    },
  },
  {
    label: "上级分类",
    key: "parent_id",
    type: "treeselect",
    props: {
      placeholder: "不选择则创建为顶级分类",
      data: parentCategoryOptions.value,
      filterable: true,
      clearable: true,
      checkStrictly: true,
      renderAfterExpand: false,
    },
  },
  {
    label: "显示排序",
    key: "sort",
    type: "number",
    props: {
      controlsPosition: "right",
      min: 0,
      max: 9999,
    },
  },
  {
    label: "状态",
    key: "status",
    type: "radiogroup",
    props: { options: STATUS_OPTIONS },
  },
]);

const { submitLoading, handleCloseDialog, handleOpenDialog, handleSubmit } =
  useCrudForm<GoodsCategoryForm>({
    formData,
    initialFormData,
    dialogVisible,
    dataFormRef,
    formRenderKey: categoryFormRenderKey,
    detailApi: GoodsCategoryAPI.getCategoryDetail,
    createApi: GoodsCategoryAPI.createCategory,
    updateApi: GoodsCategoryAPI.updateCategory,
    titles: { create: "新增商品分类", update: "修改商品分类", detail: "商品分类详情" },
    detailFormData,
    onCreateSuccess: loadCategoryData,
    onUpdateSuccess: loadCategoryData,
  });

/** 打开新增顶级分类弹窗。 */
async function handleAdd() {
  createLoading.value = true;
  try {
    await handleOpenDialog("create");
  } finally {
    createLoading.value = false;
  }
}

/** 打开分类详情弹窗。 */
async function handleOpenCategoryDetail(id: number) {
  dialogVisible.title = "商品分类详情";
  dialogVisible.type = "detail";
  const response = await GoodsCategoryAPI.getCategoryDetail(id);
  Object.assign(detailFormData.value, response.data.data ?? {});
  dialogVisible.visible = true;
}

/** 删除单个商品分类。 */
async function deleteCategoryRow(id: number, name: string) {
  try {
    await confirmDelete(`确定删除「${name}」吗？`);
    await GoodsCategoryAPI.deleteCategory([id]);
    tableRef.value?.elTableRef?.clearSelection();
    await loadCategoryData();
  } catch {
    // 用户取消或接口已统一提示失败原因
  }
}

const operationContext = {
  onAddChild: (parentId: number) =>
    void handleOpenDialog("create", undefined, { parent_id: parentId }),
  onDetail: (id: number) => void handleOpenCategoryDetail(id),
  onEdit: (id: number) => void handleOpenDialog("update", id),
  onDelete: deleteCategoryRow,
};

/** 构建商品分类行操作。 */
function buildCategoryRowActions(
  row: GoodsCategoryItem,
  context: typeof operationContext
): TableOperationAction[] {
  return [
    {
      key: "add",
      label: "新增子分类",
      artType: "add",
      perm: "module_inventory:category:create",
      run: () => context.onAddChild(row.id!),
    },
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: "module_inventory:category:detail",
      run: () => context.onDetail(row.id!),
    },
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_inventory:category:update",
      run: () => context.onEdit(row.id!),
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      perm: "module_inventory:category:delete",
      run: () => context.onDelete(row.id!, row.name),
    },
  ];
}

/** 渲染商品分类行操作单元格。 */
function formatCategoryOperationCell(row: GoodsCategoryItem) {
  return renderTableOperationCell(buildCategoryRowActions(row, operationContext), {
    wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1",
  });
}

const { columnChecks, columns } = useTableColumns<GoodsCategoryItem>(
  resolveStatusColumns(() => [
    { type: "selection", width: 48, fixed: "left" },
    { type: "globalIndex", width: 56, label: "序号" },
    { prop: "name", label: "分类名称", minWidth: 220, showOverflowTooltip: true },
    {
      prop: "status",
      label: "状态",
      width: 88,
      status: {
        0: { type: "success", text: "启用" },
        1: { type: "danger", text: "停用" },
      },
    },
    { prop: "sort", label: "排序", width: 88, sortable: true },
    {
      prop: "created_time",
      label: "创建时间",
      width: 168,
      sortable: true,
      showOverflowTooltip: true,
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
      width: 270,
      fixed: "right",
      align: "center",
      formatter: formatCategoryOperationCell,
    },
  ])
);

/** 执行分类查询。 */
async function handleSearchBarSearch(params: GoodsCategorySearchForm) {
  await searchBarRef.value?.validate?.();
  searchForm.value = { ...params };
  await loadCategoryData();
}

/** 重置分类查询条件。 */
async function onResetSearch() {
  searchForm.value = {
    name: undefined,
    status: undefined,
    created_time: undefined,
    created_id: undefined,
    updated_id: undefined,
    updated_time: undefined,
  };
  await loadCategoryData();
}

/** 批量删除选中的商品分类。 */
async function handleBatchDelete() {
  const ids = selectedIds.value;
  if (!ids.length) return;
  try {
    await confirmBatchDelete(
      ids.length,
      selectedRows.value.map((row) => row.name)
    );
    batchDeleting.value = true;
    await GoodsCategoryAPI.deleteCategory(ids);
    tableRef.value?.elTableRef?.clearSelection();
    await loadCategoryData();
  } catch {
    // 用户取消或接口已统一提示失败原因
  } finally {
    batchDeleting.value = false;
  }
}

/** 批量启用或停用选中的商品分类。 */
async function handleMoreClick(action: "enable" | "disable") {
  const ids = selectedIds.value;
  if (!ids.length) {
    ElMessage.warning("请先选择要操作的数据");
    return;
  }
  try {
    await confirmToggleStatus(action);
    moreLoading.value = true;
    await GoodsCategoryAPI.batchCategoryStatus({
      ids,
      status: action === "enable" ? 0 : 1,
    });
    await loadCategoryData();
  } catch {
    // 用户取消或接口已统一提示失败原因
  } finally {
    moreLoading.value = false;
  }
}

/** 展开或收起全部分类树节点。 */
function toggleExpand() {
  isExpanded.value = !isExpanded.value;
  nextTick(() => {
    const table = tableRef.value?.elTableRef;
    if (!table) return;
    const visit = (rows: GoodsCategoryItem[]) => {
      rows.forEach((row) => {
        if (row.children?.length) {
          table.toggleRowExpansion(row, isExpanded.value);
          visit(row.children);
        }
      });
    };
    visit(tableData.value);
  });
}

onMounted(() => {
  void loadCategoryData();
});
</script>

<template>
  <div class="fa-full-height">
    <FaSearchBar
      v-show="showSearchBar"
      ref="searchBarRef"
      v-model="searchForm"
      :items="categorySearchItems"
      :rules="searchBarRules"
      :is-expand="false"
      :show-expand="true"
      :show-reset="true"
      :show-search="true"
      :disabled-search="false"
      :default-expanded="false"
      include-audit
      @search="handleSearchBarSearch"
      @reset="onResetSearch"
    />

    <ElCard class="fa-table-card" :style="{ marginTop: showSearchBar ? '12px' : '0' }">
      <FaTableHeader
        v-model:columns="columnChecks"
        v-model:showSearchBar="showSearchBar"
        :loading="loading"
        @refresh="loadCategoryData"
      >
        <template #left>
          <div class="inline-flex flex-wrap items-center gap-2">
            <FaTableHeaderLeft
              :remove-ids="selectedIds"
              :perm-create="['module_inventory:category:create']"
              :perm-delete="['module_inventory:category:delete']"
              :delete-loading="batchDeleting"
              :create-loading="createLoading"
              :more-loading="moreLoading"
              @add="handleAdd"
              @delete="handleBatchDelete"
              @more="handleMoreClick"
            />
            <!--  :perm-patch="['module_inventory:category:patch']" -->
            <!-- <ElButton @click="toggleExpand" v-ripple>
              {{ isExpanded ? "收起" : "展开" }}
            </ElButton> -->
          </div>
        </template>
      </FaTableHeader>

      <FaTable
        ref="tableRef"
        row-key="id"
        :loading="loading"
        :columns="columns"
        :data="tableData"
        :tree-props="{ children: 'children', hasChildren: 'hasChildren' }"
        :default-expand-all="false"
        @selection-change="onTableSelectionChange"
      />
    </ElCard>

    <FaDialog
      v-model="dialogVisible.visible"
      :title="dialogVisible.title"
      width="600px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      :form-mode="dialogVisible.type"
      :confirm-loading="submitLoading"
      @cancel="handleCloseDialog"
      @close="handleCloseDialog"
      @confirm="handleSubmit()"
    >
      <FaDescriptions
        v-if="dialogVisible.type === 'detail'"
        :column="2"
        :data="detailFormData"
        :items="categoryDetailItems"
        max-height="70vh"
      />
      <FaForm
        v-else
        :key="categoryFormRenderKey"
        ref="dataFormRef"
        v-model="formData"
        scrollbar
        max-height="70vh"
        :items="categoryDialogFormItems"
        :rules="rules"
        label-suffix=":"
        :label-width="100"
        label-position="right"
        :span="24"
        :gutter="16"
        :show-reset="false"
        :show-submit="false"
        class="crud-dialog-art-form"
      />
    </FaDialog>
  </div>
</template>
