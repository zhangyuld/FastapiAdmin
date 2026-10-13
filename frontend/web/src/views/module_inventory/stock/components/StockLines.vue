<script setup lang="ts">
import type { StockLine } from "@/api/module_inventory/stock/client";
import type { GoodsItem } from "@/api/module_inventory/basic/goods";
import CheckAPI from "@/api/module_inventory/stock/check";
import type { ColumnOption } from "@/types/component";
import { Plus, Delete } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { preview } from "../utils/amount";
import StockGoodsPicker from "./StockGoodsPicker.vue";
/** 明细类型、仓库和只读状态由单据弹窗控制。 */
const props = defineProps<{
  kind: "opening" | "check";
  warehouseId?: number;
  readonly: boolean;
  disabled: boolean;
}>();
/** 异步获取账面快照期间阻止父单据保存。 */
const emit = defineEmits<{ loading: [value: boolean] }>();
/** 商品快照、业务输入及已固化成本。 */
const lines = defineModel<StockLine[]>({ required: true });
const pickerVisible = ref(false);
const loading = ref(false);
const { hasAuth } = useAuth();
/** 详情展示固化差异，编辑展示定点数预估。 */
function amount(row: StockLine, key: "difference" | "amount"): string {
  if (props.readonly)
    return String(
      key === "amount" ? (row.cost_amount ?? "-") : (row.difference_quantity ?? row.quantity ?? "-")
    );
  try {
    return preview(row, props.kind)[key];
  } catch {
    return "-";
  }
}
const columns = computed<ColumnOption<StockLine>[]>(() => [
  { prop: "goods_code", label: "商品编码", minWidth: 140 },
  { prop: "goods_name", label: "商品名称", minWidth: 180 },
  { prop: "spec", label: "规格", minWidth: 110 },
  { prop: "unit", label: "单位", width: 70 },
  ...(props.kind === "check"
    ? [
        { prop: "system_quantity", label: "账面数量", width: 120 },
        { prop: "system_stock_amount", label: "账面金额", width: 120 },
      ]
    : []),
  {
    prop: props.kind === "opening" ? "quantity" : "actual_quantity",
    label: props.kind === "opening" ? "期初数量" : "实盘数量",
    width: 160,
    useSlot: true,
  },
  { prop: "unit_cost", label: "单位成本", width: 160, useSlot: true },
  ...(props.kind === "check"
    ? [
        {
          prop: "difference_quantity",
          label: "差异数量",
          width: 120,
          formatter: (row: StockLine) => amount(row, "difference"),
        },
      ]
    : []),
  {
    prop: "cost_amount",
    label: props.kind === "check" ? "差异成本" : "期初金额",
    width: 140,
    formatter: (row: StockLine) => amount(row, "amount"),
  },
  ...(!props.readonly
    ? [{ prop: "operation", label: "操作", width: 65, fixed: "right" as const, useSlot: true }]
    : []),
]);
/** 更新业务输入，不允许编辑账面快照。 */
function change(
  index: number,
  field: "quantity" | "actual_quantity" | "unit_cost",
  value: string
): void {
  lines.value = lines.value.map((row, current) =>
    current === index ? { ...row, [field]: value } : row
  );
}
/** 移除草稿商品行，不改变其他行的快照。 */
function remove(index: number): void {
  lines.value = lines.value.filter((_, current) => current !== index);
}
/** 期初填参考成本，盘点通过后端获取当前账面快照。 */
async function add(rows: GoodsItem[]): Promise<void> {
  if (!props.warehouseId || props.disabled || loading.value) return;
  const warehouse = props.warehouseId;
  loading.value = true;
  emit("loading", true);
  try {
    const incoming: StockLine[] =
      props.kind === "check"
        ? (
            await CheckAPI.snapshot({
              warehouse_id: warehouse,
              goods_ids: rows.map((row) => row.id!),
            })
          ).data.data.map((row) => ({
            ...row,
            actual_quantity: row.system_quantity ?? "0.000",
            unit_cost: String(row.system_quantity) === "0.000" ? "" : row.unit_cost,
          }))
        : rows.map((row) => ({
            goods_id: row.id!,
            goods_code: row.goods_code,
            goods_name: row.goods_name,
            spec: row.spec,
            unit: row.unit,
            quantity: "1.000",
            unit_cost: String(row.reference_cost_price),
          }));
    if (warehouse === props.warehouseId)
      lines.value = [
        ...lines.value,
        ...incoming.filter(
          (row) => !lines.value.some((existing) => existing.goods_id === row.goods_id)
        ),
      ];
  } catch {
    ElMessage.error("商品快照加载失败，未添加明细");
  } finally {
    loading.value = false;
    emit("loading", false);
  }
}
</script>
<template>
  <section>
    <div class="mb-3 flex items-center justify-between">
      <h3 class="text-base font-medium">商品明细</h3>
      <ElButton
        v-if="!readonly && hasAuth('module_inventory:goods:query')"
        :icon="Plus"
        :disabled="disabled || !warehouseId"
        :loading="loading"
        @click="pickerVisible = true"
        >添加商品</ElButton
      >
    </div>
    <FaTable :data="lines" :columns="columns" row-key="goods_id" max-height="380">
      <template #quantity="{ row, $index }"
        ><span v-if="readonly">{{ row.quantity }}</span
        ><ElInput
          v-else
          :model-value="String(row.quantity ?? '')"
          :disabled="disabled"
          inputmode="decimal"
          @update:model-value="change($index, 'quantity', $event)"
      /></template>
      <template #actual_quantity="{ row, $index }"
        ><span v-if="readonly">{{ row.actual_quantity }}</span
        ><ElInput
          v-else
          :model-value="String(row.actual_quantity ?? '')"
          :disabled="disabled"
          inputmode="decimal"
          @update:model-value="change($index, 'actual_quantity', $event)"
      /></template>
      <template #unit_cost="{ row, $index }"
        ><span v-if="readonly || (kind === 'check' && String(row.system_quantity) !== '0.000')">{{
          row.unit_cost
        }}</span
        ><ElInput
          v-else
          :model-value="String(row.unit_cost)"
          :disabled="disabled"
          inputmode="decimal"
          @update:model-value="change($index, 'unit_cost', $event)"
      /></template>
      <template #operation="{ $index }"
        ><ElTooltip content="移除商品"
          ><ElButton
            :icon="Delete"
            text
            circle
            type="danger"
            :disabled="disabled"
            @click="remove($index)" /></ElTooltip
      ></template>
    </FaTable>
    <StockGoodsPicker
      v-model="pickerVisible"
      :excluded-ids="lines.map((row) => row.goods_id)"
      @select="add"
    />
  </section>
</template>
