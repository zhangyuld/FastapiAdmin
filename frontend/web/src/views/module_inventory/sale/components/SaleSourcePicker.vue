<script setup lang="ts">
import SaleOutAPI from "@/api/module_inventory/sale/out";
import type { SaleDocument } from "@/api/module_inventory/sale/client";
import { Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
defineOptions({ name: "SaleSourcePicker" });
/** 已保存的编辑上下文，切换来源不携带旧来源的草稿 ID。 */
const props = defineProps<{ returnId?: number; sourceId?: number }>();
/** 来源单据及可退数量已经加载完成。 */
const emit = defineEmits<{ select: [document: SaleDocument] }>();
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
  error,
} = useTable({
  core: {
    apiFn: SaleOutAPI.list,
    immediate: false,
    apiParams: { page_no: 1, page_size: 10, status: 1 },
    columnsFactory: () => [
      { prop: "order_no", label: "出库单号", minWidth: 180 },
      { prop: "customer_name", label: "客户", minWidth: 180 },
      { prop: "warehouse_name", label: "仓库", minWidth: 130 },
      { prop: "business_date", label: "业务日期", width: 120 },
      { prop: "receivable_amount", label: "销售金额", width: 130 },
      { prop: "operation", label: "操作", width: 90, fixed: "right", useSlot: true },
    ],
  },
});
/** 查询已确认的出库单。 */
async function search(): Promise<void> {
  replaceSearchParams({ order_no: keyword.value.trim() || undefined, status: 1 });
  await getData().catch(() => undefined);
}
/** 获取来源单据的实时可退数量后返回。 */
async function choose(row: SaleDocument): Promise<void> {
  if (selecting.value || loading.value || error.value) return;
  const current = sequence;
  selecting.value = true;
  try {
    const response = await SaleOutAPI.returnable(
      row.id,
      row.id === props.sourceId && props.returnId ? { exclude_return_id: props.returnId } : {}
    );
    if (current !== sequence || !visible.value) return;
    const document = response.data.data;
    if (document.status !== 1) throw new Error("只能选择已确认的出库单");
    if (!document.items?.some((line) => Number(line.returnable_quantity) > 0))
      throw new Error("该出库单没有可退商品");
    if (
      document.items.some(
        (line) =>
          line.returnable_quantity === undefined || line.returnable_amount === undefined || !line.id
      )
    )
      throw new Error("来源接口缺少明细 ID、可退数量或优惠分摊后的可退金额");
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
    title="选择原销售出库单"
    width="min(1000px, 96vw)"
    append-to-body
    :close-on-click-modal="false"
  >
    <ElSpace class="mb-3">
      <ElInput v-model="keyword" placeholder="出库单号" clearable @keyup.enter="search" />
      <ElButton :icon="Search" :loading="loading" @click="search">查询</ElButton>
    </ElSpace>
    <div v-loading="selecting">
      <ElResult v-if="error" icon="error" title="原销售单加载失败">
        <template #extra><ElButton @click="search">重试</ElButton></template>
      </ElResult>
      <FaTable
        v-else
        :data="data"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        @row-dblclick="choose"
        @pagination:size-change="(size: number) => handleSizeChange(size).catch(() => undefined)"
        @pagination:current-change="
          (page: number) => handleCurrentChange(page).catch(() => undefined)
        "
      >
        <template #operation="{ row }">
          <ElButton link type="primary" :disabled="selecting" @click="choose(row)">选择</ElButton>
        </template>
      </FaTable>
    </div>
    <template #footer><ElButton @click="visible = false">关闭</ElButton></template>
  </FaDialog>
</template>
