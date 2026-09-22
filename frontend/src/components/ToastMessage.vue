<script setup>
import { toastState } from "../services/toast";
</script>

<template>
  <div
    v-if="toastState.visible"
    class="toast"
    :class="toastState.type"
    role="status"
    aria-live="polite"
  >
    {{ toastState.message }}
  </div>
</template>
