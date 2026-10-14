<script setup lang="ts">
import type { ReportKind, ReportView, ReportQuery } from "@/api/module_inventory/report/client";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import { Refresh } from "@element-plus/icons-vue";
import { useWindowSize } from "@vueuse/core";
import { useReportOptions } from "../composables/useReportOptions";
/** 领域决定对象筛选，维度决定日期和来源单号是否可用。 */
const props = defineProps<{ kind: ReportKind; view: ReportView; loading: boolean }>();
/** 未提交的本地筛选输入，与已提交报表查询分离。 */
const model = defineModel<ReportQuery>({ required: true });
/** 筛选只提交查询，不直接修改列表状态。 */
const emit = defineEmits<{ search: [query: ReportQuery]; reset: [] }>();
const { width } = useWindowSize();
const mobile = computed(() => width.value < 768);
const {
  warehouses,
  categories,
  warehouseLoading,
  failed,
  canWarehouse,
  canCategory,
  searchWarehouses,
  retry,
} = useReportOptions();
const items = computed<SearchFormItem[]>(() =>
  [
    ...(props.kind === "stock" && props.view === "balance"
      ? []
      : [
          {
            label: "业务日期",
            key: "business_date",
            type: "date" as const,
            span: 6,
            props: { type: "daterange", valueFormat: "YYYY-MM-DD" },
          },
        ]),
    ...(props.kind === "stock"
      ? []
      : [
          {
            label: props.kind === "purchase" ? "供应商名称" : "客户名称",
            key: props.kind === "purchase" ? "supplier_name" : "customer_name",
            type: "input" as const,
            clearable: true,
            span: 6,
          },
        ]),
    {
      label: "仓库",
      key: canWarehouse ? "warehouse_id" : "warehouse_name",
      type: canWarehouse ? "select" : "input",
      clearable: true,
      span: 6,
      props: canWarehouse
        ? {
            options: warehouses.value,
            remote: true,
            filterable: true,
            clearable: true,
            remoteMethod: searchWarehouses,
            loading: warehouseLoading.value,
          }
        : {},
    },
    { label: "商品编码", key: "goods_code", type: "input", clearable: true, span: 6 },
    { label: "商品名称", key: "goods_name", type: "input", clearable: true, span: 6 },
    {
      label: "商品分类",
      key: canCategory ? "category_id" : "category_name",
      type: canCategory ? "select" : "input",
      clearable: true,
      span: 6,
      props: canCategory ? { options: categories.value, filterable: true, clearable: true } : {},
    },
    ...(props.view === "documents"
      ? [
          {
            label: "来源单号",
            key: "business_no",
            type: "input" as const,
            clearable: true,
            span: 6,
          },
        ]
      : []),
    ...(props.kind === "stock" && props.view === "balance"
      ? [
          {
            label: "库存预警",
            key: "warning",
            type: "select" as const,
            span: 6,
            props: {
              clearable: true,
              options: [
                { value: "normal", label: "正常" },
                { value: "low", label: "低于下限" },
                { value: "high", label: "高于上限" },
              ],
            },
          },
        ]
      : []),
  ].map((item) => ({ ...item, span: mobile.value ? 24 : item.span }))
);
/** 搜索组件的宽类型输入合并为明确的报表查询，视图由页面固定。 */
function submit(query: object): void {
  emit("search", { ...model.value, ...query, view: props.view });
}
</script>
<template>
  <div>
    <FaSearchBar
      v-model="model"
      :items="items"
      label-width="100px"
      :label-position="mobile ? 'top' : 'right'"
      :disabled-search="loading"
      @search="submit"
      @reset="emit('reset')"
    />
    <ElAlert
      v-if="failed.warehouse || failed.category"
      class="mt-2"
      type="warning"
      title="档案选项加载失败"
      :closable="false"
      ><ElButton link :icon="Refresh" @click="retry">重试</ElButton></ElAlert
    >
  </div>
</template>
