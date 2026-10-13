import { describe, expect, it } from "vitest";
import type { PurchaseLine } from "@/api/module_inventory/purchase/client";
import { scaledDecimal, lineAmount, storedTotalAmount, totalAmount } from "./amount";

describe("采购金额预览", () => {
  it("详情合计保留后端退货尾差，不按单价重新计算", () => {
    const lines = [
      { quantity: "0.500", unit_price: "0.0050", line_amount: "0.01" },
    ] as PurchaseLine[];
    expect(totalAmount(lines)).toBe("0.00");
    expect(storedTotalAmount(lines)).toBe("0.01");
    expect(storedTotalAmount([])).toBe("0.00");
  });
  it("按数量三位、单价四位计算并四舍五入到分", () => {
    expect(lineAmount("0.100", "0.2000")).toBe("0.02");
    expect(lineAmount("1.000", "1.0050")).toBe("1.01");
    expect(lineAmount("1.000", "1.0049")).toBe("1.00");
    expect(lineAmount("0.001", "5.0000")).toBe("0.01");
  });
  it("大数使用整数运算，不丢失分位", () => {
    expect(lineAmount("999999999.999", "9999999.9999")).toBe("9999999999890000.00");
  });
  it("拒绝非法数值和超出精度的非零小数", () => {
    for (const value of ["", "-1", "NaN", "1e3", "1.0001"]) {
      expect(() => scaledDecimal(value, 3)).toThrow();
    }
    expect(scaledDecimal("1.2300", 3)).toBe(1230n);
  });
  it("总额累加已经舍入的行金额", () => {
    const lines = [
      { quantity: "1.000", unit_price: "0.0050" },
      { quantity: "1.000", unit_price: "0.0050" },
    ] as PurchaseLine[];
    expect(totalAmount(lines)).toBe("0.02");
    expect(totalAmount([])).toBe("0.00");
  });
});
