<script setup>
import { computed, watchEffect } from "vue";

import ToastMessage from "./components/ToastMessage.vue";
import { currentPath } from "./router";
import DoctorDashboard from "./views/DoctorDashboard.vue";
import AppointmentConfirmation from "./views/AppointmentConfirmation.vue";
import PatientDashboard from "./views/PatientDashboard.vue";
import PublicHome from "./views/PublicHome.vue";

const activeView = computed(() => {
  const path = currentPath.value.toLowerCase();
  if (path.includes("appointment-confirmation")) return AppointmentConfirmation;
  if (path.includes("doctor-dashboard")) return DoctorDashboard;
  if (path.includes("patient-dashboard")) return PatientDashboard;
  return PublicHome;
});

watchEffect(() => {
  const path = currentPath.value.toLowerCase();
  document.body.dataset.page = path.includes("appointment-confirmation")
    ? "booking-confirmation"
    : path.includes("doctor-dashboard")
      ? "doctor"
      : path.includes("patient-dashboard")
        ? "patient"
        : "home";
});
</script>

<template>
  <component :is="activeView" />
  <ToastMessage />
</template>
