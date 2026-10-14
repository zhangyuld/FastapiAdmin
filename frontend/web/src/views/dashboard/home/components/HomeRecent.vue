<script setup lang="ts">
import { defineAsyncComponent, h } from "vue";
import { ElButton } from "element-plus";
import { View } from "@element-plus/icons-vue";
import type { RecentDocument } from "@/api/module_inventory/dashboard";
import type { ColumnOption } from "@/types/component";
import type { DashboardPanelState } from "../composables/useInventoryDashboard";
import { checkPerm } from "@/utils/checkPerm";
import { documentLabels, formatAmount } from "../utils/metrics";
import HomePanel from "./HomePanel.vue";
const PurchaseDialog = defineAsyncComponent(
  () => import("@/views/module_inventory/purchase/components/PurchaseDialog.vue")
);
const SaleDialog = defineAsyncComponent(
  () => import("@/views/module_inventory/sale/components/SaleDialog.vue")
);
/** 最近单据不复用报表的企业共享数据范围。 */
defineProps<{ state: DashboardPanelState<RecentDocument[]> }>();
/** 单据列表独立重试。 */
const emit = defineEmits<{ retry: [] }>();
/** 页面局部的只读来源详情状态。 */
const source = reactive<{ visible: boolean; row?: RecentDocument }>({ visible: false });
/** 离开缓存首页时关闭只读弹窗，避免返回后残留旧单据。 */
onDeactivated(() => {
  source.visible = false;
  source.row = undefined;
});
const canDetail = computed(
  () => !!source.row && checkPerm(`module_inventory:${source.row.business_type}:detail`)
);
/** 即使列表授权，也要单独校验详情按钮权限。 */
function openDetail(row: RecentDocument): void {
  if (!checkPerm(`module_inventory:${row.business_type}:detail`)) return;
  source.row = row;
  source.visible = true;
}
const columns: ColumnOption<RecentDocument>[] = [
  { prop: "business_no", label: "单号", minWidth: 190, showOverflowTooltip: true },
  {
    prop: "business_type",
    label: "类型",
    width: 100,
    formatter: (row) => documentLabels[row.business_type],
  },
  { prop: "business_date", label: "业务日期", width: 115 },
  {
    prop: "amount",
    label: "单据金额",
    minWidth: 120,
    formatter: (row) => formatAmount(row.amount),
  },
  {
    prop: "status",
    label: "状态",
    width: 90,
    formatter: (row) => ["草稿", "已确认", "已作废"][row.status],
  },
  {
    prop: "operation",
    label: "操作",
    width: 85,
    formatter: (row) =>
      checkPerm(`module_inventory:${row.business_type}:detail`)
        ? h(
            ElButton,
            { link: true, type: "primary", icon: View, onClick: () => openDetail(row) },
            () => "查看"
          )
        : "—",
  },
];
</script>
<template>
  <HomePanel
    title="最近单据"
    :loading="state.loading"
    :error="state.error"
    :forbidden="state.forbidden"
    :empty="state.data?.length === 0"
    @retry="emit('retry')"
  >
    <FaTable :data="state.data ?? []" :columns="columns" row-key="id" />
  </HomePanel>
  <template v-if="source.row && canDetail && source.visible">
    <PurchaseDialog
      v-if="
        source.row.business_type === 'purchase_in' || source.row.business_type === 'purchase_return'
      "
      :key="source.row.id"
      v-model="source.visible"
      :kind="source.row.business_type === 'purchase_in' ? 'in' : 'return'"
      mode="detail"
      :document-id="source.row.business_id"
    />
    <SaleDialog
      v-else
      :key="source.row.id"
      v-model="source.visible"
      :kind="source.row.business_type === 'sale_out' ? 'out' : 'return'"
      mode="detail"
      :document-id="source.row.business_id"
    />
  </template>
</template>
