/**
 * 系统设置默认值配置
 *
 * 统一管理系统设置的所有默认值
 *
 * ## 主要功能
 *
 * - 菜单相关默认配置
 * - 主题相关默认配置
 * - 界面显示默认配置
 * - 功能开关默认配置
 * - 样式相关默认配置
 *
 * ## 注意事项
 *
 * 1. 修改此文件的配置项时，需要同步更新以下文件：
 *    - src/layouts/fa-settings-panel/widgets/SettingActions.vue（复制配置和重置配置逻辑）
 *    - src/store/modules/setting.ts（Store 状态定义）
 * 2. 可以通过设置面板的"复制配置"按钮快速生成配置代码
 * 3. 枚举类型的值需要与 src/enums/appEnum.ts 中的定义保持一致
 */

import { LayoutMode, ComponentSize, SidebarColor, ThemeMode } from "@/enums";
import {
  SystemThemeEnum,
  MenuTypeEnum,
  MenuThemeEnum,
  LanguageEnum,
  ContainerWidthEnum,
} from "@/enums/appEnum";

const env = import.meta.env;
const { pkg } = __APP_INFO__;

// 检查用户的操作系统是否使用深色模式

/**
 * 系统设置默认值配置
 */
export const SETTING_DEFAULT_CONFIG = {
  /** 项目名称 */
  name: "智仓云",
  /** 系统标题 */
  title: (env.VITE_APP_TITLE as string) || pkg.name,
  /** 系统版本 */
  version: pkg.version as string,
  /** 是否显示设置按钮 */
  showSettings: true,
  /** 是否显示菜单搜索 */
  showMenuSearch: true,
  /** 是否显示全屏按钮 */
  showFullscreen: true,
  /** 是否显示尺寸选择 */
  showSizeSelect: true,
  /** 是否显示语言选择 */
  showLangSelect: false,
  /** 是否显示通知 */
  showNotification: true,
  /** 是否显示标签视图 */
  showTagsView: true,
  /** 是否显示应用Logo */
  showAppLogo: true,
  /** 布局方式 */
  layout: LayoutMode.LEFT,
  /** 主题模式 */
  theme: ThemeMode.LIGHT,
  /** 组件大小 */
  size: ComponentSize.DEFAULT,
  /** 语言 */
  language: LanguageEnum.ZH,
  /** 主题颜色 */
  themeColor: "#5D87FF",
  /** 是否显示水印 */
  showWatermark: false,
  /** 水印内容 */
  watermarkContent: "智仓云",
  /** 侧边栏配色方案 */
  sidebarColorScheme: SidebarColor.CLASSIC_BLUE,
  /** 项目引导可见性 */
  guideVisible: false,
  /** 是否启动引导 */
  showGuide: false,
  /** 是否开启AI助手 */
  aiEnabled: false,
  /** 是否开启灰色模式 */
  grayMode: false,
  /** 页面切换动画 */
  pageSwitchingAnimation: "fade-slide",
  /** 菜单类型 */
  menuType: MenuTypeEnum.LEFT,
  /** 菜单展开宽度 */
  menuOpenWidth: 220,
  /** 菜单是否展开 */
  menuOpen: true,
  /** 双菜单是否显示文本 */
  dualMenuShowText: false,
  /** 系统主题类型 */
  systemThemeType: SystemThemeEnum.LIGHT,
  /** 系统主题模式 */
  systemThemeMode: SystemThemeEnum.LIGHT,
  /** 菜单风格 */
  menuThemeType: MenuThemeEnum.LIGHT,
  /** 系统主题颜色 */
  systemThemeColor: "#5D87FF",
  /** 是否显示菜单按钮 */
  showMenuButton: true,
  /** 是否显示快速入口 */
  showFastEnter: true,
  /** 是否显示刷新按钮 */
  showRefreshButton: true,
  /** 是否显示面包屑 */
  showCrumbs: true,
  /** 是否显示工作台标签 */
  showWorkTab: true,
  /** 是否显示语言切换 */
  showLanguage: false,
  /** 是否显示进度条 */
  showNprogress: true,
  /** 是否显示设置引导 */
  showSettingGuide: false,
  /** 是否显示节日文本 */
  showFestivalText: false,
  /** 是否显示水印（新版本字段） */
  watermarkVisible: true,
  /** 是否自动关闭 */
  autoClose: false,
  /** 是否唯一展开 */
  uniqueOpened: true,
  /** 是否色弱模式 */
  colorWeak: false,
  /** 是否刷新 */
  refresh: true,
  /** 是否加载节日烟花 */
  holidayFireworksLoaded: false,
  /** 边框模式 */
  boxBorderMode: false,
  /** 页面过渡效果 */
  pageTransition: "slide-left",
  /** 标签页样式 */
  tabStyle: "tab-google",
  /** 自定义圆角 */
  customRadius: "0.75",
  /** 容器宽度 */
  containerWidth: ContainerWidthEnum.FULL,
  /** 节日日期 */
  festivalDate: "",
};

/** 与 Store / App 中使用的默认设置别名（同 SETTING_DEFAULT_CONFIG） */
export const defaultSettings = SETTING_DEFAULT_CONFIG;

/**
 * 获取设置默认值
 * @returns 设置默认值对象
 */
export function getSettingDefaults() {
  return { ...SETTING_DEFAULT_CONFIG };
}

/**
 * 重置为默认设置
 * @param currentSettings 当前设置对象
 */
export function resetToDefaults(currentSettings: Record<string, any>) {
  const defaults = getSettingDefaults();
  Object.keys(defaults).forEach((key) => {
    if (key in currentSettings) {
      currentSettings[key] = defaults[key as keyof typeof defaults];
    }
  });
}
