<script setup lang="ts">
import type { ReportRow } from "@/api/module_inventory/report/client";
import PurchaseDialog from "@/views/module_inventory/purchase/components/PurchaseDialog.vue";
import SaleDialog from "@/views/module_inventory/sale/components/SaleDialog.vue";
/** 报表来源信息，仅支持业务明细行，不从汇总行推导单据。 */
const props = defineProps<{ row?: ReportRow }>();
/** 原业务详情始终只读，显隐由父组件控制。 */
const visible = defineModel<boolean>({ required: true });
const { hasAuth } = useAuth();
const source = computed(() => props.row?.source);
const permission = computed(() =>
  source.value ? "module_inventory:" + source.value.business_type + ":detail" : ""
);
</script>
<template>
  <template v-if="source && hasAuth(permission)">
    <PurchaseDialog
      v-if="source.business_type === 'purchase_in' || source.business_type === 'purchase_return'"
      :key="source.business_type + source.business_id"
      v-model="visible"
      :kind="source.business_type === 'purchase_in' ? 'in' : 'return'"
      mode="detail"
      :document-id="source.business_id"
    />
    <SaleDialog
      v-else-if="source.business_type === 'sale_out' || source.business_type === 'sale_return'"
      :key="source.business_type + source.business_id"
      v-model="visible"
      :kind="source.business_type === 'sale_out' ? 'out' : 'return'"
      mode="detail"
      :document-id="source.business_id"
    />
  </template>
</template>
