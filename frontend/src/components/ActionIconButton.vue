<script setup>
import { Eye, Pencil, Trash2 } from "lucide-vue-next";
import { computed } from "vue";

const props = defineProps({
  action: { type: String, required: true },
  label: { type: String, required: true },
  disabled: { type: Boolean, default: false },
});

const icons = { view: Eye, edit: Pencil, delete: Trash2 };
const icon = computed(() => icons[props.action] || Eye);
</script>

<template>
  <button
    class="secondary-button compact-button icon-action-button action-icon-button"
    :class="`${action}-action`"
    type="button"
    :title="label"
    :aria-label="label"
    :disabled="disabled"
  >
    <component :is="icon" :size="17" aria-hidden="true" />
  </button>
</template>
