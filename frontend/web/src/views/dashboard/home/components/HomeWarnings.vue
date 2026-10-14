<script setup lang="ts">
import { ArrowRight } from "@element-plus/icons-vue";
import type { StockWarning, DashboardWarningPage } from "@/api/module_inventory/dashboard";
import type { ColumnOption } from "@/types/component";
import type { DashboardPanelState } from "../composables/useInventoryDashboard";
import { checkPerm } from "@/utils/checkPerm";
import HomePanel from "./HomePanel.vue";
/** 预警显示库存阈值，分页由首页状态管理。 */
defineProps<{ state: DashboardPanelState<DashboardWarningPage>; page: number }>();
/** 当前面板重试和分页事件。 */
const emit = defineEmits<{ retry: []; page: [value: number] }>();
const router = useRouter();
const canOpen = computed(() => checkPerm("module_inventory:stock_balance:query"));
const columns: ColumnOption<StockWarning>[] = [
  { prop: "goods_name", label: "商品", minWidth: 170, showOverflowTooltip: true },
  { prop: "warehouse_name", label: "仓库", minWidth: 140, showOverflowTooltip: true },
  {
    prop: "quantity",
    label: "当前数量",
    minWidth: 110,
    formatter: (row) => row.quantity + " " + row.unit,
  },
  { prop: "stock_min", label: "库存下限", minWidth: 100 },
  {
    prop: "stock_max",
    label: "库存上限",
    minWidth: 100,
    formatter: (row) => (Number(row.stock_max) === 0 ? "不限" : row.stock_max),
  },
  {
    prop: "warning",
    label: "预警",
    width: 100,
    formatter: (row) => (row.warning === "low" ? "低库存" : "超上限"),
  },
];
/** 库存业务页保留原查询权限，不借首页授权跳转。 */
function openStock(): void {
  if (canOpen.value) void router.push("/inventory/stock/balance");
}
</script>
<template>
  <HomePanel
    title="库存预警"
    :loading="state.loading"
    :error="state.error"
    :forbidden="state.forbidden"
    :empty="state.data?.total === 0"
    @retry="emit('retry')"
  >
    <template #actions
      ><ElButton v-if="canOpen" link :icon="ArrowRight" @click="openStock"
        >当前库存</ElButton
      ></template
    >
    <FaTable :data="state.data?.items ?? []" :columns="columns" row-key="id" />
    <ElPagination
      v-if="state.data"
      class="home-warnings__pagination"
      :current-page="page"
      :page-size="5"
      :total="state.data.total"
      layout="total, prev, pager, next"
      @current-change="emit('page', $event)"
    />
  </HomePanel>
</template>
<style scoped lang="scss">
.home-warnings__pagination {
  justify-content: flex-end;
  max-width: 100%;
  margin-top: 12px;
  overflow-x: auto;
}
</style>
