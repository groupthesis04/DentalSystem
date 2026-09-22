<script setup>
import { Moon, Sun } from "lucide-vue-next";
import { computed } from "vue";

import { session } from "../services/api";
import { dashboardTheme, toggleDashboardTheme } from "../services/theme";
import NotificationMenu from "./NotificationMenu.vue";

const props = defineProps({
  mode: { type: String, required: true },
});
const emit = defineEmits(["open-notification"]);

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
  <header class="site-header portal-header dashboard-overview-header">
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
    </div>
  </header>
</template>

<style scoped>
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
</style>
