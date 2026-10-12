import SupplierAPI from "@/api/module_inventory/basic/supplier";
import WarehouseAPI from "@/api/module_inventory/basic/warehouse";

/** 采购表单使用的远程下拉选项。 */
export interface PurchaseOption {
  value: number;
  label: string;
}
/** 加载启用的供应商、仓库并保留单据历史选项。 */
export function usePurchaseOptions() {
  const suppliers = ref<PurchaseOption[]>([]);
  const warehouses = ref<PurchaseOption[]>([]);
  const supplierLoading = ref(false);
  const warehouseLoading = ref(false);
  let supplierSequence = 0;
  let warehouseSequence = 0;
  /** 搜索启用供应商，忽略过期请求。 */
  async function searchSuppliers(keyword = ""): Promise<void> {
    const sequence = ++supplierSequence;
    supplierLoading.value = true;
    try {
      const response = await SupplierAPI.listSupplier({
        page_no: 1,
        page_size: 50,
        supplier_name: keyword || undefined,
        status: 0,
      });
      if (sequence === supplierSequence)
        suppliers.value = response.data.data.items
          .filter((item) => item.id)
          .map((item) => ({ value: item.id!, label: item.supplier_name }));
    } catch {
      if (sequence === supplierSequence) suppliers.value = [];
    } finally {
      if (sequence === supplierSequence) supplierLoading.value = false;
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
    supplierId: number,
    supplierName: string,
    warehouseId: number,
    warehouseName: string
  ): void {
    if (!suppliers.value.some((item) => item.value === supplierId))
      suppliers.value.push({ value: supplierId, label: supplierName });
    if (!warehouses.value.some((item) => item.value === warehouseId))
      warehouses.value.push({ value: warehouseId, label: warehouseName });
  }
  return {
    suppliers,
    warehouses,
    supplierLoading,
    warehouseLoading,
    searchSuppliers,
    searchWarehouses,
    retainOptions,
  };
}
