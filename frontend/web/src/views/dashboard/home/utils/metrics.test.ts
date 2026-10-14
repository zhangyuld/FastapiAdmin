import { describe, expect, it } from "vitest";
import { dashboardMetrics, formatAmount } from "./metrics";
import type { DashboardSummary } from "@/api/module_inventory/dashboard";

describe("首页经营指标", () => {
  it("大额定点字符串和负额不经过浮点转换", () => {
    expect(formatAmount("9999999999999999.99")).toBe("9,999,999,999,999,999.99");
    expect(formatAmount("-30.00")).toBe("-30.00");
    expect(formatAmount("0.00")).toBe("0.00");
    expect(formatAmount(null)).toBe("—");
  });
  it("未加载、未授权及真实零分别保留", () => {
    const initial = dashboardMetrics();
    expect(initial.every((row) => row.value === undefined)).toBe(true);
    const summary: DashboardSummary = {
      as_of: "2026-10-14T08:00:00+08:00",
      today: "2026-10-14",
      sale_today: { net_amount: "0.00", return_amount: "0.00" },
      sale_month: { net_amount: "100.00", return_amount: "30.00" },
      purchase_today: null,
      purchase_month: null,
      stock_amount: null,
      warning_count: null,
      receivable: { positive_balance: "60.00", negative_balance: "40.00" },
      payable: null,
    };
    const items = dashboardMetrics(summary);
    expect(items).toHaveLength(8);
    expect(items.find((row) => row.key === "sale_today")?.value).toBe("0.00");
    expect(items.find((row) => row.key === "purchase_today")?.value).toBeNull();
    expect(items.find((row) => row.key === "receivable")?.value).toBe("60.00");
    expect(items.find((row) => row.key === "receivable")?.detail).toContain("40.00");
  });
});
