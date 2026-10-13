import WarehouseAPI from "@/api/module_inventory/basic/warehouse";
import CategoryAPI, { type GoodsCategoryItem } from "@/api/module_inventory/basic/category";
/** 库存模块内仓库和分类下拉选项。 */
export interface StockOption {
  value: number;
  label: string;
}
/** 查询允许停用档案，录单仅使用启用仓库。 */
export function useStockOptions(enabledOnly = false) {
  const warehouses = ref<StockOption[]>([]);
  const categories = ref<StockOption[]>([]);
  const loading = ref(false);
  let sequence = 0;
  /** 搜索仓库并忽略过期响应。 */
  async function searchWarehouses(keyword = ""): Promise<void> {
    const current = ++sequence;
    loading.value = true;
    try {
      const response = await WarehouseAPI.listWarehouse({
        page_no: 1,
        page_size: 50,
        warehouse_name: keyword || undefined,
        status: enabledOnly ? 0 : undefined,
      });
      if (current === sequence)
        warehouses.value = response.data.data.items
          .filter((row) => row.id)
          .map((row) => ({ value: row.id!, label: row.warehouse_name }));
    } catch {
      if (current === sequence) warehouses.value = [];
    } finally {
      if (current === sequence) loading.value = false;
    }
  }
  /** 查询分类树并转换为带层级名称的选项。 */
  async function loadCategories(): Promise<void> {
    try {
      const response = await CategoryAPI.listCategoryTree();
      /** 仅在模块内展开分类，不改变后端树结构。 */
      function flatten(rows: GoodsCategoryItem[], prefix = ""): StockOption[] {
        return rows.flatMap((row) => [
          { value: row.id!, label: prefix + row.name },
          ...flatten(row.children ?? [], prefix + row.name + " / "),
        ]);
      }
      categories.value = flatten(response.data.data);
    } catch {
      categories.value = [];
    }
  }
  /** 为只读历史单据保留停用仓库展示值。 */
  function retainWarehouse(id: number, name: string): void {
    if (!warehouses.value.some((row) => row.value === id))
      warehouses.value.push({ value: id, label: name });
  }
  return { warehouses, categories, loading, searchWarehouses, loadCategories, retainWarehouse };
}
