<!-- 系统 Logo 默认使用智仓云本地品牌图片。 -->
<template>
  <div class="flex items-center justify-center">
    <img
      :style="logoStyle"
      :src="resolvedSrc"
      alt="logo"
      class="h-full w-full object-contain"
      @error="onImgError"
    />
  </div>
</template>

<script setup lang="ts">
import defaultLogoUrl from "@/assets/images/login/logo.png";

defineOptions({ name: "FaLogo" });

interface Props {
  /** logo 大小 */
  size?: number | string;
  /** 显式自定义地址；系统品牌入口不传入后端图片配置 */
  src?: string;
}

const props = withDefaults(defineProps<Props>(), {
  size: 36,
  src: undefined,
});

const fallbackTriggered = ref(false);

const resolvedSrc = computed(() => {
  if (fallbackTriggered.value) return defaultLogoUrl;
  const custom = props.src?.trim();
  return custom || defaultLogoUrl;
});

/** 自定义图片加载失败时回退到本地品牌图。 */
function onImgError(): void {
  if (!fallbackTriggered.value) {
    fallbackTriggered.value = true;
  }
}

const logoStyle = computed(() => ({ width: `${props.size}px`, height: `${props.size}px` }));

watch(
  () => props.src,
  () => {
    fallbackTriggered.value = false;
  }
);
</script>
