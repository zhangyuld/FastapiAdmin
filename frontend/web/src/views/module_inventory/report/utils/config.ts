import type {
  ReportKind,
  ReportView,
  ReportRow,
  ReportSummary,
} from "@/api/module_inventory/report/client";
/** 报表字段及指标的模块内展示契约。 */
export interface ReportField {
  key: string;
  label: string;
  width?: number;
  percentage?: boolean;
}
export interface ReportViewOption {
  value: ReportView;
  label: string;
}
export const reportLabels: Record<ReportKind, string> = {
  purchase: "采购报表",
  sale: "销售报表",
  stock: "库存报表",
  profit: "毛利报表",
};
export const warningLabels: Record<string, string> = {
  normal: "正常",
  low: "低于下限",
  high: "高于上限",
};
/** 每个领域仅提供自身有效的报表维度。 */
export function reportViews(kind: ReportKind): ReportViewOption[] {
  return kind === "stock"
    ? [
        { value: "balance", label: "当前库存" },
        { value: "movement", label: "期间变动" },
      ]
    : [
        { value: "documents", label: "单据明细" },
        { value: "goods", label: "商品汇总" },
      ];
}
/** URL 中不合法或跨领域的维度恢复为该领域默认视图。 */
export function reportView(kind: ReportKind, value: unknown): ReportView {
  return (
    reportViews(kind).find((option) => option.value === value)?.value ?? reportViews(kind)[0]!.value
  );
}
/** 指标和表格共用字段标签，毛利率为服务端返回的百分数。 */
function amountFields(kind: ReportKind, view: ReportView): ReportField[] {
  if (kind === "purchase")
    return [
      { key: "purchase_amount", label: "采购金额" },
      { key: "return_amount", label: "退货金额" },
      { key: "net_purchase_amount", label: "净采购金额" },
    ];
  if (kind === "sale")
    return [
      { key: "sale_amount", label: "销售应计金额" },
      { key: "return_amount", label: "退货金额" },
      { key: "net_sale_amount", label: "净销售金额" },
    ];
  if (kind === "profit")
    return [
      { key: "net_sale_amount", label: "净销售金额" },
      { key: "net_cost_amount", label: "净销售成本" },
      { key: "gross_profit", label: "毛利" },
      { key: "gross_margin", label: "毛利率", percentage: true },
    ];
  return view === "balance"
    ? [
        { key: "quantity", label: "库存数量" },
        { key: "avg_cost", label: "平均成本" },
        { key: "stock_amount", label: "库存金额" },
      ]
    : [
        { key: "in_quantity", label: "入库数量" },
        { key: "out_quantity", label: "出库数量" },
        { key: "net_quantity", label: "净变动数量" },
        { key: "in_amount", label: "入库金额" },
        { key: "out_amount", label: "出库金额" },
        { key: "net_amount", label: "净变动金额" },
      ];
}
/** 汇总只显示可跨商品合计的金额，不混合单位求总数量。 */
export function summaryFields(kind: ReportKind, view: ReportView): ReportField[] {
  if (kind === "stock")
    return view === "balance"
      ? [
          { key: "goods_count", label: "商品数" },
          { key: "stock_amount", label: "库存金额" },
        ]
      : [
          { key: "in_amount", label: "入库金额" },
          { key: "out_amount", label: "出库金额" },
          { key: "net_amount", label: "净变动金额" },
        ];
  return kind === "profit"
    ? amountFields(kind, view)
    : [{ key: "document_count", label: "有效单据数" }, ...amountFields(kind, view)];
}
/** 按维度定义表格列，汇总行不伪造来源单号。 */
export function reportFields(kind: ReportKind, view: ReportView): ReportField[] {
  const goods: ReportField[] = [
    { key: "goods_code", label: "商品编码", width: 145 },
    { key: "goods_name", label: "商品名称", width: 170 },
    { key: "spec", label: "规格", width: 120 },
    { key: "unit", label: "单位", width: 80 },
  ];
  const documents: ReportField[] = [
    { key: "business_no", label: "来源单号", width: 210 },
    { key: "business_date", label: "业务日期", width: 130 },
    {
      key: kind === "purchase" ? "supplier_name" : "customer_name",
      label: kind === "purchase" ? "供应商" : "客户",
      width: 160,
    },
  ];
  const quantities: ReportField[] =
    kind === "purchase"
      ? [
          { key: "purchase_quantity", label: "采购数量" },
          { key: "return_quantity", label: "退货数量" },
          { key: "net_quantity", label: "净采购数量" },
        ]
      : [
          { key: "sale_quantity", label: "销售数量" },
          { key: "return_quantity", label: "退货数量" },
          { key: "net_quantity", label: "净销售数量" },
        ];
  return [
    ...(view === "documents" ? documents : goods),
    { key: "warehouse_name", label: "仓库", width: 150 },
    ...(view === "goods" && (kind === "purchase" || kind === "sale") ? quantities : []),
    ...amountFields(kind, view),
    ...(kind === "stock" && view === "balance"
      ? [{ key: "warning", label: "预警", width: 120 }]
      : []),
  ];
}
/** 读取领域联合类型中的展示字段，缺失与不可计算值不显示成零。 */
export function fieldValue(row: ReportRow | ReportSummary | undefined, field: ReportField): string {
  const value = row ? (row as unknown as Record<string, unknown>)[field.key] : undefined;
  if (value === null || value === undefined || value === "") return "—";
  if (field.key === "warning") return warningLabels[String(value)] ?? "—";
  return String(value) + (field.percentage ? "%" : "");
}

/** 导出档案文本避免被当作公式，数量和带方向金额不改变精度。 */
export function exportFieldValue(row: ReportRow, field: ReportField): string {
  const value = fieldValue(row, field);
  const textFields = [
    "business_no",
    "supplier_name",
    "customer_name",
    "warehouse_name",
    "goods_code",
    "goods_name",
    "spec",
    "unit",
  ];
  return textFields.includes(field.key) && /^(?:\s*[=+@-]|[\t\r\n])/.test(value)
    ? "'" + value
    : value;
}
