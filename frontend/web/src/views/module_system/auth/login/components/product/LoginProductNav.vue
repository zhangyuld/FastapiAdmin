<script setup lang="ts">
import { ArrowRight } from "@element-plus/icons-vue";
import logo from "@/assets/images/login/logo.png";
import { loginSectionLinks, type LoginSectionId } from "../../login-product";

/** 当前阅读位置由页面滚动状态驱动。 */
defineProps<{ activeSection: LoginSectionId }>();
const emit = defineEmits<{
  /** 定位到指定产品分区。 */
  navigate: [id: LoginSectionId];
  /** 返回并聚焦账号登录表单。 */
  login: [];
}>();
</script>

<template>
  <header class="product-nav">
    <div class="product-nav__inner">
      <a
        class="product-nav__brand"
        href="#overview"
        aria-label="智仓云系统概览"
        @click.prevent="emit('navigate', 'overview')"
      >
        <img :src="logo" alt="智仓云" width="36" height="36" />
        <span>智仓云</span>
      </a>
      <nav class="product-nav__links" aria-label="产品介绍">
        <a
          v-for="link in loginSectionLinks"
          :key="link.id"
          :href="`#${link.id}`"
          :aria-current="activeSection === link.id ? 'location' : undefined"
          @click.prevent="emit('navigate', link.id)"
          >{{ link.label }}</a
        >
      </nav>
      <button class="product-nav__login" type="button" @click="emit('login')">
        立即登录 <ElIcon><ArrowRight /></ElIcon>
      </button>
    </div>
  </header>
</template>

<style scoped lang="scss">
.product-nav {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--login-surface);
  border-bottom: 1px solid var(--login-border);

  &__inner {
    display: flex;
    gap: 24px;
    align-items: center;
    justify-content: space-between;
    width: min(1200px, calc(100% - 80px));
    height: 76px;
    margin: 0 auto;
  }

  &__brand {
    display: flex;
    flex-shrink: 0;
    gap: 10px;
    align-items: center;
    font-size: 22px;
    font-weight: 650;
    color: var(--login-text);
    text-decoration: none;

    img {
      object-fit: contain;
    }
  }

  &__links {
    display: flex;
    gap: 32px;
    align-self: stretch;

    a {
      display: flex;
      align-items: center;
      font-size: 14px;
      color: var(--login-muted);
      white-space: nowrap;
      text-decoration: none;
      border-bottom: 2px solid transparent;

      &[aria-current],
      &:hover {
        color: var(--login-blue);
      }

      &[aria-current] {
        border-bottom-color: var(--login-blue);
      }
    }
  }

  &__login {
    display: flex;
    flex-shrink: 0;
    gap: 10px;
    align-items: center;
    padding: 10px 0 10px 12px;
    font-size: 14px;
    font-weight: 600;
    color: var(--login-blue);
    cursor: pointer;
    background: none;
    border: 0;
  }

  @media (width <= 760px) {
    &__inner {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 0 12px;
      width: calc(100% - 40px);
      height: 112px;
    }

    &__brand {
      font-size: 20px;
    }

    &__login {
      grid-row: 1;
      grid-column: 2;
    }

    &__links {
      grid-row: 2;
      grid-column: 1 / -1;
      gap: 12px;
      justify-content: space-between;

      a {
        min-height: 40px;
        font-size: 13px;
      }
    }
  }
}
</style>
