<script setup lang="ts">
import CustomerAPI, {
  type CustomerForm,
  type CustomerItem,
} from "@/api/module_inventory/basic/customer";
import type { DescriptionsItem } from "@/components/display/fa-descriptions/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { DialogType } from "@/hooks/core/useCrudDialog";
import type { FormItemRule } from "element-plus";

defineOptions({
  name: "InventoryCustomerDialog",
  inheritAttrs: false,
});

/** 客户弹窗输入属性。 */
interface CustomerDialogProps {
  /** 弹窗业务模式。 */
  mode: DialogType;
  /** 编辑或查看的客户 ID。 */
  customerId?: number;
}

/** 客户弹窗输出事件。 */
interface CustomerDialogEmits {
  /** 客户保存成功。 */
  success: [];
}

const props = defineProps<CustomerDialogProps>();
const emit = defineEmits<CustomerDialogEmits>();
const visible = defineModel<boolean>({ required: true });

const STATUS_OPTIONS = [
  { label: "启用", value: 0 },
  { label: "停用", value: 1 },
] as const;

const initialFormData: CustomerForm = {
  id: undefined,
  customer_code: "",
  customer_name: "",
  contact: "",
  phone: "",
  address: "",
  remark: "",
  status: 0,
};

const formData = ref<CustomerForm>({ ...initialFormData });
const detailData = ref<Partial<CustomerItem>>({});
const dataFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const detailLoading = ref(false);
const submitLoading = ref(false);

const dialogTitle = computed(() => {
  if (props.mode === "create") return "新增客户";
  if (props.mode === "update") return "修改客户";
  return "客户详情";
});

const rules: Record<keyof CustomerForm, FormItemRule[]> = {
  id: [],
  customer_code: [
    { required: true, message: "请输入客户编码", trigger: "blur" },
    { min: 1, max: 64, message: "客户编码长度应为1至64个字符", trigger: "blur" },
  ],
  customer_name: [
    { required: true, message: "请输入客户名称", trigger: "blur" },
    { min: 1, max: 200, message: "客户名称长度应为1至200个字符", trigger: "blur" },
  ],
  contact: [{ max: 64, message: "联系人不能超过64个字符", trigger: "blur" }],
  phone: [{ max: 32, message: "联系电话不能超过32个字符", trigger: "blur" }],
  address: [{ max: 500, message: "联系地址不能超过500个字符", trigger: "blur" }],
  remark: [{ max: 500, message: "备注不能超过500个字符", trigger: "blur" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
};

const formItems = computed<FormItem[]>(() => [
  {
    label: "客户编码",
    key: "customer_code",
    type: "input",
    span: 12,
    props: { placeholder: "请输入客户编码", maxlength: 64, showWordLimit: true },
  },
  {
    label: "客户名称",
    key: "customer_name",
    type: "input",
    span: 12,
    props: { placeholder: "请输入客户名称", maxlength: 200, showWordLimit: true },
  },
  {
    label: "联系人",
    key: "contact",
    type: "input",
    span: 12,
    props: { placeholder: "请输入联系人", maxlength: 64, showWordLimit: true },
  },
  {
    label: "联系电话",
    key: "phone",
    type: "input",
    span: 12,
    props: { placeholder: "请输入手机或固定电话", maxlength: 32, showWordLimit: true },
  },
  {
    label: "状态",
    key: "status",
    type: "radiogroup",
    span: 12,
    props: { options: STATUS_OPTIONS },
  },
  {
    label: "联系地址",
    key: "address",
    type: "input",
    span: 24,
    props: {
      type: "textarea",
      rows: 2,
      maxlength: 500,
      showWordLimit: true,
      placeholder: "请输入联系地址",
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
  { label: "客户编码", prop: "customer_code" },
  { label: "客户名称", prop: "customer_name" },
  { label: "联系人", prop: "contact" },
  { label: "联系电话", prop: "phone" },
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
  { label: "联系地址", prop: "address", span: 2 },
  { label: "备注", prop: "remark", span: 2 },
];

/** 将客户详情转换为可编辑表单。 */
function toCustomerForm(item: CustomerItem): CustomerForm {
  return {
    id: item.id,
    customer_code: item.customer_code,
    customer_name: item.customer_name,
    contact: item.contact ?? "",
    phone: item.phone ?? "",
    address: item.address ?? "",
    remark: item.remark ?? "",
    status: item.status,
  };
}

/** 重置客户弹窗数据。 */
function resetDialogData() {
  dataFormRef.value?.resetFields();
  dataFormRef.value?.clearValidate();
  formData.value = { ...initialFormData };
  detailData.value = {};
  formRenderKey.value += 1;
}

/** 加载编辑或详情数据。 */
async function loadCustomerDetail() {
  if (props.mode === "create" || !props.customerId) return;
  detailLoading.value = true;
  try {
    const response = await CustomerAPI.getCustomerDetail(props.customerId);
    const item = response.data.data;
    if (props.mode === "detail") {
      detailData.value = item;
    } else {
      formData.value = toCustomerForm(item);
    }
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error(error);
    handleClose();
  } finally {
    detailLoading.value = false;
  }
}

/** 关闭并清理客户弹窗。 */
function handleClose() {
  visible.value = false;
  resetDialogData();
}

/** 校验并提交客户表单。 */
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
    if (props.mode === "update" && props.customerId) {
      await CustomerAPI.updateCustomer(props.customerId, formData.value);
    } else {
      await CustomerAPI.createCustomer(formData.value);
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
    await loadCustomerDetail();
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
