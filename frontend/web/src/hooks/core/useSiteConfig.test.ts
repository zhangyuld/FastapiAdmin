import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, reactive, type EffectScope } from "vue";
import { useSiteConfig } from "./useSiteConfig";

/** 仅模拟配置存储，DOM 和 Vue 监听使用真实实现。 */
const store = reactive({
  configData: {} as Record<string, { config_value: string }>,
  getConfig: vi.fn<() => Promise<void>>(),
});
vi.mock("@stores", () => ({ useConfigStore: () => store }));

describe("站点品牌资源", () => {
  let scope: EffectScope;

  beforeEach(() => {
    scope = effectScope();
    store.configData = {};
    store.getConfig.mockReset().mockResolvedValue(undefined);
    document.head.innerHTML = "";
    document.title = "首页 - 旧名称";
    vi.stubEnv("BASE_URL", "/web/");
  });

  afterEach(() => {
    scope.stop();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  /** 在独立作用域创建监听，避免测试间遗留副作用。 */
  function initialize(): Promise<void> {
    return scope.run(() => useSiteConfig().initSiteConfig())!;
  }

  /** 读取浏览器使用的图标节点。 */
  function icon(): HTMLLinkElement | null {
    return document.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
  }

  it("沿用图标节点并忽略后端旧图，系统名称正常更新", async () => {
    const existing = document.createElement("link");
    existing.rel = "shortcut icon";
    existing.href = "https://old.example/favicon.ico";
    document.head.appendChild(existing);
    store.configData = {
      sys_name: { config_value: "智仓云" },
      favicon: { config_value: "https://old.example/server.ico" },
    };
    await initialize();
    expect(icon()).toBe(existing);
    expect(icon()?.getAttribute("href")).toBe("/web/logo.ico");
    expect(document.title).toBe("首页 - 智仓云");
  });

  it("没有系统名称或图标节点时仍创建本地图标", async () => {
    await initialize();
    expect(icon()?.getAttribute("href")).toBe("/web/logo.ico");
    expect(icon()?.type).toBe("image/x-icon");
    expect(document.title).toBe("首页 - 旧名称");
  });

  it("配置失败时本地图标仍可用", async () => {
    store.getConfig.mockRejectedValue(new Error("offline"));
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    await initialize();
    expect(icon()?.getAttribute("href")).toBe("/web/logo.ico");
  });

  it("配置重新加载不会恢复旧图标或重复创建节点", async () => {
    await initialize();
    store.configData = {
      sys_name: { config_value: "新名称" },
      favicon: { config_value: "https://old.example/restored.ico" },
    };
    await nextTick();
    expect(icon()?.getAttribute("href")).toBe("/web/logo.ico");
    expect(document.title).toBe("首页 - 新名称");
    expect(document.querySelectorAll('link[rel="icon"]')).toHaveLength(1);
  });

  it.each(["/", "/web", "/web/"])("兼容基础路径 %s", async (base) => {
    vi.stubEnv("BASE_URL", base);
    await initialize();
    expect(icon()?.getAttribute("href")).toBe(base === "/" ? "/logo.ico" : "/web/logo.ico");
  });
});
