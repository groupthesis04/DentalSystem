<script setup>
import { Menu, Moon, Sun } from "lucide-vue-next";
import { computed, ref } from "vue";

import { navigate } from "../router";
import { session } from "../services/api";
import { dashboardTheme, toggleDashboardTheme } from "../services/theme";
import NotificationMenu from "./NotificationMenu.vue";

const props = defineProps({
  mode: { type: String, required: true },
  navigationOpen: { type: Boolean, default: false },
});
const emit = defineEmits(["open-notification", "toggle-navigation"]);
const navigationButton = ref(null);
const notificationMenu = ref(null);
defineExpose({
  focusNavigationButton: () => navigationButton.value?.focus(),
  refreshNotifications: () => notificationMenu.value?.refresh(),
});

const isDoctor = computed(() => props.mode === "doctor");
const displayName = computed(
  () => session.user?.name || (isDoctor.value ? "Clinic Administrator" : "Patient"),
);
const headerDescription = computed(() =>
  isDoctor.value
    ? "Here's what's happening at BORJA Dental Clinic today."
    : "Here's what's happening in your BORJA Dental patient portal today.",
);
const greeting = computed(() => {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
});
const currentDate = computed(() =>
  new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }),
);
</script>

<template>
  <header class="site-header portal-header dashboard-overview-header mobile-dashboard-header">
    <button
      class="dashboard-mobile-brand"
      type="button"
      aria-label="Go to public homepage"
      @click="navigate('/')"
    >
      <img src="/assets/logo.png" alt="" />
      <span><strong>BORJA</strong><small>DENTAL CLINIC</small></span>
    </button>
    <div class="dashboard-header-banner">
      <div class="dashboard-header-greeting">
        <span>{{ greeting }},</span>
        <strong>{{ displayName }}</strong>
        <small>{{ headerDescription }}</small>
      </div>
      <div class="dashboard-header-date">
        <strong>{{ currentDate }}</strong>
        <span>Have a productive day!</span>
      </div>
      <div class="dashboard-header-message" aria-hidden="true">
        <strong>A Healthier Smile</strong>
        <span>A Happier You</span>
      </div>
    </div>
    <div class="auth-actions">
      <NotificationMenu ref="notificationMenu" @open-target="emit('open-notification', $event)" />
      <button
        class="theme-toggle-button"
        type="button"
        :aria-label="dashboardTheme === 'dark' ? 'Use light theme' : 'Use dark theme'"
        :aria-pressed="dashboardTheme === 'dark'"
        :title="dashboardTheme === 'dark' ? 'Use light theme' : 'Use dark theme'"
        @click="toggleDashboardTheme"
      >
        <Sun v-if="dashboardTheme === 'dark'" :size="20" aria-hidden="true" />
        <Moon v-else :size="20" aria-hidden="true" />
      </button>
      <button
        ref="navigationButton"
        class="dashboard-mobile-menu-button"
        type="button"
        aria-label="Open dashboard menu"
        aria-controls="dashboard-mobile-navigation"
        :aria-expanded="navigationOpen"
        @click="emit('toggle-navigation')"
      >
        <Menu :size="23" aria-hidden="true" />
      </button>
    </div>
  </header>
</template>

<style scoped>
.dashboard-header-banner {
  display: contents;
}

.dashboard-mobile-brand,
.dashboard-mobile-menu-button {
  display: none;
}

.portal-header.dashboard-overview-header {
  position: sticky;
  isolation: isolate;
  display: grid;
  min-height: 126px;
  grid-template-columns: minmax(330px, 1.25fr) minmax(220px, 0.72fr) minmax(210px, 0.7fr) auto;
  gap: 22px;
  overflow: visible;
  padding: 18px 28px;
  border-bottom-color: #3b3224;
  background: #171511;
}

.dashboard-overview-header::before {
  position: absolute;
  z-index: -1;
  inset: 0 0 0 57%;
  background: url("/assets/dental-about-v1.png") center 48% / cover no-repeat;
  clip-path: polygon(15% 0, 100% 0, 100% 100%, 0 100%);
  content: "";
  opacity: 0.16;
  filter: grayscale(1) sepia(0.35);
}

.dashboard-header-greeting,
.dashboard-header-date,
.dashboard-header-message {
  display: grid;
  min-width: 0;
  align-content: center;
}

.dashboard-header-greeting > span {
  color: #dbc8a0;
  font-size: 0.95rem;
}

.dashboard-header-greeting > strong {
  overflow: hidden;
  color: #ffffff;
  font-size: clamp(1.45rem, 2.5vw, 2rem);
  line-height: 1.15;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard-header-greeting > small {
  margin-top: 5px;
  color: #e1d8c8;
  font-size: 0.78rem;
}

.dashboard-header-date {
  gap: 4px;
}

.dashboard-header-date strong {
  color: #f4ede1;
  font-size: 0.73rem;
}

.dashboard-header-date span {
  color: #b9aa90;
  font-size: 0.7rem;
}

.dashboard-header-message {
  justify-items: center;
  color: #dfb967;
  font-style: italic;
  line-height: 1.25;
  text-align: center;
  transform: rotate(-5deg);
}

.dashboard-header-message strong,
.dashboard-header-message span {
  font-size: 0.86rem;
}

.dashboard-overview-header .auth-actions {
  position: relative;
  z-index: 1;
}

:global(html[data-dashboard-theme="dark"]) .portal-header.dashboard-overview-header {
  background: #0f0e0c;
}

:global(html[data-dashboard-theme="dark"]) .dashboard-header-greeting > span,
:global(html[data-dashboard-theme="dark"]) .dashboard-header-greeting > strong,
:global(html[data-dashboard-theme="dark"]) .dashboard-header-date strong {
  color: #ffffff;
}

:global(html[data-dashboard-theme="dark"]) .dashboard-header-greeting > small,
:global(html[data-dashboard-theme="dark"]) .dashboard-header-date span {
  color: #c8baa2;
}

@media (max-width: 1120px) {
  .portal-header.dashboard-overview-header {
    grid-template-columns: minmax(190px, 1fr) minmax(130px, 0.6fr) auto;
    gap: 12px;
    padding-inline: 16px;
  }

  .dashboard-header-message {
    display: none;
  }

  .dashboard-overview-header::before {
    inset-inline-start: 62%;
  }
}

@media (max-width: 760px) {
  .portal-header.dashboard-overview-header {
    min-height: 112px;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 12px;
    padding: 14px 18px;
  }

  .dashboard-header-date {
    display: none;
  }

  .dashboard-overview-header::before {
    inset-inline-start: 48%;
    opacity: 0.18;
  }

  .dashboard-header-greeting > strong {
    font-size: 1.35rem;
  }

  .dashboard-header-greeting > small {
    max-width: 290px;
  }
}

@media (max-width: 480px) {
  .portal-header.dashboard-overview-header {
    min-height: 104px;
    padding: 12px;
  }

  .dashboard-header-greeting > span,
  .dashboard-header-greeting > small {
    font-size: 0.65rem;
  }

  .dashboard-header-greeting > strong {
    max-width: 190px;
    font-size: 1.08rem;
  }

  .dashboard-overview-header :deep(.notification-button),
  .dashboard-overview-header :deep(.theme-toggle-button) {
    width: 38px;
    height: 38px;
    flex-basis: 38px;
  }
}

@media (max-width: 720px) {
  .portal-header.dashboard-overview-header.mobile-dashboard-header {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-rows: auto auto;
    min-height: 0;
    gap: 10px 8px;
    padding: 10px 12px 0;
    border-bottom: 0;
    background: var(--dashboard-bg);
    box-shadow: none;
  }

  .mobile-dashboard-header.dashboard-overview-header::before {
    display: none;
  }

  .dashboard-mobile-brand {
    display: flex;
    grid-column: 1;
    grid-row: 1;
    align-items: center;
    gap: 6px;
    width: fit-content;
    min-width: 0;
    border: 0;
    background: none;
    padding: 0;
    color: #171511;
    text-align: left;
    cursor: pointer;
  }

  .dashboard-mobile-brand img {
    width: 46px;
    height: 46px;
    object-fit: contain;
  }

  .dashboard-mobile-brand span {
    display: grid;
    gap: 0;
  }

  .dashboard-mobile-brand strong {
    font-size: 1.05rem;
    font-weight: 900;
    line-height: 1;
  }

  .dashboard-mobile-brand small {
    font-size: 0.48rem;
    font-weight: 800;
    letter-spacing: 0.03em;
    white-space: nowrap;
  }

  .mobile-dashboard-header .auth-actions {
    grid-column: 2;
    grid-row: 1;
    gap: 7px;
  }

  .mobile-dashboard-header :deep(.notification-button),
  .mobile-dashboard-header :deep(.theme-toggle-button),
  .dashboard-mobile-menu-button {
    display: inline-grid;
    width: 42px;
    height: 42px;
    flex: 0 0 42px;
    place-items: center;
    border: 1px solid #e8dfd0;
    border-radius: 50%;
    background: #fff;
    color: #171511;
    box-shadow: 0 2px 10px rgba(23, 21, 17, 0.08);
  }

  .mobile-dashboard-header :deep(.notification-panel) {
    position: fixed;
    top: 62px;
    right: 12px;
    left: 12px;
    width: auto;
    max-height: min(510px, calc(100dvh - 76px));
  }

  .dashboard-mobile-menu-button {
    cursor: pointer;
  }

  .dashboard-mobile-menu-button:hover,
  .dashboard-mobile-menu-button:focus-visible {
    outline: 2px solid #c49a46;
    color: #9d7428;
  }

  .dashboard-header-banner {
    position: relative;
    display: grid;
    grid-column: 1 / -1;
    grid-row: 2;
    grid-template-columns: minmax(0, 1fr) minmax(105px, 37%);
    align-items: center;
    min-height: 140px;
    overflow: hidden;
    border-radius: 13px;
    background: linear-gradient(105deg, #171511 0%, #27231c 68%, #171511 100%);
  }

  .dashboard-header-banner::before {
    position: absolute;
    inset: 0 0 0 48%;
    background: url("/assets/dental-about-v1.png") center / cover no-repeat;
    content: "";
    opacity: 0.17;
    filter: grayscale(1) sepia(0.35);
  }

  .mobile-dashboard-header .dashboard-header-greeting {
    position: relative;
    z-index: 1;
    grid-column: 1;
    padding: 14px 0 14px 15px;
  }

  .mobile-dashboard-header .dashboard-header-greeting > span {
    font-size: 0.9rem;
  }

  .mobile-dashboard-header .dashboard-header-greeting > strong {
    max-width: none;
    font-size: clamp(1.28rem, 5.2vw, 1.85rem);
  }

  .mobile-dashboard-header .dashboard-header-greeting > small {
    max-width: 260px;
    font-size: 0.7rem;
    line-height: 1.3;
  }

  .mobile-dashboard-header .dashboard-header-message {
    position: relative;
    z-index: 1;
    display: grid;
    grid-column: 2;
    justify-items: center;
    padding: 5px;
  }

  .mobile-dashboard-header .dashboard-header-message strong,
  .mobile-dashboard-header .dashboard-header-message span {
    font-size: clamp(0.67rem, 2.8vw, 0.86rem);
  }
}

@media (max-width: 390px) {
  .mobile-dashboard-header :deep(.notification-button),
  .mobile-dashboard-header :deep(.theme-toggle-button),
  .dashboard-mobile-menu-button {
    width: 37px;
    height: 37px;
    flex-basis: 37px;
  }

  .mobile-dashboard-header .auth-actions {
    gap: 5px;
  }

  .dashboard-mobile-brand img {
    width: 40px;
    height: 40px;
  }

  .dashboard-mobile-brand strong {
    font-size: 0.93rem;
  }

  .dashboard-header-banner {
    min-height: 132px;
    grid-template-columns: minmax(0, 1fr) minmax(82px, 33%);
  }
}

@media (max-width: 720px) {
  :global(html[data-dashboard-theme="dark"] .mobile-dashboard-header .dashboard-mobile-brand) {
    color: #f8f1e2;
  }

  :global(html[data-dashboard-theme="dark"] .mobile-dashboard-header .dashboard-mobile-brand img) {
    filter: brightness(0) invert(1);
  }

  :global(html[data-dashboard-theme="dark"] .mobile-dashboard-header .notification-button),
  :global(html[data-dashboard-theme="dark"] .mobile-dashboard-header .theme-toggle-button),
  :global(
    html[data-dashboard-theme="dark"] .mobile-dashboard-header .dashboard-mobile-menu-button
  ) {
    border-color: #594b35;
    background: #27221b;
    color: #f8f1e2;
  }
}
</style>
