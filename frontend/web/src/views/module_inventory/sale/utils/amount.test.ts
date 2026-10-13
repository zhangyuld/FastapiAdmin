import { describe, expect, it } from "vitest";
import type { SaleLine } from "@/api/module_inventory/sale/client";
import {
  scaledDecimal,
  decimalText,
  lineAmount,
  totalAmount,
  receivableAmount,
  returnLineAmount,
  returnTotalAmount,
  displayAmount,
  storedTotalAmount,
} from "./amount";

/** 构建含可退金额的销售明细。 */
function line(values: Partial<SaleLine> = {}): SaleLine {
  return {
    line_no: 1,
    goods_id: 1,
    goods_code: "G1",
    goods_name: "商品",
    unit: "件",
    quantity: "2.000",
    unit_price: "10.0000",
    line_amount: "20.00",
    returnable_quantity: "2.000",
    returnable_amount: "16.00",
    ...values,
  };
}
describe("销售金额与退款预估", () => {
  it("按分逐行舍入，优惠减法不产生浮点误差", () => {
    const lines = [
      line({ quantity: "1.000", unit_price: "0.0050" }),
      line({ quantity: "1.000", unit_price: "0.0050" }),
    ];
    expect(totalAmount(lines)).toBe("0.02");
    expect(receivableAmount(lines, "0.01")).toBe("0.01");
    expect(lineAmount("0.100", "0.2000")).toBe("0.02");
  });
  it("允许零售价和全额优惠", () => {
    expect(receivableAmount([line()], "20.00")).toBe("0.00");
    expect(lineAmount("1", "0")).toBe("0.00");
  });
  it("优惠不能超过原价", () => {
    expect(() => receivableAmount([line()], "20.01")).toThrow("优惠金额");
  });
  it.each(["-1", "1e2", "", "NaN", "1.001"])("拒绝非法或超精度金额 %s", (value) => {
    expect(() => scaledDecimal(value, 2)).toThrow();
  });
  it("拒绝超过数据库范围，保留大金额展示精度", () => {
    expect(() => scaledDecimal("10000000000000000.00", 2)).toThrow();
    expect(displayAmount("9999999999999999.99")).toBe("9,999,999,999,999,999.99");
    expect(() => decimalText(-1n, 2)).toThrow();
  });
  it("退款使用优惠后额度，不等于原单价乘数量", () => {
    expect(returnLineAmount(line({ quantity: "1.000" }))).toBe("8.00");
    expect(returnTotalAmount([line()])).toBe("16.00");
  });
  it("全退剩余额度保留尾差，免费商品可退金额为零", () => {
    expect(
      returnLineAmount(
        line({ quantity: "0.500", returnable_quantity: "0.500", returnable_amount: "0.01" })
      )
    ).toBe("0.01");
    expect(returnLineAmount(line({ returnable_amount: "0.00" }))).toBe("0.00");
  });
  it("可退额度缺失或数量超限时拒绝预估", () => {
    expect(() => returnLineAmount(line({ returnable_amount: undefined }))).toThrow("来源接口");
    expect(() => returnLineAmount(line({ quantity: "2.001" }))).toThrow("可退数量");
  });
  it("只读使用固化金额，缺失金额不展示为零", () => {
    expect(storedTotalAmount([line({ line_amount: "0.01" })])).toBe("0.01");
    expect(displayAmount(undefined)).toBe("-");
  });
});
