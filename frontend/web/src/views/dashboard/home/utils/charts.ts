import type { EChartsOption } from "@/plugins/echarts";
import type { WarehouseStock } from "@/api/module_inventory/dashboard";
import { formatAmount } from "./metrics";

/** 提示仅读取原始索引，缩放后仍取服务端定点金额。 */
export function pointIndex(params: unknown): number {
  const first = Array.isArray(params) ? params[0] : params;
  return first && typeof first === "object" && "dataIndex" in first ? Number(first.dataIndex) : -1;
}

/** 仓库名称作分类轴，多仓库通过缩放查看而非截断数据。 */
export function buildWarehouseChartOptions(rows: WarehouseStock[]): EChartsOption {
  const visibleCount = 4;
  const hasZoom = rows.length > visibleCount;
  const endValue = Math.max(0, Math.min(rows.length, visibleCount) - 1);
  return {
    grid: { left: 12, right: 16, top: 32, bottom: hasZoom ? 70 : 38, containLabel: true },
    tooltip: {
      trigger: "axis",
      confine: true,
      renderMode: "richText",
      formatter: (params: unknown): string => {
        const row = rows[pointIndex(params)];
        if (!row) return "";
        // 长名称分行展示，窄屏提示也能保留完整仓库名称。
        const characters = Array.from(row.warehouse_name);
        const lines: string[] = [];
        for (let offset = 0; offset < characters.length; offset += 12)
          lines.push(characters.slice(offset, offset + 12).join(""));
        return [...lines, `库存金额 ¥${formatAmount(row.stock_amount)}`].join("\n");
      },
    },
    xAxis: {
      type: "category",
      name: "仓库",
      nameLocation: "middle",
      nameGap: 30,
      nameTextStyle: { color: "#87909c" },
      data: rows.map((row) => row.warehouse_name),
      axisLabel: { interval: 0, width: 52, overflow: "truncate", color: "#87909c" },
    },
    yAxis: {
      type: "value",
      name: "金额（元）",
      nameTextStyle: { color: "#87909c" },
      axisLabel: { color: "#87909c" },
      splitLine: { lineStyle: { color: "#87909c", opacity: 0.12 } },
    },
    dataZoom: [
      {
        type: "slider",
        show: hasZoom,
        xAxisIndex: 0,
        startValue: 0,
        endValue,
        bottom: 4,
        height: 18,
        showDetail: false,
        brushSelect: false,
      },
      {
        type: "inside",
        disabled: !hasZoom,
        xAxisIndex: 0,
        startValue: 0,
        endValue,
        zoomOnMouseWheel: false,
        moveOnMouseWheel: false,
      },
    ],
    series: [
      {
        name: "库存金额",
        type: "bar",
        data: rows.map((row) => Number(row.stock_amount)),
        barMaxWidth: 32,
        itemStyle: { color: "#159a75" },
      },
    ],
  };
}
