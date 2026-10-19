import { onBeforeUnmount, onMounted, readonly, ref, type Ref } from "vue";
import { loginSectionLinks, type LoginSectionId } from "../login-product";

/** 当前登录页拥有独立滚动容器，不修改全局滚动或认证状态。 */
export interface LoginNavigationOptions {
  root: Ref<HTMLElement | undefined>;
}

/** 管理分区定位、高亮和返回登录后的焦点，并成对清理监听器。 */
export function useLoginSectionNavigation({ root }: LoginNavigationOptions) {
  const activeSection = ref<LoginSectionId>("overview");
  let frame = 0;
  let resizeObserver: ResizeObserver | undefined;

  /** 根据实际顶栏高度定位，兼容窄屏双行导航和短视口。 */
  function headerHeight(): number {
    return root.value?.querySelector("header")?.getBoundingClientRect().height ?? 72;
  }

  /** 以顶栏下方的阅读线选择当前分区，底部明确归属最后一屏。 */
  function updateActiveSection(): void {
    frame = 0;
    const container = root.value;
    if (!container) return;
    const readingLine = container.getBoundingClientRect().top + headerHeight() + 120;
    let current: LoginSectionId = "overview";
    for (const link of loginSectionLinks) {
      const section = container.querySelector<HTMLElement>(`#${link.id}`);
      if (section && section.getBoundingClientRect().top <= readingLine) current = link.id;
    }
    if (container.scrollHeight - container.scrollTop - container.clientHeight <= 2) {
      current = "reports";
    }
    activeSection.value = current;
  }

  /** 滚动事件仅安排一帧测量，避免每次事件重复计算布局。 */
  function scheduleUpdate(): void {
    if (!frame) frame = window.requestAnimationFrame(updateActiveSection);
  }

  /** 滚动不更改路由或重新挂载表单，减少动态效果时直接定位。 */
  function navigateTo(id: LoginSectionId): void {
    const container = root.value;
    const section = container?.querySelector<HTMLElement>(`#${id}`);
    if (!container || !section) return;
    const top =
      container.scrollTop +
      section.getBoundingClientRect().top -
      container.getBoundingClientRect().top -
      headerHeight();
    container.scrollTo({
      top: Math.max(0, top),
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }

  /** 返回首屏并聚焦账号，不触发验证码刷新或清空输入。 */
  function returnToLogin(): void {
    navigateTo("overview");
    root.value
      ?.querySelector<HTMLInputElement>('[name="username"]')
      ?.focus({ preventScroll: true });
  }

  onMounted(() => {
    root.value?.addEventListener("scroll", scheduleUpdate, { passive: true });
    window.addEventListener("resize", scheduleUpdate);
    if (typeof ResizeObserver !== "undefined" && root.value) {
      resizeObserver = new ResizeObserver(scheduleUpdate);
      resizeObserver.observe(root.value);
      const header = root.value.querySelector("header");
      if (header) resizeObserver.observe(header);
    }
    scheduleUpdate();
  });

  onBeforeUnmount(() => {
    root.value?.removeEventListener("scroll", scheduleUpdate);
    window.removeEventListener("resize", scheduleUpdate);
    resizeObserver?.disconnect();
    if (frame) window.cancelAnimationFrame(frame);
  });

  return { activeSection: readonly(activeSection), navigateTo, returnToLogin };
}
