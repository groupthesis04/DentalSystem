<script setup>
import { Menu, Moon, Sun } from "lucide-vue-next";
import { computed, ref } from "vue";

import { session } from "../services/api";
import { dashboardTheme, toggleDashboardTheme } from "../services/theme";
import NotificationMenu from "./NotificationMenu.vue";

const props = defineProps({
  mode: { type: String, required: true },
  navigationOpen: { type: Boolean, default: false },
});
const emit = defineEmits(["open-notification", "toggle-navigation", "navigate-overview"]);
const navigationButton = ref(null);
defineExpose({ focusNavigationButton: () => navigationButton.value?.focus() });

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
  <header
    class="site-header portal-header dashboard-overview-header"
    :class="{ 'doctor-mobile-header': isDoctor }"
  >
    <button
      v-if="isDoctor"
      class="dashboard-mobile-brand"
      type="button"
      aria-label="Go to dashboard overview"
      @click="emit('navigate-overview')"
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
      <NotificationMenu @open-target="emit('open-notification', $event)" />
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
        v-if="isDoctor"
        ref="navigationButton"
        class="dashboard-mobile-menu-button"
        type="button"
        aria-label="Open dashboard menu"
        aria-controls="doctor-mobile-navigation"
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
  background: #f3faff;
}

.dashboard-overview-header::before {
  position: absolute;
  z-index: -1;
  inset: 0 0 0 57%;
  background: url("/assets/dental-about-v1.png") center 48% / cover no-repeat;
  clip-path: polygon(15% 0, 100% 0, 100% 100%, 0 100%);
  content: "";
  opacity: 0.28;
}

.dashboard-header-greeting,
.dashboard-header-date,
.dashboard-header-message {
  display: grid;
  min-width: 0;
  align-content: center;
}

.dashboard-header-greeting > span {
  color: #233b61;
  font-size: 0.95rem;
}

.dashboard-header-greeting > strong {
  overflow: hidden;
  color: #10274b;
  font-size: clamp(1.45rem, 2.5vw, 2rem);
  line-height: 1.15;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard-header-greeting > small {
  margin-top: 5px;
  color: #425879;
  font-size: 0.78rem;
}

.dashboard-header-date {
  gap: 4px;
}

.dashboard-header-date strong {
  color: #253b5d;
  font-size: 0.73rem;
}

.dashboard-header-date span {
  color: #71809a;
  font-size: 0.7rem;
}

.dashboard-header-message {
  justify-items: center;
  color: #078ba4;
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
  background: #182332;
}

:global(html[data-dashboard-theme="dark"]) .dashboard-header-greeting > span,
:global(html[data-dashboard-theme="dark"]) .dashboard-header-greeting > strong,
:global(html[data-dashboard-theme="dark"]) .dashboard-header-date strong {
  color: #edf4ff;
}

:global(html[data-dashboard-theme="dark"]) .dashboard-header-greeting > small,
:global(html[data-dashboard-theme="dark"]) .dashboard-header-date span {
  color: #aebbd0;
}

@media (max-width: 1120px) {
  .portal-header.dashboard-overview-header {
    grid-template-columns: minmax(300px, 1fr) minmax(180px, 0.6fr) auto;
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
  .portal-header.dashboard-overview-header.doctor-mobile-header {
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

  .doctor-mobile-header.dashboard-overview-header::before {
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
    color: #0c2145;
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

  .doctor-mobile-header .auth-actions {
    grid-column: 2;
    grid-row: 1;
    gap: 7px;
  }

  .doctor-mobile-header :deep(.notification-button),
  .doctor-mobile-header :deep(.theme-toggle-button),
  .dashboard-mobile-menu-button {
    display: inline-grid;
    width: 42px;
    height: 42px;
    flex: 0 0 42px;
    place-items: center;
    border: 1px solid #e5edf7;
    border-radius: 50%;
    background: #fff;
    color: #0c2145;
    box-shadow: 0 2px 10px rgba(18, 39, 75, 0.06);
  }

  .doctor-mobile-header :deep(.notification-panel) {
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
    outline: 2px solid #bfd4fb;
    color: #155bdd;
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
    background: linear-gradient(105deg, #edf7ff 0%, #f7fbff 68%, #edf7ff 100%);
  }

  .dashboard-header-banner::before {
    position: absolute;
    inset: 0 0 0 48%;
    background: url("/assets/dental-about-v1.png") center / cover no-repeat;
    content: "";
    opacity: 0.29;
  }

  .doctor-mobile-header .dashboard-header-greeting {
    position: relative;
    z-index: 1;
    grid-column: 1;
    padding: 14px 0 14px 15px;
  }

  .doctor-mobile-header .dashboard-header-greeting > span {
    font-size: 0.9rem;
  }

  .doctor-mobile-header .dashboard-header-greeting > strong {
    max-width: none;
    font-size: clamp(1.28rem, 5.2vw, 1.85rem);
  }

  .doctor-mobile-header .dashboard-header-greeting > small {
    max-width: 260px;
    font-size: 0.7rem;
    line-height: 1.3;
  }

  .doctor-mobile-header .dashboard-header-message {
    position: relative;
    z-index: 1;
    display: grid;
    grid-column: 2;
    justify-items: center;
    padding: 5px;
  }

  .doctor-mobile-header .dashboard-header-message strong,
  .doctor-mobile-header .dashboard-header-message span {
    font-size: clamp(0.67rem, 2.8vw, 0.86rem);
  }
}

@media (max-width: 390px) {
  .doctor-mobile-header :deep(.notification-button),
  .doctor-mobile-header :deep(.theme-toggle-button),
  .dashboard-mobile-menu-button {
    width: 37px;
    height: 37px;
    flex-basis: 37px;
  }

  .doctor-mobile-header .auth-actions {
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
  :global(html[data-dashboard-theme="dark"] .doctor-mobile-header .dashboard-mobile-brand) {
    color: #edf4ff;
  }

  :global(html[data-dashboard-theme="dark"] .doctor-mobile-header .dashboard-mobile-brand img) {
    filter: brightness(0) invert(1);
  }

  :global(html[data-dashboard-theme="dark"] .doctor-mobile-header .notification-button),
  :global(html[data-dashboard-theme="dark"] .doctor-mobile-header .theme-toggle-button),
  :global(html[data-dashboard-theme="dark"] .doctor-mobile-header .dashboard-mobile-menu-button) {
    border-color: #3a4554;
    background: #1c2430;
    color: #f3f6fb;
  }
}
</style>
