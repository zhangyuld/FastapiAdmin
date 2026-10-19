import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { ref } from "vue";
import { useProductConfigStore, MANAGED_SETTING_KEYS } from "./product-config.store";

const mocks = vi.hoisted(() => ({
  profile: vi.fn(),
  detail: vi.fn(),
  publish: vi.fn(),
  state: {} as Record<string, unknown>,
}));
vi.mock("@/api/module_system/product-config", async () => {
  const original = await vi.importActual<typeof import("@/api/module_system/product-settings")>(
    "@/api/module_system/product-settings"
  );
  return {
    ...original,
    getProductProfile: mocks.profile,
    getProductConfig: mocks.detail,
    publishProductConfig: mocks.publish,
  };
});
vi.mock("@vueuse/core", () => ({ usePreferredDark: () => ref(false) }));
vi.mock("@/config/setting", () => ({
  SETTING_DEFAULT_CONFIG: {
    menuType: "left",
    menuOpenWidth: 220,
    menuOpen: true,
    systemThemeMode: "light",
    systemThemeType: "light",
    menuThemeType: "light",
    systemThemeColor: "#5D87FF",
    customRadius: "0.75",
    showFastEnter: true,
    showFullscreen: true,
    aiEnabled: false,
    watermarkVisible: true,
    showLanguage: false,
    showGuide: false,
  },
}));
vi.mock("./setting.store", () => ({
  useSettingsStore: () => ({
    get systemThemeColor() {
      return mocks.state.systemThemeColor as string;
    },
    get systemThemeMode() {
      return mocks.state.systemThemeMode;
    },
    get customRadius() {
      return mocks.state.customRadius;
    },
    $patch: (callback: (state: Record<string, unknown>) => void) => callback(mocks.state),
    setElementTheme: vi.fn(),
    updateThemeColor: vi.fn(),
    updateTheme: vi.fn(),
    setGlopTheme: vi.fn(),
    setCustomRadius: vi.fn(),
    hideSettingsPanel: vi.fn(),
  }),
}));
/** 框架标准接口响应。 */
function response<T>(data: T) {
  return { data: { data } };
}
beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  mocks.state = {
    showFastEnter: true,
    userEnableAi: true,
    showFullscreen: true,
    systemThemeMode: "dark",
    systemThemeColor: "#000000",
  };
});
describe("服务端产品配置", () => {
  it("空能力默认关闭，不读取旧账号本地超管配置", async () => {
    mocks.profile.mockResolvedValue(
      response({
        revision: 0,
        settings: {
          menuOpenWidth: 220,
          systemThemeMode: "light",
          systemThemeColor: "#5D87FF",
          showFullscreen: true,
        },
        capabilities: {},
      })
    );
    const store = useProductConfigStore();
    await store.loadProfile();
    expect(store.can("settings")).toBe(false);
    expect(store.can("quick_entry")).toBe(false);
    expect(mocks.state.showFastEnter).toBe(false);
    expect(mocks.state.userEnableAi).toBe(false);
    expect(mocks.state.menuOpenWidth).toBe(220);
    expect(mocks.state.systemThemeColor).toBe("#5D87FF");
  });
  it("后端新增专属布尔字段被裁剪后不能恢复为本地默认开启", async () => {
    mocks.profile.mockResolvedValue(response({ revision: 1, settings: {}, capabilities: {} }));
    await useProductConfigStore().loadProfile();
    expect(mocks.state.showFullscreen).toBe(false);
  });
  it("配置失败清空能力并提供显式失败状态", async () => {
    mocks.profile.mockRejectedValue(new Error("offline"));
    const store = useProductConfigStore();
    await store.loadProfile();
    expect(store.profileFailed).toBe(true);
    expect(store.can("settings")).toBe(false);
  });
  it("退出后迟到的超管 profile 不得恢复旧能力", async () => {
    let done!: (value: unknown) => void;
    mocks.profile.mockReturnValue(
      new Promise((resolve) => {
        done = resolve;
      })
    );
    const store = useProductConfigStore();
    const loading = store.loadProfile();
    store.reset();
    done(
      response({
        revision: 1,
        settings: { showFastEnter: true },
        capabilities: { settings: true, quick_entry: true },
      })
    );
    await loading;
    expect(store.can("quick_entry")).toBe(false);
    expect(store.profile).toBeUndefined();
  });
  it("退出后迟到的完整配置不能留在普通账号草稿中", async () => {
    let done!: (value: unknown) => void;
    mocks.detail.mockReturnValue(
      new Promise((resolve) => {
        done = resolve;
      })
    );
    const store = useProductConfigStore();
    const loading = store.loadDraft();
    store.reset();
    done(response({ revision: 1, settings: {}, features: [] }));
    await loading;
    expect(store.draft).toBeUndefined();
  });
  it("运行状态不进入发布白名单", () => {
    expect(MANAGED_SETTING_KEYS).not.toContain("refresh");
    expect(MANAGED_SETTING_KEYS).not.toContain("settingsVisible");
    expect(MANAGED_SETTING_KEYS).not.toContain("festivalDate");
  });
  it("菜单只使用后端 feature_key，支持未来追加项与子树裁剪", async () => {
    mocks.profile.mockResolvedValue(
      response({ revision: 0, settings: {}, capabilities: { future_tools: true } })
    );
    const store = useProductConfigStore();
    await store.loadProfile();
    const menus = store.filterMenus([
      { id: 1, feature_key: "settings", children: [{ id: 2 }] },
      { id: 3 },
      { id: 4, feature_key: "future_tools" },
    ]);
    expect(menus.map((menu) => menu.id)).toEqual([3, 4]);
  });
});
