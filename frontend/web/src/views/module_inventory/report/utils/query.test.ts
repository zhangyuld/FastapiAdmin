import { describe, expect, it } from "vitest";
import { normalizeReportQuery, reportFilterQuery, reportRouteQuery } from "./query";
import { exportFieldValue, fieldValue, reportFields, summaryFields } from "./config";
import type { ProfitReportRow } from "@/api/module_inventory/report/client";
describe("报表筛选和指标口径", () => {
  it.each([
    { sale: "8.00", cost: "8.99", profit: "-0.99", margin: "-12.38", text: "-12.38%" },
    { sale: "3.00", cost: "-3.00", profit: "6.00", margin: "200.00", text: "200.00%" },
    { sale: "0.00", cost: "5.00", profit: "-5.00", margin: null, text: "—" },
  ])("毛利率 $text 的显示与本地导出一致且不截断比例", ({ sale, cost, profit, margin, text }) => {
    const row: ProfitReportRow = {
      id: "profit",
      net_sale_amount: sale,
      net_cost_amount: cost,
      gross_profit: profit,
      gross_margin: margin,
    };
    const field = { key: "gross_margin", label: "毛利率", percentage: true };
    expect(fieldValue(row, field)).toBe(text);
    expect(exportFieldValue(row, field)).toBe(text);
    expect(exportFieldValue(row, { key: "gross_profit", label: "毛利" })).toBe(profit);
  });
  it("档案导出按字面值处理，负向金额不改变精度", () => {
    const row = {
      id: 1,
      supplier_name: "=2+2",
      purchase_amount: "0.00",
      return_amount: "30.00",
      net_purchase_amount: "-30.00",
    };
    expect(exportFieldValue(row, { key: "supplier_name", label: "供应商" })).toBe("'=2+2");
    expect(exportFieldValue(row, { key: "net_purchase_amount", label: "净采购金额" })).toBe(
      "-30.00"
    );
  });
  it("当前库存剔除日期、对象和来源单号", () => {
    const query = normalizeReportQuery("stock", "balance", {
      business_date: ["2026-10-01", "2026-10-13"],
      customer_name: "客户",
      business_no: "SO1",
      warehouse_id: "2",
      warning: "low",
    });
    expect(query).toEqual({
      view: "balance",
      page_no: 1,
      page_size: 10,
      warehouse_id: 2,
      warning: "low",
    });
  });
  it("期间变动接受有效日期，不携带余额预警", () => {
    const query = normalizeReportQuery("stock", "movement", {
      business_date: ["2026-10-01", "2026-10-13"],
      warning: "high",
    });
    expect(query.business_date).toEqual(["2026-10-01", "2026-10-13"]);
    expect(query.warning).toBeUndefined();
  });
  it("错误日期、逆序、多值 ID 和跨维度条件被剔除", () => {
    const query = normalizeReportQuery("purchase", "goods", {
      business_date: ["2026-02-30", "2026-03-01"],
      warehouse_id: ["2", "3"],
      category_id: 1.5,
      business_no: "PI1",
      customer_name: "客户",
      supplier_name: "  供应商  ",
    });
    expect(query).toEqual({ view: "goods", page_no: 1, page_size: 10, supplier_name: "供应商" });
    expect(
      normalizeReportQuery("sale", "documents", { business_date: ["2026-10-13", "2026-10-01"] })
        .business_date
    ).toBeUndefined();
  });
  it("跨领域视图恢复默认，并按实际视图清洗参数", () => {
    expect(
      normalizeReportQuery("stock", "documents", { business_date: ["2026-10-01", "2026-10-13"] })
        .business_date
    ).toBeUndefined();
    expect(normalizeReportQuery("sale", "balance", {}).view).toBe("documents");
  });
  it("汇总及导出去分页，URL 保留日期数组和精确筛选", () => {
    const query = normalizeReportQuery("purchase", "documents", {
      business_date: ["2026-10-01", "2026-10-13"],
      page_no: 3,
      warehouse_id: 2,
    });
    expect(reportFilterQuery(query)).not.toHaveProperty("page_no");
    expect(reportFilterQuery(query)).not.toHaveProperty("page_size");
    expect(reportRouteQuery(query)).toMatchObject({
      warehouse_id: "2",
      business_date: ["2026-10-01", "2026-10-13"],
    });
  });
  it("未接入与不可计算的指标不显示零，不跨单位汇总数量", () => {
    expect(fieldValue(undefined, { key: "gross_profit", label: "毛利" })).toBe("—");
    expect(
      fieldValue(
        {
          net_sale_amount: "0.00",
          net_cost_amount: "0.00",
          gross_profit: "0.00",
          gross_margin: null,
        },
        { key: "gross_margin", label: "毛利率", percentage: true }
      )
    ).toBe("—");
    expect(
      fieldValue(
        {
          net_sale_amount: "3.00",
          net_cost_amount: "2.00",
          gross_profit: "1.00",
          gross_margin: "33.33",
        },
        { key: "gross_margin", label: "毛利率", percentage: true }
      )
    ).toBe("33.33%");
    expect(summaryFields("purchase", "goods").some((field) => field.key.includes("quantity"))).toBe(
      false
    );
  });
  it("库存净变动不当作库存余额，明细与商品列独立", () => {
    expect(reportFields("stock", "movement").map((field) => field.key)).not.toContain("quantity");
    expect(reportFields("stock", "balance").map((field) => field.key)).not.toContain(
      "net_quantity"
    );
    expect(reportFields("sale", "goods").map((field) => field.key)).not.toContain("business_no");
  });
});
