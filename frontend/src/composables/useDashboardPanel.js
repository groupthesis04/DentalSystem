import { onBeforeUnmount, onMounted, ref, watch } from "vue";

export function useDashboardPanel(pathname, defaultPanel, panelIds) {
  const allowedPanels = new Set(panelIds);

  function panelFromUrl() {
    const requested = new URLSearchParams(window.location.search).get("panel");
    return allowedPanels.has(requested) ? requested : defaultPanel;
  }

  const activePanel = ref(panelFromUrl());

  function restorePanel() {
    if (window.location.pathname === pathname) activePanel.value = panelFromUrl();
  }

  watch(
    activePanel,
    (panel) => {
      if (window.location.pathname !== pathname) return;
      if (!allowedPanels.has(panel)) {
        activePanel.value = defaultPanel;
        return;
      }

      const url = new URL(window.location.href);
      if (panel === defaultPanel) url.searchParams.delete("panel");
      else url.searchParams.set("panel", panel);
      if (url.href !== window.location.href) {
        window.history.replaceState(window.history.state, "", url);
      }
    },
    { immediate: true },
  );

  onMounted(() => window.addEventListener("popstate", restorePanel));
  onBeforeUnmount(() => window.removeEventListener("popstate", restorePanel));

  return activePanel;
}
