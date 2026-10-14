<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
/** 面板统一异常边界，业务内容由插槽提供。 */
withDefaults(
  defineProps<{
    title: string;
    loading: boolean;
    error: boolean;
    forbidden: boolean;
    empty?: boolean;
  }>(),
  { empty: false }
);
/** 失败重试只作用于当前面板。 */
const emit = defineEmits<{ retry: [] }>();
/** 标题操作与业务内容插槽。 */
defineSlots<{ actions(): unknown; default(): unknown }>();
</script>
<template>
  <section class="home-panel" :aria-label="title" :aria-busy="loading">
    <header>
      <h2>{{ title }}</h2>
      <div class="home-panel__actions"><slot name="actions" /></div>
    </header>
    <div class="home-panel__body">
      <ElSkeleton v-if="loading" :rows="4" animated />
      <ElEmpty v-else-if="forbidden" description="暂无查看权限" :image-size="64" />
      <ElResult v-else-if="error" icon="error" title="数据加载失败"
        ><template #extra
          ><ElButton :icon="Refresh" @click="emit('retry')">重试</ElButton></template
        ></ElResult
      >
      <ElEmpty v-else-if="empty" description="暂无业务数据" :image-size="64" />
      <slot v-else />
    </div>
  </section>
</template>
<style scoped lang="scss">
.home-panel {
  min-width: 0;
  padding: 20px 0;
  border-top: 1px solid var(--el-border-color-lighter);

  header {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }

  &__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    min-width: 0;
  }

  &__body {
    min-width: 0;
    min-height: 180px;
  }
}
</style>
