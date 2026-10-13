<script setup lang="ts">
import dayjs from "dayjs";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import PurchaseInAPI from "@/api/module_inventory/purchase/in";
import PurchaseReturnAPI from "@/api/module_inventory/purchase/return";
import type {
  PurchaseKind,
  PurchaseDocument,
  PurchaseLine,
  PurchaseSaveBody,
} from "@/api/module_inventory/purchase/client";
import type { DialogType } from "@/hooks/core/useCrudDialog";
import { usePurchaseOptions } from "../composables/usePurchaseOptions";
import { scaledDecimal, decimalText, totalAmount } from "../utils/amount";
import PurchaseLines from "./PurchaseLines.vue";
import SourcePicker from "./SourcePicker.vue";
import PurchaseReturnHistory from "./PurchaseReturnHistory.vue";
/** 关联详情按需加载，避免共享单据弹窗的静态循环依赖。 */
const RelatedReturnDialog = defineAsyncComponent(() => import("./PurchaseDialog.vue"));
defineOptions({ name: "PurchaseDocumentDialog" });
/** 单据弹窗输入。 */
const props = defineProps<{ kind: PurchaseKind; mode: DialogType; documentId?: number }>();
/** 草稿保存后的列表刷新事件。 */
const emit = defineEmits<{ success: [] }>();
const visible = defineModel<boolean>({ required: true });
/** 本地单据编辑状态。 */
interface PurchaseFormState {
  supplier_id?: number;
  warehouse_id?: number;
  business_date: string;
  remark: string;
  return_reason: string;
  source_purchase_in_id?: number;
  source_order_no: string;
  items: PurchaseLine[];
}
const state = ref<PurchaseFormState>(emptyState());
const document = ref<PurchaseDocument>();
const formRef = ref<FormInstance>();
const loading = ref(false);
const failed = ref(false);
const saving = ref(false);
const sourceVisible = ref(false);
/** 入库详情内打开的退货单，只允许详情模式。 */
const relatedReturn = reactive<{ visible: boolean; id?: number }>({ visible: false });
let sequence = 0;
const {
  suppliers,
  warehouses,
  supplierLoading,
  warehouseLoading,
  searchSuppliers,
  searchWarehouses,
  retainOptions,
} = usePurchaseOptions();
const api = computed(() => (props.kind === "in" ? PurchaseInAPI : PurchaseReturnAPI));
const label = computed(() => (props.kind === "in" ? "采购入库" : "采购退货"));
const readonly = computed(
  () => props.mode === "detail" || (document.value && document.value.status !== 0)
);
const sourced = computed(() => !!state.value.source_purchase_in_id);
/** 退货只读档案名称，兼容历史档案未出现在启用选项中的情况。 */
const supplierName = computed<string>(
  () =>
    suppliers.value.find((item) => item.value === state.value.supplier_id)?.label ??
    (state.value.supplier_id ? String(state.value.supplier_id) : "")
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
const rules: FormRules<PurchaseFormState> = {
  source_purchase_in_id: [{ required: true, message: "请选择原采购入库单", trigger: "change" }],
  supplier_id: [{ required: true, message: "请选择供应商", trigger: "change" }],
  warehouse_id: [{ required: true, message: "请选择仓库", trigger: "change" }],
  business_date: [{ required: true, message: "请选择业务日期", trigger: "change" }],
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
/** 生成空白采购单据。 */
function emptyState(): PurchaseFormState {
  return {
    business_date: dayjs().format("YYYY-MM-DD"),
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
    await Promise.all([searchSuppliers(), searchWarehouses()]);
    if (current !== sequence || !visible.value) return;
    if (props.mode !== "create") {
      if (!props.documentId) throw new Error("缺少单据 ID");
      const response = await api.value.detail(props.documentId);
      if (current !== sequence || !visible.value) return;
      const item = response.data.data;
      if (!Array.isArray(item.items)) throw new Error("详情接口缺少商品明细");
      document.value = item;
      state.value = {
        supplier_id: item.supplier_id,
        warehouse_id: item.warehouse_id,
        business_date: item.business_date,
        remark: item.remark ?? "",
        return_reason: item.return_reason ?? "",
        source_purchase_in_id: item.source_purchase_in_id,
        source_order_no: item.source_order_no ?? "",
        items: item.items.map((line) => ({ ...line })),
      };
      retainOptions(item.supplier_id, item.supplier_name, item.warehouse_id, item.warehouse_name);
      if (
        props.kind === "return" &&
        item.source_purchase_in_id &&
        item.status === 0 &&
        props.mode === "update"
      ) {
        const available = await PurchaseInAPI.returnable(item.source_purchase_in_id, {
          exclude_return_id: item.id,
        });
        if (current !== sequence || !visible.value) return;
        state.value.items = state.value.items.map((line) => ({
          ...line,
          returnable_quantity: available.data.data.items?.find(
            (source) => source.id === line.source_purchase_in_item_id
          )?.returnable_quantity,
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
async function applySource(source: PurchaseDocument): Promise<void> {
  if (readonly.value || loading.value || saving.value) return;
  const current = sequence;
  if (state.value.items.length) {
    try {
      await ElMessageBox.confirm("切换原入库单将替换当前商品明细，是否继续？", "切换来源", {
        type: "warning",
      });
    } catch {
      return;
    }
  }
  if (current !== sequence || !visible.value) return;
  retainOptions(
    source.supplier_id,
    source.supplier_name,
    source.warehouse_id,
    source.warehouse_name
  );
  state.value = {
    ...state.value,
    supplier_id: source.supplier_id,
    warehouse_id: source.warehouse_id,
    source_purchase_in_id: source.id,
    source_order_no: source.order_no,
    items: (source.items ?? [])
      .filter((line) => Number(line.returnable_quantity) > 0)
      .map((line, index) => ({
        ...line,
        id: undefined,
        line_no: index + 1,
        source_purchase_in_item_id: line.id,
        quantity: String(line.returnable_quantity),
      })),
  };
}
/** 校验明细精度、来源和可退数量并保存草稿。 */
async function submit(): Promise<void> {
  if (saving.value || loading.value || failed.value || readonly.value) return;
  if (props.kind === "return" && !sourced.value) {
    ElMessage.error("请选择原采购入库单");
    return;
  }
  if (!(await formRef.value?.validate().catch(() => false))) return;
  try {
    if (!state.value.items.length) throw new Error("请至少添加一项商品");
    const seen = new Set<number>();
    const items = state.value.items.map((line) => {
      if (seen.has(line.source_purchase_in_item_id ?? line.goods_id))
        throw new Error("存在重复商品明细");
      seen.add(line.source_purchase_in_item_id ?? line.goods_id);
      const quantity = scaledDecimal(line.quantity, 3);
      const price = scaledDecimal(line.unit_price, 4);
      if (quantity <= 0n) throw new Error("商品数量必须大于零");
      if (
        sourced.value &&
        (!line.source_purchase_in_item_id ||
          line.returnable_quantity === undefined ||
          quantity > scaledDecimal(line.returnable_quantity, 3))
      )
        throw new Error("退货数量超过可退数量或来源数据缺失");
      return {
        goods_id: line.goods_id,
        quantity: decimalText(quantity, 3),
        unit_price: decimalText(price, 4),
        ...(sourced.value ? { source_purchase_in_item_id: line.source_purchase_in_item_id } : {}),
      };
    });
    if (scaledDecimal(totalAmount(state.value.items), 2) > 999999999999999999n)
      throw new Error("单据金额超过允许范围");
    const body: PurchaseSaveBody = {
      supplier_id: state.value.supplier_id!,
      warehouse_id: state.value.warehouse_id!,
      business_date: state.value.business_date,
      remark: state.value.remark.trim(),
      items,
      ...(props.kind === "return"
        ? {
            return_reason: state.value.return_reason.trim(),
            source_purchase_in_id: state.value.source_purchase_in_id,
          }
        : {}),
    };
    saving.value = true;
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
    <div v-loading="loading" class="purchase-form">
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
              ><ElFormItem label="原入库单" prop="source_purchase_in_id"
                ><ElInput
                  :model-value="state.source_order_no"
                  readonly
                  placeholder="请选择原采购入库单"
                  ><template v-if="!readonly" #append
                    ><ElTooltip content="选择原入库单"
                      ><ElButton
                        :icon="Search"
                        @click="
                          sourceVisible = true
                        " /></ElTooltip></template></ElInput></ElFormItem
            ></ElCol>
            <ElCol :xs="24" :sm="12"
              ><ElFormItem label="供应商" prop="supplier_id"
                ><ElInput
                  v-if="kind === 'return'"
                  :model-value="supplierName"
                  readonly
                  placeholder="选择原入库单后自动带出" /><ElSelect
                  v-else
                  v-model="state.supplier_id"
                  filterable
                  remote
                  :remote-method="searchSuppliers"
                  :loading="supplierLoading"
                  :disabled="readonly || sourced || loading || saving"
                  placeholder="请选择供应商"
                  ><ElOption
                    v-for="item in suppliers"
                    :key="item.value"
                    :value="item.value"
                    :label="item.label" /></ElSelect></ElFormItem
            ></ElCol>
            <ElCol :xs="24" :sm="12"
              ><ElFormItem :label="kind === 'in' ? '入库仓库' : '退货仓库'" prop="warehouse_id"
                ><ElInput
                  v-if="kind === 'return'"
                  :model-value="warehouseName"
                  readonly
                  placeholder="选择原入库单后自动带出" /><ElSelect
                  v-else
                  v-model="state.warehouse_id"
                  filterable
                  remote
                  :remote-method="searchWarehouses"
                  :loading="warehouseLoading"
                  :disabled="readonly || sourced || loading || saving"
                  placeholder="请选择仓库"
                  ><ElOption
                    v-for="item in warehouses"
                    :key="item.value"
                    :value="item.value"
                    :label="item.label" /></ElSelect></ElFormItem
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
        <PurchaseLines
          v-model="state.items"
          :readonly="!!readonly || loading || saving"
          :sourced="kind === 'return' || sourced"
          :show-returns="kind === 'in' && !!readonly"
        />
        <PurchaseReturnHistory
          v-if="visible && kind === 'in' && readonly && document?.return_summary"
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
    <SourcePicker
      v-model="sourceVisible"
      :return-id="documentId"
      :source-id="document?.source_purchase_in_id"
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
.purchase-form {
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
