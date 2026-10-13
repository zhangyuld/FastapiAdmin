<script setup lang="ts">
import type { StockRecord } from "@/api/module_inventory/stock/client";
import PurchaseDialog from "@/views/module_inventory/purchase/components/PurchaseDialog.vue";
import SaleDialog from "@/views/module_inventory/sale/components/SaleDialog.vue";
import StockDocumentDialog from "./StockDocumentDialog.vue";
/** 流水来源指针，不以库存查询权限替代来源详情权限。 */
const props = defineProps<{ record?: StockRecord }>();
/** 来源详情显隐状态。 */
const visible = defineModel<boolean>({ required: true });
const { hasAuth } = useAuth();
const type = computed(() => props.record?.business_type ?? "");
const permission = computed(
  () =>
    "module_inventory:" +
    ({
      opening_balance: "stock_opening",
      stock_check_gain: "stock_check",
      stock_check_loss: "stock_check",
    }[type.value] ?? type.value) +
    ":detail"
);
</script>
<template>
  <template v-if="record?.business_id && hasAuth(permission)">
    <PurchaseDialog
      :key="type"
      v-if="type === 'purchase_in' || type === 'purchase_return'"
      v-model="visible"
      :kind="type === 'purchase_in' ? 'in' : 'return'"
      mode="detail"
      :document-id="record.business_id"
    />
    <SaleDialog
      :key="type"
      v-else-if="type === 'sale_out' || type === 'sale_return'"
      v-model="visible"
      :kind="type === 'sale_out' ? 'out' : 'return'"
      mode="detail"
      :document-id="record.business_id"
    />
    <StockDocumentDialog
      :key="type"
      v-else-if="
        type === 'opening_balance' || type === 'stock_check_gain' || type === 'stock_check_loss'
      "
      v-model="visible"
      :kind="type === 'opening_balance' ? 'opening' : 'check'"
      mode="detail"
      :document-id="record.business_id"
    />
  </template>
</template>
