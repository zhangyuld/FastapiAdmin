import { computed, onActivated, onDeactivated, onMounted, onUnmounted, reactive, ref } from "vue";
import { checkPerm } from "@/utils/checkPerm";
import {
  getDashboardSummary,
  getDashboardTrend,
  getWarehouseStock,
  getStockWarnings,
  getRecentDocuments,
  type DashboardSummary,
  type DashboardTrend,
  type WarehouseStock,
  type StockWarning,
  type RecentDocument,
  type TrendPeriod,
} from "@/api/module_inventory/dashboard";

/** 面板未加载、失败及无权限状态彼此独立。 */
export interface DashboardPanelState<T> {
  data?: T;
  loading: boolean;
  error: boolean;
  forbidden: boolean;
  sequence: number;
}
/** 创建局部面板状态，不缓存上一个账号的业务数据。 */
function panel<T>(): DashboardPanelState<T> {
  return { loading: false, error: false, forbidden: false, sequence: 0 };
}
/** 首页请求与失效管理，切换趋势和分页不影响其他区域。 */
export function useInventoryDashboard() {
  const summary = reactive(panel<DashboardSummary>());
  const trend = reactive(panel<DashboardTrend>());
  const warehouses = reactive(panel<WarehouseStock[]>());
  const warnings = reactive(panel<PageResult<StockWarning>>());
  const recent = reactive(panel<RecentDocument[]>());
  const period = ref<TrendPeriod>("30d");
  const warningPage = ref(1);
  let active = true;
  let mounted = false;
  const canTrend = computed(
    () =>
      checkPerm("module_inventory:sale_report:query") ||
      checkPerm("module_inventory:purchase_report:query")
  );
  const canStock = computed(() => checkPerm("module_inventory:stock_report:query"));
  const canRecent = computed(() =>
    ["purchase_in", "purchase_return", "sale_out", "sale_return"].some((kind) =>
      checkPerm(`module_inventory:${kind}:query`)
    )
  );
  const states = [summary, trend, warehouses, warnings, recent];
  const refreshing = computed(() => states.some((state) => state.loading));

  /** 忽略旧请求和离开页面后的回包，失败时清除过期数据。 */
  async function load<T>(
    state: DashboardPanelState<T>,
    allowed: boolean,
    fetch: () => Promise<T>
  ): Promise<void> {
    const sequence = ++state.sequence;
    state.data = undefined;
    state.error = false;
    state.forbidden = !allowed;
    state.loading = false;
    if (!allowed || !active) return;
    state.loading = true;
    try {
      const data = await fetch();
      if (active && sequence === state.sequence) state.data = data;
    } catch (error) {
      if (active && sequence === state.sequence) {
        const failure = error as { response?: { status?: number }; status?: number; code?: number };
        const status = failure?.response?.status ?? failure?.status ?? failure?.code;
        state.forbidden = status === 403;
        state.error = !state.forbidden;
      }
    } finally {
      if (sequence === state.sequence) state.loading = false;
    }
  }
  /** 重新读取全部经营指标。 */
  function loadSummary(): Promise<void> {
    return load(summary, true, async () => (await getDashboardSummary()).data.data);
  }
  /** 只刷新趋势期间。 */
  function loadTrend(): Promise<void> {
    return load(
      trend,
      canTrend.value,
      async () => (await getDashboardTrend({ period: period.value })).data.data
    );
  }
  /** 只刷新当前仓库金额。 */
  function loadWarehouses(): Promise<void> {
    return load(warehouses, canStock.value, async () => (await getWarehouseStock()).data.data);
  }
  /** 分页预警采用独立请求序号。 */
  function loadWarnings(): Promise<void> {
    return load(
      warnings,
      canStock.value,
      async () => (await getStockWarnings({ page_no: warningPage.value, page_size: 5 })).data.data
    );
  }
  /** 只刷新原业务权限范围内最近单据。 */
  function loadRecent(): Promise<void> {
    return load(
      recent,
      canRecent.value,
      async () => (await getRecentDocuments({ limit: 8 })).data.data
    );
  }
  /** 各区域独立完成或失败，不互相阻塞。 */
  async function refresh(): Promise<void> {
    await Promise.all([loadSummary(), loadTrend(), loadWarehouses(), loadWarnings(), loadRecent()]);
  }
  /** 切换趋势时立即淘汰上一期间请求。 */
  function changePeriod(value: TrendPeriod): void {
    period.value = value;
    void loadTrend();
  }
  /** 切换预警页，不重新读取指标和图表。 */
  function changeWarningPage(value: number): void {
    warningPage.value = value;
    void loadWarnings();
  }
  /** 停用缓存页面时使所有未完成请求失效。 */
  function deactivate(): void {
    active = false;
    states.forEach((state) => {
      state.sequence++;
      state.loading = false;
    });
  }
  onMounted(() => {
    mounted = true;
    void refresh();
  });
  onActivated(() => {
    if (!active && mounted) {
      active = true;
      void refresh();
    }
  });
  onDeactivated(deactivate);
  onUnmounted(deactivate);
  return {
    summary,
    trend,
    warehouses,
    warnings,
    recent,
    period,
    warningPage,
    refreshing,
    refresh,
    loadSummary,
    loadTrend,
    loadWarehouses,
    loadWarnings,
    loadRecent,
    changePeriod,
    changeWarningPage,
  };
}
