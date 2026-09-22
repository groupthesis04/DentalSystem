<script setup>
import { computed } from "vue";

import { initials } from "../services/format";

const props = defineProps({
  name: { type: String, default: "User" },
  image: { type: String, default: "" },
  large: { type: Boolean, default: false },
});

const label = computed(() => initials(props.name));
const style = computed(() =>
  props.image
    ? {
        backgroundImage: `url("${props.image.replaceAll('"', "%22")}")`,
        backgroundSize: "cover",
        backgroundPosition: "center",
      }
    : {},
);
</script>

<template>
  <div class="profile-avatar" :class="{ large }" :style="style" :aria-label="name">
    <span v-if="!image">{{ label }}</span>
  </div>
</template>
