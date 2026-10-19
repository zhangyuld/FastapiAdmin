<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, type FormRules } from "element-plus";
import AuthAPI, { type CaptchaInfo, type LoginFormData } from "@/api/module_system/auth";
import { useUserStore, useSettingsStore } from "@stores";
import { useProductConfigStore } from "@/store/modules/product-config.store";
import FaLoginAccountForm from "./components/forms/FaLoginAccountForm.vue";
import LoginProductNav from "./components/product/LoginProductNav.vue";
import LoginOverviewSection from "./components/product/LoginOverviewSection.vue";
import LoginFeatureSection from "./components/product/LoginFeatureSection.vue";
import { loginProductSections } from "./login-product";
import { useLoginSectionNavigation } from "./composables/useLoginSectionNavigation";

defineOptions({ name: "Login" });
const pageRoot = ref<HTMLElement>();
const { activeSection, navigateTo, returnToLogin } = useLoginSectionNavigation({ root: pageRoot });
/** 账号表单、验证码和请求状态，不包含其他认证渠道。 */
interface LoginPageState {
  loading: boolean;
  captchaLoading: boolean;
  captchaFailed: boolean;
  verified: boolean;
  formKey: number;
}
const state = reactive<LoginPageState>({
  loading: false,
  captchaLoading: false,
  captchaFailed: false,
  verified: false,
  formKey: 0,
});
const form = reactive<LoginFormData>({
  username: "",
  password: "",
  remember: false,
  captcha_key: "",
  login_type: "PC端",
});
/** 表单模型保持同一响应式对象，导航和子组件更新不会重建输入。 */
function updateLoginForm(value: LoginFormData): void {
  Object.assign(form, value);
}
const captcha = reactive<CaptchaInfo>({ enable: true, key: "", img_base: "" });
const passing = ref(false);
const attempted = ref(false);
const account = ref<InstanceType<typeof FaLoginAccountForm>>();
const user = useUserStore();
const settings = useSettingsStore();
const route = useRoute();
const router = useRouter();
const rules: FormRules<LoginFormData> = {
  username: [{ required: true, message: "请输入账号", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};
let captchaSequence = 0;
let active = true;
let verification: Promise<void> | undefined;
/** 刷新验证码失败时禁止登录，不降级为不需要验证。 */
async function loadCaptcha(): Promise<void> {
  const sequence = ++captchaSequence;
  state.captchaLoading = true;
  state.captchaFailed = false;
  state.verified = false;
  passing.value = false;
  attempted.value = false;
  try {
    const result = (await AuthAPI.getCaptcha()).data.data;
    if (!active || sequence !== captchaSequence) return;
    Object.assign(captcha, result);
    form.captcha_key = result.key;
    state.verified = !result.enable;
  } catch {
    if (active && sequence === captchaSequence) state.captchaFailed = true;
  } finally {
    if (sequence === captchaSequence) state.captchaLoading = false;
  }
}
/** 滑块完成必须等待后端确认，避免先提交账号请求的竞态。 */
async function verifySlider(): Promise<void> {
  if (!captcha.enable) {
    state.verified = true;
    return;
  }
  const sequence = captchaSequence;
  try {
    await AuthAPI.sliderComplete(form.captcha_key ?? "");
    if (active && sequence === captchaSequence) state.verified = true;
  } catch {
    if (active && sequence === captchaSequence) await loadCaptcha();
  }
}
watch(passing, (value) => {
  if (value) verification = verifySlider();
});
/** 登录后只允许站内跳转，恢复原目标的查询和锚点。 */
async function submit(): Promise<void> {
  if (state.loading || state.captchaLoading || state.captchaFailed) return;
  try {
    if (!(await account.value?.validate())) return;
    if (verification) await verification;
    if (!state.verified) {
      attempted.value = true;
      return;
    }
    state.loading = true;
    await user.login(form);
    const raw = typeof route.query.redirect === "string" ? route.query.redirect : "/home";
    await router.replace(raw.startsWith("/") && !raw.startsWith("//") ? raw : "/home");
  } catch {
    if (active) {
      state.formKey++;
      await loadCaptcha();
      ElMessage.error("登录失败，请检查账号和密码");
    }
  } finally {
    state.loading = false;
  }
}
onMounted(async () => {
  useProductConfigStore().reset();
  if (user.isLogin) {
    await router.replace("/home");
    return;
  }
  await loadCaptcha();
});
onBeforeUnmount(() => {
  active = false;
  captchaSequence++;
});
</script>
<template>
  <div ref="pageRoot" class="zhicang-login">
    <a class="zhicang-login__skip" href="#login-account" @click.prevent="returnToLogin"
      >跳转到账号登录</a
    >
    <LoginProductNav
      :active-section="activeSection"
      @navigate="navigateTo"
      @login="returnToLogin"
    />
    <main>
      <LoginOverviewSection @explore="navigateTo('trade')">
        <template #account>
          <section
            id="login-account"
            class="zhicang-login__account"
            aria-labelledby="login-heading"
          >
            <p class="zhicang-login__welcome">欢迎回来</p>
            <h2 id="login-heading">登录智仓云</h2>
            <p class="zhicang-login__hint">进入你的经营工作台</p>
            <ElAlert
              v-if="state.captchaFailed"
              title="验证码加载失败"
              type="error"
              :closable="false"
              ><ElButton link @click="loadCaptcha">重试</ElButton></ElAlert
            >
            <FaLoginAccountForm
              ref="account"
              :login-form="form"
              @update:login-form="updateLoginForm"
              v-model:is-passing="passing"
              v-model:is-click-pass="attempted"
              account-only
              :rules="rules"
              :captcha-state="captcha"
              :code-loading="state.captchaLoading"
              demo-account-key="super"
              :accounts="[]"
              :form-key="state.formKey"
              :is-dark="settings.isDark"
              drag-verify-text-color="var(--el-text-color-secondary)"
              :loading="state.loading"
              @submit="submit"
            />
          </section>
        </template>
      </LoginOverviewSection>
      <LoginFeatureSection
        v-for="section in loginProductSections"
        :key="section.id"
        :section="section"
      />
    </main>
    <footer class="zhicang-login__footer">
      <span>智仓云 · 让经营心中有数</span
      ><button type="button" @click="returnToLogin">
        登录工作台 <FaSvgIcon icon="ri:arrow-right-line" :size="16" />
      </button>
    </footer>
  </div>
</template>
<style scoped lang="scss">
.zhicang-login {
  --login-surface: #fff;
  --login-soft: #f4f8fc;
  --login-mint: #f2f9f7;
  --login-border: #e1e9f1;
  --login-text: #1e303f;
  --login-muted: #617384;
  --login-blue: #3e6de0;
  --login-green: #16856e;

  height: 100dvh;
  overflow: auto;
  overscroll-behavior-y: contain;
  color: var(--login-text);
  letter-spacing: 0;
  background: var(--login-surface);

  &__skip {
    position: fixed;
    top: 8px;
    left: 16px;
    z-index: 30;
    padding: 12px;
    color: var(--login-blue);
    background: var(--login-surface);
    transform: translateY(-150%);

    &:focus {
      transform: none;
    }
  }

  &__account {
    h2 {
      margin: 0 0 8px;
      font-size: 26px;
      font-weight: 600;
    }

    :deep(.el-input__wrapper) {
      min-height: 44px;
      background: var(--login-surface);
    }

    :deep(.el-button--primary) {
      min-height: 44px;
      color: #fff;
      background: #3e6de0;
      border-color: #3e6de0;
    }
  }

  &__welcome {
    margin: 0 0 14px;
    font-size: 13px;
    color: var(--login-green);
  }

  &__hint {
    margin: 0 0 26px;
    font-size: 13px;
    color: var(--login-muted);
  }

  &__footer {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    align-items: center;
    justify-content: space-between;
    width: min(1120px, calc(100% - 40px));
    min-height: 100px;
    padding: 24px 0;
    margin: 0 auto;
    font-size: 13px;
    color: var(--login-muted);

    button {
      display: flex;
      gap: 10px;
      align-items: center;
      padding: 8px 0;
      color: var(--login-blue);
      cursor: pointer;
      background: none;
      border: 0;
    }
  }

  :deep(a:focus-visible),
  :deep(button:focus-visible) {
    outline: 2px solid var(--login-blue);
    outline-offset: 4px;
  }
  @media (prefers-reduced-motion: no-preference) {
    &__account {
      animation: login-appear 400ms ease-out;
    }
  }
}

:global(html.dark .zhicang-login) {
  --login-surface: #191e23;
  --login-soft: #20282e;
  --login-mint: #202e2b;
  --login-border: #35414a;
  --login-text: #edf2f5;
  --login-muted: #a9bac5;
  --login-blue: #8baaff;
  --login-green: #68cdb0;
}
@keyframes login-appear {
  from {
    opacity: 0;
    transform: translateY(8px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
