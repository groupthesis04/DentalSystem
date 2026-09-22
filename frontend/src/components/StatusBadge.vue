<script setup>
import { computed } from "vue";

import { statusLabel } from "../services/format";

const props = defineProps({ status: { type: String, default: "" } });
const normalized = computed(() => String(props.status || "").toLowerCase());
</script>

<template>
  <span class="status" :class="normalized">{{ statusLabel(normalized) }}</span>
</template>
