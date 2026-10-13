<script setup lang="ts">
import dayjs from "dayjs";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import OpeningAPI from "@/api/module_inventory/stock/opening";
import CheckAPI from "@/api/module_inventory/stock/check";
import type { StockLine, StockDocument, StockSaveBody } from "@/api/module_inventory/stock/client";
import type { DialogType } from "@/hooks/core/useCrudDialog";
import { useStockOptions } from "../composables/useStockOptions";
import { scaled, decimal, preview } from "../utils/amount";
import StockLines from "./StockLines.vue";
/** 单据弹窗输入，详情不能修改仓库或业务字段。 */
const props = defineProps<{ kind: "opening" | "check"; mode: DialogType; documentId?: number }>();
/** 保存成功后刷新主单列表。 */
const emit = defineEmits<{ success: [] }>();
/** 单据弹窗显隐模型。 */
const visible = defineModel<boolean>({ required: true });
/** 单据本地编辑状态，不放入跨页面 store。 */
interface FormState {
  warehouse_id?: number;
  business_date: string;
  remark: string;
  items: StockLine[];
}
const state = reactive<FormState>({
  business_date: dayjs().format("YYYY-MM-DD"),
  remark: "",
  items: [],
});
const document = ref<StockDocument>();
const formRef = ref<FormInstance>();
const loading = ref(false);
const failed = ref(false);
const saving = ref(false);
const snapshotLoading = ref(false);
let sequence = 0;
const api = props.kind === "opening" ? OpeningAPI : CheckAPI;
const label = props.kind === "opening" ? "期初库存" : "库存盘点";
const readonly = computed(
  () => props.mode === "detail" || (document.value !== undefined && document.value.status !== 0)
);
const { hasAuth } = useAuth();
const prefix = "module_inventory:stock_" + props.kind;
const {
  warehouses,
  loading: warehouseLoading,
  searchWarehouses,
  retainWarehouse,
} = useStockOptions(true);
const rules: FormRules = {
  warehouse_id: [{ required: true, message: "请选择仓库", trigger: "change" }],
  business_date: [{ required: true, message: "请选择业务日期", trigger: "change" }],
};
/** 将服务端完整快照填入本地表单。 */
function populate(value: StockDocument): void {
  document.value = value;
  state.warehouse_id = value.warehouse_id;
  state.business_date = value.business_date;
  state.remark = value.remark ?? "";
  state.items = (value.items ?? []).map((row) => ({ ...row }));
  retainWarehouse(value.warehouse_id, value.warehouse_name);
}
/** 重新打开时清空旧状态，并丢弃过期详情响应。 */
async function initialize(): Promise<void> {
  const current = ++sequence;
  loading.value = true;
  failed.value = false;
  document.value = undefined;
  state.warehouse_id = undefined;
  state.business_date = dayjs().format("YYYY-MM-DD");
  state.remark = "";
  state.items = [];
  try {
    if (!readonly.value && hasAuth("module_inventory:warehouse:query")) await searchWarehouses();
    if (props.documentId) {
      const response = await api.detail(props.documentId);
      if (current === sequence) populate(response.data.data);
    }
  } catch {
    if (current === sequence) failed.value = true;
  } finally {
    if (current === sequence) loading.value = false;
  }
}
/** 仓库更换后不能保留旧仓库的账面快照。 */
function changeWarehouse(): void {
  state.items = [];
}
/** 验证精度并仅提交当前单据种类允许的业务字段。 */
function buildBody(): StockSaveBody {
  if (!state.warehouse_id || !state.business_date || !state.items.length)
    throw new Error("请选择仓库、日期并添加商品");
  return {
    warehouse_id: state.warehouse_id,
    business_date: state.business_date,
    remark: state.remark.trim(),
    items: state.items.map((row) => {
      preview(row, props.kind);
      if (props.kind === "opening")
        return {
          goods_id: row.goods_id,
          quantity: decimal(scaled(row.quantity ?? "", 3), 3),
          unit_cost: decimal(scaled(row.unit_cost, 4), 4),
        };
      return {
        goods_id: row.goods_id,
        actual_quantity: decimal(scaled(row.actual_quantity ?? "", 3), 3),
        ...(String(row.system_quantity) === "0.000" && row.unit_cost !== ""
          ? { unit_cost: decimal(scaled(row.unit_cost, 4), 4) }
          : {}),
      };
    }),
  };
}
/** 保存中禁止重复请求，接口失败不关闭表单。 */
async function save(): Promise<void> {
  if (
    readonly.value ||
    loading.value ||
    saving.value ||
    snapshotLoading.value ||
    failed.value ||
    !hasAuth(prefix + (props.mode === "create" ? ":create" : ":update"))
  )
    return;
  saving.value = true;
  try {
    if (!(await formRef.value?.validate().catch(() => false))) return;
    let body: StockSaveBody;
    try {
      body = buildBody();
    } catch (error) {
      ElMessage.warning((error as Error).message);
      return;
    }
    if (document.value)
      await api.update(document.value.id, { ...body, version: document.value.version });
    else await api.create(body);
    ElMessage.success("保存成功");
    emit("success");
    visible.value = false;
  } catch {
    /* 请求层展示接口失败。 */
  } finally {
    saving.value = false;
  }
}
/** 明确提示刷新会丢弃未保存修改，刷新后保留后端已保存实盘数供重新核对。 */
async function refreshSnapshot(): Promise<void> {
  if (!document.value || readonly.value || saving.value || snapshotLoading.value) return;
  try {
    await ElMessageBox.confirm(
      "重新读取已保存草稿的账面快照？未保存修改会丢弃，刷新后请重新核对实盘数量。",
      "刷新账面快照",
      { type: "warning" }
    );
  } catch {
    return;
  }
  saving.value = true;
  try {
    populate(
      (await CheckAPI.refresh(document.value.id, { version: document.value.version })).data.data
    );
    ElMessage.success("账面快照已刷新，请重新核对实盘数量");
  } catch {
    /* 请求层展示版本冲突或接口失败。 */
  } finally {
    saving.value = false;
  }
}
/** 保存与商品快照加载期间禁止关闭单据。 */
function beforeClose(done: () => void): void {
  if (!saving.value && !snapshotLoading.value) done();
}
/** 关闭当前弹窗，保存过程中不触发其他弹窗的关闭。 */
function close(): void {
  if (!saving.value && !snapshotLoading.value) visible.value = false;
}
watch(
  visible,
  (value) => {
    if (value) void initialize();
    else sequence++;
  },
  { immediate: true }
);
</script>
<template>
  <FaDialog
    v-model="visible"
    :title="(readonly ? '查看' : document ? '编辑' : '新增') + label"
    width="min(1200px, 96vw)"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :before-close="beforeClose"
  >
    <div v-loading="loading">
      <ElResult v-if="failed" icon="error" title="单据加载失败"
        ><template #extra
          ><ElButton :icon="Refresh" @click="initialize">重试</ElButton></template
        ></ElResult
      >
      <template v-else>
        <ElForm
          ref="formRef"
          :model="state"
          :rules="rules"
          label-width="100px"
          :disabled="readonly || loading || saving || snapshotLoading"
        >
          <ElRow :gutter="16">
            <ElCol :xs="24" :sm="12"
              ><ElFormItem label="单据编号"
                ><ElInput
                  :model-value="document?.doc_no ?? ''"
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
            <ElCol :span="24"
              ><ElFormItem label="仓库" prop="warehouse_id"
                ><ElSelect
                  v-model="state.warehouse_id"
                  filterable
                  remote
                  :remote-method="searchWarehouses"
                  :loading="warehouseLoading"
                  style="width: 100%"
                  @change="changeWarehouse"
                  ><ElOption
                    v-for="row in warehouses"
                    :key="row.value"
                    :value="row.value"
                    :label="row.label" /></ElSelect></ElFormItem
            ></ElCol>
            <ElCol :span="24"
              ><ElFormItem label="备注"
                ><ElInput
                  v-model="state.remark"
                  type="textarea"
                  maxlength="500"
                  :rows="2" /></ElFormItem
            ></ElCol>
          </ElRow>
        </ElForm>
        <div
          v-if="kind === 'check' && document && !readonly && hasAuth(prefix + ':update')"
          class="mb-3 flex justify-end"
        >
          <ElButton
            :icon="Refresh"
            :loading="saving"
            :disabled="snapshotLoading"
            @click="refreshSnapshot"
            >刷新账面快照</ElButton
          >
        </div>
        <StockLines
          v-model="state.items"
          :kind="kind"
          :warehouse-id="state.warehouse_id"
          :readonly="readonly"
          :disabled="loading || saving || snapshotLoading"
          @loading="snapshotLoading = $event"
        />
        <ElDescriptions v-if="readonly && document" class="mt-4" :column="2" border>
          <ElDescriptionsItem label="状态">{{
            ["草稿", "已确认", "已作废"][document.status]
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="确认人">{{
            document.confirmed_name ?? "-"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="确认时间">{{
            document.confirmed_time ?? "-"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="作废时间">{{
            document.voided_time ?? "-"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="作废原因">{{
            document.void_reason ?? "-"
          }}</ElDescriptionsItem>
        </ElDescriptions>
      </template>
    </div>
    <template #footer
      ><ElButton :disabled="saving || snapshotLoading" @click="close">关闭</ElButton
      ><ElButton
        v-if="!readonly && hasAuth(prefix + (mode === 'create' ? ':create' : ':update'))"
        type="primary"
        :loading="saving"
        :disabled="loading || failed || snapshotLoading"
        @click="save"
        >保存草稿</ElButton
      ></template
    >
  </FaDialog>
</template>
