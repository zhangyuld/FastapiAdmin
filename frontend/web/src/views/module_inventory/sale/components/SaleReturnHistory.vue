<script setup lang="ts">
import SaleOutAPI from "@/api/module_inventory/sale/out";
import type { SaleReturnSummary } from "@/api/module_inventory/sale/client";
import type { RelatedSaleReturn } from "@/api/module_inventory/sale/out";
import type { ColumnOption } from "@/types/component";
import { Refresh } from "@element-plus/icons-vue";

defineOptions({ name: "SaleReturnHistory" });
/** 出库详情关联退货，汇总由主单接口提供。 */
const props = defineProps<{ sourceId: number; summary: SaleReturnSummary }>();
/** 打开有详情权限的退货单。 */
const emit = defineEmits<{ detail: [id: number]; refresh: [] }>();
const { hasAuth } = useAuth();
/** 关联退货分页与请求状态。 */
interface ReturnHistoryState {
  items: RelatedSaleReturn[];
  page: number;
  size: number;
  total: number;
  loading: boolean;
  failed: boolean;
}
const state = reactive<ReturnHistoryState>({
  items: [],
  page: 1,
  size: 10,
  total: 0,
  loading: false,
  failed: false,
});
const canQuery = computed(() => hasAuth("module_inventory:sale_return:query"));
const canDetail = computed(() => hasAuth("module_inventory:sale_return:detail"));
const statusText = computed(
  () =>
    ({
      none: "未退货",
      partial: "部分退货",
      full: "全部退货",
    })[props.summary.return_status]
);
const columns: ColumnOption<RelatedSaleReturn>[] = [
  { prop: "order_no", label: "退货单号", minWidth: 200, useSlot: true },
  { prop: "business_date", label: "业务日期", width: 120 },
  { prop: "status", label: "状态", width: 100, useSlot: true },
  { prop: "return_amount", label: "退货金额", width: 130 },
  { prop: "return_reason", label: "退货原因", minWidth: 180 },
  { prop: "confirmed_time", label: "确认时间", minWidth: 170 },
];
let sequence = 0;
/** 加载指定原单的可见退货，忽略切换单据后的过期响应。 */
async function load(): Promise<void> {
  const current = ++sequence;
  state.failed = false;
  state.items = [];
  if (!canQuery.value) {
    state.loading = false;
    return;
  }
  state.loading = true;
  try {
    const response = await SaleOutAPI.relatedReturns(props.sourceId, {
      page_no: state.page,
      page_size: state.size,
    });
    if (current !== sequence) return;
    state.items = response.data.data.items;
    state.total = response.data.data.total;
  } catch {
    if (current === sequence) state.failed = true;
  } finally {
    if (current === sequence) state.loading = false;
  }
}
/** 切换分页后重新读取关联记录。 */
function changePage(page: number): void {
  state.page = page;
  void load();
}
watch(
  [() => props.sourceId, canQuery],
  () => {
    state.page = 1;
    state.total = 0;
    void load();
  },
  { immediate: true }
);
onUnmounted(() => {
  sequence++;
});
</script>

<template>
  <section class="mt-4">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <h3 class="text-base font-medium">关联退货</h3>
      <ElButton v-if="canQuery" :icon="Refresh" :loading="state.loading" @click="emit('refresh')"
        >刷新</ElButton
      >
    </div>
    <ElDescriptions :column="3" border class="mb-3">
      <ElDescriptionsItem label="退货情况">{{ statusText }}</ElDescriptionsItem>
      <ElDescriptionsItem label="有效退货单数">{{ summary.confirmed_count }}</ElDescriptionsItem>
      <ElDescriptionsItem label="有效退货金额">{{ summary.returned_amount }}</ElDescriptionsItem>
    </ElDescriptions>
    <ElEmpty v-if="!canQuery" description="暂无退货查询权限" />
    <ElResult v-else-if="state.failed" icon="error" title="关联退货加载失败">
      <template #extra><ElButton :icon="Refresh" @click="load">重试</ElButton></template>
    </ElResult>
    <template v-else>
      <FaTable :data="state.items" :columns="columns" :loading="state.loading" row-key="id">
        <template #order_no="{ row }">
          <ElButton v-if="canDetail" link type="primary" @click="emit('detail', row.id)">{{
            row.order_no
          }}</ElButton>
          <span v-else>{{ row.order_no }}</span>
        </template>
        <template #status="{ row }"
          ><ElTag :type="row.status === 1 ? 'success' : row.status === 2 ? 'info' : 'warning'">{{
            ["草稿", "已确认", "已作废"][row.status]
          }}</ElTag></template
        >
      </FaTable>
      <ElPagination
        class="mt-3"
        :current-page="state.page"
        :page-size="state.size"
        :total="state.total"
        layout="total, prev, pager, next"
        @current-change="changePage"
      />
    </template>
  </section>
</template>
