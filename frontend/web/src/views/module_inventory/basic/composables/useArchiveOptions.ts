import { computed, onActivated, onBeforeUnmount, onDeactivated, reactive, ref } from "vue";
import type { AxiosPromise } from "axios";
import type { ArchiveOptionsQuery } from "@/api/module_inventory/basic/options";
import { getCategoryOptions, type CategoryOptionItem } from "@/api/module_inventory/basic/options";

/** 进销存模块内部使用的下拉选项，历史停用值可展示但不能新选。 */
export interface ArchiveSelectOption {
  value: number;
  label: string;
  disabled?: boolean;
}
/** 单个远程选项列表的请求状态，不放入全局Store。 */
interface ArchiveOptionState {
  loading: boolean;
  failed: boolean;
  loaded: boolean;
  page: number;
  hasNext: boolean;
  keyword: string;
}
/** 分类选项在缓存恢复时区分未加载、空结果和请求失败。 */
interface CategoryOptionState {
  loading: boolean;
  failed: boolean;
  loaded: boolean;
}
/** 轻量档案加载器及显示映射。 */
interface ArchiveOptionConfig<T> {
  fetch: (query: ArchiveOptionsQuery) => AxiosPromise<ApiResponse<PageResult<T>>>;
  map: (row: T) => ArchiveSelectOption;
  enabledOnly?: boolean;
}

/** 分页搜索、触底追加、失败重试和历史值回显，限定在进销存模块内复用。 */
export function useArchiveOptions<T>({ fetch, map, enabledOnly = false }: ArchiveOptionConfig<T>) {
  const options = ref<ArchiveSelectOption[]>([]);
  const state = reactive<ArchiveOptionState>({
    loading: false,
    failed: false,
    loaded: false,
    page: 0,
    hasNext: false,
    keyword: "",
  });
  const retained = new Map<number, ArchiveSelectOption>();
  let sequence = 0;
  let active = true;

  /** 保留单据携带的历史显示值，启用专用列表中不能重新选择历史停用档案。 */
  function retain(value: number, label: string): void {
    if (options.value.some((item) => item.value === value)) return;
    const option = { value, label, disabled: enabledOnly };
    retained.set(value, option);
    options.value = [...options.value, option];
  }

  /** 请求指定页，仅当前请求可以写回；下一页失败不推进页码或丢弃已加载数据。 */
  async function load(page: number, keyword: string, replace: boolean): Promise<void> {
    if (!active || (!replace && state.loading)) return;
    const current = ++sequence;
    state.loading = true;
    state.failed = false;
    try {
      const response = await fetch({
        keyword: keyword || undefined,
        status: enabledOnly ? 0 : undefined,
        page_no: page,
        page_size: 50,
      });
      if (!active || current !== sequence) return;
      const data = response.data.data;
      const merged = new Map<number, ArchiveSelectOption>();
      for (const option of [...(replace ? [] : options.value), ...data.items.map(map)])
        merged.set(option.value, option);
      for (const [id, option] of retained) if (!merged.has(id)) merged.set(id, option);
      options.value = [...merged.values()];
      state.page = page;
      state.hasNext = data.has_next ?? page * 50 < data.total;
      state.loaded = true;
    } catch {
      if (active && current === sequence) state.failed = true;
    } finally {
      if (active && current === sequence) state.loading = false;
    }
  }

  /** 新关键词从第一页开始，取消旧请求回写，避免混入上次搜索结果。 */
  async function search(keyword = ""): Promise<void> {
    if (!active) return;
    state.keyword = keyword.trim();
    state.page = 0;
    state.loaded = false;
    state.hasNext = false;
    options.value = [...retained.values()];
    await load(1, state.keyword, true);
  }

  /** 到达选项底部时继续加载，不局限于第一页50条。 */
  async function loadMore(direction = "bottom"): Promise<void> {
    if (direction === "bottom" && state.hasNext) await load(state.page + 1, state.keyword, false);
  }

  /** 重新打开失败的下拉时重试失败页；未初始化时加载第一页。 */
  function onVisibleChange(visible: boolean): void {
    if (!visible || state.loading) return;
    if (!state.loaded) void search(state.keyword);
    else if (state.failed) void load(state.page + 1, state.keyword, false);
  }

  const selectProps = computed(() => ({
    options: options.value,
    filterable: true,
    remote: true,
    clearable: true,
    remoteMethod: search,
    loading: state.loading && !state.loaded,
    onEndReached: loadMore,
    onVisibleChange,
    noDataText: state.failed ? "加载失败，请重新打开重试" : "暂无数据",
  }));
  onActivated(() => {
    active = true;
  });
  /** 离开缓存页面后废弃异步回写，不改变其他页面的选项状态。 */
  function deactivate(): void {
    active = false;
    sequence++;
    state.loading = false;
  }
  onDeactivated(deactivate);
  onBeforeUnmount(deactivate);
  return {
    options,
    state,
    loading: computed(() => state.loading),
    selectProps,
    search,
    loadMore,
    retain,
  };
}

/** 展开轻量分类树，层级名称用于业务筛选。 */
export function flattenCategoryOptions(
  rows: CategoryOptionItem[],
  prefix = ""
): ArchiveSelectOption[] {
  return rows.flatMap((row) => [
    { value: row.id, label: prefix + row.name + (row.status === 1 ? "（停用）" : "") },
    ...flattenCategoryOptions(row.children, prefix + row.name + " / "),
  ]);
}

/** 独立加载轻量分类树，不依赖分类管理权限。 */
export function useCategoryOptions() {
  const categories = ref<ArchiveSelectOption[]>([]);
  const state = reactive<CategoryOptionState>({ loading: false, failed: false, loaded: false });
  let sequence = 0;
  let active = true;
  /** 历史查询保留停用分类；离开页面后不接受旧响应。 */
  async function load(): Promise<void> {
    if (!active) return;
    const current = ++sequence;
    state.loading = true;
    state.failed = false;
    try {
      const response = await getCategoryOptions();
      if (active && current === sequence) {
        categories.value = flattenCategoryOptions(response.data.data);
        state.loaded = true;
      }
    } catch {
      if (active && current === sequence) state.failed = true;
    } finally {
      if (active && current === sequence) state.loading = false;
    }
  }
  /** 重新打开失败的分类下拉时重试。 */
  function onVisibleChange(visible: boolean): void {
    if (visible && (!state.loaded || state.failed) && !state.loading) void load();
  }
  onActivated(() => {
    active = true;
  });
  /** 废弃缓存页离开后的异步回写。 */
  function deactivate(): void {
    active = false;
    sequence++;
    state.loading = false;
  }
  onDeactivated(deactivate);
  onBeforeUnmount(deactivate);
  return { categories, state, load, onVisibleChange };
}
