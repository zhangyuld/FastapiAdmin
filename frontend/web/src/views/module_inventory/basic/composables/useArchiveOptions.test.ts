import { flushPromises, mount } from "@vue/test-utils";
import type { AxiosPromise, AxiosResponse } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { getCategoryOptions, type ArchiveOptionsQuery } from "@/api/module_inventory/basic/options";
import { flattenCategoryOptions, useArchiveOptions, useCategoryOptions } from "./useArchiveOptions";

vi.mock("@/api/module_inventory/basic/options", () => ({ getCategoryOptions: vi.fn() }));
/** 模拟精简档案，不提供任何审计和联系字段。 */
interface Row {
  id: number;
  name: string;
}
type Result = AxiosResponse<ApiResponse<PageResult<Row>>>;
const fetchOptions =
  vi.fn<(query: ArchiveOptionsQuery) => AxiosPromise<ApiResponse<PageResult<Row>>>>();
let subject: ReturnType<typeof useArchiveOptions<Row>>;
const wrappers: ReturnType<typeof mount>[] = [];

/** 构建与请求封装一致的分页响应。 */
function result(items: Row[], page = 1, total = items.length): Result {
  return {
    data: { data: { items, total, page_no: page, page_size: 50, has_next: page * 50 < total } },
  } as Result;
}
/** 通过真实生命周期挂载，不依赖全局自动导入。 */
function createSubject(enabledOnly = false) {
  const wrapper = mount(
    defineComponent({
      setup() {
        subject = useArchiveOptions({
          fetch: fetchOptions,
          enabledOnly,
          map: (row) => ({ value: row.id, label: row.name }),
        });
        return () => h("div");
      },
    })
  );
  wrappers.push(wrapper);
  return wrapper;
}
beforeEach(() => {
  vi.clearAllMocks();
  fetchOptions.mockResolvedValue(result([{ id: 1, name: "档案一" }]));
});
afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
});

describe("档案轻量分页选项", () => {
  it("历史查询省略状态，搜索关键词清理首尾空白", async () => {
    createSubject();
    await subject.search("  编码  ");
    expect(fetchOptions).toHaveBeenCalledWith({
      keyword: "编码",
      status: undefined,
      page_no: 1,
      page_size: 50,
    });
    expect(subject.options.value).toEqual([{ value: 1, label: "档案一" }]);
  });
  it("录单只请求启用档案", async () => {
    createSubject(true);
    await subject.search();
    expect(fetchOptions).toHaveBeenCalledWith(expect.objectContaining({ status: 0 }));
  });
  it("超过50条触底追加下一页，顶部和末页不多发请求", async () => {
    createSubject();
    const rows = Array.from({ length: 50 }, (_, i) => ({ id: i + 1, name: `档案${i + 1}` }));
    fetchOptions
      .mockResolvedValueOnce(result(rows, 1, 51))
      .mockResolvedValueOnce(result([{ id: 51, name: "第51条" }], 2, 51));
    await subject.search();
    await subject.selectProps.value.onEndReached("top");
    expect(fetchOptions).toHaveBeenCalledTimes(1);
    await subject.selectProps.value.onEndReached("bottom");
    expect(subject.options.value).toHaveLength(51);
    expect(subject.options.value[50]?.value).toBe(51);
    await subject.loadMore();
    expect(fetchOptions).toHaveBeenCalledTimes(2);
  });
  it("追加失败保留列表，重新打开重试原失败页", async () => {
    createSubject();
    fetchOptions
      .mockResolvedValueOnce(result([{ id: 1, name: "档案一" }], 1, 51))
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(result([{ id: 51, name: "档案二" }], 2, 51));
    await subject.search();
    await subject.loadMore();
    expect(subject.options.value).toHaveLength(1);
    expect(subject.state.failed).toBe(true);
    expect(subject.state.page).toBe(1);
    subject.selectProps.value.onVisibleChange(true);
    await flushPromises();
    expect(fetchOptions).toHaveBeenLastCalledWith(expect.objectContaining({ page_no: 2 }));
    expect(subject.options.value).toHaveLength(2);
    expect(subject.state.failed).toBe(false);
  });
  it("首次失败重新打开可重试，空数据不是失败", async () => {
    createSubject();
    fetchOptions.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(result([]));
    await subject.search();
    expect(subject.selectProps.value.noDataText).toContain("加载失败");
    subject.selectProps.value.onVisibleChange(true);
    await flushPromises();
    expect(subject.state.failed).toBe(false);
    expect(subject.state.loaded).toBe(true);
    expect(subject.options.value).toEqual([]);
  });
  it("忽略过期搜索，不能混合两个关键词的结果", async () => {
    createSubject();
    let resolveOld: ((value: Result) => void) | undefined;
    fetchOptions
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOld = resolve;
          })
      )
      .mockResolvedValueOnce(result([{ id: 2, name: "新结果" }]));
    const old = subject.search("old");
    await subject.search("new");
    resolveOld?.(result([{ id: 1, name: "旧结果" }]));
    await old;
    expect(subject.options.value).toEqual([{ value: 2, label: "新结果" }]);
  });
  it("追加去重，不重复堆叠服务端已有ID", async () => {
    createSubject();
    fetchOptions
      .mockResolvedValueOnce(result([{ id: 1, name: "档案一" }], 1, 51))
      .mockResolvedValueOnce(
        result(
          [
            { id: 1, name: "档案一" },
            { id: 2, name: "档案二" },
          ],
          2,
          51
        )
      );
    await subject.search();
    await subject.loadMore();
    expect(subject.options.value).toHaveLength(2);
  });
  it("历史档案名称保留，新录单不能重新选入回显项", async () => {
    createSubject(true);
    subject.retain(99, "历史仓库");
    await subject.search("新仓库");
    expect(subject.options.value).toContainEqual({ value: 99, label: "历史仓库", disabled: true });
  });
  it("卸载不接受旧请求回写，也不再发新请求", async () => {
    const wrapper = createSubject();
    let complete: ((value: Result) => void) | undefined;
    fetchOptions.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          complete = resolve;
        })
    );
    const pending = subject.search();
    wrapper.unmount();
    complete?.(result([{ id: 9, name: "过期" }]));
    await pending;
    expect(subject.options.value).toEqual([]);
    await subject.search("other");
    expect(fetchOptions).toHaveBeenCalledTimes(1);
  });
});

describe("分类轻量树", () => {
  it("保留完整层级和停用分类标识", () => {
    expect(
      flattenCategoryOptions([
        {
          id: 1,
          name: "父",
          parent_id: null,
          status: 0,
          children: [{ id: 2, name: "子", parent_id: 1, status: 1, children: [] }],
        },
      ])
    ).toEqual([
      { value: 1, label: "父" },
      { value: 2, label: "父 / 子（停用）" },
    ]);
  });
  it("失败可单独重试，不需要分类管理授权", async () => {
    let category: ReturnType<typeof useCategoryOptions>;
    const wrapper = mount(
      defineComponent({
        setup() {
          category = useCategoryOptions();
          return () => h("div");
        },
      })
    );
    wrappers.push(wrapper);
    vi.mocked(getCategoryOptions)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ ...result([]), data: { ...result([]).data, data: [] } });
    await category!.load();
    expect(category!.state.failed).toBe(true);
    category!.onVisibleChange(true);
    await flushPromises();
    expect(category!.state.failed).toBe(false);
    expect(getCategoryOptions).toHaveBeenCalledTimes(2);
  });
});
