<script setup>
import {
  CalendarClock,
  CalendarDays,
  ChartNoAxesColumnIncreasing,
  ClipboardList,
  FileText,
  LayoutDashboard,
  ListFilter,
  MessageCircleMore,
  MessageSquareText,
  Users,
} from "lucide-vue-next";
import { nextTick, onMounted, ref } from "vue";

import ContentManagement from "../components/doctor/ContentManagement.vue";
import DoctorAccount from "../components/doctor/DoctorAccount.vue";
import DoctorOverview from "../components/doctor/DoctorOverview.vue";
import DoctorReports from "../components/doctor/DoctorReports.vue";
import PatientManagement from "../components/doctor/PatientManagement.vue";
import ScheduleManagement from "../components/doctor/ScheduleManagement.vue";
import ServiceRecords from "../components/doctor/ServiceRecords.vue";
import SmsManagement from "../components/doctor/SmsManagement.vue";
import PortalHeader from "../components/PortalHeader.vue";
import PortalSidebar from "../components/PortalSidebar.vue";
import { useDoctorStore } from "../composables/useDoctorStore";
import { apiRequest, refreshSession, session, signOut } from "../services/api";
import { dashboardPath, navigate } from "../router";
import { consumeQueuedToast, queueToast, showToast } from "../services/toast";

const { state, load } = useDoctorStore();
const activePanel = ref("doctorOverview");
const highlightedId = ref("");

const navItems = [
  { id: "doctorOverview", label: "Overview", icon: LayoutDashboard },
  { id: "doctorAppointments", label: "Appointments", icon: CalendarDays },
  { id: "doctorPatients", label: "Patients & Treatments", shortLabel: "Patients", icon: Users },
  {
    id: "doctorServiceRecords",
    label: "Service Records",
    shortLabel: "Service Records",
    icon: ClipboardList,
  },
  { id: "doctorSchedule", label: "Schedule", icon: CalendarClock },
  { id: "doctorSettings", label: "Services & Content", shortLabel: "Services", icon: ListFilter },
  {
    id: "doctorSms",
    label: "SMS",
    icon: MessageCircleMore,
    children: [
      { id: "doctorSmsCenter", label: "SMS Center", icon: MessageSquareText },
      { id: "doctorSmsTemplates", label: "Templates", icon: FileText },
      { id: "doctorSmsLogs", label: "Message Logs", icon: ClipboardList },
    ],
  },
  { id: "doctorStatistics", label: "Reports", icon: ChartNoAxesColumnIncreasing },
];

async function refreshData() {
  try {
    await load();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function logout() {
  try {
    await signOut();
    queueToast("Logged out.");
    navigate("/");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function updateAppointmentStatus(item, status) {
  try {
    const data = await apiRequest("/api/appointments", {
      method: "PATCH",
      body: { id: item.id, status },
    });
    const index = state.appointments.findIndex((entry) => entry.id === item.id);
    if (index >= 0) state.appointments.splice(index, 1, data.appointment);
    for (const cancelledId of data.cancelled_appointment_ids || []) {
      const cancelledIndex = state.appointments.findIndex((entry) => entry.id === cancelledId);
      if (cancelledIndex >= 0) state.appointments[cancelledIndex].status = "cancelled";
    }
    showToast(`Appointment ${status === "approved" ? "accepted" : status}.`);
    await load();
  } catch (error) {
    showToast(error.message, "error");
    await refreshData();
  }
}

async function openNotification(item) {
  const targets = {
    appointment: "doctorAppointments",
    treatment: "doctorPatients",
    feedback: "doctorSettings",
  };
  activePanel.value = targets[item.entity_type] || "doctorOverview";
  highlightedId.value = item.entity_id || "";
  await nextTick();
  window.setTimeout(() => {
    const target = document.querySelector(`[data-entity-id="${CSS.escape(highlightedId.value)}"]`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, 100);
  window.setTimeout(() => {
    highlightedId.value = "";
  }, 3200);
}

async function openReportEntity(panel, entityId) {
  highlightedId.value = entityId || "";
  activePanel.value = panel;
  await nextTick();
  window.setTimeout(() => {
    const target = document.querySelector(`[data-entity-id="${CSS.escape(highlightedId.value)}"]`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, 100);
  window.setTimeout(() => {
    highlightedId.value = "";
  }, 3200);
}

onMounted(async () => {
  document.title = "Doctor Dashboard - BORJA Dental Clinic";
  consumeQueuedToast();
  try {
    const user = await refreshSession();
    if (!user) {
      queueToast("Please log in to continue.", "error");
      navigate("/?login=1");
      return;
    }
    if (user.role !== "doctor") {
      navigate(dashboardPath(user.role));
      return;
    }
    await load();
  } catch (error) {
    showToast(error.message, "error");
  }
});
</script>

<template>
  <template v-if="session.user">
    <main class="portal-page doctor-portal">
      <PortalSidebar
        :user="session.user"
        role-label="Doctor / Admin"
        :items="navItems"
        :active="activePanel"
        profile-panel-id="doctorProfile"
        @select="activePanel = $event"
        @logout="logout"
      />
      <div class="portal-workspace">
        <PortalHeader mode="doctor" @open-notification="openNotification" />
        <section class="portal-main" aria-label="Doctor dashboard">
          <div
            v-if="state.loading && !state.patients.length && !state.appointments.length"
            class="loading-state"
          >
            Loading clinic dashboard...
          </div>
          <DoctorOverview
            v-else-if="activePanel === 'doctorOverview'"
            :state="state"
            :highlighted-id="highlightedId"
            @select-panel="activePanel = $event"
            @status-change="updateAppointmentStatus"
            @refresh="refreshData"
          />
          <PatientManagement
            v-else-if="activePanel === 'doctorPatients'"
            :state="state"
            :highlighted-id="highlightedId"
            @refresh="refreshData"
          />
          <ServiceRecords
            v-else-if="activePanel === 'doctorServiceRecords'"
            :state="state"
            :highlighted-id="highlightedId"
          />
          <ScheduleManagement
            v-else-if="activePanel === 'doctorAppointments'"
            mode="appointments"
            :state="state"
            :highlighted-id="highlightedId"
            @refresh="refreshData"
            @status-change="updateAppointmentStatus"
          />
          <ScheduleManagement
            v-else-if="activePanel === 'doctorSchedule'"
            mode="schedule"
            :state="state"
            :highlighted-id="highlightedId"
            @refresh="refreshData"
            @status-change="updateAppointmentStatus"
          />
          <ContentManagement v-else-if="activePanel === 'doctorSettings'" :state="state" />
          <SmsManagement
            v-else-if="activePanel.startsWith('doctorSms')"
            :section="activePanel"
            @select-panel="activePanel = $event"
          />
          <DoctorReports
            v-else-if="activePanel === 'doctorStatistics'"
            :state="state"
            @select-panel="activePanel = $event"
            @open-record="openReportEntity('doctorPatients', $event)"
            @open-appointment="openReportEntity('doctorAppointments', $event)"
            @open-patient="openReportEntity('doctorPatients', $event)"
          />
          <DoctorAccount v-else mode="doctor" />
        </section>
      </div>
    </main>
  </template>
  <div v-else class="loading-state">Opening your dashboard...</div>
</template>
