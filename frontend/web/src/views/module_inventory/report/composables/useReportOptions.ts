import WarehouseAPI from "@/api/module_inventory/basic/warehouse";
import CategoryAPI, { type GoodsCategoryItem } from "@/api/module_inventory/basic/category";
/** 报表模块内档案选择选项。 */
interface ReportOption {
  value: number;
  label: string;
}
/** 有档案查询权限时使用下拉，无权限时由筛选组件改为名称输入。 */
export function useReportOptions() {
  const { hasAuth } = useAuth();
  const canWarehouse = hasAuth("module_inventory:warehouse:query");
  const canCategory = hasAuth("module_inventory:category:query");
  const warehouses = ref<ReportOption[]>([]);
  const categories = ref<ReportOption[]>([]);
  const warehouseLoading = ref(false);
  const failed = reactive({ warehouse: false, category: false });
  let sequence = 0;
  let categorySequence = 0;
  let active = true;
  /** 远程搜索历史仓库，不过滤停用档案，忽略过期结果。 */
  async function searchWarehouses(keyword = ""): Promise<void> {
    if (!canWarehouse || !active) return;
    const request = ++sequence;
    warehouseLoading.value = true;
    failed.warehouse = false;
    try {
      const response = await WarehouseAPI.listWarehouse({
        page_no: 1,
        page_size: 50,
        warehouse_name: keyword || undefined,
      });
      if (active && request === sequence)
        warehouses.value = response.data.data.items
          .filter((row) => row.id)
          .map((row) => ({ value: row.id!, label: row.warehouse_name }));
    } catch {
      if (active && request === sequence) {
        warehouses.value = [];
        failed.warehouse = true;
      }
    } finally {
      if (active && request === sequence) warehouseLoading.value = false;
    }
  }
  /** 展开分类树，层级名称保持在报表模块内部。 */
  function flatten(rows: GoodsCategoryItem[], prefix = ""): ReportOption[] {
    return rows.flatMap((row) => [
      { value: row.id!, label: prefix + row.name },
      ...flatten(row.children ?? [], prefix + row.name + " / "),
    ]);
  }
  /** 分类查询失败时保留重试入口，不阻断商品名称筛选。 */
  async function loadCategories(): Promise<void> {
    if (!canCategory || !active) return;
    const request = ++categorySequence;
    failed.category = false;
    try {
      const response = await CategoryAPI.listCategoryTree();
      if (active && request === categorySequence) categories.value = flatten(response.data.data);
    } catch {
      if (active && request === categorySequence) {
        categories.value = [];
        failed.category = true;
      }
    }
  }
  /** 分别重试失败的档案选项。 */
  function retry(): void {
    if (failed.warehouse) void searchWarehouses();
    if (failed.category) void loadCategories();
  }
  onMounted(() => {
    void searchWarehouses();
    void loadCategories();
  });
  onActivated(() => {
    active = true;
  });
  onDeactivated(() => {
    active = false;
    sequence++;
    categorySequence++;
    warehouseLoading.value = false;
  });
  onBeforeUnmount(() => {
    active = false;
    sequence++;
    categorySequence++;
  });
  return {
    warehouses,
    categories,
    warehouseLoading,
    failed,
    canWarehouse,
    canCategory,
    searchWarehouses,
    retry,
  };
}
