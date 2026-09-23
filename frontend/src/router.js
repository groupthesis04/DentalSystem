import { ref } from "vue";

function normalizedPath() {
  return window.location.pathname || "/";
}

export const currentPath = ref(normalizedPath());

window.addEventListener("popstate", () => {
  currentPath.value = normalizedPath();
  window.scrollTo({ top: 0, behavior: "auto" });
});

export function navigate(path, { replace = false } = {}) {
  if (normalizedPath() === path) return;
  if (replace) window.history.replaceState({}, "", path);
  else window.history.pushState({}, "", path);
  currentPath.value = normalizedPath();
  window.scrollTo({ top: 0, behavior: "auto" });
}

export function dashboardPath(role) {
  return role === "doctor" ? "/doctor-dashboard.html" : "/patient-dashboard.html";
}
