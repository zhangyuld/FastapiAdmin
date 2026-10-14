<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import HomeMetrics from "./components/HomeMetrics.vue";
import HomeCharts from "./components/HomeCharts.vue";
import HomeWarnings from "./components/HomeWarnings.vue";
import HomeRecent from "./components/HomeRecent.vue";
import { useInventoryDashboard } from "./composables/useInventoryDashboard";

defineOptions({ name: "Home", inheritAttrs: false });
const {
  summary,
  trend,
  warehouses,
  warnings,
  recent,
  period,
  warningPage,
  refreshing,
  refresh,
  loadSummary,
  loadTrend,
  loadWarehouses,
  loadWarnings,
  loadRecent,
  changePeriod,
  changeWarningPage,
} = useInventoryDashboard();
const updatedTime = computed(() => (summary.data ? summary.data.as_of.slice(11, 19) : "—"));
</script>
<template>
  <main class="inventory-home">
    <header class="inventory-home__header">
      <div>
        <h1>经营概览</h1>
        <span>{{ summary.data?.today ?? "—" }} · 更新于 {{ updatedTime }}</span>
      </div>
      <ElTooltip content="刷新首页数据"
        ><ElButton :icon="Refresh" :loading="refreshing" aria-label="刷新首页数据" @click="refresh"
      /></ElTooltip>
    </header>
    <HomeMetrics
      :data="summary.data"
      :loading="summary.loading"
      :error="summary.error"
      @retry="loadSummary"
    />
    <HomeCharts
      :trend="trend"
      :warehouses="warehouses"
      :period="period"
      @period="changePeriod"
      @retry-trend="loadTrend"
      @retry-warehouses="loadWarehouses"
    />
    <HomeWarnings
      :state="warnings"
      :page="warningPage"
      @retry="loadWarnings"
      @page="changeWarningPage"
    />
    <HomeRecent :state="recent" @retry="loadRecent" />
  </main>
</template>
<style scoped lang="scss">
.inventory-home {
  min-width: 0;

  &__header {
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: space-between;

    h1 {
      margin: 0 0 6px;
      font-size: 22px;
      font-weight: 600;
    }

    span {
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }
}
</style>
