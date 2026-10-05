<script setup>
import { Check, ChevronDown } from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from "vue";

const props = defineProps({
  services: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  label: { type: String, default: "Dental services" },
  placeholder: { type: String, default: "Select services" },
  invalid: { type: Boolean, default: false },
});
const selected = defineModel({ type: Array, default: () => [] });
const root = ref(null);
const trigger = ref(null);
const open = ref(false);
const listId = `service-options-${useId().replaceAll(":", "")}`;
const selectedNames = computed(() => (Array.isArray(selected.value) ? selected.value : []));
const availableServices = computed(() => [
  ...new Set(
    [...props.services, ...selectedNames.value]
      .map((service) => (typeof service === "string" ? service : service?.name))
      .filter(Boolean),
  ),
]);
const summary = computed(() => {
  if (!selectedNames.value.length) {
    return availableServices.value.length ? props.placeholder : "No services available";
  }
  if (selectedNames.value.length === 1) return selectedNames.value[0];
  return `${selectedNames.value[0]} +${selectedNames.value.length - 1} more`;
});

function toggle(name) {
  if (props.disabled) return;
  selected.value = selectedNames.value.includes(name)
    ? selectedNames.value.filter((item) => item !== name)
    : [...selectedNames.value, name];
}

function focusOption(index) {
  root.value?.querySelectorAll('[role="checkbox"]')?.[index]?.focus();
}

function onTriggerKeydown(event) {
  if (!["ArrowDown", "ArrowUp"].includes(event.key) || props.disabled) return;
  event.preventDefault();
  open.value = true;
  nextTick(() => focusOption(event.key === "ArrowDown" ? 0 : availableServices.value.length - 1));
}

function onPickerKeydown(event) {
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  const options = [...(root.value?.querySelectorAll('[role="checkbox"]') || [])];
  const current = options.indexOf(document.activeElement);
  if (current < 0 || !options.length) return;
  event.preventDefault();
  const next =
    event.key === "Home"
      ? 0
      : event.key === "End"
        ? options.length - 1
        : (current + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
  options[next].focus();
}

function onFocusOut(event) {
  if (!root.value?.contains(event.relatedTarget)) open.value = false;
}

function onOutsidePointerDown(event) {
  if (open.value && !root.value?.contains(event.target)) open.value = false;
}

function onDocumentKeydown(event) {
  if (event.key !== "Escape" || !open.value) return;
  event.preventDefault();
  event.stopPropagation();
  open.value = false;
  trigger.value?.focus();
}

onMounted(() => {
  document.addEventListener("pointerdown", onOutsidePointerDown);
  document.addEventListener("keydown", onDocumentKeydown, true);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onOutsidePointerDown);
  document.removeEventListener("keydown", onDocumentKeydown, true);
});
</script>

<template>
  <div ref="root" class="service-multi-select" @keydown="onPickerKeydown" @focusout="onFocusOut">
    <button
      ref="trigger"
      type="button"
      class="service-multi-trigger"
      :disabled="disabled || !availableServices.length"
      :aria-controls="listId"
      :aria-expanded="open"
      :aria-invalid="invalid"
      :aria-label="`${label}: ${summary}. Select one or more services`"
      @click="open = !open"
      @keydown="onTriggerKeydown"
    >
      <span class="service-multi-summary">{{ summary }}</span>
      <ChevronDown :size="17" aria-hidden="true" />
    </button>
    <div v-show="open" :id="listId" class="service-multi-options" role="group" :aria-label="label">
      <button
        v-for="name in availableServices"
        :key="name"
        type="button"
        role="checkbox"
        class="service-multi-option"
        :aria-checked="selectedNames.includes(name)"
        @click="toggle(name)"
      >
        <span class="service-multi-check" aria-hidden="true">
          <Check v-if="selectedNames.includes(name)" :size="13" />
        </span>
        <span>{{ name }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.service-multi-select {
  position: relative;
  min-width: 0;
  color: #171511;
  font: inherit;
}

.service-multi-trigger {
  display: flex;
  width: 100%;
  min-height: 44px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #e8dfd0;
  border-radius: 8px;
  color: #29241d;
  background: #fff;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.service-multi-trigger:hover,
.service-multi-trigger:focus-visible {
  border-color: #c49a46;
  outline: 3px solid rgb(196 154 70 / 18%);
}

.service-multi-trigger[aria-invalid="true"] {
  border-color: #c52f45;
}

.service-multi-trigger:disabled {
  color: #817869;
  background: #f4f1eb;
  cursor: not-allowed;
}

.service-multi-summary {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.service-multi-options {
  position: absolute;
  z-index: 30;
  top: calc(100% + 5px);
  left: 0;
  width: 100%;
  max-height: min(280px, 45vh);
  overflow-y: auto;
  padding: 5px;
  border: 1px solid #e8dfd0;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 14px 28px rgb(23 21 17 / 16%);
}

.service-multi-option {
  display: flex;
  width: 100%;
  min-height: 36px;
  align-items: center;
  gap: 9px;
  padding: 7px 9px;
  border: 0;
  border-radius: 5px;
  color: #171511;
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.service-multi-option:hover,
.service-multi-option:focus-visible {
  outline: 0;
  background: #f8f1e2;
}

.service-multi-check {
  display: grid;
  width: 17px;
  height: 17px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid #b5a483;
  border-radius: 4px;
}

.service-multi-option[aria-checked="true"] .service-multi-check {
  color: #fff;
  border-color: #9d7428;
  background: #9d7428;
}
</style>
