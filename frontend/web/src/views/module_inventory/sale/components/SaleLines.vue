<script setup lang="ts">
import type { SaleLine } from "@/api/module_inventory/sale/client";
import type { GoodsItem } from "@/api/module_inventory/basic/goods";
import type { ColumnOption } from "@/types/component";
import { Delete, Plus } from "@element-plus/icons-vue";
import SaleGoodsPicker from "./SaleGoodsPicker.vue";
import {
  lineAmount,
  storedTotalAmount,
  totalAmount,
  returnLineAmount,
  returnTotalAmount,
} from "../utils/amount";
defineOptions({ name: "SaleLines" });
/** 明细编辑控制，关联来源后限制商品及单价。 */
const props = defineProps<{
  readonly: boolean;
  sourced: boolean;
  /** 出库详情展示已退及剩余数量，不改变退货编辑约束。 */
  showReturns?: boolean;
}>();
/** 商品明细双向模型。 */
const lines = defineModel<SaleLine[]>({ required: true });
const pickerVisible = ref(false);
/** 详情展示固化金额，编辑时按数量和单价计算预估金额。 */
const total = computed(() => {
  try {
    return props.readonly
      ? storedTotalAmount(lines.value)
      : props.sourced
        ? returnTotalAmount(lines.value)
        : totalAmount(lines.value);
  } catch {
    return "-";
  }
});
const columns = computed<ColumnOption<SaleLine>[]>(() => [
  { prop: "line_no", label: "行号", width: 60 },
  { prop: "goods_code", label: "商品编码", minWidth: 130 },
  { prop: "goods_name", label: "商品名称", minWidth: 180 },
  { prop: "spec", label: "规格", minWidth: 110 },
  { prop: "unit", label: "单位", width: 70 },
  ...(props.sourced ? [{ prop: "returnable_quantity", label: "可退数量", width: 110 }] : []),
  ...(props.showReturns
    ? [
        { prop: "returned_quantity", label: "已退数量", width: 110 },
        { prop: "returnable_quantity", label: "剩余可退数量", width: 130 },
      ]
    : []),
  { prop: "quantity", label: "数量", width: 180, useSlot: true },
  { prop: "unit_price", label: "单价", width: 180, useSlot: true },
  {
    prop: "line_amount",
    label: "金额",
    width: 130,
    formatter: (row: SaleLine) => {
      try {
        return props.readonly
          ? String(row.line_amount)
          : props.sourced
            ? returnLineAmount(row)
            : lineAmount(row.quantity, row.unit_price);
      } catch {
        return "-";
      }
    },
  },
  ...(props.readonly
    ? [
        {
          prop: "unit_cost",
          label: "固化单位成本",
          width: 130,
          formatter: (row: SaleLine) => row.unit_cost ?? "-",
        },
        {
          prop: "cost_amount",
          label: "固化成本金额",
          width: 130,
          formatter: (row: SaleLine) => row.cost_amount ?? "-",
        },
      ]
    : []),
  ...(props.readonly
    ? []
    : [{ prop: "operation", label: "操作", width: 65, fixed: "right" as const, useSlot: true }]),
]);
/** 追加商品快照，避免同一商品重复录入。 */
function addGoods(rows: GoodsItem[]): void {
  const existing = new Set(lines.value.map((line) => line.goods_id));
  const additions = rows
    .filter((row) => row.id && !existing.has(row.id))
    .map((row) => ({
      line_no: 0,
      goods_id: row.id!,
      goods_code: row.goods_code,
      goods_name: row.goods_name,
      spec: row.spec,
      unit: row.unit,
      quantity: "1.000",
      unit_price: String(row.sale_price),
      line_amount: "0.00",
    }));
  lines.value = [...lines.value, ...additions].map((line, index) => ({
    ...line,
    line_no: index + 1,
  }));
}
/** 修改明细数量或价格，父级始终收到新数组。 */
function changeValue(
  index: number,
  key: "quantity" | "unit_price",
  value: number | undefined
): void {
  lines.value = lines.value.map((line, lineIndex) =>
    lineIndex === index
      ? { ...line, [key]: value === undefined ? "" : value.toFixed(key === "quantity" ? 3 : 4) }
      : line
  );
}
/** 删除明细并重新编号。 */
function removeLine(index: number): void {
  lines.value = lines.value
    .filter((_, lineIndex) => lineIndex !== index)
    .map((line, lineIndex) => ({ ...line, line_no: lineIndex + 1 }));
}
</script>
<template>
  <section>
    <div class="mb-3 flex items-center justify-between">
      <h3 class="text-base font-medium">商品明细</h3>
      <ElButton v-if="!readonly && !sourced" :icon="Plus" @click="pickerVisible = true"
        >添加商品</ElButton
      >
    </div>
    <FaTable :data="lines" :columns="columns" row-key="line_no" max-height="360">
      <template #quantity="{ row, $index }">
        <span v-if="readonly">{{ row.quantity }}</span>
        <ElInputNumber
          v-else
          :model-value="row.quantity === '' ? undefined : Number(row.quantity)"
          :min="0.001"
          :max="sourced ? Math.min(Number(row.returnable_quantity ?? 0), 1000000000) : 1000000000"
          :precision="3"
          :step="1"
          controls-position="right"
          style="width: 155px"
          @update:model-value="changeValue($index, 'quantity', $event)"
        />
      </template>
      <template #unit_price="{ row, $index }">
        <span v-if="readonly || sourced">{{ row.unit_price }}</span>
        <ElInputNumber
          v-else
          :model-value="row.unit_price === '' ? undefined : Number(row.unit_price)"
          :min="0"
          :max="1000000000"
          :precision="4"
          :step="1"
          controls-position="right"
          style="width: 155px"
          @update:model-value="changeValue($index, 'unit_price', $event)"
        />
      </template>
      <template #operation="{ $index }">
        <ElTooltip content="移除商品"
          ><ElButton :icon="Delete" circle text type="danger" @click="removeLine($index)"
        /></ElTooltip>
      </template>
    </FaTable>
    <div class="mt-3 flex justify-end gap-6">
      <span>共 {{ lines.length }} 项</span
      ><strong
        >{{ sourced ? (readonly ? "退货合计" : "预计退货合计") : "原价合计" }}：{{ total }}</strong
      >
    </div>
    <SaleGoodsPicker
      v-model="pickerVisible"
      :excluded-ids="lines.map((line) => line.goods_id)"
      @select="addGoods"
    />
  </section>
</template>
