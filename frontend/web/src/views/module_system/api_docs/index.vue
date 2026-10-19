<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import { createDocsSession } from "@/api/module_system/product-config";
import { useProductConfigStore } from "@/store/modules/product-config.store";
defineOptions({ name: "Docs" });
/** 文档 iframe 只加载后端签发的同源地址，不向 URL 传递令牌。 */
const state = reactive<{ loading: boolean; failed: boolean; url: string }>({
  loading: false,
  failed: false,
  url: "",
});
const product = useProductConfigStore();
let active = true;
/** 文档访问会话有效期五分钟，重新进入页面重新签发。 */
async function load(): Promise<void> {
  if (!product.can("api_docs")) return;
  state.loading = true;
  state.failed = false;
  try {
    const response = await createDocsSession();
    if (active) state.url = response.data.data.url;
  } catch {
    if (active) {
      state.url = "";
      state.failed = true;
    }
  } finally {
    state.loading = false;
  }
}
onMounted(load);
onActivated(() => {
  if (!active) {
    active = true;
    void load();
  }
});
onDeactivated(() => {
  active = false;
  state.url = "";
});
onBeforeUnmount(() => {
  active = false;
});
</script>
<template>
  <ElResult v-if="!product.can('api_docs')" icon="warning" title="暂无接口管理权限" />
  <ElResult v-else-if="state.failed" icon="error" title="接口文档加载失败"
    ><template #extra><ElButton :icon="Refresh" @click="load">重试</ElButton></template></ElResult
  >
  <div v-else v-loading="state.loading" class="api-docs">
    <iframe v-if="state.url" :src="state.url" title="智仓云接口文档" />
  </div>
</template>
<style scoped lang="scss">
.api-docs {
  height: calc(100dvh - 180px);
  min-height: 420px;

  iframe {
    width: 100%;
    height: 100%;
    border: 0;
  }
}
</style>
