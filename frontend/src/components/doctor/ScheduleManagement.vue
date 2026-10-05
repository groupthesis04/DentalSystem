<script setup>
import {
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  Clock3,
  Info,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Settings,
  Timer,
  Trash2,
  UserRound,
} from "lucide-vue-next";
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";

import AvatarBadge from "../AvatarBadge.vue";
import AddAppointmentModal from "./AddAppointmentModal.vue";
import ClearAppointmentsModal from "./ClearAppointmentsModal.vue";
import CompleteAppointmentModal from "./CompleteAppointmentModal.vue";
import ScheduleFollowUpModal from "./ScheduleFollowUpModal.vue";
import { apiRequest, session } from "../../services/api";
import {
  appointmentService,
  appointmentServices,
  formatDate,
  localDateIso,
} from "../../services/format";
import { showToast } from "../../services/toast";
import { validatedPayload } from "../../services/validation";

const props = defineProps({
  state: { type: Object, required: true },
  highlightedId: { type: String, default: "" },
  mode: {
    type: String,
    default: "schedule",
    validator: (value) => ["schedule", "appointments"].includes(value),
  },
});
const emit = defineEmits(["refresh", "status-change"]);
const today = localDateIso();
const currentMonth = today.slice(0, 7);
const month = ref(currentMonth);
const selectedDates = ref(new Set());
const schedule = reactive({ time_in: "08:00", time_out: "17:00", interval: "30", _website: "" });
const busy = ref(false);
const addAppointmentOpen = ref(false);
const clearDialogOpen = ref(false);
const clearBusy = ref(false);
const completionAppointment = ref(null);
const completionRecord = ref(null);
const followUpContext = ref(null);
const followUpWasScheduled = ref(false);
const appointmentSearch = ref("");
const serviceFilter = ref("");
const statusFilter = ref("");
const appointmentPage = ref(1);
const appointmentPageSize = 7;
const appointmentStatuses = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Accepted" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];
const openStatusId = ref("");
const statusMenuRef = ref(null);
const statusMenuTrigger = ref(null);
const statusMenuStyle = ref({});
const openStatusAppointment = computed(() =>
  props.state.appointments.find((item) => item.id === openStatusId.value),
);

const selectedDoctor = computed(
  () => session.user?.name || props.state.clinicDoctor || "Clinic dentist",
);
const monthLabel = computed(() => {
  const [year, monthNumber] = month.value.split("-").map(Number);
  return new Date(year, monthNumber - 1, 1).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
});
const canGoPrevious = computed(() => month.value > currentMonth);
const formattedWorkingHours = computed(
  () => `${formatClock(schedule.time_in)} - ${formatClock(schedule.time_out)}`,
);

const calendarCells = computed(() => {
  const [year, monthNumber] = month.value.split("-").map(Number);
  const firstWeekday = new Date(year, monthNumber - 1, 1).getDay();
  const dayCount = new Date(year, monthNumber, 0).getDate();
  const cellCount = Math.ceil((firstWeekday + dayCount) / 7) * 7;

  return Array.from({ length: cellCount }, (_, index) => {
    const dateValue = new Date(year, monthNumber - 1, 1 - firstWeekday + index);
    const date = localDateIso(dateValue);
    const current = date.slice(0, 7) === month.value;
    const slots = props.state.availability.filter((slot) => slot.date === date);
    const fullyBooked = slots.length > 0 && slots.every((slot) => slot.booked);
    return {
      day: dateValue.getDate(),
      date,
      key: date,
      current,
      past: current && date < today,
      disabled: !current || date < today,
      available: slots.length > 0 && !fullyBooked,
      fullyBooked,
    };
  });
});
const sortedAppointments = computed(() =>
  [...props.state.appointments].sort((a, b) =>
    `${b.created_at || ""} ${b.date} ${b.time}`.localeCompare(
      `${a.created_at || ""} ${a.date} ${a.time}`,
    ),
  ),
);
const serviceOptions = computed(() =>
  [...new Set(props.state.services.map((service) => service.name).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  ),
);
const filteredAppointments = computed(() => {
  const query = appointmentSearch.value.trim().toLowerCase();
  return sortedAppointments.value.filter((item) => {
    const matchesQuery =
      !query ||
      `${item.patient_name || ""} ${item.patient_email || ""} ${appointmentService(item)}`
        .toLowerCase()
        .includes(query);
    const matchesService =
      !serviceFilter.value || appointmentServices(item).includes(serviceFilter.value);
    const matchesStatus = !statusFilter.value || item.status === statusFilter.value;
    return matchesQuery && matchesService && matchesStatus;
  });
});
const appointmentPageCount = computed(() =>
  Math.max(1, Math.ceil(filteredAppointments.value.length / appointmentPageSize)),
);
const visibleAppointments = computed(() => {
  const start = (appointmentPage.value - 1) * appointmentPageSize;
  return filteredAppointments.value.slice(start, start + appointmentPageSize);
});
const appointmentPageNumbers = computed(() => {
  const visibleCount = Math.min(5, appointmentPageCount.value);
  let first = Math.max(1, appointmentPage.value - Math.floor(visibleCount / 2));
  first = Math.min(first, appointmentPageCount.value - visibleCount + 1);
  return Array.from({ length: visibleCount }, (_, index) => first + index);
});
const firstVisibleAppointment = computed(() =>
  filteredAppointments.value.length ? (appointmentPage.value - 1) * appointmentPageSize + 1 : 0,
);
const lastVisibleAppointment = computed(() =>
  Math.min(appointmentPage.value * appointmentPageSize, filteredAppointments.value.length),
);
const patientById = computed(
  () => new Map(props.state.patients.map((patient) => [patient.id, patient])),
);

watch(month, () => {
  selectedDates.value = new Set();
});
watch([appointmentSearch, serviceFilter, statusFilter], () => {
  appointmentPage.value = 1;
});
watch(appointmentPageCount, (count) => {
  if (appointmentPage.value > count) appointmentPage.value = count;
});
watch([appointmentPage, appointmentSearch, serviceFilter, statusFilter, () => props.mode], () => {
  closeStatusMenu();
});
watch(
  () => props.highlightedId,
  (appointmentId) => {
    if (!appointmentId) return;
    appointmentSearch.value = "";
    serviceFilter.value = "";
    statusFilter.value = "";
    const index = sortedAppointments.value.findIndex((item) => item.id === appointmentId);
    if (index >= 0) appointmentPage.value = Math.floor(index / appointmentPageSize) + 1;
  },
  { immediate: true },
);

function formatClock(value) {
  const [hours, minutes] = String(value || "00:00")
    .split(":")
    .map(Number);
  const suffix = hours >= 12 ? "PM" : "AM";
  return `${String(hours % 12 || 12).padStart(2, "0")}:${String(minutes || 0).padStart(2, "0")} ${suffix}`;
}

function changeMonth(offset) {
  const [year, monthNumber] = month.value.split("-").map(Number);
  const candidate = new Date(year, monthNumber - 1 + offset, 1);
  const value = `${candidate.getFullYear()}-${String(candidate.getMonth() + 1).padStart(2, "0")}`;
  if (value >= currentMonth) month.value = value;
}

function goToCurrentMonth() {
  month.value = currentMonth;
  selectedDates.value = new Set();
}

function resetSchedule() {
  month.value = currentMonth;
  selectedDates.value = new Set();
  schedule.time_in = "08:00";
  schedule.time_out = "17:00";
  schedule.interval = "30";
}

function toggleDate(cell) {
  if (cell.disabled) return;
  const next = new Set(selectedDates.value);
  if (next.has(cell.date)) next.delete(cell.date);
  else next.add(cell.date);
  selectedDates.value = next;
}

async function createSchedule() {
  busy.value = true;
  try {
    const payload = validatedPayload({
      doctor: session.user?.name || props.state.clinicDoctor,
      dates: [...selectedDates.value].sort().join(","),
      time_in: schedule.time_in,
      time_out: schedule.time_out,
      interval: schedule.interval,
      _website: schedule._website,
    });
    if (!payload.dates) throw new Error("Select at least one available date.");
    const data = await apiRequest("/api/availability", { method: "POST", body: payload });
    props.state.availability.push(...(data.availability_created || [data.availability]));
    selectedDates.value = new Set();
    showToast(
      `${data.created_count || 1} appointment slot${data.created_count === 1 ? "" : "s"} created.`,
    );
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    busy.value = false;
  }
}

function openClearDialog() {
  clearDialogOpen.value = true;
}

async function clearAppointments(payload) {
  clearBusy.value = true;
  try {
    const data = await apiRequest("/api/appointments", {
      method: "DELETE",
      body: payload,
    });
    const cancelledAppointments = new Map(
      (data.cancelled_appointments || []).map((item) => [item.id, item]),
    );
    props.state.appointments.forEach((item, index) => {
      if (cancelledAppointments.has(item.id)) {
        props.state.appointments.splice(index, 1, cancelledAppointments.get(item.id));
      }
    });
    const removedSlotIds = new Set(data.removed_availability_ids || []);
    for (let index = props.state.availability.length - 1; index >= 0; index -= 1) {
      if (removedSlotIds.has(props.state.availability[index].id)) {
        props.state.availability.splice(index, 1);
      }
    }
    clearDialogOpen.value = false;
    showToast(
      `${data.cancelled_count || 0} appointment(s) cancelled and ${data.removed_slot_count || 0} time slot(s) cleared.`,
    );
    emit("refresh");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    clearBusy.value = false;
  }
}

function patientImage(appointment) {
  return patientById.value.get(appointment.patient_id)?.profile_image || "";
}

function selectAppointmentPage(page) {
  appointmentPage.value = Math.min(Math.max(page, 1), appointmentPageCount.value);
}

function statusLabel(status) {
  return appointmentStatuses.find((option) => option.value === status)?.label || status;
}

function closeStatusMenu(restoreFocus = false) {
  const trigger = statusMenuTrigger.value;
  openStatusId.value = "";
  statusMenuTrigger.value = null;
  if (restoreFocus) nextTick(() => trigger?.focus());
}

function focusStatusOption(index) {
  nextTick(() => statusMenuRef.value?.querySelectorAll('[role="menuitemradio"]')[index]?.focus());
}

function openStatusMenu(item, event, focusIndex) {
  if (openStatusId.value === item.id) {
    closeStatusMenu(true);
    return;
  }

  const trigger = event.currentTarget;
  const rect = trigger.getBoundingClientRect();
  const menuHeight = Math.min(176, Math.max(80, window.innerHeight - 16));
  const menuWidth = Math.min(Math.max(158, rect.width), window.innerWidth - 16);
  const openAbove =
    rect.bottom + menuHeight + 6 > window.innerHeight - 8 && rect.top > menuHeight + 14;
  const top = openAbove ? rect.top - menuHeight - 6 : rect.bottom + 6;
  statusMenuStyle.value = {
    top: `${Math.max(8, Math.min(top, window.innerHeight - menuHeight - 8))}px`,
    left: `${Math.max(8, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 8))}px`,
    width: `${menuWidth}px`,
    maxHeight: `${menuHeight}px`,
  };
  statusMenuTrigger.value = trigger;
  openStatusId.value = item.id;
  focusStatusOption(
    focusIndex ??
      Math.max(
        0,
        appointmentStatuses.findIndex((option) => option.value === item.status),
      ),
  );
}

function onStatusOptionKeydown(event, index) {
  if (event.key === "Escape") {
    event.preventDefault();
    closeStatusMenu(true);
  } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const direction = event.key === "ArrowDown" ? 1 : -1;
    focusStatusOption(
      (index + direction + appointmentStatuses.length) % appointmentStatuses.length,
    );
  } else if (event.key === "Home" || event.key === "End") {
    event.preventDefault();
    focusStatusOption(event.key === "Home" ? 0 : appointmentStatuses.length - 1);
  } else if (event.key === "Tab") {
    closeStatusMenu();
  }
}

function selectAppointmentStatus(item, nextStatus) {
  closeStatusMenu(true);
  if (item && nextStatus !== item.status) changeAppointmentStatus(item, nextStatus);
}

function onStatusPointerDown(event) {
  if (
    !statusMenuRef.value?.contains(event.target) &&
    !statusMenuTrigger.value?.contains(event.target)
  ) {
    closeStatusMenu();
  }
}

function onStatusScroll(event) {
  if (!statusMenuRef.value?.contains(event.target)) closeStatusMenu();
}

function onStatusResize() {
  closeStatusMenu();
}

onMounted(() => {
  document.addEventListener("pointerdown", onStatusPointerDown);
  window.addEventListener("scroll", onStatusScroll, true);
  window.addEventListener("resize", onStatusResize);
});
onUnmounted(() => {
  document.removeEventListener("pointerdown", onStatusPointerDown);
  window.removeEventListener("scroll", onStatusScroll, true);
  window.removeEventListener("resize", onStatusResize);
});

function manualAppointmentCreated(data) {
  addAppointmentOpen.value = false;
  if (data.appointment) {
    const existingIndex = props.state.appointments.findIndex(
      (item) => item.id === data.appointment.id,
    );
    if (existingIndex >= 0) props.state.appointments.splice(existingIndex, 1, data.appointment);
    else props.state.appointments.unshift(data.appointment);
  }
  if (data.patient && !props.state.patients.some((patient) => patient.id === data.patient.id)) {
    props.state.patients.push(data.patient);
  }
  const cancelledIds = new Set(data.cancelled_appointment_ids || []);
  props.state.appointments.forEach((item) => {
    if (cancelledIds.has(item.id)) item.status = "cancelled";
  });
  appointmentPage.value = 1;
  emit("refresh");
}

function changeAppointmentStatus(item, nextStatus) {
  if (nextStatus !== "completed") {
    emit("status-change", item, nextStatus);
    return;
  }

  if (item.date > today) {
    showToast("A future appointment cannot be marked completed yet.", "error");
    return;
  }

  completionAppointment.value = item;
  completionRecord.value =
    props.state.records.find((record) => record.appointment_id === item.id) || null;
}

function closeCompletionRecord() {
  completionAppointment.value = null;
  completionRecord.value = null;
}

function applyCompletedRecord(record, sourceAppointment = completionAppointment.value) {
  const recordIndex = props.state.records.findIndex((item) => item.id === record.id);
  if (recordIndex >= 0) props.state.records.splice(recordIndex, 1, record);
  else props.state.records.unshift(record);

  const appointment = props.state.appointments.find((item) => item.id === sourceAppointment?.id);
  if (appointment) appointment.status = "completed";
}

function appointmentCompleted(record) {
  applyCompletedRecord(record);

  closeCompletionRecord();
  showToast("Treatment record saved. Appointment marked completed.");
  emit("refresh");
}

function continueToFollowUp({ record, date }) {
  const sourceAppointment = { ...completionAppointment.value, status: "completed" };
  applyCompletedRecord(record, sourceAppointment);
  followUpContext.value = { appointment: sourceAppointment, record, date };
  followUpWasScheduled.value = false;
  closeCompletionRecord();
  emit("refresh");
}

function returnToTreatmentRecord() {
  const context = followUpContext.value;
  if (!context) return;
  followUpContext.value = null;
  completionAppointment.value = context.appointment;
  completionRecord.value = context.record;
}

function followUpScheduled(data) {
  const appointment = data.appointment;
  if (appointment) {
    const existingIndex = props.state.appointments.findIndex((item) => item.id === appointment.id);
    if (existingIndex >= 0) props.state.appointments.splice(existingIndex, 1, appointment);
    else props.state.appointments.unshift(appointment);
  }

  const cancelledIds = new Set(data.cancelled_appointment_ids || []);
  props.state.appointments.forEach((item) => {
    if (cancelledIds.has(item.id)) item.status = "cancelled";
  });
  followUpWasScheduled.value = true;
  emit("refresh");
}

function closeFollowUp() {
  if (!followUpWasScheduled.value) {
    showToast("Treatment record saved. Follow-up appointment was not scheduled.");
  }
  followUpContext.value = null;
  followUpWasScheduled.value = false;
}
</script>

<template>
  <section
    class="workspace-panel schedule-workspace"
    :class="{ 'appointments-workspace': mode === 'appointments' }"
  >
    <template v-if="mode === 'schedule'">
      <section class="schedule-hero" aria-labelledby="availability-title">
        <span class="schedule-hero-icon"><CalendarDays :size="28" /></span>
        <div>
          <span class="section-kicker">Admin Control</span>
          <h1 id="availability-title">Clinic Availability</h1>
          <p>Set and manage the available dates and working hours for the clinic dentist.</p>
        </div>
      </section>

      <form class="schedule-builder" @submit.prevent="createSchedule">
        <label class="hp-field" aria-hidden="true"
          >Website<input v-model="schedule._website" tabindex="-1"
        /></label>

        <section class="schedule-settings-panel" aria-labelledby="schedule-settings-title">
          <header class="schedule-section-heading">
            <span><Settings :size="23" /></span>
            <div>
              <h2 id="schedule-settings-title">Schedule Settings</h2>
              <p>Select dates and set their availability.</p>
            </div>
          </header>

          <div class="schedule-fields">
            <label class="schedule-field">
              <span>Dentist</span>
              <span class="schedule-control">
                <UserRound :size="19" />
                <input :value="selectedDoctor" readonly required />
              </span>
            </label>
            <label class="schedule-field">
              <span>Schedule Month</span>
              <span class="schedule-control">
                <CalendarDays :size="18" />
                <input v-model="month" type="month" :min="currentMonth" required />
              </span>
            </label>
            <div class="schedule-time-fields">
              <label class="schedule-field">
                <span>Time In</span>
                <span class="schedule-control">
                  <Clock3 :size="18" />
                  <input v-model="schedule.time_in" type="time" step="900" required />
                </span>
              </label>
              <label class="schedule-field">
                <span>Time Out</span>
                <span class="schedule-control">
                  <Clock3 :size="18" />
                  <input v-model="schedule.time_out" type="time" step="900" required />
                </span>
              </label>
            </div>
            <label class="schedule-field">
              <span>Slot Interval</span>
              <span class="schedule-control">
                <Timer :size="18" />
                <select v-model="schedule.interval">
                  <option value="15">15 minutes</option>
                  <option value="30">30 minutes</option>
                  <option value="60">60 minutes</option>
                </select>
              </span>
            </label>
          </div>

          <div class="schedule-information">
            <Info :size="20" />
            <p>
              Selected dates will be available for the clinic dentist using these working hours.
            </p>
          </div>

          <div class="schedule-form-actions">
            <button class="secondary-button" type="button" @click="resetSchedule">
              <RotateCcw :size="18" /> Reset
            </button>
            <button class="primary-button" type="submit" :disabled="busy">
              <Save :size="18" /> {{ busy ? "Saving..." : "Save Availability" }}
            </button>
          </div>
        </section>

        <div class="schedule-calendar-column">
          <section class="schedule-summary-grid" aria-label="Availability summary">
            <article class="schedule-summary-card">
              <span><CalendarDays :size="22" /></span>
              <div>
                <strong>{{ selectedDates.size }}</strong>
                <small>Selected Dates</small>
                <p>Click on dates to select</p>
              </div>
            </article>
            <article class="schedule-summary-card working-hours">
              <span><Clock3 :size="22" /></span>
              <div>
                <strong>{{ formattedWorkingHours }}</strong>
                <small>Working Hours</small>
                <p>Daily schedule</p>
              </div>
            </article>
            <article class="schedule-summary-card slot-duration">
              <span><Timer :size="22" /></span>
              <div>
                <strong>{{ schedule.interval }} minutes</strong>
                <small>Slot Duration</small>
                <p>Per appointment</p>
              </div>
            </article>
            <article class="schedule-summary-card dentist-summary">
              <span><UserRound :size="22" /></span>
              <div>
                <strong>{{ selectedDoctor }}</strong>
                <small>Selected Dentist</small>
                <p>Set availability</p>
              </div>
            </article>
          </section>

          <fieldset class="schedule-calendar-panel">
            <legend class="sr-only">Select available dates</legend>
            <header class="schedule-calendar-heading">
              <h2>{{ monthLabel }}</h2>
              <div class="schedule-calendar-actions">
                <button
                  type="button"
                  title="Previous month"
                  aria-label="Previous month"
                  :disabled="!canGoPrevious"
                  @click="changeMonth(-1)"
                >
                  <ChevronLeft :size="20" />
                </button>
                <button type="button" @click="goToCurrentMonth">Today</button>
                <button
                  type="button"
                  title="Next month"
                  aria-label="Next month"
                  @click="changeMonth(1)"
                >
                  <ChevronRight :size="20" />
                </button>
              </div>
            </header>

            <div class="schedule-weekdays" aria-hidden="true">
              <span>Sun</span><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span
              ><span>Fri</span><span>Sat</span>
            </div>
            <div class="schedule-calendar" role="group" aria-label="Select available dates">
              <button
                v-for="cell in calendarCells"
                :key="cell.key"
                class="schedule-calendar-day"
                :class="{
                  selected: selectedDates.has(cell.date),
                  available: cell.available,
                  'fully-booked': cell.fullyBooked,
                  unavailable: !cell.current,
                  past: cell.past,
                }"
                type="button"
                :disabled="cell.disabled"
                :aria-label="formatDate(cell.date)"
                :aria-pressed="selectedDates.has(cell.date)"
                @click="toggleDate(cell)"
              >
                {{ cell.day }}
              </button>
            </div>

            <div class="schedule-calendar-legend" aria-label="Calendar status legend">
              <span><i class="selected"></i>Selected</span>
              <span><i class="available"></i>Available</span>
              <span><i class="fully-booked"></i>Fully Booked</span>
              <span><i class="unavailable"></i>Unavailable</span>
              <button class="clear-appointments-trigger" type="button" @click="openClearDialog">
                <Trash2 :size="17" />
                Clear Appointments
              </button>
            </div>
          </fieldset>
        </div>
      </form>
    </template>

    <section v-else class="appointment-list-panel" aria-labelledby="appointment-list-title">
      <header class="appointment-list-heading">
        <span><CalendarDays :size="24" /></span>
        <div>
          <span class="section-kicker">Patient Bookings</span>
          <h2 id="appointment-list-title">Appointment Schedule</h2>
          <p>View and manage all patient appointments.</p>
        </div>
        <div class="add-appointment-action">
          <button type="button" @click="addAppointmentOpen = true">
            <Plus :size="19" />
            Add Appointment
          </button>
          <small>For walk-in patients or manual booking</small>
        </div>
      </header>

      <div class="appointment-list-toolbar">
        <label class="appointment-search">
          <span class="sr-only">Search appointments</span>
          <Search :size="20" aria-hidden="true" />
          <input
            v-model="appointmentSearch"
            type="search"
            placeholder="Search patient name, email, or service..."
          />
        </label>

        <label class="appointment-filter">
          <span class="sr-only">Filter appointments by service</span>
          <select v-model="serviceFilter" aria-label="Filter appointments by service">
            <option value="">All Services</option>
            <option v-for="service in serviceOptions" :key="service" :value="service">
              {{ service }}
            </option>
          </select>
          <ChevronDown :size="16" aria-hidden="true" />
        </label>

        <label class="appointment-filter">
          <span class="sr-only">Filter appointments by status</span>
          <select v-model="statusFilter" aria-label="Filter appointments by status">
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="approved">Accepted</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <ChevronDown :size="16" aria-hidden="true" />
        </label>

        <button class="appointment-refresh-button" type="button" @click="emit('refresh')">
          <RefreshCw :size="17" aria-hidden="true" />
          Refresh
        </button>
      </div>

      <div class="appointment-table-wrap">
        <table class="appointment-list-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Patient</th>
              <th>Service</th>
              <th>
                <span class="appointment-heading-with-icon"
                  ><CalendarDays :size="16" aria-hidden="true" />Date</span
                >
              </th>
              <th>
                <span class="appointment-heading-with-icon"
                  ><Clock3 :size="16" aria-hidden="true" />Time</span
                >
              </th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(item, index) in visibleAppointments"
              :key="item.id"
              :data-entity-id="item.id"
              :class="{ 'notification-target-glow': highlightedId === item.id }"
            >
              <td data-label="#">
                {{ (appointmentPage - 1) * appointmentPageSize + index + 1 }}
              </td>
              <td data-label="Patient">
                <div class="appointment-patient">
                  <AvatarBadge :name="item.patient_name || 'Patient'" :image="patientImage(item)" />
                  <span>
                    <strong>{{ item.patient_name || "Patient" }}</strong>
                    <small>{{ item.patient_email || "No email address" }}</small>
                  </span>
                </div>
              </td>
              <td data-label="Service">{{ appointmentService(item) }}</td>
              <td data-label="Date">{{ formatDate(item.date) }}</td>
              <td data-label="Time">{{ formatClock(item.time) }}</td>
              <td data-label="Status">
                <button
                  type="button"
                  class="appointment-status-control"
                  :class="`status-${item.status}`"
                  :aria-label="`Update status for ${item.patient_name || 'patient'}, currently ${statusLabel(item.status)}`"
                  aria-haspopup="menu"
                  :aria-expanded="openStatusId === item.id"
                  :aria-controls="openStatusId === item.id ? 'appointment-status-menu' : undefined"
                  @click="openStatusMenu(item, $event)"
                  @keydown.down.prevent="openStatusMenu(item, $event, 0)"
                  @keydown.up.prevent="openStatusMenu(item, $event, appointmentStatuses.length - 1)"
                >
                  <i aria-hidden="true"></i>
                  <span>{{ statusLabel(item.status) }}</span>
                  <ChevronDown :size="14" aria-hidden="true" />
                </button>
              </td>
            </tr>
            <tr v-if="!visibleAppointments.length" class="appointment-empty-row">
              <td colspan="6">No appointments match the selected filters.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="appointment-list-footer">
        <span>
          Showing {{ firstVisibleAppointment }} to {{ lastVisibleAppointment }} of
          {{ filteredAppointments.length }} appointments
        </span>
        <nav
          v-if="appointmentPageCount > 1"
          class="appointment-pagination"
          aria-label="Appointment pages"
        >
          <button
            type="button"
            aria-label="Previous appointment page"
            :disabled="appointmentPage === 1"
            @click="selectAppointmentPage(appointmentPage - 1)"
          >
            <ChevronLeft :size="17" />
          </button>
          <button
            v-for="pageNumber in appointmentPageNumbers"
            :key="pageNumber"
            type="button"
            :class="{ active: appointmentPage === pageNumber }"
            :aria-current="appointmentPage === pageNumber ? 'page' : undefined"
            @click="selectAppointmentPage(pageNumber)"
          >
            {{ pageNumber }}
          </button>
          <button
            type="button"
            aria-label="Next appointment page"
            :disabled="appointmentPage === appointmentPageCount"
            @click="selectAppointmentPage(appointmentPage + 1)"
          >
            <ChevronRight :size="17" />
          </button>
        </nav>
      </footer>
    </section>

    <Teleport to="body">
      <div
        v-if="mode === 'appointments' && openStatusId"
        id="appointment-status-menu"
        ref="statusMenuRef"
        class="appointment-status-menu"
        :style="statusMenuStyle"
        role="menu"
        aria-label="Appointment status"
      >
        <button
          v-for="(option, index) in appointmentStatuses"
          :key="option.value"
          type="button"
          class="appointment-status-option"
          :class="[
            `status-${option.value}`,
            { selected: openStatusAppointment?.status === option.value },
          ]"
          role="menuitemradio"
          :aria-checked="openStatusAppointment?.status === option.value"
          @click="selectAppointmentStatus(openStatusAppointment, option.value)"
          @keydown="onStatusOptionKeydown($event, index)"
        >
          <i aria-hidden="true"></i>
          <span>{{ option.label }}</span>
          <Check
            v-if="openStatusAppointment?.status === option.value"
            :size="15"
            aria-hidden="true"
          />
        </button>
      </div>
    </Teleport>

    <AddAppointmentModal
      v-if="mode === 'appointments' && addAppointmentOpen"
      :state="state"
      :doctor="selectedDoctor"
      @close="addAppointmentOpen = false"
      @created="manualAppointmentCreated"
    />

    <ClearAppointmentsModal
      v-if="mode === 'schedule' && clearDialogOpen"
      :state="state"
      :doctor="selectedDoctor"
      :initial-month="month"
      :busy="clearBusy"
      @close="clearDialogOpen = false"
      @clear="clearAppointments"
    />

    <CompleteAppointmentModal
      v-if="mode === 'appointments' && completionAppointment"
      :appointment="completionAppointment"
      :existing-record="completionRecord"
      :availability="state.availability"
      :services="serviceOptions"
      :doctor="selectedDoctor"
      @close="closeCompletionRecord"
      @completed="appointmentCompleted"
      @follow-up="continueToFollowUp"
    />

    <ScheduleFollowUpModal
      v-if="mode === 'appointments' && followUpContext"
      :state="state"
      :appointment="followUpContext.appointment"
      :record="followUpContext.record"
      :preferred-date="followUpContext.date"
      :doctor="selectedDoctor"
      @back="returnToTreatmentRecord"
      @close="closeFollowUp"
      @scheduled="followUpScheduled"
    />
  </section>
</template>

<style scoped>
.schedule-workspace {
  display: grid;
  gap: 14px;
}

.schedule-hero {
  display: flex;
  min-height: 128px;
  align-items: center;
  gap: 18px;
  padding: 20px 30px;
  border: 1px solid #f4e7cd;
  border-radius: 8px;
  background: #ffffff;
}

.schedule-hero-icon,
.schedule-section-heading > span,
.schedule-summary-card > span {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  color: #8a6526;
  background: #f4e7cd;
}

.schedule-hero-icon {
  width: 58px;
  height: 58px;
  border-radius: 8px;
}

.schedule-hero h1,
.schedule-hero p,
.schedule-section-heading h2,
.schedule-section-heading p,
.schedule-summary-card p,
.schedule-calendar-heading h2 {
  margin: 0;
}

.schedule-hero h1 {
  margin-top: 2px;
  color: #171511;
  font-size: clamp(1.45rem, 2.1vw, 1.9rem);
  line-height: 1.15;
}

.schedule-hero p {
  margin-top: 6px;
  color: #514b42;
  font-size: 0.82rem;
}

.schedule-builder {
  display: grid;
  grid-template-columns: minmax(330px, 0.68fr) minmax(620px, 1.55fr);
  align-items: stretch;
  gap: 14px;
}

.schedule-builder > *,
.schedule-calendar-column {
  min-width: 0;
}

.schedule-settings-panel,
.schedule-calendar-panel {
  border: 1px solid #f4e7cd;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 5px 18px rgba(23, 21, 17, 5%);
}

.schedule-settings-panel {
  display: grid;
  align-content: start;
  gap: 18px;
  padding: 20px;
}

.schedule-section-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}

.schedule-section-heading > span {
  width: 48px;
  height: 48px;
  border-radius: 8px;
}

.schedule-section-heading h2 {
  color: #171511;
  font-size: 1rem;
}

.schedule-section-heading p {
  margin-top: 2px;
  color: #706b61;
  font-size: 0.73rem;
}

.schedule-fields {
  display: grid;
  gap: 13px;
}

.schedule-field {
  display: grid;
  gap: 6px;
  color: #171511;
  font-size: 0.74rem;
  font-weight: 750;
}

.schedule-control {
  display: flex;
  min-width: 0;
  min-height: 46px;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  color: #171511;
  border: 1px solid #f4e7cd;
  border-radius: 7px;
  background: #ffffff;
}

.schedule-control > svg {
  flex: 0 0 auto;
}

.schedule-control :is(input, select) {
  width: 100%;
  min-width: 0;
  min-height: 42px;
  border: 0;
  outline: 0;
  background: transparent;
  color: #171511;
  padding: 0;
  font: inherit;
  font-size: 0.79rem;
}

.schedule-control input[readonly] {
  background: transparent;
}

.schedule-time-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.schedule-information {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 13px 14px;
  color: #8a6526;
  border-radius: 7px;
  background: #f8f1e2;
}

.schedule-information svg {
  flex: 0 0 auto;
  color: #8a6526;
}

.schedule-information p {
  margin: 0;
  font-size: 0.7rem;
  line-height: 1.5;
}

.schedule-form-actions {
  display: grid;
  grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
  gap: 10px;
}

.schedule-form-actions button {
  display: inline-flex;
  min-height: 46px;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.schedule-calendar-column {
  display: grid;
  align-content: start;
  gap: 12px;
}

.schedule-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.schedule-summary-card {
  display: grid;
  min-width: 0;
  min-height: 108px;
  grid-template-columns: 48px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  padding: 14px;
  border: 1px solid #f4e7cd;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(23, 21, 17, 4%);
}

.schedule-summary-card > span {
  width: 48px;
  height: 48px;
  border-radius: 8px;
}

.schedule-summary-card.working-hours > span {
  color: #8a6526;
  background: #f4e7cd;
}

.schedule-summary-card.slot-duration > span {
  color: #8a6526;
  background: #f4e7cd;
}

.schedule-summary-card.dentist-summary > span {
  color: #8a6526;
  background: #f8f1e2;
}

.schedule-summary-card div {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.schedule-summary-card strong {
  overflow-wrap: anywhere;
  color: #171511;
  font-size: 0.88rem;
  line-height: 1.2;
}

.schedule-summary-card small {
  color: #514b42;
  font-size: 0.7rem;
  font-weight: 650;
}

.schedule-summary-card p {
  margin-top: 7px;
  color: #706b61;
  font-size: 0.72rem;
}

.schedule-calendar-panel {
  min-width: 0;
  margin: 0;
  padding: 18px;
}

.schedule-calendar-heading {
  display: flex;
  min-height: 46px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.schedule-calendar-heading h2 {
  color: #171511;
  font-size: 1.25rem;
}

.schedule-calendar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.schedule-calendar-actions button {
  display: grid;
  min-width: 42px;
  height: 42px;
  place-items: center;
  padding: 0 12px;
  color: #171511;
  border: 1px solid #f4e7cd;
  border-radius: 7px;
  background: #ffffff;
  font-size: 0.75rem;
  font-weight: 750;
  cursor: pointer;
}

.schedule-calendar-actions button:hover:not(:disabled),
.schedule-calendar-actions button:focus-visible {
  color: #8a6526;
  border-color: #c49a46;
  outline: none;
  background: #f8f1e2;
}

.schedule-calendar-actions button:disabled {
  cursor: default;
  opacity: 0.38;
}

.schedule-weekdays,
.schedule-calendar {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 6px;
}

.schedule-weekdays {
  margin-bottom: 7px;
  color: #514b42;
  font-size: 0.72rem;
  font-weight: 800;
  text-align: center;
  text-transform: uppercase;
}

.schedule-calendar-day {
  min-width: 0;
  min-height: 52px;
  color: #171511;
  border: 1px solid #f4e7cd;
  border-radius: 7px;
  background: #ffffff;
  font-size: 0.78rem;
  font-weight: 800;
  cursor: pointer;
  transition:
    border-color 140ms ease,
    background 140ms ease,
    color 140ms ease,
    transform 140ms ease;
}

.schedule-calendar-day:hover:not(:disabled),
.schedule-calendar-day:focus-visible {
  border-color: #8a6526;
  outline: none;
  transform: translateY(-1px);
}

.schedule-calendar-day.available {
  color: #8a6526;
  border-color: #f4e7cd;
  background: #f4e7cd;
}

.schedule-calendar-day.fully-booked {
  color: #d72c43;
  border-color: #f4cbd1;
  background: #ffe8eb;
}

.schedule-calendar-day.selected {
  color: #ffffff;
  border-color: #8a6526;
  background: #8a6526;
  box-shadow: inset 0 -3px 0 rgba(23, 21, 17, 14%);
}

.schedule-calendar-day.unavailable {
  color: #cfc5b3;
  border-color: #f5f2eb;
  background: #f5f2eb;
}

.schedule-calendar-day.past {
  color: #706b61;
  border-color: #e8dfd0;
  background: #fcfbf8;
}

.schedule-calendar-day:disabled {
  cursor: default;
}

.schedule-calendar-legend {
  display: flex;
  min-height: 50px;
  align-items: center;
  gap: clamp(18px, 4vw, 44px);
  margin-top: 14px;
  padding: 10px 12px;
  color: #171511;
  border-radius: 7px;
  background: #f8f1e2;
  font-size: 0.72rem;
  font-weight: 650;
}

.schedule-calendar-legend span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.schedule-calendar-legend i {
  width: 19px;
  height: 19px;
  flex: 0 0 19px;
  border-radius: 5px;
}

.schedule-calendar-legend i.selected {
  background: #8a6526;
}

.schedule-calendar-legend i.available {
  background: #dfc48a;
}

.schedule-calendar-legend i.fully-booked {
  background: #ffb7c2;
}

.schedule-calendar-legend i.unavailable {
  background: #e8dfd0;
}

.clear-appointments-trigger {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-left: auto;
  padding: 0 16px;
  color: #d71935;
  border: 1px solid #ee9eaa;
  border-radius: 7px;
  background: #ffffff;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.clear-appointments-trigger:hover,
.clear-appointments-trigger:focus-visible {
  border-color: #d71935;
  outline: none;
  background: #fff1f3;
}

.appointment-list-panel {
  min-width: 0;
  overflow: hidden;
  color: #171511;
  border: 1px solid #eadac0;
  border-radius: 20px;
  background: #fffdf9;
  box-shadow: 0 16px 42px rgba(75, 54, 25, 8%);
}

.appointment-list-heading {
  position: relative;
  display: flex;
  min-height: 132px;
  align-items: center;
  gap: 18px;
  padding: 24px 28px;
  border-bottom: 1px solid #f2e8d8;
  background:
    radial-gradient(ellipse 54% 100% at 79% 123%, rgba(213, 170, 89, 13%) 0 45%, transparent 46%),
    radial-gradient(ellipse 50% 125% at 90% -48%, rgba(213, 170, 89, 15%) 0 55%, transparent 56%),
    linear-gradient(110deg, #fffefd 0%, #fffaf1 100%);
}

.appointment-list-heading > * {
  position: relative;
  z-index: 1;
}

.appointment-list-heading > span {
  display: grid;
  width: 70px;
  height: 70px;
  flex: 0 0 70px;
  place-items: center;
  color: #855713;
  border: 1px solid #f2e2c4;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 25%, #fff9ef, #f2dfb9);
}

.appointment-list-heading > div:not(.add-appointment-action) {
  min-width: 0;
}

.appointment-list-heading h2,
.appointment-list-heading p {
  margin: 0;
}

.appointment-list-heading h2 {
  margin-top: 4px;
  color: #17130e;
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(1.5rem, 2.2vw, 1.9rem);
  line-height: 1.15;
}

.appointment-list-heading p {
  margin-top: 5px;
  color: #665e54;
  font-size: 0.85rem;
}

.add-appointment-action {
  display: grid;
  justify-items: center;
  gap: 6px;
  margin-left: auto;
}

.add-appointment-action button {
  display: inline-flex;
  min-height: 48px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 23px;
  color: #ffffff;
  border: 1px solid #94661f;
  border-radius: 11px;
  background: linear-gradient(110deg, #9e6d24, #be8e3b 53%, #91611a);
  box-shadow: 0 8px 20px rgba(138, 101, 38, 20%);
  font: inherit;
  font-size: 0.9rem;
  font-weight: 750;
  cursor: pointer;
}

.add-appointment-action button:hover,
.add-appointment-action button:focus-visible {
  border-color: #6f4811;
  outline: 2px solid #d6ad62;
  outline-offset: 2px;
  background: linear-gradient(110deg, #805517, #ae7d30 53%, #754b11);
}

.add-appointment-action small {
  color: #706b61;
  font-size: 0.72rem;
}

.appointment-list-toolbar {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(170px, 0.36fr) minmax(160px, 0.32fr) auto;
  gap: 12px;
  margin: 16px 16px 0;
  padding: 8px;
  border: 1px solid #f1e4d0;
  border-radius: 13px;
  background: #fffdf9;
}

.appointment-search,
.appointment-filter {
  position: relative;
  display: flex;
  min-width: 0;
  height: 48px;
  align-items: center;
  color: #342c22;
  border: 1px solid #e9d8bd;
  border-radius: 9px;
  background: #ffffff;
}

.appointment-search {
  gap: 12px;
  padding: 0 15px;
}

.appointment-search > svg {
  flex: 0 0 auto;
  color: #9a661c;
}

.appointment-search:focus-within,
.appointment-filter:focus-within {
  border-color: #8a6526;
  box-shadow: 0 0 0 3px rgba(138, 101, 38, 12%);
}

.appointment-search input,
.appointment-filter select {
  min-width: 0;
  color: inherit;
  border: 0;
  outline: 0;
  background: transparent;
  font: inherit;
}

.appointment-search input {
  width: 100%;
  height: 100%;
}

.appointment-search input::placeholder {
  color: #70685e;
}

.appointment-filter select {
  width: 100%;
  height: 100%;
  padding: 0 38px 0 11px;
  appearance: none;
  cursor: pointer;
}

.appointment-filter option {
  color: #171511;
  background: #ffffff;
}

.appointment-filter > svg {
  position: absolute;
  right: 12px;
  pointer-events: none;
}

.appointment-refresh-button {
  display: inline-flex;
  min-width: 104px;
  height: 48px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 16px;
  color: #795016;
  border: 1px solid #f0dec0;
  border-radius: 9px;
  background: #f8edda;
  font: inherit;
  font-size: 0.85rem;
  font-weight: 750;
  cursor: pointer;
}

.appointment-refresh-button:hover,
.appointment-refresh-button:focus-visible {
  border-color: #c89846;
  outline: 2px solid #d6ad62;
  outline-offset: 2px;
  background: #f4e3c5;
}

.appointment-table-wrap {
  width: calc(100% - 32px);
  overflow-x: auto;
  margin: 10px 16px 0;
  border: 1px solid #f0e4d1;
  border-radius: 12px 12px 0 0;
}

.appointment-list-table {
  width: 100%;
  min-width: 870px;
  border-collapse: collapse;
  table-layout: fixed;
}

.appointment-list-table th,
.appointment-list-table td {
  padding: 13px 14px;
  text-align: left;
  vertical-align: middle;
}

.appointment-list-table th {
  color: #514334;
  background: linear-gradient(90deg, #faf1e3, #fdf9f2);
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
}

.appointment-heading-with-icon {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.appointment-heading-with-icon svg {
  color: #956419;
}

.appointment-list-table th:first-child,
.appointment-list-table td:first-child {
  width: 44px;
  text-align: center;
}

.appointment-list-table th:nth-child(2) {
  width: 30%;
}

.appointment-list-table th:nth-child(3) {
  width: 23%;
}

.appointment-list-table th:nth-child(4) {
  width: 15%;
}

.appointment-list-table th:nth-child(5) {
  width: 13%;
}

.appointment-list-table th:nth-child(6) {
  width: 184px;
}

.appointment-list-table tbody tr {
  border-bottom: 1px solid #eee4d7;
  transition: background-color 160ms ease;
}

.appointment-list-table tbody tr:not(.appointment-empty-row):hover {
  background: #fff9ed;
}

.appointment-list-table tbody tr:last-child {
  border-bottom: 0;
}

.appointment-list-table td {
  color: #29231d;
  font-size: 0.82rem;
}

.appointment-patient {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.appointment-patient :deep(.profile-avatar) {
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  color: #6d4614;
  border: 1px solid #f1dfbd;
  background-color: #f6e7cd;
  font-size: 0.78rem;
}

.appointment-patient > span {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.appointment-patient strong,
.appointment-patient small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.appointment-patient strong {
  color: #17130e;
  font-size: 0.84rem;
}

.appointment-patient small {
  color: #72695e;
  font-size: 0.74rem;
}

.appointment-status-control {
  display: grid;
  width: 158px;
  height: 38px;
  grid-template-columns: 8px minmax(88px, 1fr) 14px;
  align-items: center;
  gap: 7px;
  padding: 0 9px;
  color: #81500b;
  border: 1px solid #f4d69c;
  border-radius: 21px;
  background: #fff4df;
  font: inherit;
  font-size: 0.76rem;
  font-weight: 800;
  text-align: left;
  cursor: pointer;
}

.appointment-status-control i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #eea114;
}

.appointment-status-control span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.appointment-status-control > svg {
  pointer-events: none;
}

.appointment-status-control:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(138, 101, 38, 12%);
}

.appointment-status-control.status-approved,
.appointment-status-control.status-accepted {
  color: #12659e;
  border-color: #a6d4ed;
  background: #e9f5fc;
}

.appointment-status-control.status-approved i,
.appointment-status-control.status-accepted i {
  background: #1d83c4;
}

.appointment-status-control.status-completed {
  color: #147347;
  border-color: #a7dcc0;
  background: #e9f9ef;
}

.appointment-status-control.status-completed i {
  background: #249558;
}

.appointment-status-control.status-cancelled {
  color: #d72445;
  border-color: #ffcbd4;
  background: #fff0f3;
}

.appointment-status-control.status-cancelled i {
  background: #ef3c5d;
}

.appointment-status-menu {
  position: fixed;
  z-index: 1200;
  display: grid;
  gap: 3px;
  overflow-y: auto;
  padding: 7px;
  border: 1px solid #e9d8bd;
  border-radius: 11px;
  background: #ffffff;
  box-shadow: 0 16px 34px rgba(60, 42, 16, 18%);
}

.appointment-status-option {
  display: grid;
  min-height: 40px;
  grid-template-columns: 8px minmax(0, 1fr) 15px;
  align-items: center;
  gap: 9px;
  padding: 0 9px;
  color: #171511;
  border: 0;
  border-radius: 5px;
  background: transparent;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
}

.appointment-status-option:hover,
.appointment-status-option:focus-visible,
.appointment-status-option.selected {
  outline: none;
  background: #f8edda;
}

.appointment-status-option i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #eea114;
}

.appointment-status-option.status-approved i,
.appointment-status-option.status-accepted i {
  background: #1d83c4;
}

.appointment-status-option.status-completed i {
  background: #249558;
}

.appointment-status-option.status-cancelled i {
  background: #ef3c5d;
}

.appointment-status-option.status-pending.selected {
  color: #81500b;
  background: #fff4df;
}

.appointment-status-option.status-approved.selected,
.appointment-status-option.status-accepted.selected {
  color: #12659e;
  background: #e9f5fc;
}

.appointment-status-option.status-completed.selected {
  color: #147347;
  background: #e9f9ef;
}

.appointment-status-option.status-cancelled.selected {
  color: #d72445;
  background: #fff0f3;
}

.appointment-status-option > svg {
  color: #8a6526;
}

:global(html[data-dashboard-theme="dark"] .appointment-status-menu) {
  border-color: #514b42;
  background: #28241e;
  box-shadow: 0 12px 32px rgba(17, 16, 15, 40%);
}

:global(html[data-dashboard-theme="dark"] .appointment-status-option) {
  color: #edddbd;
}

:global(html[data-dashboard-theme="dark"] .appointment-status-option:hover),
:global(html[data-dashboard-theme="dark"] .appointment-status-option:focus-visible),
:global(html[data-dashboard-theme="dark"] .appointment-status-option.selected) {
  background: #3f321e;
}

:global(html[data-dashboard-theme="dark"] .appointment-status-option.status-pending.selected) {
  color: #f7d898;
  background: #493820;
}

:global(html[data-dashboard-theme="dark"] .appointment-status-option.status-approved.selected),
:global(html[data-dashboard-theme="dark"] .appointment-status-option.status-accepted.selected) {
  color: #b9e0fc;
  background: #203c51;
}

:global(html[data-dashboard-theme="dark"] .appointment-status-option.status-completed.selected) {
  color: #a7ecc0;
  background: #1f3f2b;
}

:global(html[data-dashboard-theme="dark"] .appointment-status-option.status-cancelled.selected) {
  color: #ffc4ce;
  background: #4b2631;
}

.appointment-empty-row td {
  height: 110px;
  color: #706b61;
  text-align: center;
}

.appointment-list-footer {
  display: flex;
  min-height: 64px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 11px 24px;
  color: #5e554b;
  border-top: 1px solid #f0e4d1;
  background: #fffdf9;
  font-size: 0.77rem;
}

.appointment-pagination {
  display: flex;
  align-items: center;
  gap: 6px;
}

.appointment-pagination button {
  display: inline-flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  color: #594632;
  border: 1px solid #eadac0;
  border-radius: 8px;
  background: #ffffff;
  font: inherit;
  font-weight: 750;
  cursor: pointer;
}

.appointment-pagination button:hover:not(:disabled),
.appointment-pagination button:focus-visible {
  border-color: #c49a46;
  outline: none;
}

.appointment-pagination button.active {
  color: #ffffff;
  border-color: #90601c;
  background: linear-gradient(120deg, #a9772e, #865719);
}

.appointment-pagination button:disabled {
  color: #aaa194;
  background: #fcfbf8;
  cursor: not-allowed;
}

:global(html[data-dashboard-theme="dark"]) .schedule-hero,
:global(html[data-dashboard-theme="dark"]) .schedule-settings-panel,
:global(html[data-dashboard-theme="dark"]) .schedule-calendar-panel,
:global(html[data-dashboard-theme="dark"]) .schedule-summary-card {
  color: #edddbd;
  border-color: #514b42;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .schedule-hero h1,
:global(html[data-dashboard-theme="dark"]) .schedule-section-heading h2,
:global(html[data-dashboard-theme="dark"]) .schedule-summary-card strong,
:global(html[data-dashboard-theme="dark"]) .schedule-calendar-heading h2 {
  color: #f8f1e2;
}

:global(html[data-dashboard-theme="dark"]) .schedule-hero p,
:global(html[data-dashboard-theme="dark"]) .schedule-section-heading p,
:global(html[data-dashboard-theme="dark"]) .schedule-summary-card small,
:global(html[data-dashboard-theme="dark"]) .schedule-summary-card p,
:global(html[data-dashboard-theme="dark"]) .schedule-field,
:global(html[data-dashboard-theme="dark"]) .schedule-weekdays {
  color: #cfc5b3;
}

:global(html[data-dashboard-theme="dark"]) .schedule-control,
:global(html[data-dashboard-theme="dark"]) .schedule-control :is(input, select),
:global(html[data-dashboard-theme="dark"]) .schedule-calendar-actions button,
:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day {
  color: #edddbd;
  border-color: #514b42;
  background: #171511;
}

:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day.available {
  color: #edddbd;
  border-color: #d5aa59;
  background: #241e17;
}

:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day.fully-booked {
  color: #ffc2cb;
  border-color: #7d3542;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day.selected {
  color: #171511;
  border-color: #d5aa59;
  background: #d5aa59;
}

:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day.unavailable,
:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day.past {
  color: #706b61;
  border-color: #28241e;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .schedule-calendar-legend {
  color: #cfc5b3;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .clear-appointments-trigger {
  color: #ffb7c2;
  border-color: #7d3542;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-panel,
:global(html[data-dashboard-theme="dark"]) .appointment-list-footer,
:global(html[data-dashboard-theme="dark"]) .appointment-search,
:global(html[data-dashboard-theme="dark"]) .appointment-filter,
:global(html[data-dashboard-theme="dark"]) .appointment-pagination button {
  color: #edddbd;
  border-color: #514b42;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-heading {
  border-color: #514b42;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-heading > span {
  color: #e3c985;
  border-color: #70532d;
  background: #3f321e;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-heading h2 {
  color: #f8f1e2;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-heading p,
:global(html[data-dashboard-theme="dark"]) .add-appointment-action small {
  color: #aaa194;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-toolbar,
:global(html[data-dashboard-theme="dark"]) .appointment-list-footer {
  border-color: #514b42;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-toolbar,
:global(html[data-dashboard-theme="dark"]) .appointment-table-wrap {
  border-color: #514b42;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .appointment-search > svg,
:global(html[data-dashboard-theme="dark"]) .appointment-heading-with-icon svg {
  color: #d6ad62;
}

:global(html[data-dashboard-theme="dark"]) .appointment-search input::placeholder {
  color: #b9ab96;
}

:global(html[data-dashboard-theme="dark"]) .appointment-filter option {
  color: #f8f1e2;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-table th {
  color: #cfc5b3;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-table tbody tr {
  border-color: #514b42;
}

:global(html[data-dashboard-theme="dark"])
  .appointment-list-table
  tbody
  tr:not(.appointment-empty-row):hover {
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-table td,
:global(html[data-dashboard-theme="dark"]) .appointment-patient strong {
  color: #edddbd;
}

:global(html[data-dashboard-theme="dark"]) .appointment-patient small,
:global(html[data-dashboard-theme="dark"]) .appointment-empty-row td {
  color: #aaa194;
}

:global(html[data-dashboard-theme="dark"]) .appointment-patient :deep(.profile-avatar) {
  color: #f8e4bc;
  border-color: #70532d;
  background-color: #493923;
}

:global(html[data-dashboard-theme="dark"] .appointment-status-control.status-approved),
:global(html[data-dashboard-theme="dark"] .appointment-status-control.status-accepted) {
  color: #b9e0fc;
  border-color: #365e78;
  background: #203c51;
}

:global(html[data-dashboard-theme="dark"] .appointment-status-control.status-completed) {
  color: #a7ecc0;
  border-color: #326f4b;
  background: #1f3f2b;
}

:global(html[data-dashboard-theme="dark"] .appointment-status-control.status-pending) {
  color: #f7d898;
  border-color: #82602d;
  background: #493820;
}

:global(html[data-dashboard-theme="dark"] .appointment-status-control.status-cancelled) {
  color: #ffc4ce;
  border-color: #804351;
  background: #4b2631;
}

:global(html[data-dashboard-theme="dark"]) .appointment-refresh-button {
  color: #e3c985;
  border-color: #d5aa59;
  background: #3f321e;
}

:global(html[data-dashboard-theme="dark"]) .appointment-pagination button.active {
  color: #171511;
  border-color: #d5aa59;
  background: #d5aa59;
}

@media (max-width: 1180px) {
  .schedule-builder {
    grid-template-columns: 1fr;
  }

  .appointment-list-toolbar {
    grid-template-columns: minmax(260px, 1fr) repeat(2, minmax(150px, 0.42fr)) auto;
  }
}

@media (max-width: 1020px) {
  .appointment-list-toolbar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .appointment-search,
  .appointment-refresh-button {
    grid-column: 1 / -1;
  }
}

@media (max-width: 860px) {
  .schedule-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .appointment-list-toolbar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .appointment-search {
    grid-column: 1 / -1;
  }

  .appointment-refresh-button {
    grid-column: 1 / -1;
  }

  .appointment-list-heading {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .appointment-list-toolbar {
    margin: 12px 12px 0;
  }

  .appointment-table-wrap {
    width: calc(100% - 24px);
    margin: 10px 12px 0;
  }

  .add-appointment-action {
    width: 100%;
    justify-items: stretch;
    margin-left: 0;
  }

  .add-appointment-action small {
    text-align: center;
  }
}

@media (max-width: 600px) {
  .schedule-hero {
    min-height: 116px;
    align-items: flex-start;
    padding: 18px;
  }

  .schedule-hero-icon {
    width: 48px;
    height: 48px;
  }

  .schedule-hero h1 {
    font-size: 1.35rem;
  }

  .schedule-settings-panel,
  .schedule-calendar-panel {
    padding: 14px;
  }

  .schedule-time-fields {
    grid-template-columns: 1fr;
  }

  .schedule-form-actions {
    grid-template-columns: 1fr;
  }

  .schedule-summary-card {
    min-height: 96px;
    grid-template-columns: 40px minmax(0, 1fr);
    padding: 11px;
  }

  .schedule-summary-card > span {
    width: 40px;
    height: 40px;
  }

  .schedule-calendar-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .schedule-calendar-actions {
    width: 100%;
  }

  .schedule-calendar-actions button:nth-child(2) {
    flex: 1;
  }

  .schedule-weekdays,
  .schedule-calendar {
    gap: 4px;
  }

  .schedule-weekdays {
    font-size: 0.72rem;
  }

  .schedule-calendar-day {
    min-height: 40px;
    border-radius: 5px;
    font-size: 0.7rem;
  }

  .schedule-calendar-legend {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .clear-appointments-trigger {
    grid-column: 1 / -1;
    margin-left: 0;
  }

  .appointment-list-toolbar {
    grid-template-columns: 1fr;
  }

  .appointment-list-heading {
    min-height: 0;
    padding: 19px;
  }

  .appointment-list-heading > span {
    width: 52px;
    height: 52px;
    flex-basis: 52px;
  }

  .appointment-list-heading h2 {
    font-size: 1.4rem;
  }

  .appointment-search,
  .appointment-refresh-button {
    grid-column: auto;
  }

  .appointment-table-wrap {
    padding: 0 8px 10px;
    border: 0;
    background: transparent;
  }

  .appointment-list-table {
    min-width: 0;
  }

  .appointment-list-table thead {
    display: none;
  }

  .appointment-list-table tbody {
    display: grid;
    gap: 9px;
  }

  .appointment-list-table tbody tr {
    display: grid;
    padding: 10px 14px;
    border: 1px solid #ebddc8;
    border-radius: 12px;
    background: #ffffff;
    box-shadow: 0 4px 14px rgba(75, 54, 25, 5%);
  }

  .appointment-list-table th,
  .appointment-list-table td,
  .appointment-list-table th:first-child,
  .appointment-list-table td:first-child {
    width: auto;
    padding: 7px 0;
    text-align: left;
  }

  .appointment-list-table td {
    display: grid;
    grid-template-columns: 82px minmax(0, 1fr);
    align-items: center;
    gap: 10px;
    border-bottom: 1px solid #f5f2eb;
  }

  .appointment-list-table td::before {
    content: attr(data-label);
    color: #706b61;
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
  }

  .appointment-list-table td:last-child {
    border-bottom: 0;
  }

  .appointment-empty-row {
    display: block !important;
  }

  .appointment-empty-row td {
    display: block;
    height: auto;
    padding: 26px 10px;
    text-align: center;
    border: 0;
  }

  .appointment-empty-row td::before {
    display: none;
  }

  .appointment-status-control {
    width: min(100%, 160px);
  }

  .appointment-list-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  :global(html[data-dashboard-theme="dark"]) .appointment-list-table tbody tr {
    border-color: #514b42;
    background: #28241e;
  }
}

@media (max-width: 390px) {
  .schedule-summary-grid {
    grid-template-columns: 1fr;
  }

  .schedule-hero {
    gap: 12px;
    padding: 14px;
  }

  .schedule-hero-icon {
    display: none;
  }

  .schedule-calendar-day {
    min-height: 36px;
  }
}
</style>
