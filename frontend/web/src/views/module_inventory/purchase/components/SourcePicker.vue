<script setup lang="ts">
import PurchaseInAPI from "@/api/module_inventory/purchase/in";
import type { PurchaseDocument } from "@/api/module_inventory/purchase/types";
import { Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
defineOptions({ name: "PurchaseSourcePicker" });
/** 已保存的编辑上下文，切换来源不携带旧来源的草稿 ID。 */
const props = defineProps<{ returnId?: number; sourceId?: number }>();
/** 来源单据及可退数量已经加载完成。 */
const emit = defineEmits<{ select: [document: PurchaseDocument] }>();
const visible = defineModel<boolean>({ required: true });
const keyword = ref("");
const selecting = ref(false);
let sequence = 0;
const {
  data,
  loading,
  columns,
  pagination,
  getData,
  replaceSearchParams,
  handleSizeChange,
  handleCurrentChange,
} = useTable({
  core: {
    apiFn: PurchaseInAPI.list,
    immediate: false,
    apiParams: { page_no: 1, page_size: 10, status: 1 },
    columnsFactory: () => [
      { prop: "order_no", label: "入库单号", minWidth: 180 },
      { prop: "supplier_name", label: "供应商", minWidth: 180 },
      { prop: "warehouse_name", label: "仓库", minWidth: 130 },
      { prop: "business_date", label: "业务日期", width: 120 },
      { prop: "total_amount", label: "采购金额", width: 130 },
      { prop: "operation", label: "操作", width: 90, fixed: "right", useSlot: true },
    ],
  },
});
/** 查询已确认的入库单。 */
async function search(): Promise<void> {
  replaceSearchParams({ order_no: keyword.value.trim() || undefined, status: 1 });
  await getData();
}
/** 获取来源单据的实时可退数量后返回。 */
async function choose(row: PurchaseDocument): Promise<void> {
  if (selecting.value) return;
  const current = sequence;
  selecting.value = true;
  try {
    const response = await PurchaseInAPI.returnable(
      row.id,
      row.id === props.sourceId && props.returnId ? { exclude_return_id: props.returnId } : {}
    );
    if (current !== sequence || !visible.value) return;
    const document = response.data.data;
    if (document.status !== 1) throw new Error("只能选择已确认的入库单");
    if (!document.items?.some((line) => Number(line.returnable_quantity) > 0))
      throw new Error("该入库单没有可退商品");
    if (document.items.some((line) => line.returnable_quantity === undefined || !line.id))
      throw new Error("来源接口缺少明细 ID 或可退数量");
    emit("select", document);
    visible.value = false;
  } catch (error) {
    if (current === sequence && visible.value && error instanceof Error)
      ElMessage.error(error.message);
  } finally {
    if (current === sequence) selecting.value = false;
  }
}
watch(visible, async (value) => {
  sequence++;
  selecting.value = false;
  if (value) {
    keyword.value = "";
    await search();
  }
});
</script>
<template>
  <FaDialog
    v-model="visible"
    title="选择原采购入库单"
    width="min(1000px, 96vw)"
    append-to-body
    :close-on-click-modal="false"
  >
    <ElSpace class="mb-3">
      <ElInput v-model="keyword" placeholder="入库单号" clearable @keyup.enter="search" />
      <ElButton :icon="Search" :loading="loading" @click="search">查询</ElButton>
    </ElSpace>
    <div v-loading="selecting">
      <FaTable
        :data="data"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        @row-dblclick="choose"
        @pagination:size-change="handleSizeChange"
        @pagination:current-change="handleCurrentChange"
      >
        <template #operation="{ row }">
          <ElButton link type="primary" :disabled="selecting" @click="choose(row)">选择</ElButton>
        </template>
      </FaTable>
    </div>
    <template #footer><ElButton @click="visible = false">关闭</ElButton></template>
  </FaDialog>
</template>
