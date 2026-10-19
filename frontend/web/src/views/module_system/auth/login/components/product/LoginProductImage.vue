<script setup lang="ts">
import { reactive, watch } from "vue";
/** 本地脱敏截图；固定比例保留布局，避免滚动定位随加载跳动。 */
const props = withDefaults(defineProps<{ src: string; alt: string; eager?: boolean }>(), {
  eager: false,
});
/** 截图加载状态，不影响表单或业务请求。 */
interface ImageState {
  failed: boolean;
  loaded: boolean;
}
const state = reactive<ImageState>({ failed: false, loaded: false });
watch(
  () => props.src,
  () => {
    state.failed = false;
    state.loaded = false;
  }
);
</script>

<template>
  <figure class="product-image" :class="{ 'product-image--loaded': state.loaded }">
    <img
      v-if="!state.failed"
      :src="src"
      :alt="alt"
      width="1440"
      height="850"
      :loading="eager ? 'eager' : 'lazy'"
      :fetchpriority="eager ? 'high' : 'auto'"
      decoding="async"
      @load="state.loaded = true"
      @error="state.failed = true"
    />
    <div v-else class="product-image__error" role="status">
      <FaSvgIcon icon="ri:image-line" :size="28" /><span>界面预览暂不可用</span>
    </div>
  </figure>
</template>

<style scoped lang="scss">
.product-image {
  width: 100%;
  aspect-ratio: 1440 / 850;
  margin: 0;
  overflow: hidden;
  background: var(--login-soft);
  border: 1px solid var(--login-border);
  border-radius: 6px;
  box-shadow: 0 18px 48px rgb(27 56 93 / 7%);

  img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  &__error {
    display: flex;
    flex-direction: column;
    gap: 12px;
    align-items: center;
    justify-content: center;
    height: 100%;
    font-size: 14px;
    color: var(--login-muted);
  }
}
</style>
