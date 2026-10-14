<script setup lang="ts">
import { defineAsyncComponent } from "vue";
import type { EChartsOption } from "@/plugins/echarts";
import type { DashboardTrend, WarehouseStock, TrendPeriod } from "@/api/module_inventory/dashboard";
import type { DashboardPanelState } from "../composables/useInventoryDashboard";
import { formatAmount } from "../utils/metrics";
import HomePanel from "./HomePanel.vue";
/** 两类只读图表，期间只控制经营趋势。 */
const props = defineProps<{
  trend: DashboardPanelState<DashboardTrend>;
  warehouses: DashboardPanelState<WarehouseStock[]>;
  period: TrendPeriod;
}>();
/** 图表分别重试及切换期间。 */
const emit = defineEmits<{ period: [value: TrendPeriod]; retryTrend: []; retryWarehouses: [] }>();
const Chart = defineAsyncComponent(() => import("@/components/charts/fa-echarts/index.vue"));
const periodOptions = [
  { label: "近7天", value: "7d" },
  { label: "近30天", value: "30d" },
  { label: "本月", value: "month" },
];
/** 图表回调仅读取索引，提示使用纯文本及原始金额。 */
function pointIndex(params: unknown): number {
  const first = Array.isArray(params) ? params[0] : params;
  return first && typeof first === "object" && "dataIndex" in first ? Number(first.dataIndex) : -1;
}
/** 分段控件值限制为服务端预置期间。 */
function selectPeriod(value: string | number | boolean): void {
  if (value === "7d" || value === "30d" || value === "month") emit("period", value);
}
const trendOptions = computed<EChartsOption>(() => {
  const points = props.trend.data?.points ?? [];
  const series: EChartsOption["series"] = [];
  if (points.some((point) => point.sale_amount !== null))
    series.push({
      name: "销售净额",
      type: "line",
      data: points.map((point) => Number(point.sale_amount)),
      showSymbol: false,
      itemStyle: { color: "#159a75" },
      lineStyle: { width: 2 },
    });
  if (points.some((point) => point.purchase_amount !== null))
    series.push({
      name: "采购净额",
      type: "line",
      data: points.map((point) => Number(point.purchase_amount)),
      showSymbol: false,
      itemStyle: { color: "#3678d4" },
      lineStyle: { width: 2 },
    });
  return {
    grid: { left: 12, right: 16, bottom: 8, top: 46, containLabel: true },
    legend: { top: 0, textStyle: { color: "#87909c" } },
    tooltip: {
      trigger: "axis",
      renderMode: "richText",
      formatter: (params: unknown) => {
        const point = points[pointIndex(params)];
        return point
          ? [
              point.business_date,
              point.sale_amount !== null ? `销售净额 ¥${formatAmount(point.sale_amount)}` : "",
              point.purchase_amount !== null
                ? `采购净额 ¥${formatAmount(point.purchase_amount)}`
                : "",
            ]
              .filter(Boolean)
              .join("\n")
          : "";
      },
    },
    xAxis: {
      type: "category",
      data: points.map((point) => point.business_date.slice(5)),
      boundaryGap: false,
      axisLabel: { color: "#87909c" },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#87909c" },
      splitLine: { lineStyle: { color: "#87909c", opacity: 0.12 } },
    },
    series,
  };
});
const warehouseOptions = computed<EChartsOption>(() => {
  const rows = props.warehouses.data ?? [];
  return {
    grid: { left: 10, right: 30, top: 12, bottom: 24, containLabel: true },
    tooltip: {
      trigger: "axis",
      renderMode: "richText",
      formatter: (params: unknown) => {
        const row = rows[pointIndex(params)];
        return row ? `${row.warehouse_name}\n库存金额 ¥${formatAmount(row.stock_amount)}` : "";
      },
    },
    xAxis: {
      type: "value",
      axisLabel: { color: "#87909c" },
      splitLine: { lineStyle: { opacity: 0.12 } },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: rows.map((row) => row.warehouse_name),
      axisLabel: { width: 95, overflow: "truncate", color: "#87909c" },
    },
    series: [
      {
        type: "bar",
        data: rows.map((row) => Number(row.stock_amount)),
        barMaxWidth: 18,
        itemStyle: { color: "#159a75" },
      },
    ],
  };
});
const warehouseHeight = computed(
  () => Math.max(280, (props.warehouses.data?.length ?? 0) * 36 + 50) + "px"
);
</script>
<template>
  <div class="home-charts">
    <HomePanel
      title="经营趋势"
      :loading="trend.loading"
      :error="trend.error"
      :forbidden="trend.forbidden"
      :empty="!trend.data?.points.length"
      @retry="emit('retryTrend')"
    >
      <template #actions
        ><ElSegmented
          :model-value="period"
          :options="periodOptions"
          size="small"
          @change="selectPeriod"
      /></template>
      <Chart :key="period" :options="trendOptions" height="280px" />
    </HomePanel>
    <HomePanel
      title="仓库库存金额"
      :loading="warehouses.loading"
      :error="warehouses.error"
      :forbidden="warehouses.forbidden"
      :empty="!warehouses.data?.length"
      @retry="emit('retryWarehouses')"
    >
      <div class="home-charts__warehouses">
        <Chart :options="warehouseOptions" :height="warehouseHeight" />
      </div>
    </HomePanel>
  </div>
</template>
<style scoped lang="scss">
.home-charts {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: 28px;

  &__warehouses {
    max-height: 400px;
    overflow-y: auto;
  }
  @media (width <= 960px) {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }
}
</style>
