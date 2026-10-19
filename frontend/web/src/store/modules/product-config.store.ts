import { defineStore } from "pinia";
import { ref, watch } from "vue";
import { usePreferredDark } from "@vueuse/core";
import { SystemThemeEnum } from "@/enums/appEnum";
import { ThemeMode } from "@/enums/settings/theme.enum";
import { useSettingsStore } from "./setting.store";
import { SETTING_DEFAULT_CONFIG } from "@/config/setting";
import type { MenuTable } from "@/api/module_system/menu";
import {
  MANAGED_SETTING_KEYS,
  getProductProfile,
  getProductConfig,
  publishProductConfig,
  type ProductProfile,
  type ProductConfig,
  type InterfaceSettings,
} from "@/api/module_system/product-config";

/** 配置不持久化用户能力，重新登录必须重新读取后端身份视图。 */
export const useProductConfigStore = defineStore("productConfig", () => {
  const profile = ref<ProductProfile>();
  const draft = ref<ProductConfig>();
  const loading = ref(false);
  const failed = ref(false);
  const profileFailed = ref(false);
  const prefersDark = usePreferredDark();
  const settingStore = useSettingsStore();
  let sequence = 0;
  let draftSequence = 0;

  /** 展示能力只取后端结果，失败和未加载默认关闭。 */
  function can(key: string): boolean {
    return profile.value?.capabilities[key] === true;
  }
  /** 专属菜单用后端提供的标识判定，不在前端维护角色或模块名单。 */
  function filterMenus(menus: MenuTable[]): MenuTable[] {
    return menus
      .filter((menu) => !menu.feature_key || can(menu.feature_key))
      .map((menu) => ({
        ...menu,
        children: menu.children ? filterMenus(menu.children) : undefined,
      }));
  }
  /** 获取可发布设置的当前快照，不复制令牌和标签页状态。 */
  function snapshot(): InterfaceSettings {
    const store = useSettingsStore();
    return Object.fromEntries(
      MANAGED_SETTING_KEYS.map((key) => [key, store[key]])
    ) as unknown as InterfaceSettings;
  }
  /** 将后端配置覆盖受管本地设置，专属字段缺失时始终关闭。 */
  function apply(
    values: Partial<InterfaceSettings>,
    capabilities: Record<string, boolean> = {}
  ): void {
    const store = useSettingsStore();
    const defaults = { ...SETTING_DEFAULT_CONFIG, userEnableAi: SETTING_DEFAULT_CONFIG.aiEnabled };
    const settings = Object.fromEntries(
      MANAGED_SETTING_KEYS.map((key) => [key, values[key] ?? defaults[key]])
    );
    for (const key of MANAGED_SETTING_KEYS)
      if (!(key in values) && typeof defaults[key] === "boolean") settings[key] = false;
    store.$patch((state) => Object.assign(state, settings));
    store.setElementTheme(store.systemThemeColor!);
    store.updateThemeColor(store.systemThemeColor!);
    const actualTheme =
      store.systemThemeMode === SystemThemeEnum.AUTO
        ? prefersDark.value
          ? SystemThemeEnum.DARK
          : SystemThemeEnum.LIGHT
        : store.systemThemeMode;
    store.setGlopTheme(actualTheme, store.systemThemeMode);
    store.updateTheme(actualTheme === SystemThemeEnum.DARK ? ThemeMode.DARK : ThemeMode.LIGHT);
    document.documentElement.classList.toggle("dark", actualTheme === SystemThemeEnum.DARK);
    store.setCustomRadius(store.customRadius);
    if (!capabilities.settings) store.hideSettingsPanel();
  }
  /** 登录、重新进入和刷新时读取配置；失败保持业务可用但专属功能关闭。 */
  async function loadProfile(): Promise<void> {
    const current = ++sequence;
    profile.value = undefined;
    profileFailed.value = false;
    try {
      const response = await getProductProfile();
      if (current !== sequence) return;
      profile.value = response.data.data;
      apply(profile.value.settings, profile.value.capabilities);
    } catch {
      if (current === sequence) {
        profile.value = undefined;
        profileFailed.value = true;
        apply({});
      }
    }
  }
  /** 超管重新加载发布基线，保留接口错误供面板显示。 */
  async function loadDraft(): Promise<void> {
    const current = ++draftSequence;
    loading.value = true;
    failed.value = false;
    try {
      const result = (await getProductConfig()).data.data;
      if (current === draftSequence) draft.value = result;
    } catch {
      if (current === draftSequence) {
        draft.value = undefined;
        failed.value = true;
      }
    } finally {
      if (current === draftSequence) loading.value = false;
    }
  }
  /** 界面预览及后端策略一起发布，版本冲突不覆盖用户草稿。 */
  async function publish(): Promise<void> {
    const current = sequence;
    if (!draft.value || !can("settings")) throw new Error("暂无可发布的配置");
    const body: ProductConfig = {
      revision: draft.value.revision,
      settings: snapshot(),
      features: draft.value.features,
      quick_links: draft.value.quick_links,
    };
    const result = (await publishProductConfig(body)).data.data;
    if (current !== sequence) return;
    draft.value = result;
    await loadProfile();
  }
  /** 退出清空专属能力及草稿，旧账号未完成请求不能恢复能力。 */
  function reset(): void {
    sequence++;
    draftSequence++;
    loading.value = false;
    profile.value = undefined;
    draft.value = undefined;
    failed.value = false;
    profileFailed.value = false;
    apply({});
  }
  /** 系统主题只建立一份 store 级监听，不随配置刷新累积监听器。 */
  watch(prefersDark, () => {
    if (settingStore.systemThemeMode === SystemThemeEnum.AUTO) {
      const actual = prefersDark.value ? SystemThemeEnum.DARK : SystemThemeEnum.LIGHT;
      settingStore.setGlopTheme(actual, SystemThemeEnum.AUTO);
      settingStore.updateTheme(actual === SystemThemeEnum.DARK ? ThemeMode.DARK : ThemeMode.LIGHT);
      document.documentElement.classList.toggle("dark", actual === SystemThemeEnum.DARK);
    }
  });
  return {
    profile,
    draft,
    loading,
    failed,
    profileFailed,
    can,
    filterMenus,
    snapshot,
    apply,
    loadProfile,
    loadDraft,
    publish,
    reset,
  };
});

export { MANAGED_SETTING_KEYS } from "@/api/module_system/product-config";
