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
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";

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
import { useDashboardPanel } from "../composables/useDashboardPanel";
import { useDoctorStore } from "../composables/useDoctorStore";
import { apiRequest, refreshSession, session, signOut } from "../services/api";
import { dashboardPath, navigate } from "../router";
import { consumeQueuedToast, queueToast, showToast } from "../services/toast";

const { state, load } = useDoctorStore();
const highlightedId = ref("");
const mobileNavigationOpen = ref(false);
const portalHeader = ref(null);
let dashboardSocket = null;
let reconnectTimer = null;
let refreshTimer = null;
let reconnectAttempt = 0;
let dashboardActive = false;
let requestedLoad = 0;
let completedLoad = 0;
let loadingPromise = null;

function loadDashboard() {
  requestedLoad += 1;
  if (!loadingPromise) {
    loadingPromise = (async () => {
      try {
        while (completedLoad < requestedLoad) {
          const currentLoad = requestedLoad;
          await load();
          completedLoad = currentLoad;
        }
      } finally {
        loadingPromise = null;
      }
    })();
  }
  return loadingPromise;
}

function queueSocketRefresh() {
  if (!dashboardActive || refreshTimer) return;
  refreshTimer = window.setTimeout(() => {
    refreshTimer = null;
    loadDashboard().catch((error) => showToast(error.message, "error"));
    portalHeader.value?.refreshNotifications();
  }, 100);
}

function scheduleReconnect() {
  if (!dashboardActive || reconnectTimer) return;
  const delay = Math.min(1000 * 2 ** reconnectAttempt, 30000);
  reconnectAttempt = Math.min(reconnectAttempt + 1, 5);
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connectDashboardSocket();
  }, delay);
}

function connectDashboardSocket() {
  if (!dashboardActive || dashboardSocket) return;
  const url = new URL("/ws/admin-updates/", window.location.href);
  url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";

  let connection;
  try {
    connection = new WebSocket(url);
  } catch {
    scheduleReconnect();
    return;
  }
  dashboardSocket = connection;
  connection.onopen = () => {
    reconnectAttempt = 0;
    // A change may have happened while this socket was disconnected.
    queueSocketRefresh();
  };
  connection.onmessage = (message) => {
    try {
      if (JSON.parse(message.data)?.type === "dashboard.changed") queueSocketRefresh();
    } catch {
      // Ignore messages that are not dashboard change events.
    }
  };
  connection.onerror = () => connection.close();
  connection.onclose = () => {
    if (dashboardSocket === connection) dashboardSocket = null;
    scheduleReconnect();
  };
}

function stopDashboardSocket() {
  dashboardActive = false;
  window.clearTimeout(reconnectTimer);
  window.clearTimeout(refreshTimer);
  reconnectTimer = null;
  refreshTimer = null;
  if (dashboardSocket) {
    const connection = dashboardSocket;
    dashboardSocket = null;
    connection.onclose = null;
    connection.close();
  }
}

function closeMobileNavigation(restoreFocus = false) {
  mobileNavigationOpen.value = false;
  if (restoreFocus) nextTick(() => portalHeader.value?.focusNavigationButton());
}

function selectPanel(panel) {
  activePanel.value = panel;
  closeMobileNavigation();
}

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
const activePanel = useDashboardPanel(dashboardPath("doctor"), "doctorOverview", [
  ...navItems.flatMap((item) =>
    item.children?.length ? item.children.map((child) => child.id) : [item.id],
  ),
  "doctorProfile",
]);

async function refreshData() {
  try {
    await loadDashboard();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function logout() {
  try {
    await signOut();
    stopDashboardSocket();
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
    await loadDashboard();
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
  dashboardActive = true;
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
    try {
      await loadDashboard();
    } catch (error) {
      showToast(error.message, "error");
    }
    connectDashboardSocket();
  } catch (error) {
    showToast(error.message, "error");
  }
});

onBeforeUnmount(stopDashboardSocket);
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
        :mobile-drawer="true"
        :mobile-open="mobileNavigationOpen"
        @select="selectPanel"
        @logout="logout"
        @close-navigation="closeMobileNavigation(true)"
      />
      <div class="portal-workspace">
        <PortalHeader
          ref="portalHeader"
          mode="doctor"
          :navigation-open="mobileNavigationOpen"
          @toggle-navigation="mobileNavigationOpen = !mobileNavigationOpen"
          @open-notification="openNotification"
        />
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
          <DoctorAccount v-else-if="activePanel === 'doctorProfile'" mode="doctor" />
        </section>
      </div>
    </main>
  </template>
  <div v-else class="loading-state">Opening your dashboard...</div>
</template>
