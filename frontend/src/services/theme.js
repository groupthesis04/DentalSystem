import { ref } from "vue";

const STORAGE_KEY = "dental-dashboard-theme";

function getInitialTheme() {
  try {
    const savedTheme = window.localStorage.getItem(STORAGE_KEY);
    if (savedTheme === "dark" || savedTheme === "light") {
      return savedTheme;
    }
  } catch {
    // The dashboard still works when browser storage is unavailable.
  }

  return "light";
}

export const dashboardTheme = ref(getInitialTheme());

export function applyDashboardTheme(theme, persist = true) {
  const nextTheme = theme === "dark" ? "dark" : "light";
  dashboardTheme.value = nextTheme;
  document.documentElement.dataset.dashboardTheme = nextTheme;

  if (persist) {
    try {
      window.localStorage.setItem(STORAGE_KEY, nextTheme);
    } catch {
      // The selected theme remains active for the current page session.
    }
  }
}

export function toggleDashboardTheme() {
  applyDashboardTheme(dashboardTheme.value === "dark" ? "light" : "dark");
}

applyDashboardTheme(dashboardTheme.value, false);
