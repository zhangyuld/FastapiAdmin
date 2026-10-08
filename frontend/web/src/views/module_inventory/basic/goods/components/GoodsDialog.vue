<script setup lang="ts">
import GoodsAPI, { type GoodsForm, type GoodsItem } from "@/api/module_inventory/basic/goods";
import type { DescriptionsItem } from "@/components/display/fa-descriptions/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { DialogType } from "@/hooks/core/useCrudDialog";
import type { FormItemRule } from "element-plus";

defineOptions({
  name: "InventoryGoodsDialog",
  inheritAttrs: false,
});

/** 商品弹窗输入属性。 */
interface GoodsDialogProps {
  /** 弹窗业务模式。 */
  mode: DialogType;
  /** 编辑或查看的商品 ID。 */
  goodsId?: number;
  /** 商品分类树形选项。 */
  categoryOptions: OptionType[];
}

/** 商品弹窗输出事件。 */
interface GoodsDialogEmits {
  /** 商品保存成功。 */
  success: [];
}

const props = defineProps<GoodsDialogProps>();
const emit = defineEmits<GoodsDialogEmits>();
const visible = defineModel<boolean>({ required: true });

const STATUS_OPTIONS = [
  { label: "启用", value: 0 },
  { label: "停用", value: 1 },
] as const;

const initialFormData: GoodsForm = {
  id: undefined,
  category_id: undefined,
  goods_code: "",
  goods_name: "",
  spec: "",
  unit: "",
  reference_cost_price: 0,
  sale_price: 0,
  stock_min: 0,
  stock_max: 0,
  remark: "",
  status: 0,
};

const formData = ref<GoodsForm>({ ...initialFormData });
const detailData = ref<Partial<GoodsItem>>({});
const dataFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const detailLoading = ref(false);
const submitLoading = ref(false);

const dialogTitle = computed(() => {
  if (props.mode === "create") return "新增商品";
  if (props.mode === "update") return "修改商品";
  return "商品详情";
});

/** 校验最高库存不能小于最低库存。 */
function validateStockMax(_rule: unknown, value: number, callback: (error?: Error) => void) {
  if (value > 0 && value < formData.value.stock_min) {
    callback(new Error("最高库存不能小于最低库存"));
    return;
  }
  callback();
}

const rules: Record<keyof GoodsForm, FormItemRule[]> = {
  id: [],
  category_id: [{ required: true, message: "请选择商品分类", trigger: "change" }],
  goods_code: [
    { required: true, message: "请输入商品编码", trigger: "blur" },
    { min: 1, max: 64, message: "商品编码长度应为1至64个字符", trigger: "blur" },
  ],
  goods_name: [
    { required: true, message: "请输入商品名称", trigger: "blur" },
    { min: 1, max: 200, message: "商品名称长度应为1至200个字符", trigger: "blur" },
  ],
  spec: [{ max: 200, message: "规格型号不能超过200个字符", trigger: "blur" }],
  unit: [
    { required: true, message: "请输入基本单位", trigger: "blur" },
    { min: 1, max: 32, message: "基本单位长度应为1至32个字符", trigger: "blur" },
  ],
  reference_cost_price: [{ required: true, message: "请输入参考进价", trigger: "change" }],
  sale_price: [{ required: true, message: "请输入默认销售价", trigger: "change" }],
  stock_min: [{ required: true, message: "请输入最低库存", trigger: "change" }],
  stock_max: [
    { required: true, message: "请输入最高库存", trigger: "change" },
    { validator: validateStockMax, trigger: "change" },
  ],
  remark: [{ max: 500, message: "备注不能超过500个字符", trigger: "blur" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
};

const formItems = computed<FormItem[]>(() => [
  {
    label: "商品编码",
    key: "goods_code",
    type: "input",
    span: 12,
    props: { placeholder: "请输入商品编码", maxlength: 64, showWordLimit: true },
  },
  {
    label: "商品名称",
    key: "goods_name",
    type: "input",
    span: 12,
    props: { placeholder: "请输入商品名称", maxlength: 200, showWordLimit: true },
  },
  {
    label: "商品分类",
    key: "category_id",
    type: "treeselect",
    span: 12,
    props: {
      placeholder: "请选择商品分类",
      data: props.categoryOptions,
      filterable: true,
      clearable: true,
      checkStrictly: true,
      renderAfterExpand: false,
    },
  },
  {
    label: "规格型号",
    key: "spec",
    type: "input",
    span: 12,
    props: { placeholder: "请输入规格型号", maxlength: 200, showWordLimit: true },
  },
  {
    label: "基本单位",
    key: "unit",
    type: "input",
    span: 12,
    props: { placeholder: "如：件、箱、千克", maxlength: 32 },
  },
  {
    label: "参考进价",
    key: "reference_cost_price",
    type: "number",
    span: 12,
    props: { min: 0, precision: 4, step: 0.0001, controlsPosition: "right" },
  },
  {
    label: "默认销售价",
    key: "sale_price",
    type: "number",
    span: 12,
    props: { min: 0, precision: 4, step: 0.0001, controlsPosition: "right" },
  },
  {
    label: "最低库存",
    key: "stock_min",
    type: "number",
    span: 12,
    props: { min: 0, precision: 3, step: 0.001, controlsPosition: "right" },
  },
  {
    label: "最高库存",
    key: "stock_max",
    type: "number",
    span: 12,
    props: { min: 0, precision: 3, step: 0.001, controlsPosition: "right" },
  },
  {
    label: "状态",
    key: "status",
    type: "radiogroup",
    span: 12,
    props: { options: STATUS_OPTIONS },
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
  { label: "商品编码", prop: "goods_code" },
  { label: "商品名称", prop: "goods_name" },
  { label: "商品分类", prop: "category_name" },
  { label: "规格型号", prop: "spec" },
  { label: "基本单位", prop: "unit" },
  { label: "参考进价", prop: "reference_cost_price" },
  { label: "默认销售价", prop: "sale_price" },
  { label: "最低库存", prop: "stock_min" },
  { label: "最高库存", prop: "stock_max" },
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
  { label: "备注", prop: "remark", span: 2 },
];

/** 将商品详情转换为可编辑表单。 */
function toGoodsForm(item: GoodsItem): GoodsForm {
  return {
    id: item.id,
    category_id: item.category_id,
    goods_code: item.goods_code,
    goods_name: item.goods_name,
    spec: item.spec ?? "",
    unit: item.unit,
    reference_cost_price: Number(item.reference_cost_price),
    sale_price: Number(item.sale_price),
    stock_min: Number(item.stock_min),
    stock_max: Number(item.stock_max),
    remark: item.remark ?? "",
    status: item.status,
  };
}

/** 重置商品弹窗数据。 */
function resetDialogData() {
  dataFormRef.value?.resetFields();
  dataFormRef.value?.clearValidate();
  formData.value = { ...initialFormData };
  detailData.value = {};
  formRenderKey.value += 1;
}

/** 加载编辑或详情数据。 */
async function loadGoodsDetail() {
  if (props.mode === "create" || !props.goodsId) return;
  detailLoading.value = true;
  try {
    const response = await GoodsAPI.getGoodsDetail(props.goodsId);
    const item = response.data.data;
    if (props.mode === "detail") {
      detailData.value = item;
    } else {
      formData.value = toGoodsForm(item);
    }
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error(error);
    handleClose();
  } finally {
    detailLoading.value = false;
  }
}

/** 关闭并清理商品弹窗。 */
function handleClose() {
  visible.value = false;
  resetDialogData();
}

/** 校验并提交商品表单。 */
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
    if (props.mode === "update" && props.goodsId) {
      await GoodsAPI.updateGoods(props.goodsId, formData.value);
    } else {
      await GoodsAPI.createGoods(formData.value);
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
    await loadGoodsDetail();
  }
);
</script>

<template>
  <FaDialog
    v-model="visible"
    :title="dialogTitle"
    width="820px"
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
