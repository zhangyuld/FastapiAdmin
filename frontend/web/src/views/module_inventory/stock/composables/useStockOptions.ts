import { computed } from "vue";
import { getWarehouseOptions } from "@/api/module_inventory/basic/options";
import {
  useArchiveOptions,
  useCategoryOptions,
  type ArchiveSelectOption,
} from "../../basic/composables/useArchiveOptions";

/** 库存模块内部的档案选择项。 */
export type StockOption = ArchiveSelectOption;

/** 库存查询允许停用档案，期初及盘点录单只选启用仓库。 */
export function useStockOptions(enabledOnly = false) {
  const warehouse = useArchiveOptions({
    fetch: getWarehouseOptions,
    enabledOnly,
    map: (row) => ({
      value: row.id,
      label: row.warehouse_name + (row.status === 1 ? "（停用）" : ""),
    }),
  });
  const category = useCategoryOptions();
  return {
    warehouses: warehouse.options,
    categories: category.categories,
    loading: warehouse.loading,
    warehouseSelectProps: warehouse.selectProps,
    categorySelectProps: computed(() => ({
      options: category.categories.value,
      filterable: true,
      clearable: true,
      loading: category.state.loading,
      onVisibleChange: category.onVisibleChange,
      noDataText: category.state.failed ? "加载失败，请重新打开重试" : "暂无数据",
    })),
    searchWarehouses: warehouse.search,
    loadCategories: category.load,
    retainWarehouse: warehouse.retain,
  };
}
