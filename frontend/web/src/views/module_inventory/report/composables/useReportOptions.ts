import { computed, onMounted } from "vue";
import { getWarehouseOptions } from "@/api/module_inventory/basic/options";
import { useArchiveOptions, useCategoryOptions } from "../../basic/composables/useArchiveOptions";

/** 报表使用登录可读的轻量档案，不再按档案管理权限降级输入框。 */
export function useReportOptions() {
  const warehouse = useArchiveOptions({
    fetch: getWarehouseOptions,
    map: (row) => ({
      value: row.id,
      label: row.warehouse_name + (row.status === 1 ? "（停用）" : ""),
    }),
  });
  const category = useCategoryOptions();
  const failed = computed(() => ({
    warehouse: warehouse.state.failed,
    category: category.state.failed,
  }));
  /** 仅重试失败的选项，不重新请求报表数据。 */
  function retry(): void {
    if (warehouse.state.failed) warehouse.selectProps.value.onVisibleChange(true);
    if (category.state.failed) void category.load();
  }
  onMounted(() => {
    void warehouse.search();
    void category.load();
  });
  return {
    warehouses: warehouse.options,
    categories: category.categories,
    warehouseLoading: warehouse.loading,
    failed,
    warehouseSelectProps: warehouse.selectProps,
    categorySelectProps: computed(() => ({
      options: category.categories.value,
      filterable: true,
      clearable: true,
      loading: category.state.loading,
      onVisibleChange: category.onVisibleChange,
    })),
    searchWarehouses: warehouse.search,
    retry,
  };
}
