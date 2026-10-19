import { request } from "@utils";
import type { AxiosPromise } from "axios";
import type {
  MenuTypeEnum,
  MenuThemeEnum,
  SystemThemeEnum,
  ContainerWidthEnum,
} from "@/enums/appEnum";

/** 后端发布的界面契约，不包含用户会话和刷新状态。 */
export interface InterfaceSettings {
  menuType: MenuTypeEnum;
  menuOpenWidth: number;
  menuOpen: boolean;
  dualMenuShowText: boolean;
  systemThemeType: SystemThemeEnum;
  systemThemeMode: SystemThemeEnum;
  menuThemeType: MenuThemeEnum;
  systemThemeColor: string;
  showMenuButton: boolean;
  showFastEnter: boolean;
  showRefreshButton: boolean;
  showCrumbs: boolean;
  showWorkTab: boolean;
  showLanguage: boolean;
  showNprogress: boolean;
  showSettingGuide: boolean;
  showFestivalText: boolean;
  watermarkVisible: boolean;
  showAppLogo: boolean;
  showGuide: boolean;
  grayMode: boolean;
  userEnableAi: boolean;
  autoClose: boolean;
  uniqueOpened: boolean;
  colorWeak: boolean;
  boxBorderMode: boolean;
  pageTransition: string;
  tabStyle: string;
  customRadius: string;
  containerWidth: ContainerWidthEnum;
  showMenuSearch: boolean;
  showFullscreen: boolean;
  showSizeSelect: boolean;
  showNotification: boolean;
}
/** 可扩展超管功能策略，开放条件由服务端执行。 */
export interface FeatureRule {
  key: string;
  label: string;
  enabled: boolean;
  access_policy: "superuser_only";
  built_in: boolean;
  api_prefixes: string[];
  menu_prefixes: string[];
  permission_prefixes: string[];
  component_prefixes: string[];
  setting_keys: string[];
}
/** 完整发布版本只有超管可读取。 */
export interface ProductConfig {
  revision: number;
  settings: InterfaceSettings;
  features: FeatureRule[];
  quick_links: ProductQuickLink[];
}
/** 专属链接不会出现在普通用户响应中。 */
export interface ProductQuickLink {
  name: string;
  link: string;
  enabled: boolean;
  order: number;
}
/** 登录用户接收后端裁剪后的配置。 */
export interface ProductProfile {
  revision: number;
  settings: Partial<InterfaceSettings>;
  capabilities: Record<string, boolean>;
  quick_links?: ProductQuickLink[];
}

export { MANAGED_SETTING_KEYS } from "./product-settings";

/** 获取当前用户的有效配置，不读取浏览器中的角色配置名单。 */
export function getProductProfile(): AxiosPromise<ApiResponse<ProductProfile>> {
  return request<ApiResponse<ProductProfile>>({
    url: "/system/product-config/profile",
    method: "get",
  });
}
/** 获取超管的完整配置编辑基线。 */
export function getProductConfig(): AxiosPromise<ApiResponse<ProductConfig>> {
  return request<ApiResponse<ProductConfig>>({
    url: "/system/product-config/detail",
    method: "get",
  });
}
/** 发布内容必须携带读取时的版本，后端拒绝覆盖更新版本。 */
export type PublishProductConfig = ProductConfig;
/** 发布当前界面默认值及超管策略。 */
export function publishProductConfig(
  data: PublishProductConfig
): AxiosPromise<ApiResponse<ProductConfig>> {
  return request<ApiResponse<ProductConfig>>({
    url: "/system/product-config/publish",
    method: "post",
    data,
  });
}
/** 为同源文档建立短期 HttpOnly cookie，不向地址栏写入令牌。 */
export function createDocsSession(): AxiosPromise<ApiResponse<{ url: string }>> {
  return request<ApiResponse<{ url: string }>>({
    url: "/system/product-config/docs-session",
    method: "post",
  });
}
