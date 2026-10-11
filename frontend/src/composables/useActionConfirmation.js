import { nextTick, onBeforeUnmount, ref } from "vue";

export function useActionConfirmation() {
  const confirmation = ref(null);
  let resolvePending = null;
  let trigger = null;

  function requestConfirmation(details) {
    if (resolvePending) return Promise.resolve(false);
    trigger = document.activeElement;
    confirmation.value = details;
    return new Promise((resolve) => {
      resolvePending = resolve;
    });
  }

  function answerConfirmation(accepted) {
    const resolve = resolvePending;
    if (!resolve) return;
    const focusTarget = trigger;
    resolvePending = null;
    trigger = null;
    confirmation.value = null;
    resolve(Boolean(accepted));
    nextTick(() => {
      if (focusTarget?.isConnected) focusTarget.focus();
    });
  }

  onBeforeUnmount(() => {
    resolvePending?.(false);
    resolvePending = null;
    confirmation.value = null;
  });

  return { confirmation, requestConfirmation, answerConfirmation };
}
