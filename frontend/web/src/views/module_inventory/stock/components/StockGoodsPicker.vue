<script setup lang="ts">
import GoodsAPI, { type GoodsItem } from "@/api/module_inventory/basic/goods";
import { Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
defineOptions({ name: "StockGoodsPicker" });
/** 已存在明细中的商品 ID。 */
const props = defineProps<{ excludedIds: number[] }>();
/** 确认选中的启用商品。 */
const emit = defineEmits<{ select: [rows: GoodsItem[]] }>();
const visible = defineModel<boolean>({ required: true });
const keyword = ref("");
const selected = ref<GoodsItem[]>([]);
const tableRef = ref<{ elTableRef?: { clearSelection: () => void } }>();
const {
  data,
  loading,
  columns,
  pagination,
  replaceSearchParams,
  getData,
  handleSizeChange,
  handleCurrentChange,
  error,
} = useTable({
  core: {
    apiFn: GoodsAPI.listGoods,
    immediate: false,
    apiParams: { page_no: 1, page_size: 10, status: 0 },
    columnsFactory: () => [
      {
        type: "selection",
        reserveSelection: true,
        width: 48,
        selectable: (row: GoodsItem) => !props.excludedIds.includes(row.id!),
      },
      { prop: "goods_code", label: "商品编码", minWidth: 140 },
      { prop: "goods_name", label: "商品名称", minWidth: 180 },
      { prop: "spec", label: "规格", minWidth: 110 },
      { prop: "unit", label: "单位", width: 80 },
      { prop: "reference_cost_price", label: "参考成本", width: 120 },
    ],
  },
});
/** 查询当前页商品并保留其他页勾选。 */
async function search(): Promise<void> {
  replaceSearchParams({ goods_name: keyword.value.trim() || undefined, status: 0 });
  await getData().catch(() => undefined);
}
/** 合并跨页选择，剔除当前页取消勾选的商品。 */
function onSelection(rows: GoodsItem[]): void {
  const selectedMap = new Map(
    rows.filter((item) => !props.excludedIds.includes(item.id!)).map((item) => [item.id, item])
  );
  selected.value = [...selectedMap.values()];
}
/** 将商品返回到单据明细。 */
function confirm(): void {
  if (loading.value || error.value) return;
  if (!selected.value.length) {
    ElMessage.warning("请选择商品");
    return;
  }
  emit("select", selected.value);
  visible.value = false;
}
watch(visible, async (value) => {
  if (!value) return;
  selected.value = [];
  await nextTick();
  tableRef.value?.elTableRef?.clearSelection();
  keyword.value = "";
  await search();
});
</script>
<template>
  <FaDialog
    v-model="visible"
    title="选择商品"
    width="min(960px, 96vw)"
    append-to-body
    :close-on-click-modal="false"
    form-mode="create"
    confirm-text="添加商品"
    @cancel="visible = false"
    @confirm="confirm"
  >
    <ElSpace class="mb-3">
      <ElInput v-model="keyword" placeholder="商品名称" clearable @keyup.enter="search" />
      <ElButton :icon="Search" :loading="loading" @click="search">查询</ElButton>
      <span>已选 {{ selected.length }} 项</span>
    </ElSpace>
    <ElResult v-if="error" icon="error" title="商品加载失败">
      <template #extra><ElButton @click="search">重试</ElButton></template>
    </ElResult>
    <FaTable
      v-else
      ref="tableRef"
      :data="data"
      :columns="columns"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      @selection-change="onSelection"
      @pagination:size-change="(size: number) => handleSizeChange(size).catch(() => undefined)"
      @pagination:current-change="
        (page: number) => handleCurrentChange(page).catch(() => undefined)
      "
    />
  </FaDialog>
</template>
