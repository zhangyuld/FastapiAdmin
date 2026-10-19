import { getSupplierOptions, getWarehouseOptions } from "@/api/module_inventory/basic/options";
import {
  useArchiveOptions,
  type ArchiveSelectOption,
} from "../../basic/composables/useArchiveOptions";

/** 采购模块下拉展示项，不包含基础档案管理详情。 */
export type PurchaseOption = ArchiveSelectOption;

/** 录单只选启用档案，历史查询包含停用档案。 */
export function usePurchaseOptions(enabledOnly = false) {
  const supplier = useArchiveOptions({
    fetch: getSupplierOptions,
    enabledOnly,
    map: (row) => ({
      value: row.id,
      label: row.supplier_name + (row.status === 1 ? "（停用）" : ""),
    }),
  });
  const warehouse = useArchiveOptions({
    fetch: getWarehouseOptions,
    enabledOnly,
    map: (row) => ({
      value: row.id,
      label: row.warehouse_name + (row.status === 1 ? "（停用）" : ""),
    }),
  });
  /** 历史名称由单据携带，不请求档案管理详情。 */
  function retainOptions(
    supplierId: number,
    supplierName: string,
    warehouseId: number,
    warehouseName: string
  ): void {
    supplier.retain(supplierId, supplierName);
    warehouse.retain(warehouseId, warehouseName);
  }
  return {
    suppliers: supplier.options,
    warehouses: warehouse.options,
    supplierLoading: supplier.loading,
    warehouseLoading: warehouse.loading,
    supplierSelectProps: supplier.selectProps,
    warehouseSelectProps: warehouse.selectProps,
    searchSuppliers: supplier.search,
    searchWarehouses: warehouse.search,
    retainOptions,
  };
}
