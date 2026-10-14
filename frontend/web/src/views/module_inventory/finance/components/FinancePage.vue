<script setup lang="ts">
import type { FinanceKind } from "@/api/module_inventory/finance/client";
import FinanceList from "./FinanceList.vue";
/** 应收或应付页面入口。 */
const props = defineProps<{ kind: FinanceKind }>();
const route = useRoute();
const router = useRouter();
/** 页面局部状态，缓存页不响应其他往来页面的 URL 参数。 */
interface PageState {
  view: "balance" | "bills";
  partyId?: number;
}
const state = reactive<PageState>({ view: "bills" });
const view = computed(() => state.view);
const partyId = computed(() => state.partyId);
/** 仅从当前业务页面恢复视图和余额跳转的对象限制。 */
function restoreRoute(): void {
  if (route.path !== "/inventory/finance/" + props.kind) return;
  state.view = route.query.view === "balance" ? "balance" : "bills";
  const value = Number(route.query.party_id);
  state.partyId = Number.isSafeInteger(value) && value > 0 ? value : undefined;
}
watch(() => [route.path, route.query.view, route.query.party_id], restoreRoute, {
  immediate: true,
});
/** 切换账单明细和当前余额，取消旧对象限制。 */
function changeView(value: string | number | boolean | undefined): void {
  void router.replace({ query: { view: value === "balance" ? "balance" : "bills" } });
}
/** 从往来余额查看该对象的全部账单。 */
function selectParty(id: number): void {
  void router.replace({ query: { view: "bills", party_id: id } });
}
</script>
<template>
  <div class="fa-full-height">
    <ElRadioGroup :model-value="view" class="mb-3" @change="changeView">
      <ElRadioButton value="bills">账单明细</ElRadioButton>
      <ElRadioButton value="balance">往来余额</ElRadioButton>
    </ElRadioGroup>
    <FinanceList
      :key="kind + view + (partyId ?? '')"
      :kind="props.kind"
      :balance="view === 'balance'"
      :party-id="partyId"
      @select-party="selectParty"
    />
  </div>
</template>
