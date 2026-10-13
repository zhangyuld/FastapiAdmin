import { describe, expect, it } from "vitest";
import type { StockLine } from "@/api/module_inventory/stock/client";
import { scaled, decimal, preview } from "./amount";

/** 构造独立定点数明细，不连接接口。 */
function line(extra: Partial<StockLine>): StockLine {
  return {
    goods_id: 1,
    goods_code: "G1",
    goods_name: "测试商品",
    unit: "件",
    unit_cost: "0.3333",
    ...extra,
  };
}
describe("库存金额定点数", () => {
  it("期初金额按分舍入，避免浮点误差", () => {
    expect(preview(line({ quantity: "3.000" }), "opening")).toEqual({
      difference: "3.000",
      amount: "1.00",
    });
    expect(preview(line({ quantity: "0.001", unit_cost: "5.0000" }), "opening").amount).toBe(
      "0.01"
    );
  });
  it("盘亏采用账面金额比例并结清尾差", () => {
    expect(
      preview(
        line({ system_quantity: "3.000", system_stock_amount: "1.00", actual_quantity: "0.000" }),
        "check"
      )
    ).toEqual({ difference: "-3.000", amount: "-1.00" });
    expect(
      preview(
        line({ system_quantity: "3.000", system_stock_amount: "1.00", actual_quantity: "2.000" }),
        "check"
      ).amount
    ).toBe("-0.33");
  });
  it("盘盈使用原金额与数量比例，而非已舍入单价", () => {
    expect(
      preview(
        line({ system_quantity: "3.000", system_stock_amount: "1.00", actual_quantity: "103.000" }),
        "check"
      ).amount
    ).toBe("33.33");
  });
  it("零库存盘盈需要明确成本，零成本允许", () => {
    const row = line({
      system_quantity: "0.000",
      system_stock_amount: "0.00",
      actual_quantity: "2.000",
      unit_cost: "",
    });
    expect(() => preview(row, "check")).toThrow("填写单位成本");
    expect(preview({ ...row, unit_cost: "0.0000" }, "check").amount).toBe("0.00");
  });
  it("大数往返不丢精度", () => {
    expect(decimal(scaled("999999999999999.999", 3), 3)).toBe("999999999999999.999");
    expect(decimal(-1n, 3)).toBe("-0.001");
  });
  it.each(["-1", "NaN", "1e3", "1.0001", "1000000000000000"])(
    "拒绝非法或超范围数量 %s",
    (input) => {
      expect(() => scaled(input, 3)).toThrow();
    }
  );
});
