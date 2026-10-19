import { mount } from "@vue/test-utils";
import { defineComponent, h, nextTick, ref } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useLoginSectionNavigation } from "./useLoginSectionNavigation";

let subject: ReturnType<typeof useLoginSectionNavigation>;
const wrappers: ReturnType<typeof mount>[] = [];
const scrollTo = vi.fn();
let reducedMotion = false;

/** 宿主包含实际容器、分区和账号，模拟布局而不依赖jsdom排版。 */
function createSubject() {
  const wrapper = mount(
    defineComponent({
      setup() {
        const root = ref<HTMLElement>();
        subject = useLoginSectionNavigation({ root });
        return () =>
          h("div", { ref: root }, [
            h("header"),
            ...["overview", "trade", "stock", "reports"].map((id) => h("section", { id })),
            h("input", { name: "username" }),
          ]);
      },
    }),
    { attachTo: document.body }
  );
  wrappers.push(wrapper);
  const container = wrapper.element as HTMLElement;
  Object.defineProperties(container, {
    clientHeight: { value: 800 },
    scrollHeight: { value: 4000 },
    scrollTop: { value: 0, writable: true },
  });
  container.scrollTo = scrollTo;
  vi.spyOn(container, "getBoundingClientRect").mockReturnValue({ top: 0 } as DOMRect);
  vi.spyOn(container.querySelector("header")!, "getBoundingClientRect").mockReturnValue({
    height: 112,
  } as DOMRect);
  for (const [index, section] of [...container.querySelectorAll("section")].entries()) {
    vi.spyOn(section, "getBoundingClientRect").mockImplementation(
      () => ({ top: 112 + index * 1000 - container.scrollTop }) as DOMRect
    );
  }
  return { wrapper, container };
}

beforeEach(() => {
  vi.useFakeTimers();
  scrollTo.mockClear();
  reducedMotion = false;
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: reducedMotion }))
  );
});
afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

describe("登录页分区导航", () => {
  it("定位扣除实际双行顶栏高度，首屏不产生负偏移", () => {
    createSubject();
    subject.navigateTo("stock");
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 2000, behavior: "smooth" });
    subject.navigateTo("overview");
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, behavior: "smooth" });
  });
  it("减少动态效果偏好下直接跳转", () => {
    createSubject();
    reducedMotion = true;
    subject.navigateTo("reports");
    expect(scrollTo).toHaveBeenCalledWith({ top: 3000, behavior: "auto" });
  });
  it("滚动更新阅读位置，容器底部归属最后一屏", async () => {
    const { container } = createSubject();
    container.scrollTop = 2000;
    container.dispatchEvent(new Event("scroll"));
    vi.advanceTimersByTime(20);
    await nextTick();
    expect(subject.activeSection.value).toBe("stock");
    container.scrollTop = 3200;
    container.dispatchEvent(new Event("scroll"));
    vi.advanceTimersByTime(20);
    expect(subject.activeSection.value).toBe("reports");
  });
  it("返回登录保留账号值，并以preventScroll聚焦账号", () => {
    const { container } = createSubject();
    const input = container.querySelector("input")!;
    input.value = "operator";
    const focus = vi.spyOn(input, "focus");
    subject.returnToLogin();
    expect(input.value).toBe("operator");
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
  });
  it("卸载时清理滚动、窗口和待处理动画帧", () => {
    const removeWindow = vi.spyOn(window, "removeEventListener");
    const { wrapper, container } = createSubject();
    const removeRoot = vi.spyOn(container, "removeEventListener");
    const cancel = vi.spyOn(window, "cancelAnimationFrame");
    wrapper.unmount();
    expect(removeWindow).toHaveBeenCalledWith("resize", expect.any(Function));
    expect(removeRoot).toHaveBeenCalledWith("scroll", expect.any(Function));
    expect(cancel).toHaveBeenCalled();
  });
});
