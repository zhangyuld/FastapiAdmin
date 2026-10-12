/** 采购单据种类。 */
export type PurchaseKind = "in" | "return";
/** 草稿、已确认、已作废。 */
export type PurchaseStatus = 0 | 1 | 2;
/** 十进制数据以字符串传输。 */
export type PurchaseDecimal = string | number;
/** 采购列表查询参数。 */
export interface PurchaseQuery extends Partial<PageQuery>, UserByQueryParams {
  order_no?: string;
  supplier_id?: number;
  warehouse_id?: number;
  business_date?: string[];
  source_order_no?: string;
  status?: PurchaseStatus;
}
/** 商品明细及来源入库快照。 */
export interface PurchaseLine {
  id?: number;
  line_no: number;
  goods_id: number;
  goods_code: string;
  goods_name: string;
  spec?: string | null;
  unit: string;
  quantity: PurchaseDecimal;
  unit_price: PurchaseDecimal;
  line_amount: PurchaseDecimal;
  source_purchase_in_item_id?: number;
  /** 后端计算的可退数量，编辑时须包含本单原有数量。 */
  returnable_quantity?: PurchaseDecimal;
  unit_cost?: PurchaseDecimal;
  cost_amount?: PurchaseDecimal;
  /** 原入库明细累计已确认且未作废的退货数量。 */
  returned_quantity?: PurchaseDecimal;
}
/** 原入库单实际退货汇总，统计不受下游单据数据范围影响。 */
export interface PurchaseReturnSummary {
  return_status: "none" | "partial" | "full";
  confirmed_count: number;
  returned_amount: PurchaseDecimal;
}
/** 当前用户可见的关联退货摘要。 */
export interface RelatedPurchaseReturn {
  id: number;
  order_no: string;
  business_date: string;
  status: PurchaseStatus;
  total_amount: PurchaseDecimal;
  return_reason: string;
  confirmed_time?: string | null;
}
/** 采购列表记录；详情同时返回 items。 */
export interface PurchaseDocument extends BaseType {
  id: number;
  order_no: string;
  supplier_id: number;
  supplier_name: string;
  warehouse_id: number;
  warehouse_name: string;
  business_date: string;
  total_amount: PurchaseDecimal;
  status: PurchaseStatus;
  version: number;
  remark?: string | null;
  source_purchase_in_id?: number;
  source_order_no?: string | null;
  return_reason?: string;
  confirmed_name?: string;
  confirmed_time?: string;
  voided_name?: string;
  voided_time?: string;
  void_reason?: string;
  items?: PurchaseLine[];
  return_summary?: PurchaseReturnSummary;
}
/** 保存明细输入，金额、成本与快照由后端生成。 */
export interface PurchaseLineInput {
  goods_id: number;
  quantity: string;
  unit_price: string;
  source_purchase_in_item_id?: number;
}
/** 单据保存参数，编辑必须携带 version。 */
export interface PurchaseSaveBody {
  supplier_id: number;
  warehouse_id: number;
  business_date: string;
  remark: string;
  version?: number;
  source_purchase_in_id?: number;
  return_reason?: string;
  items: PurchaseLineInput[];
}
