import { ref } from "vue";

function normalizedPath() {
  return window.location.pathname || "/";
}

export const currentPath = ref(normalizedPath());

window.addEventListener("popstate", () => {
  currentPath.value = normalizedPath();
  window.scrollTo({ top: 0, behavior: "auto" });
});

export function navigate(path) {
  if (normalizedPath() === path) return;
  window.history.pushState({}, "", path);
  currentPath.value = normalizedPath();
  window.scrollTo({ top: 0, behavior: "auto" });
}

export function dashboardPath(role) {
  return role === "doctor" ? "/doctor-dashboard.html" : "/patient-dashboard.html";
}
