<script setup lang="ts">
import { ElMessage, type FormRules } from "element-plus";
import AuthAPI, { type CaptchaInfo, type LoginFormData } from "@/api/module_system/auth";
import { useUserStore, useSettingsStore } from "@stores";
import { useProductConfigStore } from "@/store/modules/product-config.store";
import FaLoginAccountForm from "./components/forms/FaLoginAccountForm.vue";

defineOptions({ name: "Login" });
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
  <main class="zhicang-login">
    <div class="zhicang-login__content">
      <section class="zhicang-login__intro">
        <FaLogo />
        <h1>智仓云</h1>
        <p class="zhicang-login__lead">让采购、销售、库存与往来账目清晰协同。</p>
        <p>
          从商品档案到出入库、退货与盘点，贯通日常业务；通过经营报表掌握库存价值、应收应付与商品毛利。
        </p>
        <ul>
          <li>采购销售 · 业务单据有据可查</li>
          <li>库存管理 · 数量成本清晰可见</li>
          <li>往来报表 · 经营数据及时掌握</li>
        </ul>
      </section>
      <section class="zhicang-login__account" aria-label="账号登录">
        <h2>账号登录</h2>
        <ElAlert v-if="state.captchaFailed" title="验证码加载失败" type="error" :closable="false"
          ><ElButton link @click="loadCaptcha">重试</ElButton></ElAlert
        >
        <FaLoginAccountForm
          ref="account"
          v-model:login-form="form"
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
    </div>
  </main>
</template>
<style scoped lang="scss">
.zhicang-login {
  display: flex;
  align-items: center;
  min-height: 100dvh;
  padding: 48px 24px;
  background: var(--el-bg-color-page);

  &__content {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 360px;
    gap: 96px;
    width: min(100%, 980px);
    margin: 0 auto;
  }

  &__intro {
    min-width: 0;
    padding-top: 16px;
    color: var(--el-text-color-secondary);

    h1 {
      margin: 24px 0 20px;
      font-size: 42px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    p {
      font-size: 15px;
      line-height: 1.9;
    }

    ul {
      padding: 0;
      margin-top: 28px;
      list-style: none;
    }

    li {
      margin: 14px 0;
      font-size: 14px;
    }
  }

  &__lead {
    color: var(--el-text-color-primary);
  }

  &__account {
    align-self: center;
    min-width: 0;

    h2 {
      margin: 0 0 24px;
      font-size: 22px;
    }
  }
  @media (width <= 760px) {
    padding: 32px 20px;

    &__content {
      grid-template-columns: minmax(0, 1fr);
      gap: 30px;
      max-width: 420px;
    }

    &__intro {
      padding-top: 0;

      h1 {
        margin: 16px 0;
        font-size: 30px;
      }

      ul {
        display: none;
      }
    }
  }
}
</style>
