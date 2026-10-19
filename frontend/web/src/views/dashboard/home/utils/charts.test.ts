import { describe, expect, it } from "vitest";
import type { WarehouseStock } from "@/api/module_inventory/dashboard";
import { buildWarehouseChartOptions, pointIndex } from "./charts";

/** 生成仓库绘图样本，保留金额字符串作为提示的唯一来源。 */
function warehouses(count: number): WarehouseStock[] {
  return Array.from({ length: count }, (_, index) => ({
    warehouse_id: index + 1,
    warehouse_name: `仓库${index + 1}`,
    stock_amount: `${index + 1}.25`,
  }));
}

/** 调用纯文本提示回调，不依赖浏览器 canvas。 */
function tooltip(rows: WarehouseStock[], params: unknown): string {
  const options = buildWarehouseChartOptions(rows);
  return (options.tooltip as { formatter: (value: unknown) => string }).formatter(params);
}

describe("首页仓库金额图", () => {
  it("X轴为仓库分类，Y轴为库存金额，保留服务端顺序", () => {
    const options = buildWarehouseChartOptions(warehouses(2));
    expect(options.xAxis).toMatchObject({
      type: "category",
      name: "仓库",
      data: ["仓库1", "仓库2"],
    });
    expect(options.yAxis).toMatchObject({ type: "value", name: "金额（元）" });
    expect(options.series).toMatchObject([{ type: "bar", data: [1.25, 2.25] }]);
  });

  it("少量仓库无需显示缩放条，长名称轴标签截断", () => {
    const options = buildWarehouseChartOptions(warehouses(4));
    expect(options.dataZoom).toMatchObject([{ show: false }, { disabled: true }]);
    expect(options.xAxis).toMatchObject({ axisLabel: { interval: 0, overflow: "truncate" } });
  });

  it("超过四个仓库时启用横向缩放，保留全部分类和金额", () => {
    const options = buildWarehouseChartOptions(warehouses(12));
    expect(options.dataZoom).toMatchObject([
      { type: "slider", show: true, xAxisIndex: 0, startValue: 0, endValue: 3 },
      { type: "inside", disabled: false, xAxisIndex: 0 },
    ]);
    expect(options.xAxis).toMatchObject({ data: warehouses(12).map((row) => row.warehouse_name) });
    expect(options.series).toMatchObject([
      { data: warehouses(12).map((row) => Number(row.stock_amount)) },
    ]);
    expect(tooltip(warehouses(12), [{ dataIndex: 8 }])).toBe("仓库9\n库存金额 ¥9.25");
  });

  it("长名称完整分行，提示大金额仍使用原始定点字符串", () => {
    const name = "华东区域成品中心超长名称测试仓库";
    const text = tooltip(
      [{ warehouse_id: 1, warehouse_name: name, stock_amount: "9999999999999999.99" }],
      { dataIndex: 0 }
    );
    expect(text.split("\n").slice(0, -1).join("")).toBe(name);
    expect(text).toContain("库存金额 ¥9,999,999,999,999,999.99");
  });

  it.each(["0.00", "-2.50"])("保留金额 %s 的方向与精度", (amount) => {
    const row = { warehouse_id: 1, warehouse_name: "仓库", stock_amount: amount };
    expect(tooltip([row], { dataIndex: 0 })).toBe(`仓库\n库存金额 ¥${amount}`);
  });

  it("空数据和无效提示索引安全返回，不生成负缩放索引", () => {
    const options = buildWarehouseChartOptions([]);
    expect(options.dataZoom).toMatchObject([{ show: false, endValue: 0 }, { disabled: true }]);
    expect(tooltip([], { dataIndex: 0 })).toBe("");
    expect(tooltip(warehouses(2), undefined)).toBe("");
    expect(pointIndex([])).toBe(-1);
    expect(pointIndex([{ dataIndex: 2 }])).toBe(2);
  });
});
