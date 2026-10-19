<script setup lang="ts">
import { ArrowDown } from "@element-plus/icons-vue";
import { loginOverviewImage } from "../../login-product";
import LoginProductImage from "./LoginProductImage.vue";

/** 首屏只组合产品概览与常驻的账号登录区域。 */
defineSlots<{ account(): unknown }>();
const emit = defineEmits<{
  /** 继续浏览采购销售介绍。 */
  explore: [];
}>();
</script>

<template>
  <section id="overview" class="login-overview" aria-labelledby="overview-title">
    <div class="login-overview__inner">
      <div class="login-overview__copy">
        <p class="login-overview__eyebrow"><span /> 采购 · 销售 · 库存 · 经营</p>
        <h1 id="overview-title">智仓云</h1>
        <p class="login-overview__lead">把进销存理清，让经营心中有数。</p>
        <p class="login-overview__description">
          连接商品、单据与往来账目。日常业务有序流转，<br
            class="login-overview__break"
          />库存数量、成本与经营表现，清晰呈现。
        </p>
        <div class="login-overview__highlights">
          <span><FaSvgIcon icon="ri:route-line" :size="17" />单据可追溯</span
          ><span><FaSvgIcon icon="ri:archive-line" :size="17" />库存可掌握</span
          ><span><FaSvgIcon icon="ri:pie-chart-line" :size="17" />经营可分析</span>
        </div>
      </div>
      <div class="login-overview__visual">
        <LoginProductImage
          :src="loginOverviewImage"
          alt="智仓云经营概览，展示标准业务样例的经营指标、采购销售趋势及仓库库存金额"
          eager
        />
      </div>
      <div class="login-overview__account"><slot name="account" /></div>
      <button type="button" class="login-overview__explore" @click="emit('explore')">
        了解业务全貌 <ElIcon><ArrowDown /></ElIcon>
      </button>
    </div>
  </section>
</template>

<style scoped lang="scss">
.login-overview {
  background: var(--login-soft);
  border-bottom: 1px solid var(--login-border);

  &__inner {
    display: grid;
    grid-template-areas: "copy account" "visual account" "explore explore";
    grid-template-columns: minmax(0, 1fr) 330px;
    gap: 28px 64px;
    align-content: center;
    width: min(1200px, calc(100% - 80px));
    min-height: min(850px, calc(100dvh - 116px));
    padding: 48px 0 22px;
    margin: 0 auto;
  }

  &__copy {
    grid-area: copy;
    min-width: 0;
  }

  &__eyebrow {
    display: flex;
    gap: 9px;
    align-items: center;
    margin: 0 0 12px;
    font-size: 12px;
    color: var(--login-muted);

    span {
      width: 6px;
      height: 6px;
      background: var(--login-green);
      border-radius: 50%;
    }
  }

  h1 {
    margin: 0 0 12px;
    font-size: 56px;
    font-weight: 650;
    line-height: 1.2;
  }

  &__lead {
    margin: 0 0 16px;
    font-size: 23px;
    font-weight: 500;
    line-height: 1.5;
  }

  &__description {
    margin: 0;
    font-size: 14px;
    line-height: 1.9;
    color: var(--login-muted);
  }

  &__highlights {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    margin-top: 22px;
    font-size: 12px;
    color: var(--login-muted);

    span {
      display: flex;
      gap: 6px;
      align-items: center;
    }

    :deep(svg) {
      color: var(--login-green);
    }
  }

  &__visual {
    grid-area: visual;
    width: min(100%, 730px);
  }

  &__account {
    grid-area: account;
    align-self: center;
    min-width: 0;
    padding: 28px 0 28px 32px;
    border-left: 1px solid var(--login-border);
  }

  &__explore {
    display: flex;
    grid-area: explore;
    gap: 10px;
    align-items: center;
    justify-content: center;
    width: fit-content;
    padding: 8px;
    margin: 0 auto;
    font-size: 12px;
    color: var(--login-muted);
    cursor: pointer;
    background: none;
    border: 0;
  }

  @media (width >= 1600px) {
    &__inner {
      grid-template-columns: minmax(0, 1fr) 350px;
      column-gap: 90px;
      width: min(1360px, calc(100% - 120px));
    }
  }
  @media (width <= 1000px) {
    &__inner {
      grid-template-columns: minmax(0, 1fr) 300px;
      column-gap: 32px;
    }

    h1 {
      font-size: 46px;
    }

    &__lead {
      font-size: 20px;
    }

    &__break {
      display: none;
    }
  }
  @media (width <= 760px) {
    &__inner {
      grid-template-areas: "copy" "account" "visual" "explore";
      grid-template-columns: minmax(0, 1fr);
      row-gap: 26px;
      width: calc(100% - 40px);
      max-width: 520px;
      min-height: 0;
      padding-top: 30px;
    }

    h1 {
      font-size: 38px;
    }

    &__lead {
      font-size: 18px;
    }

    &__description {
      font-size: 13px;
    }

    &__highlights {
      gap: 16px;
      margin-top: 16px;
    }

    &__account {
      padding: 24px 0 0;
      border-top: 1px solid var(--login-border);
      border-left: 0;
    }
  }
}
</style>
