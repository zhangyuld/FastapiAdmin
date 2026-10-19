<script setup lang="ts">
import type { LoginProductSection } from "../../login-product";
import LoginProductImage from "./LoginProductImage.vue";

/** 每屏只展示一类已交付业务能力及其真实界面。 */
defineProps<{ section: LoginProductSection }>();
</script>

<template>
  <section
    :id="section.id"
    class="product-section"
    :class="`product-section--${section.id}`"
    :aria-labelledby="`${section.id}-title`"
  >
    <div class="product-section__inner">
      <div class="product-section__heading">
        <p class="product-section__eyebrow">
          <span>{{ section.number }}</span
          >{{ section.label }}
        </p>
        <h2 :id="`${section.id}-title`">{{ section.title }}</h2>
        <p class="product-section__description">{{ section.description }}</p>
      </div>
      <ul class="product-section__features">
        <li v-for="feature in section.features" :key="feature.title">
          <FaSvgIcon :icon="feature.icon" :size="24" />
          <div>
            <h3>{{ feature.title }}</h3>
            <p>{{ feature.description }}</p>
          </div>
        </li>
      </ul>
      <LoginProductImage :src="section.image" :alt="section.imageAlt" />
    </div>
  </section>
</template>

<style scoped lang="scss">
.product-section {
  padding: 64px 0 56px;
  background: var(--login-surface);
  border-bottom: 1px solid var(--login-border);

  &--stock {
    background: var(--login-mint);
  }

  &__inner {
    width: min(1120px, calc(100% - 80px));
    margin: 0 auto;
  }

  &__eyebrow {
    display: flex;
    gap: 12px;
    align-items: center;
    margin: 0 0 14px;
    font-size: 13px;
    font-weight: 600;
    color: var(--login-green);

    span {
      font-size: 12px;
      font-variant-numeric: tabular-nums;
      opacity: 0.7;
    }
  }

  h2 {
    margin: 0 0 16px;
    font-size: 32px;
    font-weight: 600;
    line-height: 1.4;
  }

  &__description {
    max-width: 660px;
    margin: 0;
    font-size: 14px;
    line-height: 1.9;
    color: var(--login-muted);
  }

  &__features {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 32px;
    padding: 0;
    margin: 32px 0;
    list-style: none;

    li {
      display: flex;
      gap: 14px;
      min-width: 0;
    }

    :deep(svg) {
      flex-shrink: 0;
      margin-top: 2px;
      color: var(--login-blue);
    }

    h3 {
      margin: 0 0 8px;
      font-size: 15px;
      font-weight: 600;
    }

    p {
      margin: 0;
      font-size: 12px;
      line-height: 1.8;
      color: var(--login-muted);
    }
  }
  @media (width <= 760px) {
    padding: 40px 0;

    &__inner {
      width: calc(100% - 40px);
    }

    h2 {
      font-size: 25px;
    }

    &__description {
      font-size: 13px;
    }

    &__features {
      grid-template-columns: minmax(0, 1fr);
      gap: 20px;
      margin: 26px 0;
    }
  }
}
</style>
