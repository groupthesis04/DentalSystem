<script setup>
import { Save, TriangleAlert } from "lucide-vue-next";
import { nextTick, onMounted, ref, useId } from "vue";

import BaseModal from "./BaseModal.vue";

defineProps({
  title: { type: String, required: true },
  message: { type: String, required: true },
  confirmLabel: { type: String, default: "Confirm" },
  tone: { type: String, default: "save" },
});
const emit = defineEmits(["confirm", "cancel"]);
const cancelButton = ref(null);
const messageId = `action-confirm-message-${useId().replaceAll(":", "")}`;

onMounted(() => nextTick(() => cancelButton.value?.focus()));
</script>

<template>
  <BaseModal
    :title="title"
    eyebrow="Please confirm"
    size-class="action-confirm-dialog"
    :described-by="messageId"
    @close="emit('cancel')"
  >
    <template #header-icon>
      <span class="action-confirm-icon" :class="{ 'is-save': tone === 'save' }" aria-hidden="true">
        <Save v-if="tone === 'save'" :size="25" />
        <TriangleAlert v-else :size="26" />
      </span>
    </template>
    <div class="action-confirm-body">
      <p :id="messageId">{{ message }}</p>
      <div class="action-confirm-actions">
        <button
          ref="cancelButton"
          class="action-confirm-cancel"
          type="button"
          @click="emit('cancel')"
        >
          Cancel
        </button>
        <button
          class="action-confirm-submit"
          :class="{ 'is-save': tone === 'save' }"
          type="button"
          @click="emit('confirm')"
        >
          {{ confirmLabel }}
        </button>
      </div>
    </div>
  </BaseModal>
</template>

<style scoped>
:global(.crud-dialog.action-confirm-dialog) {
  width: min(500px, calc(100% - 32px));
  border-color: var(--dashboard-border, #e8dfd0);
  border-radius: 14px;
  background: var(--dashboard-surface, #ffffff);
  color: var(--dashboard-text, #171511);
}

:global(.action-confirm-dialog .crud-dialog-header) {
  border-bottom-color: var(--dashboard-border, #e8dfd0);
  background: var(--dashboard-surface, #ffffff);
}

.action-confirm-icon {
  display: grid;
  width: 48px;
  height: 48px;
  flex: 0 0 48px;
  place-items: center;
  border-radius: 12px;
  background: #fff0ed;
  color: #bc2727;
}

.action-confirm-icon.is-save {
  background: #f8f1e2;
  color: #8a6526;
}

.action-confirm-body {
  padding: 22px;
}

.action-confirm-body > p {
  margin: 0;
  color: var(--dashboard-text, #171511);
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.action-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid var(--dashboard-border, #e8dfd0);
  margin-top: 22px;
  padding-top: 18px;
}

.action-confirm-actions button {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--dashboard-border, #e8dfd0);
  border-radius: 8px;
  padding: 0 17px;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.action-confirm-cancel {
  background: var(--dashboard-surface, #ffffff);
  color: var(--dashboard-text, #171511);
}

.action-confirm-cancel:hover,
.action-confirm-cancel:focus-visible {
  background: var(--dashboard-bg, #f8f6f1);
}

.action-confirm-actions .action-confirm-submit {
  border-color: #c62828;
  background: #c62828;
  color: #ffffff;
}

.action-confirm-submit:hover,
.action-confirm-submit:focus-visible {
  background: #a51c1c;
}

.action-confirm-actions .action-confirm-submit.is-save {
  border-color: #8a6526;
  background: #8a6526;
}

.action-confirm-submit.is-save:hover,
.action-confirm-submit.is-save:focus-visible {
  background: #72521b;
}

.action-confirm-actions button:focus-visible {
  outline: 3px solid rgba(196, 154, 70, 0.45);
  outline-offset: 2px;
}

@media (max-width: 520px) {
  .action-confirm-actions {
    flex-direction: column-reverse;
  }

  .action-confirm-actions > * {
    width: 100%;
  }
}
</style>
