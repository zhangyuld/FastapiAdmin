<script setup lang="ts">
import WarehouseAPI, {
  type WarehouseForm,
  type WarehouseItem,
} from "@/api/module_inventory/basic/warehouse";
import type { DescriptionsItem } from "@/components/display/fa-descriptions/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { DialogType } from "@/hooks/core/useCrudDialog";
import type { FormItemRule } from "element-plus";

defineOptions({
  name: "InventoryWarehouseDialog",
  inheritAttrs: false,
});

/** 仓库弹窗输入属性。 */
interface WarehouseDialogProps {
  /** 弹窗业务模式。 */
  mode: DialogType;
  /** 编辑或查看的仓库 ID。 */
  warehouseId?: number;
}

/** 仓库弹窗输出事件。 */
interface WarehouseDialogEmits {
  /** 仓库保存成功。 */
  success: [];
}

const props = defineProps<WarehouseDialogProps>();
const emit = defineEmits<WarehouseDialogEmits>();
const visible = defineModel<boolean>({ required: true });

const STATUS_OPTIONS = [
  { label: "启用", value: 0 },
  { label: "停用", value: 1 },
] as const;

const initialFormData: WarehouseForm = {
  id: undefined,
  warehouse_code: "",
  warehouse_name: "",
  address: "",
  remark: "",
  status: 0,
};

const formData = ref<WarehouseForm>({ ...initialFormData });
const detailData = ref<Partial<WarehouseItem>>({});
const dataFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const detailLoading = ref(false);
const submitLoading = ref(false);

const dialogTitle = computed(() => {
  if (props.mode === "create") return "新增仓库";
  if (props.mode === "update") return "修改仓库";
  return "仓库详情";
});

const rules: Record<keyof WarehouseForm, FormItemRule[]> = {
  id: [],
  warehouse_code: [
    { required: true, message: "请输入仓库编码", trigger: "blur" },
    { min: 1, max: 64, message: "仓库编码长度应为1至64个字符", trigger: "blur" },
  ],
  warehouse_name: [
    { required: true, message: "请输入仓库名称", trigger: "blur" },
    { min: 1, max: 100, message: "仓库名称长度应为1至100个字符", trigger: "blur" },
  ],
  address: [{ max: 500, message: "仓库地址不能超过500个字符", trigger: "blur" }],
  remark: [{ max: 500, message: "备注不能超过500个字符", trigger: "blur" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
};

const formItems = computed<FormItem[]>(() => [
  {
    label: "仓库编码",
    key: "warehouse_code",
    type: "input",
    span: 12,
    props: { placeholder: "请输入仓库编码", maxlength: 64, showWordLimit: true },
  },
  {
    label: "仓库名称",
    key: "warehouse_name",
    type: "input",
    span: 12,
    props: { placeholder: "请输入仓库名称", maxlength: 100, showWordLimit: true },
  },
  {
    label: "状态",
    key: "status",
    type: "radiogroup",
    span: 12,
    props: { options: STATUS_OPTIONS },
  },
  {
    label: "仓库地址",
    key: "address",
    type: "input",
    span: 24,
    props: {
      type: "textarea",
      rows: 2,
      maxlength: 500,
      showWordLimit: true,
      placeholder: "请输入仓库地址",
    },
  },
  {
    label: "备注",
    key: "remark",
    type: "input",
    span: 24,
    props: {
      type: "textarea",
      rows: 3,
      maxlength: 500,
      showWordLimit: true,
      placeholder: "请输入备注",
    },
  },
]);

const detailItems: DescriptionsItem[] = [
  { label: "仓库编码", prop: "warehouse_code" },
  { label: "仓库名称", prop: "warehouse_name" },
  {
    label: "状态",
    prop: "status",
    tag: {
      map: {
        "0": { type: "success", text: "启用" },
        "1": { type: "danger", text: "停用" },
      },
    },
  },
  { label: "创建人", prop: "created_by.name" },
  { label: "更新人", prop: "updated_by.name" },
  { label: "创建时间", prop: "created_time" },
  { label: "更新时间", prop: "updated_time" },
  { label: "仓库地址", prop: "address", span: 2 },
  { label: "备注", prop: "remark", span: 2 },
];

/** 将仓库详情转换为可编辑表单。 */
function toWarehouseForm(item: WarehouseItem): WarehouseForm {
  return {
    id: item.id,
    warehouse_code: item.warehouse_code,
    warehouse_name: item.warehouse_name,
    address: item.address ?? "",
    remark: item.remark ?? "",
    status: item.status,
  };
}

/** 重置仓库弹窗数据。 */
function resetDialogData() {
  dataFormRef.value?.resetFields();
  dataFormRef.value?.clearValidate();
  formData.value = { ...initialFormData };
  detailData.value = {};
  formRenderKey.value += 1;
}

/** 加载编辑或详情数据。 */
async function loadWarehouseDetail() {
  if (props.mode === "create" || !props.warehouseId) return;
  detailLoading.value = true;
  try {
    const response = await WarehouseAPI.getWarehouseDetail(props.warehouseId);
    const item = response.data.data;
    if (props.mode === "detail") {
      detailData.value = item;
    } else {
      formData.value = toWarehouseForm(item);
    }
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error(error);
    handleClose();
  } finally {
    detailLoading.value = false;
  }
}

/** 关闭并清理仓库弹窗。 */
function handleClose() {
  visible.value = false;
  resetDialogData();
}

/** 校验并提交仓库表单。 */
async function handleSubmit() {
  if (props.mode === "detail") {
    handleClose();
    return;
  }
  const form = dataFormRef.value;
  if (!form) return;
  const valid = await (form.validate as () => Promise<boolean>)().catch(() => false);
  if (!valid) return;

  submitLoading.value = true;
  try {
    if (props.mode === "update" && props.warehouseId) {
      await WarehouseAPI.updateWarehouse(props.warehouseId, formData.value);
    } else {
      await WarehouseAPI.createWarehouse(formData.value);
    }
    emit("success");
    handleClose();
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error(error);
  } finally {
    submitLoading.value = false;
  }
}

watch(
  () => visible.value,
  async (isVisible) => {
    if (!isVisible) return;
    resetDialogData();
    await loadWarehouseDetail();
  }
);
</script>

<template>
  <FaDialog
    v-model="visible"
    :title="dialogTitle"
    width="760px"
    dialog-class="crud-embed-dialog"
    modal-class="crud-embed-dialog"
    :form-mode="mode"
    :confirm-loading="submitLoading"
    @cancel="handleClose"
    @close="handleClose"
    @confirm="handleSubmit"
  >
    <div v-loading="detailLoading">
      <FaDescriptions
        v-if="mode === 'detail'"
        :column="2"
        :data="detailData"
        :items="detailItems"
        max-height="70vh"
      />
      <FaForm
        v-else
        :key="formRenderKey"
        ref="dataFormRef"
        v-model="formData"
        scrollbar
        max-height="70vh"
        :items="formItems"
        :rules="rules"
        label-suffix=":"
        :label-width="100"
        label-position="right"
        :span="24"
        :gutter="16"
        :show-reset="false"
        :show-submit="false"
        class="crud-dialog-art-form"
      />
    </div>
  </FaDialog>
</template>
