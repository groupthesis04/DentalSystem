<script setup>
import { X } from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, useId } from "vue";

const props = defineProps({
  title: { type: String, required: true },
  eyebrow: { type: String, default: "" },
  sizeClass: { type: String, default: "" },
  labelledBy: { type: String, default: "" },
});
const emit = defineEmits(["close"]);
const generatedId = `dialog-title-${useId().replaceAll(":", "")}`;
const titleId = computed(() => props.labelledBy || generatedId);

function onKeydown(event) {
  if (event.key === "Escape") emit("close");
}

onMounted(() => {
  const count = Number(document.body.dataset.modalCount || 0) + 1;
  document.body.dataset.modalCount = String(count);
  document.body.classList.add("modal-open");
  window.addEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => {
  const count = Math.max(0, Number(document.body.dataset.modalCount || 1) - 1);
  if (count) document.body.dataset.modalCount = String(count);
  else {
    delete document.body.dataset.modalCount;
    document.body.classList.remove("modal-open");
  }
  window.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <Teleport to="body">
    <div class="modal-backdrop" @mousedown.self="emit('close')">
      <section
        class="crud-dialog vue-modal"
        :class="sizeClass"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
      >
        <div class="crud-dialog-shell">
          <header class="crud-dialog-header">
            <div v-if="$slots['header-icon']" class="crud-dialog-heading-with-icon">
              <slot name="header-icon" />
              <div>
                <span v-if="eyebrow" class="section-kicker">{{ eyebrow }}</span>
                <h2 :id="titleId">{{ title }}</h2>
                <slot name="subtitle" />
              </div>
            </div>
            <div v-else>
              <span v-if="eyebrow" class="section-kicker">{{ eyebrow }}</span>
              <h2 :id="titleId">{{ title }}</h2>
              <slot name="subtitle" />
            </div>
            <button class="icon-button" type="button" aria-label="Close" @click="emit('close')">
              <X :size="19" aria-hidden="true" />
            </button>
          </header>
          <slot />
        </div>
      </section>
    </div>
  </Teleport>
</template>
