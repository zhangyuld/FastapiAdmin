<script setup lang="ts">
import type { FinanceRecord } from "@/api/module_inventory/finance/client";
import PurchaseDialog from "@/views/module_inventory/purchase/components/PurchaseDialog.vue";
import SaleDialog from "@/views/module_inventory/sale/components/SaleDialog.vue";
/** 来源账单指针，原单仍由业务详情权限授权。 */
const props = defineProps<{ record?: FinanceRecord }>();
/** 只读来源弹窗的双向显隐状态。 */
const visible = defineModel<boolean>({ required: true });
const { hasAuth } = useAuth();
const type = computed(() => props.record?.business_type ?? "");
const permission = computed(() => "module_inventory:" + type.value + ":detail");
</script>
<template>
  <template v-if="record?.business_id && hasAuth(permission)">
    <PurchaseDialog
      v-if="type === 'purchase_in' || type === 'purchase_return'"
      :key="type + record.business_id"
      v-model="visible"
      :kind="type === 'purchase_in' ? 'in' : 'return'"
      mode="detail"
      :document-id="record.business_id"
    />
    <SaleDialog
      v-else-if="type === 'sale_out' || type === 'sale_return'"
      :key="type + record.business_id"
      v-model="visible"
      :kind="type === 'sale_out' ? 'out' : 'return'"
      mode="detail"
      :document-id="record.business_id"
    />
  </template>
</template>
