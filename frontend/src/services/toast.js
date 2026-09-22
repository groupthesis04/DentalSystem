import { reactive } from "vue";

export const toastState = reactive({
  message: "",
  type: "success",
  visible: false,
});

let timer;

export function showToast(message, type = "success") {
  toastState.message = message;
  toastState.type = type;
  toastState.visible = true;
  window.clearTimeout(timer);
  timer = window.setTimeout(() => {
    toastState.visible = false;
  }, 3600);
}

export function queueToast(message, type = "success") {
  sessionStorage.setItem("drms_toast", JSON.stringify({ message, type }));
}

export function consumeQueuedToast() {
  const queued = sessionStorage.getItem("drms_toast");
  if (!queued) return;
  sessionStorage.removeItem("drms_toast");
  try {
    const { message, type } = JSON.parse(queued);
    showToast(message, type);
  } catch {
    // Ignore malformed session data.
  }
}
