<!-- 账号密码登录表单（含快捷账号、验证码、滑块） -->
<template>
  <div>
    <ElForm
      ref="formRef"
      :model="loginForm"
      :rules="rules"
      :key="formKey"
      class="login-page-form"
      :validate-on-rule-change="false"
      @keyup.enter="$emit('submit')"
    >
      <ElFormItem v-if="!accountOnly">
        <ElSelect
          :model-value="demoAccountKey"
          class="custom-height w-full"
          :placeholder="$t('login.quickSelectAccount')"
          @update:model-value="$emit('setupAccount', $event as AccountKey)"
        >
          <ElOption
            v-for="account in accounts"
            :key="account.key"
            :label="account.label"
            :value="account.key"
          >
            <span>{{ account.label }}</span>
          </ElOption>
        </ElSelect>
      </ElFormItem>

      <ElFormItem prop="username">
        <ElInput
          class="custom-height"
          v-model.trim="loginForm.username"
          name="username"
          autocomplete="username"
          aria-label="账号"
          clearable
          :placeholder="$t('login.placeholder.username')"
        >
          <template #prefix>
            <ElIcon><User /></ElIcon>
          </template>
        </ElInput>
      </ElFormItem>

      <ElTooltip :visible="isCapsLock" :content="$t('login.capsLock')" placement="right">
        <ElFormItem prop="password">
          <ElInput
            class="custom-height"
            v-model.trim="loginForm.password"
            name="password"
            aria-label="密码"
            type="password"
            autocomplete="current-password"
            show-password
            clearable
            :placeholder="$t('login.placeholder.password')"
            @keyup="onPasswordKeyup"
          >
            <template #prefix>
              <ElIcon><Lock /></ElIcon>
            </template>
          </ElInput>
        </ElFormItem>
      </ElTooltip>

      <div class="login-form-tail flex flex-col gap-[1.1rem]">
        <div v-if="captchaState.enable" class="relative pb-3">
          <div
            class="relative z-2 overflow-hidden select-none rounded-lg border border-transparent transition duration-300"
            :class="{ 'border-[#FF4E4F]!': !isPassing && isClickPass }"
          >
            <FaDragVerify
              ref="dragVerifyRef"
              v-model:value="isPassing"
              :text="$t('login.sliderText')"
              :text-color="dragVerifyTextColor"
              :success-text="$t('login.sliderSuccessText')"
              progress-bar-bg="var(--el-color-success)"
              :background="isDark ? '#26272F' : 'var(--el-border-color-light)'"
              handler-bg="var(--default-box-color)"
            />
          </div>
          <p
            class="absolute top-0 z-1 mt-2 px-px text-xs text-[#f56c6c] transition duration-300"
            :class="{ 'translate-y-10': !isPassing && isClickPass }"
          >
            {{ $t("login.placeholder.slider") }}
          </p>
        </div>

        <div class="login-options-row flex items-center justify-between text-sm">
          <ElCheckbox v-model="loginForm.remember" class="login-remember">
            {{ $t("login.rememberPwd") }}
          </ElCheckbox>
          <ElLink
            v-if="!accountOnly"
            type="primary"
            underline="never"
            class="inline-flex items-center text-sm leading-[inherit]!"
            @click="$emit('forget')"
          >
            {{ $t("login.forgetPwd") }}
          </ElLink>
        </div>

        <div>
          <ElButton
            class="h-11 w-full rounded-lg! text-base font-medium"
            type="primary"
            :loading="loading"
            v-ripple
            @click="$emit('submit')"
          >
            {{ $t("login.btnText") }}
          </ElButton>
        </div>

        <div v-if="!accountOnly" class="login-secondary-actions grid grid-cols-2 gap-2">
          <ElButton class="login-secondary-btn" plain @click="$emit('openMobile')">
            {{ $t("login.mobileLogin") }}
          </ElButton>
          <ElButton class="login-secondary-btn" plain @click="$emit('openQr')">
            {{ $t("login.qrLogin") }}
          </ElButton>
        </div>
      </div>
    </ElForm>

    <FaLoginThirdPartySection v-if="!accountOnly" @oauth="$emit('oauth', $event)" />

    <FaLoginAuthLinkRow
      v-if="!accountOnly"
      :hint="$t('login.noAccount')"
      :link-text="$t('login.register')"
      @link="$emit('register')"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Lock, User } from "@element-plus/icons-vue";
import type { CaptchaInfo, LoginFormData } from "@/api/module_system/auth";
import type { FormInstance, FormRules } from "element-plus";
import type { Account, AccountKey } from "@views/module_system/auth/login/types";

const loginForm = defineModel<LoginFormData>("loginForm", { required: true });

defineOptions({ name: "FaLoginAccountForm" });

interface Props {
  /** 产品账号登录禁用演示填充及其他认证入口。 */
  accountOnly?: boolean;
  /** 账号密码校验规则。 */
  rules: FormRules;
  /** 服务端验证码配置。 */
  captchaState: CaptchaInfo;
  /** 验证码请求状态。 */
  codeLoading: boolean;
  /** 仅旧版演示登录使用的预选账号。 */
  demoAccountKey: AccountKey;
  /** 仅旧版演示登录可选的账号。 */
  accounts: Account[];
  /** 认证失败后重建表单校验及滑块。 */
  formKey: number | string;
  /** 滑块的主题模式。 */
  isDark: boolean;
  /** 滑块提示文字颜色。 */
  dragVerifyTextColor: string;
  /** 账号请求状态。 */
  loading: boolean;
}

withDefaults(defineProps<Props>(), {});

const isPassing = defineModel<boolean>("isPassing", { required: true });
const isClickPass = defineModel<boolean>("isClickPass", { required: true });

interface Emits {
  submit: [];
  setupAccount: [key: AccountKey];
  getCaptcha: [];
  openMobile: [];
  openQr: [];
  forget: [];
  register: [];
  oauth: [provider: "wechat" | "qq" | "github" | "gitee"];
}

const emit = defineEmits<Emits>();

const formRef = ref<FormInstance>();
const dragVerifyRef = ref<{ reset?: () => void } | null>(null);
const isCapsLock = ref(false);

/** 密码输入时检测大写锁定，保留现有回车提交行为。 */
function onPasswordKeyup(event: KeyboardEvent): void {
  if (event instanceof KeyboardEvent) {
    isCapsLock.value = event.getModifierState("CapsLock");
    if (event.key === "Enter") {
      emit("submit");
    }
  }
}

/** 执行账号表单校验，尚未挂载时禁止提交。 */
async function validate(): Promise<boolean> {
  return (await formRef.value?.validate()) ?? false;
}
/** 清除现有字段校验提示。 */
function clearValidate(): void {
  formRef.value?.clearValidate();
}
/** 重置滑块展示，不变更服务端认证状态。 */
function resetDragVerify(): void {
  dragVerifyRef.value?.reset?.();
}
defineExpose({ validate, clearValidate, resetDragVerify });
</script>
