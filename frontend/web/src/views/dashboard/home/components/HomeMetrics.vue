<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import type { DashboardSummary } from "@/api/module_inventory/dashboard";
import { dashboardMetrics, formatAmount } from "../utils/metrics";
/** 八项经营指标的加载与授权状态。 */
const props = defineProps<{ data?: DashboardSummary; loading: boolean; error: boolean }>();
/** 指标请求独立重试。 */
const emit = defineEmits<{ retry: [] }>();
const metrics = computed(() => dashboardMetrics(props.data));
</script>
<template>
  <section class="home-metrics" aria-label="经营指标" :aria-busy="loading">
    <ElAlert v-if="error" title="经营指标加载失败" type="error" :closable="false"
      ><ElButton link :icon="Refresh" @click="emit('retry')">重试</ElButton></ElAlert
    >
    <article
      v-for="item in metrics"
      :key="item.key"
      class="home-metrics__item"
      :class="'home-metrics__item--' + item.tone"
    >
      <div class="home-metrics__label">
        <FaSvgIcon :icon="item.icon" /><span>{{ item.title }}</span>
      </div>
      <ElSkeleton v-if="loading" :rows="1" animated />
      <template v-else>
        <strong
          >{{ item.count ? (item.value ?? "—") : formatAmount(item.value)
          }}<small v-if="item.value !== null && item.value !== undefined">{{
            item.count ? "项" : "元"
          }}</small></strong
        >
        <span class="home-metrics__detail">{{
          item.value === null ? "暂无查看权限" : item.detail || " "
        }}</span>
      </template>
    </article>
  </section>
</template>
<style scoped lang="scss">
.home-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin: 20px 0 24px;

  > .el-alert {
    grid-column: 1 / -1;
  }

  &__item {
    min-width: 0;
    min-height: 116px;
    padding: 16px;
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 6px;
  }

  &__label {
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 13px;
    color: var(--el-text-color-secondary);

    .fa-svg-icon {
      font-size: 20px;
    }
  }

  &__item--sale svg {
    color: var(--el-color-success);
  }

  &__item--purchase svg {
    color: var(--el-color-primary);
  }

  &__item--stock svg {
    color: var(--el-color-warning);
  }

  &__item--finance svg {
    color: var(--el-color-danger);
  }

  strong {
    display: block;
    margin: 12px 0 6px;
    font-size: 24px;
    font-variant-numeric: tabular-nums;
    line-height: 1.3;
    overflow-wrap: anywhere;

    small {
      margin-left: 5px;
      font-size: 12px;
      font-weight: 400;
      color: var(--el-text-color-secondary);
    }
  }

  &__detail {
    display: block;
    min-height: 17px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    overflow-wrap: anywhere;
  }
  @media (width <= 1100px) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  @media (width <= 480px) {
    gap: 8px;

    &__item {
      padding: 12px;
    }

    strong {
      font-size: 20px;
    }
  }
}
</style>
