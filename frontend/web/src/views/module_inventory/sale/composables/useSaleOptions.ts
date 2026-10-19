import { getCustomerOptions, getWarehouseOptions } from "@/api/module_inventory/basic/options";
import {
  useArchiveOptions,
  type ArchiveSelectOption,
} from "../../basic/composables/useArchiveOptions";

/** 销售模块下拉展示项。 */
export type SaleOption = ArchiveSelectOption;

/** 录单只选启用客户和仓库，历史查询包含停用档案。 */
export function useSaleOptions(enabledOnly = false) {
  const customer = useArchiveOptions({
    fetch: getCustomerOptions,
    enabledOnly,
    map: (row) => ({
      value: row.id,
      label: row.customer_name + (row.status === 1 ? "（停用）" : ""),
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
  /** 保留原单名称，不扩大客户或仓库详情权限。 */
  function retainOptions(
    customerId: number,
    customerName: string,
    warehouseId: number,
    warehouseName: string
  ): void {
    customer.retain(customerId, customerName);
    warehouse.retain(warehouseId, warehouseName);
  }
  return {
    customers: customer.options,
    warehouses: warehouse.options,
    customerLoading: customer.loading,
    warehouseLoading: warehouse.loading,
    customerSelectProps: customer.selectProps,
    warehouseSelectProps: warehouse.selectProps,
    searchCustomers: customer.search,
    searchWarehouses: warehouse.search,
    retainOptions,
  };
}
