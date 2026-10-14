import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Router, RouteLocationNormalized } from "vue-router";
import { setupBeforeEachGuard } from "./guards";
const mocks = vi.hoisted(() => ({
  refresh: { dynamicRoutesRegistered: false, pendingLoading: false, routeInitFailed: false },
  menu: {
    menuList: [{ path: "/inventory/finance/payable" }],
    removeRouteFns: [],
    setMenuList: vi.fn(),
    addRemoveRouteFns: vi.fn(),
  },
}));
vi.mock("@/store", () => ({
  useUserStore: () => ({ info: { username: "super" }, routeList: [{}] }),
  useMenuStore: () => mocks.menu,
  useWorktabStore: () => ({ validateWorktabs: vi.fn() }),
}));
vi.mock("./routes", () => ({
  IframeRouteManager: { getInstance: () => ({ save: vi.fn() }) },
  ROUTE_PATH_LOGIN_ALT: "/auth/login",
}));
vi.mock("./index", () => ({ router: {}, HOME_PAGE_PATH: "/home" }));
vi.mock("@utils/navigation", () => ({ setPageTitle: vi.fn(), setWorktab: vi.fn() }));
vi.mock("@utils/ui", () => ({ NProgress: { start: vi.fn(), done: vi.fn() } }));
vi.mock("@utils/auth", () => ({ Auth: { isLoggedIn: () => true } }));
vi.mock("@utils/http", () => ({ isHttpError: () => false, ApiStatus: {} }));
vi.mock("./refresh", () => ({ refreshState: mocks.refresh }));
vi.mock("@/hooks/core/useCommon", () => ({ getMainScrollEl: vi.fn() }));
vi.mock("./MenuProcessor", () => ({
  MenuProcessor: class {
    /** 返回有权限的动态菜单。 */
    async getMenuList() {
      return mocks.menu.menuList;
    }
  },
}));
vi.mock("./route-loader", () => ({
  RouteRegistry: class {
    /** 隔离真实路由注册。 */
    register() {}
    /** 测试不需要路由清理函数。 */
    getRemoveRouteFns() {
      return [];
    }
  },
}));
beforeEach(() => {
  Object.assign(mocks.refresh, {
    dynamicRoutesRegistered: false,
    pendingLoading: false,
    routeInitFailed: false,
  });
});
/** 取得实际守卫回调，复现刷新时的 catch-all 首次导航。 */
function guard() {
  const register = vi.fn();
  setupBeforeEachGuard({ beforeEach: register } as unknown as Router);
  return register.mock.calls[0]![0] as (to: RouteLocationNormalized) => Promise<unknown>;
}
/** 带对象筛选和页面锚点的动态业务目标。 */
function target(path = "/inventory/finance/payable"): RouteLocationNormalized {
  return {
    path,
    query: { view: "bills", party_id: "6" },
    hash: "#detail",
    matched: [{ name: "CatchAll404" }],
  } as unknown as RouteLocationNormalized;
}
describe("动态路由刷新恢复", () => {
  it("重新解析时保留 query 与 hash", async () => {
    expect(await guard()(target())).toEqual({
      path: "/inventory/finance/payable",
      query: { view: "bills", party_id: "6" },
      hash: "#detail",
      replace: true,
    });
    expect(mocks.refresh.dynamicRoutesRegistered).toBe(true);
  });
  it("无权限路径仍回落首页，不携带业务对象参数", async () => {
    expect(await guard()(target("/inventory/unknown"))).toEqual({ path: "/home", replace: true });
  });
});
