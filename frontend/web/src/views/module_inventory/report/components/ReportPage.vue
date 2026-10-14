<script setup lang="ts">
import type { ReportKind, ReportView } from "@/api/module_inventory/report/client";
import { reportView, reportViews } from "../utils/config";
import ReportContent from "./ReportContent.vue";
/** 路由入口固定报表领域，页面缓存不响应其他领域参数。 */
const props = defineProps<{ kind: ReportKind }>();
const route = useRoute();
const router = useRouter();
/** 当前页面局部视图状态。 */
interface PageState {
  view: ReportView;
}
const state = reactive<PageState>({ view: reportView(props.kind, route.query.view) });
const options = computed(() => reportViews(props.kind));
/** 主动切换维度时清除旧查询，避免日期或单号残留。 */
function changeView(value: string | number | boolean | undefined): void {
  void router.replace({
    path: "/inventory/report/" + props.kind,
    query: { view: reportView(props.kind, value) },
  });
}
watch(
  () => [route.path, route.query.view],
  () => {
    if (route.path === "/inventory/report/" + props.kind)
      state.view = reportView(props.kind, route.query.view);
  },
  { immediate: true }
);
</script>
<template>
  <div class="fa-full-height">
    <ElRadioGroup :model-value="state.view" class="mb-3" @change="changeView"
      ><ElRadioButton v-for="option in options" :key="option.value" :value="option.value">{{
        option.label
      }}</ElRadioButton></ElRadioGroup
    >
    <ReportContent :key="kind + state.view" :kind="kind" :view="state.view" />
  </div>
</template>
