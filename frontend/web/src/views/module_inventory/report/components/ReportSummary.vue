<script setup lang="ts">
import type { ReportKind, ReportView, ReportSummary } from "@/api/module_inventory/report/client";
import { Refresh } from "@element-plus/icons-vue";
import { summaryFields, fieldValue } from "../utils/config";
/** 指标只展示服务端完整筛选汇总，未加载时不伪造零值。 */
const props = defineProps<{
  kind: ReportKind;
  view: ReportView;
  value?: ReportSummary;
  loading: boolean;
  failed: boolean;
}>();
/** 汇总加载失败时独立重试。 */
const emit = defineEmits<{ retry: [] }>();
const fields = computed(() => summaryFields(props.kind, props.view));
</script>
<template>
  <section v-loading="loading" class="report-summary" aria-label="报表汇总">
    <ElAlert
      v-if="failed"
      class="report-summary__failure"
      title="报表汇总加载失败"
      type="error"
      :closable="false"
      ><ElButton link :icon="Refresh" @click="emit('retry')">重试</ElButton></ElAlert
    >
    <div v-for="field in fields" :key="field.key" class="report-summary__metric">
      <span>{{ field.label }}</span
      ><strong>{{ fieldValue(value, field) }}</strong>
    </div>
  </section>
</template>
<style scoped lang="scss">
.report-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  min-height: 84px;
  padding: 12px 0;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color);

  &__failure {
    grid-column: 1 / -1;
  }

  &__metric {
    min-width: 0;
    color: var(--el-text-color-secondary);

    strong {
      display: block;
      margin-top: 6px;
      font-size: 20px;
      color: var(--el-text-color-primary);
      overflow-wrap: anywhere;
    }
  }
  @media (width <= 768px) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
