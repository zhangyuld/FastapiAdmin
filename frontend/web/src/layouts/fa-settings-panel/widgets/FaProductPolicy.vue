<script setup lang="ts">
import { Check, Plus, Refresh, EditPen, Delete } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { FeatureRule } from "@/api/module_system/product-config";
import { useProductConfigStore } from "@/store/modules/product-config.store";
import { refreshAppCaches } from "@stores";

/** 后端策略编辑状态不与受管主题设置混合持久化。 */
interface PolicyFormState {
  visible: boolean;
  key: string;
  label: string;
  api: string;
  menu: string;
  settings: string;
  saving: boolean;
  editingKey: string | null;
  permissions: string;
  components: string;
}
const product = useProductConfigStore();
const form = reactive<PolicyFormState>({
  visible: false,
  key: "",
  label: "",
  api: "",
  menu: "",
  settings: "",
  saving: false,
  editingKey: null,
  permissions: "",
  components: "",
});
/** 输入前缀转换为有序数组，合法性及保护边界由后端校验。 */
function values(text: string): string[] {
  return text
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}
/** 追加专属策略草稿，不在前端添加角色判断。 */
function addRule(): void {
  if (!product.draft || !form.key.trim() || !form.label.trim()) {
    ElMessage.warning("请填写标识和名称");
    return;
  }
  if (!form.editingKey && product.draft.features.some((rule) => rule.key === form.key.trim())) {
    ElMessage.warning("功能标识已存在");
    return;
  }
  const rule: FeatureRule = {
    key: form.key.trim(),
    label: form.label.trim(),
    enabled: true,
    access_policy: "superuser_only",
    built_in: false,
    api_prefixes: values(form.api),
    menu_prefixes: values(form.menu),
    setting_keys: values(form.settings),
    permission_prefixes: values(form.permissions),
    component_prefixes: values(form.components),
  };
  const original = product.draft.features.find((item) => item.key === form.editingKey);
  if (original)
    Object.assign(original, { ...rule, built_in: original.built_in, enabled: original.enabled });
  else product.draft.features.push(rule);
  form.visible = false;
  Object.assign(form, {
    key: "",
    label: "",
    api: "",
    menu: "",
    settings: "",
    permissions: "",
    components: "",
    editingKey: null,
  });
}
/** 修改策略草稿，内置项只能扩展保护范围，服务端最终校验。 */
function editRule(rule?: FeatureRule): void {
  Object.assign(form, {
    visible: true,
    editingKey: rule?.key ?? null,
    key: rule?.key ?? "",
    label: rule?.label ?? "",
    api: rule?.api_prefixes.join(",") ?? "",
    menu: rule?.menu_prefixes.join(",") ?? "",
    settings: rule?.setting_keys.join(",") ?? "",
    permissions: rule?.permission_prefixes.join(",") ?? "",
    components: rule?.component_prefixes.join(",") ?? "",
  });
}
/** 删除追加项只修改草稿，发布后才影响所有用户。 */
async function removeRule(rule: FeatureRule): Promise<void> {
  if (rule.built_in || !product.draft) return;
  try {
    await ElMessageBox.confirm("移除该专属策略？", "确认", { type: "warning" });
    product.draft.features = product.draft.features.filter((item) => item.key !== rule.key);
  } catch {
    /* 取消保留草稿。 */
  }
}
/** 发布成功后刷新菜单及路由，普通用户在下次登录或刷新获取新版本。 */
async function publish(): Promise<void> {
  form.saving = true;
  try {
    await product.publish();
    await refreshAppCaches();
    ElMessage.success("配置已发布");
  } catch {
    ElMessage.error("发布失败，请检查配置或重新加载最新版本");
  } finally {
    form.saving = false;
  }
}
/** 重新加载服务端基线，不丢弃当前主题预览。 */
async function reload(): Promise<void> {
  await product.loadDraft();
}
onMounted(reload);
</script>
<template>
  <section v-if="product.can('settings')" class="product-policy">
    <header>
      <h3>超管专属功能</h3>
      <ElButton :icon="Plus" size="small" @click="editRule()">新增</ElButton>
    </header>
    <ElSkeleton v-if="product.loading" :rows="3" animated />
    <ElAlert v-else-if="product.failed" title="策略加载失败" type="error" :closable="false"
      ><ElButton link :icon="Refresh" @click="reload">重试</ElButton></ElAlert
    >
    <template v-else-if="product.draft">
      <div v-for="rule in product.draft.features" :key="rule.key" class="product-policy__row">
        <span>{{ rule.label }}</span
        ><ElSwitch v-model="rule.enabled" /><ElTooltip content="编辑策略"
          ><ElButton link :icon="EditPen" @click="editRule(rule)" /></ElTooltip
        ><ElTooltip v-if="!rule.built_in" content="移除策略"
          ><ElButton link type="danger" :icon="Delete" @click="removeRule(rule)"
        /></ElTooltip>
      </div>
      <footer>
        <span>版本 {{ product.draft.revision }}</span
        ><ElButton :icon="Refresh" :disabled="form.saving" @click="reload">重新加载</ElButton
        ><ElButton type="primary" :icon="Check" :loading="form.saving" @click="publish"
          >保存并发布</ElButton
        >
      </footer>
    </template>
    <FaDialog
      v-model="form.visible"
      :title="form.editingKey ? '编辑超管专属项' : '新增超管专属项'"
      width="480px"
    >
      <ElForm label-position="top"
        ><ElFormItem label="功能标识"
          ><ElInput v-model="form.key" :disabled="!!form.editingKey" /></ElFormItem
        ><ElFormItem label="名称"><ElInput v-model="form.label" /></ElFormItem
        ><ElFormItem label="接口路径前缀"><ElInput v-model="form.api" /></ElFormItem
        ><ElFormItem label="菜单路径前缀"><ElInput v-model="form.menu" /></ElFormItem
        ><ElFormItem label="专属配置字段"><ElInput v-model="form.settings" /></ElFormItem
        ><ElFormItem label="权限标识前缀"><ElInput v-model="form.permissions" /></ElFormItem
        ><ElFormItem label="页面组件前缀"><ElInput v-model="form.components" /></ElFormItem
      ></ElForm>
      <template #footer
        ><ElButton @click="form.visible = false">取消</ElButton
        ><ElButton type="primary" :icon="Check" @click="addRule">确定</ElButton></template
      >
    </FaDialog>
  </section>
</template>
<style scoped lang="scss">
.product-policy {
  padding-top: 16px;
  margin-top: 28px;
  border-top: 1px solid var(--el-border-color);

  header,
  footer {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }

  header {
    justify-content: space-between;
  }

  h3 {
    margin: 0 0 12px;
    font-size: 15px;
  }

  &__row {
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0;

    span {
      flex: 1;
      overflow-wrap: anywhere;
    }
  }

  footer {
    margin-top: 16px;

    span {
      margin-right: auto;
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }
}
</style>
