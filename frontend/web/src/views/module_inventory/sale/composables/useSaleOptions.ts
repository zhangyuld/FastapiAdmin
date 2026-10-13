import CustomerAPI from "@/api/module_inventory/basic/customer";
import WarehouseAPI from "@/api/module_inventory/basic/warehouse";

/** 销售表单使用的远程下拉选项。 */
export interface SaleOption {
  value: number;
  label: string;
}
/** 加载启用的客户、仓库并保留单据历史选项。 */
export function useSaleOptions() {
  const customers = ref<SaleOption[]>([]);
  const warehouses = ref<SaleOption[]>([]);
  const customerLoading = ref(false);
  const warehouseLoading = ref(false);
  let customerSequence = 0;
  let warehouseSequence = 0;
  /** 搜索启用客户，忽略过期请求。 */
  async function searchCustomers(keyword = ""): Promise<void> {
    const sequence = ++customerSequence;
    customerLoading.value = true;
    try {
      const response = await CustomerAPI.listCustomer({
        page_no: 1,
        page_size: 50,
        customer_name: keyword || undefined,
        status: 0,
      });
      if (sequence === customerSequence)
        customers.value = response.data.data.items
          .filter((item) => item.id)
          .map((item) => ({ value: item.id!, label: item.customer_name }));
    } catch {
      if (sequence === customerSequence) customers.value = [];
    } finally {
      if (sequence === customerSequence) customerLoading.value = false;
    }
  }
  /** 搜索启用仓库，忽略过期请求。 */
  async function searchWarehouses(keyword = ""): Promise<void> {
    const sequence = ++warehouseSequence;
    warehouseLoading.value = true;
    try {
      const response = await WarehouseAPI.listWarehouse({
        page_no: 1,
        page_size: 50,
        warehouse_name: keyword || undefined,
        status: 0,
      });
      if (sequence === warehouseSequence)
        warehouses.value = response.data.data.items
          .filter((item) => item.id)
          .map((item) => ({ value: item.id!, label: item.warehouse_name }));
    } catch {
      if (sequence === warehouseSequence) warehouses.value = [];
    } finally {
      if (sequence === warehouseSequence) warehouseLoading.value = false;
    }
  }
  /** 为历史单据补入未在当前搜索结果中的选项。 */
  function retainOptions(
    customerId: number,
    customerName: string,
    warehouseId: number,
    warehouseName: string
  ): void {
    if (!customers.value.some((item) => item.value === customerId))
      customers.value.push({ value: customerId, label: customerName });
    if (!warehouses.value.some((item) => item.value === warehouseId))
      warehouses.value.push({ value: warehouseId, label: warehouseName });
  }
  return {
    customers,
    warehouses,
    customerLoading,
    warehouseLoading,
    searchCustomers,
    searchWarehouses,
    retainOptions,
  };
}
