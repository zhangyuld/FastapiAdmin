/**
 * useSiteConfig - 站点配置初始化（标题 + favicon）。
 *
 * 从 configStore 同步系统名称，favicon 固定使用本地品牌资源。
 * 通过 watch 响应名称变更，旧图片配置不覆盖当前品牌。
 *
 * 应在 App.vue 的 onMounted 中调用。
 */

import { watch } from "vue";
import { useConfigStore } from "@stores";

/** 按构建基础路径设置本地图标，兼容子目录部署。 */
const updateFavicon = (): void => {
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"], link[rel="shortcut icon"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.appendChild(link);
  }
  link.type = "image/x-icon";
  link.href = `${import.meta.env.BASE_URL.replace(/\/?$/, "/")}logo.ico`;
};

/** 初始化站点名称与本地图标，并跟随服务端名称更新。 */
export function useSiteConfig(): { initSiteConfig: () => Promise<void> } {
  const configStore = useConfigStore();

  /** 替换 document.title 中的站点名后缀 */
  const applyConfig = (): void => {
    updateFavicon();
    const { sys_name } = configStore.configData;
    if (!sys_name?.config_value) return;
    const siteName = sys_name.config_value.trim();
    const existing = document.title;
    const dashIdx = existing.lastIndexOf(" - ");
    document.title = dashIdx > 0 ? `${existing.slice(0, dashIdx)} - ${siteName}` : siteName;
  };

  /** 配置请求失败时也保留本地图标，不依赖后端图片服务。 */
  const initSiteConfig = async (): Promise<void> => {
    updateFavicon();
    try {
      await configStore.getConfig();
      applyConfig();
    } catch (error) {
      console.error("[SiteConfig] 获取配置失败:", error);
    }
  };

  /** 配置更新后自动同步（管理员后台修改配置后重新拉取时） */
  watch(
    () => configStore.configData,
    () => applyConfig(),
    { deep: false }
  );

  return { initSiteConfig };
}
