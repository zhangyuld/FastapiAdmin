<script setup lang="ts">
import dayjs from "dayjs";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import SaleOutAPI from "@/api/module_inventory/sale/out";
import SaleReturnAPI from "@/api/module_inventory/sale/return";
import type {
  SaleKind,
  SaleDocument,
  SaleLine,
  SaleSaveBody,
} from "@/api/module_inventory/sale/client";
import type { DialogType } from "@/hooks/core/useCrudDialog";
import { useSaleOptions } from "../composables/useSaleOptions";
import {
  scaledDecimal,
  decimalText,
  totalAmount,
  receivableAmount,
  returnTotalAmount,
} from "../utils/amount";
import SaleLines from "./SaleLines.vue";
import SaleSourcePicker from "./SaleSourcePicker.vue";
import SaleReturnHistory from "./SaleReturnHistory.vue";
/** 关联详情按需加载，避免共享单据弹窗的静态循环依赖。 */
const RelatedReturnDialog = defineAsyncComponent(() => import("./SaleDialog.vue"));
defineOptions({ name: "SaleDocumentDialog" });
/** 单据弹窗输入。 */
const props = defineProps<{ kind: SaleKind; mode: DialogType; documentId?: number }>();
/** 草稿保存后的列表刷新事件。 */
const emit = defineEmits<{ success: [] }>();
const visible = defineModel<boolean>({ required: true });
/** 本地单据编辑状态。 */
interface SaleFormState {
  customer_id?: number;
  warehouse_id?: number;
  business_date: string;
  discount_amount: string;
  remark: string;
  return_reason: string;
  source_sale_out_id?: number;
  source_order_no: string;
  items: SaleLine[];
}
const state = ref<SaleFormState>(emptyState());
const document = ref<SaleDocument>();
const formRef = ref<FormInstance>();
const loading = ref(false);
const failed = ref(false);
const saving = ref(false);
const sourceVisible = ref(false);
/** 出库详情内打开的退货单，只允许详情模式。 */
const relatedReturn = reactive<{ visible: boolean; id?: number }>({ visible: false });
let sequence = 0;
const {
  customers,
  warehouses,
  customerSelectProps,
  warehouseSelectProps,
  searchCustomers,
  searchWarehouses,
  retainOptions,
} = useSaleOptions(true);
const api = computed(() => (props.kind === "out" ? SaleOutAPI : SaleReturnAPI));
const label = computed(() => (props.kind === "out" ? "销售出库" : "销售退货"));
const readonly = computed(
  () => props.mode === "detail" || (document.value && document.value.status !== 0)
);
const sourced = computed(() => !!state.value.source_sale_out_id);
/** 录单金额为预估，详情金额以服务端固化值展示。 */
const amountSummary = computed(() => {
  if (readonly.value && document.value)
    return {
      original: document.value.original_amount ?? "-",
      discount: document.value.discount_amount ?? "-",
      receivable: document.value.receivable_amount ?? "-",
      returned: document.value.return_amount ?? "-",
    };
  try {
    return {
      original: totalAmount(state.value.items),
      discount: state.value.discount_amount,
      receivable: receivableAmount(state.value.items, state.value.discount_amount),
      returned: props.kind === "return" ? returnTotalAmount(state.value.items) : "-",
    };
  } catch {
    return { original: "-", discount: state.value.discount_amount, receivable: "-", returned: "-" };
  }
});
/** 退货只读档案名称，兼容历史档案未出现在启用选项中的情况。 */
const customerName = computed<string>(
  () =>
    customers.value.find((item) => item.value === state.value.customer_id)?.label ??
    (state.value.customer_id ? String(state.value.customer_id) : "")
);
const warehouseName = computed<string>(
  () =>
    warehouses.value.find((item) => item.value === state.value.warehouse_id)?.label ??
    (state.value.warehouse_id ? String(state.value.warehouse_id) : "")
);
const title = computed(
  () =>
    (props.mode === "create" ? "新增" : readonly.value ? "" : "编辑") +
    label.value +
    (readonly.value ? "详情" : "")
);
const rules: FormRules<SaleFormState> = {
  source_sale_out_id: [{ required: true, message: "请选择原销售出库单", trigger: "change" }],
  customer_id: [{ required: true, message: "请选择客户", trigger: "change" }],
  warehouse_id: [{ required: true, message: "请选择仓库", trigger: "change" }],
  business_date: [{ required: true, message: "请选择业务日期", trigger: "change" }],
  discount_amount: [
    {
      validator: (_rule, _value, callback) => {
        try {
          if (props.kind === "out")
            receivableAmount(state.value.items, state.value.discount_amount);
          callback();
        } catch (error) {
          callback(error instanceof Error ? error : new Error("优惠金额无效"));
        }
      },
      trigger: "blur",
    },
  ],
  return_reason: [
    {
      validator: (_rule, value, callback) =>
        callback(
          props.kind === "return" && !String(value ?? "").trim()
            ? new Error("请输入退货原因")
            : undefined
        ),
      trigger: "blur",
    },
  ],
};
/** 生成空白销售单据。 */
function emptyState(): SaleFormState {
  return {
    business_date: dayjs().format("YYYY-MM-DD"),
    discount_amount: "0.00",
    remark: "",
    return_reason: "",
    source_order_no: "",
    items: [],
  };
}
/** 读取历史单据，避免弹窗关闭后的旧请求覆盖新单据。 */
async function initialize(): Promise<void> {
  const current = ++sequence;
  state.value = emptyState();
  document.value = undefined;
  failed.value = false;
  loading.value = true;
  try {
    await Promise.all([searchCustomers(), searchWarehouses()]);
    if (current !== sequence || !visible.value) return;
    if (props.mode !== "create") {
      if (!props.documentId) throw new Error("缺少单据 ID");
      const response = await api.value.detail(props.documentId);
      if (current !== sequence || !visible.value) return;
      const item = response.data.data;
      if (!Array.isArray(item.items)) throw new Error("详情接口缺少商品明细");
      document.value = item;
      state.value = {
        customer_id: item.customer_id,
        warehouse_id: item.warehouse_id,
        business_date: item.business_date,
        discount_amount: String(item.discount_amount ?? "0.00"),
        remark: item.remark ?? "",
        return_reason: item.return_reason ?? "",
        source_sale_out_id: item.source_sale_out_id,
        source_order_no: item.source_order_no ?? "",
        items: item.items.map((line) => ({ ...line })),
      };
      retainOptions(item.customer_id, item.customer_name, item.warehouse_id, item.warehouse_name);
      if (
        props.kind === "return" &&
        item.source_sale_out_id &&
        item.status === 0 &&
        props.mode === "update"
      ) {
        const available = await SaleOutAPI.returnable(item.source_sale_out_id, {
          exclude_return_id: item.id,
        });
        if (current !== sequence || !visible.value) return;
        state.value.items = state.value.items.map((line) => ({
          ...line,
          returnable_quantity: available.data.data.items?.find(
            (source) => source.id === line.source_sale_out_item_id
          )?.returnable_quantity,
          returnable_amount: available.data.data.items?.find(
            (source) => source.id === line.source_sale_out_item_id
          )?.returnable_amount,
        }));
      }
    }
  } catch (error) {
    if (current === sequence && visible.value) {
      failed.value = true;
      if (error instanceof Error) ElMessage.error(error.message);
    }
  } finally {
    if (current === sequence) loading.value = false;
  }
}
/** 切换来源前确认清除现有明细。 */
async function applySource(source: SaleDocument): Promise<void> {
  if (readonly.value || loading.value || saving.value) return;
  const current = sequence;
  if (state.value.items.length) {
    try {
      await ElMessageBox.confirm("切换原出库单将替换当前商品明细，是否继续？", "切换来源", {
        type: "warning",
      });
    } catch {
      return;
    }
  }
  if (current !== sequence || !visible.value) return;
  retainOptions(
    source.customer_id,
    source.customer_name,
    source.warehouse_id,
    source.warehouse_name
  );
  state.value = {
    ...state.value,
    customer_id: source.customer_id,
    warehouse_id: source.warehouse_id,
    source_sale_out_id: source.id,
    source_order_no: source.order_no,
    items: (source.items ?? [])
      .filter((line) => Number(line.returnable_quantity) > 0)
      .map((line, index) => ({
        ...line,
        id: undefined,
        line_no: index + 1,
        source_sale_out_item_id: line.id,
        quantity: String(line.returnable_quantity),
      })),
  };
}
/** 校验明细精度、来源和可退数量并保存草稿。 */
async function submit(): Promise<void> {
  if (saving.value || loading.value || failed.value || readonly.value) return;
  if (props.kind === "return" && !sourced.value) {
    ElMessage.error("请选择原销售出库单");
    return;
  }
  saving.value = true;
  try {
    if (!(await formRef.value?.validate().catch(() => false))) return;
    if (!state.value.items.length) throw new Error("请至少添加一项商品");
    const seen = new Set<number>();
    const items = state.value.items.map((line) => {
      if (seen.has(line.source_sale_out_item_id ?? line.goods_id))
        throw new Error("存在重复商品明细");
      seen.add(line.source_sale_out_item_id ?? line.goods_id);
      const quantity = scaledDecimal(line.quantity, 3);
      const price = scaledDecimal(line.unit_price, 4);
      if (quantity <= 0n) throw new Error("商品数量必须大于零");
      if (
        sourced.value &&
        (!line.source_sale_out_item_id ||
          line.returnable_quantity === undefined ||
          quantity > scaledDecimal(line.returnable_quantity, 3))
      )
        throw new Error("退货数量超过可退数量或来源数据缺失");
      return {
        goods_id: line.goods_id,
        quantity: decimalText(quantity, 3),
        unit_price: decimalText(price, 4),
        ...(sourced.value ? { source_sale_out_item_id: line.source_sale_out_item_id } : {}),
      };
    });
    if (props.kind === "out") receivableAmount(state.value.items, state.value.discount_amount);
    else returnTotalAmount(state.value.items);
    const body: SaleSaveBody = {
      customer_id: state.value.customer_id!,
      warehouse_id: state.value.warehouse_id!,
      business_date: state.value.business_date,
      remark: state.value.remark.trim(),
      items,
      ...(props.kind === "return"
        ? {
            return_reason: state.value.return_reason.trim(),
            source_sale_out_id: state.value.source_sale_out_id!,
          }
        : { discount_amount: decimalText(scaledDecimal(state.value.discount_amount, 2), 2) }),
    };
    if (props.mode === "update" && document.value)
      await api.value.update(document.value.id, { ...body, version: document.value.version });
    else await api.value.create(body);
    ElMessage.success("草稿保存成功");
    emit("success");
    visible.value = false;
  } catch (error) {
    if (error instanceof Error) ElMessage.error(error.message);
  } finally {
    saving.value = false;
  }
}
watch(
  visible,
  (value) => {
    if (value) void initialize();
    else {
      sequence++;
      sourceVisible.value = false;
      relatedReturn.visible = false;
    }
  },
  { immediate: true }
);
/** 保存请求完成前阻止关闭单据，避免成功回调关闭其他单据。 */
function beforeClose(done: () => void): void {
  if (!saving.value) done();
}
/** 从关联记录打开只读退货详情。 */
function viewReturn(id: number): void {
  relatedReturn.id = id;
  relatedReturn.visible = true;
}
</script>
<template>
  <FaDialog
    v-model="visible"
    :title="title"
    width="min(1200px, 96vw)"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :before-close="beforeClose"
  >
    <div v-loading="loading" class="sale-form">
      <ElResult v-if="failed" icon="error" title="单据加载失败"
        ><template #extra><ElButton @click="initialize">重试</ElButton></template></ElResult
      >
      <template v-else>
        <ElForm
          ref="formRef"
          :model="state"
          :rules="rules"
          label-width="100px"
          :disabled="readonly || loading || saving"
        >
          <ElRow :gutter="16">
            <ElCol :xs="24" :sm="12"
              ><ElFormItem label="单据编号"
                ><ElInput
                  :model-value="document?.order_no ?? ''"
                  placeholder="保存后生成"
                  disabled /></ElFormItem
            ></ElCol>
            <ElCol :xs="24" :sm="12"
              ><ElFormItem label="业务日期" prop="business_date"
                ><ElDatePicker
                  v-model="state.business_date"
                  type="date"
                  value-format="YYYY-MM-DD"
                  style="width: 100%" /></ElFormItem
            ></ElCol>
            <ElCol v-if="kind === 'return'" :span="24"
              ><ElFormItem label="原出库单" prop="source_sale_out_id"
                ><ElInput
                  :model-value="state.source_order_no"
                  readonly
                  placeholder="请选择原销售出库单"
                  ><template v-if="!readonly" #append
                    ><ElTooltip content="选择原出库单"
                      ><ElButton
                        :icon="Search"
                        @click="
                          sourceVisible = true
                        " /></ElTooltip></template></ElInput></ElFormItem
            ></ElCol>
            <ElCol :xs="24" :sm="12"
              ><ElFormItem label="客户" prop="customer_id"
                ><ElInput
                  v-if="kind === 'return'"
                  :model-value="customerName"
                  readonly
                  placeholder="选择原出库单后自动带出" /><ElSelect
                  v-else
                  v-model="state.customer_id"
                  v-bind="customerSelectProps"
                  :disabled="readonly || sourced || loading || saving"
                  placeholder="请选择客户"
                  ><ElOption
                    v-for="item in customers"
                    :key="item.value"
                    :value="item.value"
                    :label="item.label"
                    :disabled="item.disabled" /></ElSelect></ElFormItem
            ></ElCol>
            <ElCol :xs="24" :sm="12"
              ><ElFormItem :label="kind === 'out' ? '出库仓库' : '退货仓库'" prop="warehouse_id"
                ><ElInput
                  v-if="kind === 'return'"
                  :model-value="warehouseName"
                  readonly
                  placeholder="选择原出库单后自动带出" /><ElSelect
                  v-else
                  v-model="state.warehouse_id"
                  v-bind="warehouseSelectProps"
                  :disabled="readonly || sourced || loading || saving"
                  placeholder="请选择仓库"
                  ><ElOption
                    v-for="item in warehouses"
                    :key="item.value"
                    :value="item.value"
                    :label="item.label"
                    :disabled="item.disabled" /></ElSelect></ElFormItem
            ></ElCol>
            <ElCol v-if="kind === 'return'" :span="24"
              ><ElFormItem label="退货原因" prop="return_reason"
                ><ElInput
                  v-model="state.return_reason"
                  type="textarea"
                  :rows="2"
                  maxlength="500"
                  show-word-limit /></ElFormItem
            ></ElCol>
            <ElCol v-if="kind === 'out'" :xs="24" :sm="12">
              <ElFormItem label="优惠金额" prop="discount_amount">
                <ElInput v-model="state.discount_amount" inputmode="decimal" maxlength="20" />
              </ElFormItem>
            </ElCol>
            <ElCol :span="24"
              ><ElFormItem label="备注"
                ><ElInput
                  v-model="state.remark"
                  type="textarea"
                  :rows="2"
                  maxlength="500"
                  show-word-limit /></ElFormItem
            ></ElCol>
          </ElRow>
        </ElForm>
        <SaleLines
          v-model="state.items"
          :readonly="!!readonly || loading || saving"
          :sourced="kind === 'return' || sourced"
          :show-returns="kind === 'out' && !!readonly"
        />
        <ElDescriptions class="mt-3" :column="1" border>
          <template v-if="kind === 'out'">
            <ElDescriptionsItem label="原价合计">{{ amountSummary.original }}</ElDescriptionsItem>
            <ElDescriptionsItem label="优惠金额">{{ amountSummary.discount }}</ElDescriptionsItem>
            <ElDescriptionsItem :label="readonly ? '应收金额' : '预计应收金额'">{{
              amountSummary.receivable
            }}</ElDescriptionsItem>
          </template>
          <ElDescriptionsItem v-else :label="readonly ? '退货金额' : '预计退货金额'">{{
            amountSummary.returned
          }}</ElDescriptionsItem>
        </ElDescriptions>
        <SaleReturnHistory
          v-if="visible && kind === 'out' && readonly && document?.return_summary"
          :key="document.id"
          :source-id="document.id"
          :summary="document.return_summary"
          @detail="viewReturn"
          @refresh="initialize"
        />
        <ElDescriptions v-if="document" class="mt-4" :column="2" border>
          <ElDescriptionsItem label="状态">{{
            ["草稿", "已确认", "已作废"][document.status]
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建人">{{
            document.created_by?.name ?? "-"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建时间">{{
            document.created_time ?? "-"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="更新人">{{
            document.updated_by?.name ?? "-"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="更新时间">{{
            document.updated_time ?? "-"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="确认人">{{
            document.confirmed_name ?? "-"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="确认时间">{{
            document.confirmed_time ?? "-"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="作废人">{{ document.voided_name ?? "-" }}</ElDescriptionsItem>
          <ElDescriptionsItem label="作废时间">{{
            document.voided_time ?? "-"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="作废原因">{{
            document.void_reason ?? "-"
          }}</ElDescriptionsItem>
        </ElDescriptions>
      </template>
    </div>
    <template #footer>
      <ElButton :disabled="saving" @click="visible = false">{{
        readonly ? "关闭" : "取消"
      }}</ElButton>
      <ElButton
        v-if="!readonly"
        type="primary"
        :loading="saving"
        :disabled="loading || failed"
        @click="submit"
        >保存草稿</ElButton
      >
    </template>
    <SaleSourcePicker
      v-model="sourceVisible"
      :return-id="documentId"
      :source-id="document?.source_sale_out_id"
      @select="applySource"
    />
    <RelatedReturnDialog
      v-if="relatedReturn.visible"
      v-model="relatedReturn.visible"
      kind="return"
      mode="detail"
      :document-id="relatedReturn.id"
      append-to-body
    />
  </FaDialog>
</template>
<style scoped lang="scss">
.sale-form {
  max-height: 70vh;
  overflow: auto;

  :deep(.el-descriptions__table) {
    table-layout: fixed;
  }

  :deep(.el-descriptions__content) {
    overflow-wrap: anywhere;
  }
}
</style>
