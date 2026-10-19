import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./index.vue";
import LoginProductNav from "./components/product/LoginProductNav.vue";
import LoginProductImage from "./components/product/LoginProductImage.vue";

const mocks = vi.hoisted(() => ({
  captcha: vi.fn(),
  slider: vi.fn(),
  login: vi.fn(),
  replace: vi.fn(),
  reset: vi.fn(),
  route: { query: {} as Record<string, string> },
}));
vi.mock("@/api/module_system/auth", () => ({
  default: { getCaptcha: mocks.captcha, sliderComplete: mocks.slider },
}));
vi.mock("@stores", () => ({
  useUserStore: () => ({ isLogin: false, login: mocks.login }),
  useSettingsStore: () => ({ isDark: false }),
}));
vi.mock("@/store/modules/product-config.store", () => ({
  useProductConfigStore: () => ({ reset: mocks.reset }),
}));
vi.mock("vue-router", () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ replace: mocks.replace }),
}));

const wrappers: ReturnType<typeof mount>[] = [];
/** 挂载真实账号表单，业务截图和滑块只替换外部展示依赖。 */
function createPage() {
  const wrapper = mount(Login, {
    global: {
      plugins: [ElementPlus],
      mocks: { $t: (key: string) => key },
      directives: { ripple: () => undefined },
      stubs: {
        FaSvgIcon: true,
        FaLoginThirdPartySection: true,
        FaLoginAuthLinkRow: true,
        FaDragVerify: {
          props: ["value"],
          emits: ["update:value"],
          template:
            '<button data-test="slider" @click="$emit(\'update:value\', true)">完成验证</button>',
        },
      },
    },
  });
  wrappers.push(wrapper);
  (wrapper.element as HTMLElement).scrollTo = vi.fn();
  return wrapper;
}
/** 填写真实账号和密码输入框。 */
async function fillAccount(wrapper: ReturnType<typeof createPage>): Promise<void> {
  await wrapper.get('input[name="username"]').setValue("operator");
  await wrapper.get('input[name="password"]').setValue("safe-test-password");
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.route.query = {};
  mocks.captcha.mockResolvedValue({
    data: { data: { enable: false, key: "captcha-key", img_base: "" } },
  });
  mocks.login.mockResolvedValue(undefined);
  mocks.slider.mockResolvedValue({ data: { data: { verified: true } } });
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: true }))
  );
});
afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  vi.unstubAllGlobals();
  document.querySelectorAll(".el-message").forEach((element) => element.remove());
});

describe("四屏登录页与账号认证", () => {
  it("四屏始终存在，介绍导航不重置输入或刷新验证码", async () => {
    const wrapper = createPage();
    await flushPromises();
    await fillAccount(wrapper);
    expect(wrapper.findAll("main > section")).toHaveLength(4);
    wrapper.getComponent(LoginProductNav).vm.$emit("navigate", "stock");
    await flushPromises();
    expect((wrapper.get('input[name="username"]').element as HTMLInputElement).value).toBe(
      "operator"
    );
    expect((wrapper.get('input[name="password"]').element as HTMLInputElement).value).toBe(
      "safe-test-password"
    );
    expect(mocks.captcha).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).not.toMatch(/手机登录|扫码登录|快捷选择账号|第三方登录/);
  });
  it("验证码禁用时正常登录，保留站内查询和锚点跳转", async () => {
    mocks.route.query.redirect = "/inventory/stock/balance?page=2#result";
    const wrapper = createPage();
    await flushPromises();
    await fillAccount(wrapper);
    await wrapper.get(".el-button--primary").trigger("click");
    await flushPromises();
    expect(mocks.login).toHaveBeenCalledWith(
      expect.objectContaining({ username: "operator", captcha_key: "captcha-key" })
    );
    expect(mocks.replace).toHaveBeenCalledWith(mocks.route.query.redirect);
  });
  it("外站重定向回落首页", async () => {
    mocks.route.query.redirect = "//external.example";
    const wrapper = createPage();
    await flushPromises();
    await fillAccount(wrapper);
    await wrapper.get(".el-button--primary").trigger("click");
    await flushPromises();
    expect(mocks.replace).toHaveBeenCalledWith("/home");
  });
  it("验证码加载失败时阻止登录，并能重试", async () => {
    mocks.captcha.mockRejectedValueOnce(new Error("offline"));
    const wrapper = createPage();
    await flushPromises();
    await fillAccount(wrapper);
    await wrapper.get(".el-button--primary").trigger("click");
    expect(mocks.login).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("验证码加载失败");
    await wrapper.get(".el-button.is-link").trigger("click");
    await flushPromises();
    expect(mocks.captcha).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).not.toContain("验证码加载失败");
  });
  it("滑块验证未获服务端确认时不得提交账号，导航不丢失验证状态", async () => {
    mocks.captcha.mockResolvedValue({
      data: { data: { enable: true, key: "slider-key", img_base: "" } },
    });
    let complete: (() => void) | undefined;
    mocks.slider.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          complete = resolve;
        })
    );
    const wrapper = createPage();
    await flushPromises();
    await fillAccount(wrapper);
    await wrapper.get(".el-button--primary").trigger("click");
    await flushPromises();
    expect(mocks.login).not.toHaveBeenCalled();
    await wrapper.get('[data-test="slider"]').trigger("click");
    wrapper.getComponent(LoginProductNav).vm.$emit("navigate", "trade");
    await wrapper.get(".el-button--primary").trigger("click");
    await flushPromises();
    expect(mocks.login).not.toHaveBeenCalled();
    complete?.();
    await flushPromises();
    expect(mocks.login).toHaveBeenCalledTimes(1);
    expect(mocks.captcha).toHaveBeenCalledTimes(1);
  });
  it("认证失败保留账号密码并刷新验证码", async () => {
    mocks.login.mockRejectedValueOnce(new Error("wrong password"));
    const wrapper = createPage();
    await flushPromises();
    await fillAccount(wrapper);
    await wrapper.get(".el-button--primary").trigger("click");
    await flushPromises();
    expect(mocks.captcha).toHaveBeenCalledTimes(2);
    expect(mocks.replace).not.toHaveBeenCalled();
    expect((wrapper.get('input[name="username"]').element as HTMLInputElement).value).toBe(
      "operator"
    );
  });
  it("截图加载失败提供占位，不影响常驻账号表单", async () => {
    const wrapper = createPage();
    const image = wrapper.getComponent(LoginProductImage);
    await image.get("img").trigger("error");
    expect(image.text()).toContain("界面预览暂不可用");
    expect(wrapper.find('input[name="username"]').exists()).toBe(true);
  });
});
