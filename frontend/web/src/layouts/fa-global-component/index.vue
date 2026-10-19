<!-- 全局组件 -->
<template>
  <component
    v-for="componentConfig in enabledComponents"
    :key="componentConfig.key"
    :is="componentConfig.component"
  />
</template>

<script setup lang="ts">
import { getEnabledGlobalComponents } from "@/config/modules/component";
import { useProductConfigStore } from "@/store/modules/product-config.store";
const product = useProductConfigStore();
defineOptions({ name: "FaGlobalComponent" });
const enabledComponents = computed(() =>
  getEnabledGlobalComponents().filter(
    (item) =>
      item.key !== "fireworks-effect" && (item.key !== "settings-panel" || product.can("settings"))
  )
);
</script>
