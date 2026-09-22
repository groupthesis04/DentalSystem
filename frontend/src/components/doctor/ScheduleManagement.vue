<script setup>
import {
  CalendarDays,
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
import { computed, reactive, ref, watch } from "vue";

import AvatarBadge from "../AvatarBadge.vue";
import AddAppointmentModal from "./AddAppointmentModal.vue";
import ClearAppointmentsModal from "./ClearAppointmentsModal.vue";
import CompleteAppointmentModal from "./CompleteAppointmentModal.vue";
import ScheduleFollowUpModal from "./ScheduleFollowUpModal.vue";
import { apiRequest, session } from "../../services/api";
import { formatDate, localDateIso } from "../../services/format";
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
      `${item.patient_name || ""} ${item.patient_email || ""} ${item.service || ""}`
        .toLowerCase()
        .includes(query);
    const matchesService = !serviceFilter.value || item.service === serviceFilter.value;
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

function changeAppointmentStatus(item, event) {
  const nextStatus = event.target.value;
  if (nextStatus !== "completed") {
    emit("status-change", item, nextStatus);
    return;
  }

  event.target.value = item.status;
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
          <Search :size="18" aria-hidden="true" />
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
              <th>Date</th>
              <th>Time</th>
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
              <td data-label="Service">{{ item.service }}</td>
              <td data-label="Date">{{ formatDate(item.date) }}</td>
              <td data-label="Time">{{ formatClock(item.time) }}</td>
              <td data-label="Status">
                <label class="appointment-status-control" :class="`status-${item.status}`">
                  <span class="sr-only">Update status for {{ item.patient_name }}</span>
                  <i aria-hidden="true"></i>
                  <select
                    :value="item.status"
                    :aria-label="`Update status for ${item.patient_name || 'patient'}`"
                    @change="changeAppointmentStatus(item, $event)"
                  >
                    <option value="pending">Pending</option>
                    <option value="approved">Accepted</option>
                    <option value="completed">Completed</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                  <ChevronDown :size="14" aria-hidden="true" />
                </label>
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
  border: 1px solid #d9e8f2;
  border-radius: 8px;
  background: #fff;
}

.schedule-hero-icon,
.schedule-section-heading > span,
.schedule-summary-card > span {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  color: #0789a2;
  background: #ddf5fa;
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
  color: #12294e;
  font-size: clamp(1.45rem, 2.1vw, 1.9rem);
  line-height: 1.15;
}

.schedule-hero p {
  margin-top: 6px;
  color: #536a89;
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
  border: 1px solid #dfe8f0;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 5px 18px rgb(31 64 102 / 5%);
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
  color: #152a4d;
  font-size: 1rem;
}

.schedule-section-heading p {
  margin-top: 2px;
  color: #6c7d95;
  font-size: 0.73rem;
}

.schedule-fields {
  display: grid;
  gap: 13px;
}

.schedule-field {
  display: grid;
  gap: 6px;
  color: #15294a;
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
  color: #193354;
  border: 1px solid #d1deea;
  border-radius: 7px;
  background: #fff;
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
  color: #13284a;
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
  color: #355d82;
  border-radius: 7px;
  background: #eaf7ff;
}

.schedule-information svg {
  flex: 0 0 auto;
  color: #159ed0;
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
  border: 1px solid #dfe8f0;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 4px 14px rgb(31 64 102 / 4%);
}

.schedule-summary-card > span {
  width: 48px;
  height: 48px;
  border-radius: 8px;
}

.schedule-summary-card.working-hours > span {
  color: #078375;
  background: #e2f7f0;
}

.schedule-summary-card.slot-duration > span {
  color: #0c7e83;
  background: #e7f8f5;
}

.schedule-summary-card.dentist-summary > span {
  color: #236ee3;
  background: #edf4ff;
}

.schedule-summary-card div {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.schedule-summary-card strong {
  overflow-wrap: anywhere;
  color: #14284b;
  font-size: 0.88rem;
  line-height: 1.2;
}

.schedule-summary-card small {
  color: #506783;
  font-size: 0.7rem;
  font-weight: 650;
}

.schedule-summary-card p {
  margin-top: 7px;
  color: #718098;
  font-size: 0.63rem;
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
  color: #14284b;
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
  color: #183052;
  border: 1px solid #d5e1ec;
  border-radius: 7px;
  background: #fff;
  font-size: 0.75rem;
  font-weight: 750;
  cursor: pointer;
}

.schedule-calendar-actions button:hover:not(:disabled),
.schedule-calendar-actions button:focus-visible {
  color: #087f96;
  border-color: #85ccda;
  outline: none;
  background: #eefbfc;
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
  color: #526987;
  font-size: 0.67rem;
  font-weight: 800;
  text-align: center;
  text-transform: uppercase;
}

.schedule-calendar-day {
  min-width: 0;
  min-height: 52px;
  color: #172c4d;
  border: 1px solid #d7e2ec;
  border-radius: 7px;
  background: #fff;
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
  border-color: #0792aa;
  outline: none;
  transform: translateY(-1px);
}

.schedule-calendar-day.available {
  color: #075b58;
  border-color: #cfeee2;
  background: #e7f8f1;
}

.schedule-calendar-day.fully-booked {
  color: #d72c43;
  border-color: #f4cbd1;
  background: #ffe8eb;
}

.schedule-calendar-day.selected {
  color: #fff;
  border-color: #078da5;
  background: #079bb4;
  box-shadow: inset 0 -3px 0 rgb(0 90 111 / 14%);
}

.schedule-calendar-day.unavailable {
  color: #aebac9;
  border-color: #edf1f5;
  background: #f3f6f9;
}

.schedule-calendar-day.past {
  color: #77879d;
  border-color: #e0e7ee;
  background: #fbfcfd;
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
  color: #243a5b;
  border-radius: 7px;
  background: #f6f9fc;
  font-size: 0.68rem;
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
  background: #079bb4;
}

.schedule-calendar-legend i.available {
  background: #a9ead2;
}

.schedule-calendar-legend i.fully-booked {
  background: #ffb7c2;
}

.schedule-calendar-legend i.unavailable {
  background: #d5dee8;
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
  background: #fff;
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
  color: #112342;
  border: 1px solid #dce6ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 8px 24px rgb(30 73 104 / 6%);
}

.appointment-list-heading {
  display: flex;
  min-height: 112px;
  align-items: center;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid #e2eaf1;
  background: #fbfdff;
}

.appointment-list-heading > span {
  display: grid;
  width: 58px;
  height: 58px;
  flex: 0 0 58px;
  place-items: center;
  color: #0878df;
  border: 1px solid #d2e7fb;
  border-radius: 8px;
  background: #edf6ff;
}

.appointment-list-heading > div:not(.add-appointment-action) {
  min-width: 0;
}

.appointment-list-heading h2,
.appointment-list-heading p {
  margin: 0;
}

.appointment-list-heading h2 {
  margin-top: 3px;
  color: #112342;
  font-size: 1.3rem;
}

.appointment-list-heading p {
  margin-top: 3px;
  color: #647690;
  font-size: 0.72rem;
}

.add-appointment-action {
  display: grid;
  justify-items: center;
  gap: 6px;
  margin-left: auto;
}

.add-appointment-action button {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 18px;
  color: #fff;
  border: 1px solid #0874df;
  border-radius: 7px;
  background: #0878e5;
  box-shadow: 0 6px 14px rgb(8 120 229 / 20%);
  font: inherit;
  font-size: 0.78rem;
  font-weight: 800;
  cursor: pointer;
}

.add-appointment-action button:hover,
.add-appointment-action button:focus-visible {
  border-color: #0565c6;
  outline: none;
  background: #056ed7;
}

.add-appointment-action small {
  color: #6d7d92;
  font-size: 0.61rem;
}

.appointment-list-toolbar {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(160px, 0.34fr) minmax(150px, 0.3fr) auto;
  gap: 9px;
  padding: 12px;
  border-bottom: 1px solid #e2eaf1;
}

.appointment-search,
.appointment-filter {
  position: relative;
  display: flex;
  min-width: 0;
  height: 43px;
  align-items: center;
  color: #58708e;
  border: 1px solid #d8e3ed;
  border-radius: 6px;
  background: #fff;
}

.appointment-search {
  gap: 10px;
  padding: 0 13px;
}

.appointment-search:focus-within,
.appointment-filter:focus-within {
  border-color: #1686cf;
  box-shadow: 0 0 0 3px rgb(22 134 207 / 12%);
}

.appointment-search input,
.appointment-filter select,
.appointment-status-control select {
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
  color: #8292a8;
}

.appointment-filter select {
  width: 100%;
  height: 100%;
  padding: 0 38px 0 13px;
  appearance: none;
  cursor: pointer;
}

.appointment-filter > svg {
  position: absolute;
  right: 12px;
  pointer-events: none;
}

.appointment-refresh-button {
  display: inline-flex;
  min-width: 104px;
  height: 43px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 16px;
  color: #096bd5;
  border: 1px solid #d7e8fb;
  border-radius: 6px;
  background: #edf5ff;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 750;
  cursor: pointer;
}

.appointment-refresh-button:hover,
.appointment-refresh-button:focus-visible {
  border-color: #9bc8f4;
  outline: none;
  background: #e1efff;
}

.appointment-table-wrap {
  width: 100%;
  overflow-x: auto;
}

.appointment-list-table {
  width: 100%;
  min-width: 870px;
  border-collapse: collapse;
  table-layout: fixed;
}

.appointment-list-table th,
.appointment-list-table td {
  padding: 10px 14px;
  text-align: left;
  vertical-align: middle;
}

.appointment-list-table th {
  color: #5f7088;
  background: #f2f6fa;
  font-size: 0.67rem;
  font-weight: 800;
  text-transform: uppercase;
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
  border-bottom: 1px solid #e5ebf1;
  transition: background-color 160ms ease;
}

.appointment-list-table tbody tr:not(.appointment-empty-row):hover {
  background: #f8fbfd;
}

.appointment-list-table tbody tr:last-child {
  border-bottom: 0;
}

.appointment-list-table td {
  color: #263c5c;
  font-size: 0.76rem;
}

.appointment-patient {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.appointment-patient :deep(.profile-avatar) {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  font-size: 0.66rem;
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
  color: #112342;
  font-size: 0.78rem;
}

.appointment-patient small {
  color: #718198;
  font-size: 0.64rem;
}

.appointment-status-control {
  display: grid;
  width: 158px;
  height: 34px;
  grid-template-columns: 8px minmax(88px, 1fr) 14px;
  align-items: center;
  gap: 7px;
  padding: 0 9px;
  color: #9b5c00;
  border: 1px solid #ffdda0;
  border-radius: 6px;
  background: #fff5df;
}

.appointment-status-control i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #f5a000;
}

.appointment-status-control select {
  width: 100%;
  height: 100%;
  overflow: visible;
  appearance: none;
  font-size: 0.68rem;
  font-weight: 800;
  white-space: nowrap;
  cursor: pointer;
}

.appointment-status-control > svg {
  pointer-events: none;
}

.appointment-status-control:focus-within {
  box-shadow: 0 0 0 3px rgb(23 137 210 / 12%);
}

.appointment-status-control.status-approved {
  color: #087c59;
  border-color: #bdebdc;
  background: #e8faf3;
}

.appointment-status-control.status-approved i {
  background: #13ad7d;
}

.appointment-status-control.status-completed {
  color: #0875bd;
  border-color: #c8e5fb;
  background: #eaf5ff;
}

.appointment-status-control.status-completed i {
  background: #1597e5;
}

.appointment-status-control.status-cancelled {
  color: #d72445;
  border-color: #ffcbd4;
  background: #fff0f3;
}

.appointment-status-control.status-cancelled i {
  background: #ef3c5d;
}

.appointment-empty-row td {
  height: 110px;
  color: #718198;
  text-align: center;
}

.appointment-list-footer {
  display: flex;
  min-height: 58px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 14px;
  color: #566d8a;
  border-top: 1px solid #e2eaf1;
  background: #fff;
  font-size: 0.7rem;
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
  color: #42607f;
  border: 1px solid #dce5ee;
  border-radius: 6px;
  background: #fff;
  font: inherit;
  font-weight: 750;
  cursor: pointer;
}

.appointment-pagination button:hover:not(:disabled),
.appointment-pagination button:focus-visible {
  border-color: #72b7e8;
  outline: none;
}

.appointment-pagination button.active {
  color: #fff;
  border-color: #0878cf;
  background: #0878cf;
}

.appointment-pagination button:disabled {
  color: #aab6c4;
  background: #f7f9fb;
  cursor: not-allowed;
}

:global(html[data-dashboard-theme="dark"]) .schedule-hero,
:global(html[data-dashboard-theme="dark"]) .schedule-settings-panel,
:global(html[data-dashboard-theme="dark"]) .schedule-calendar-panel,
:global(html[data-dashboard-theme="dark"]) .schedule-summary-card {
  color: #e8edf6;
  border-color: #344154;
  background: #1d2635;
}

:global(html[data-dashboard-theme="dark"]) .schedule-hero h1,
:global(html[data-dashboard-theme="dark"]) .schedule-section-heading h2,
:global(html[data-dashboard-theme="dark"]) .schedule-summary-card strong,
:global(html[data-dashboard-theme="dark"]) .schedule-calendar-heading h2 {
  color: #edf3fb;
}

:global(html[data-dashboard-theme="dark"]) .schedule-hero p,
:global(html[data-dashboard-theme="dark"]) .schedule-section-heading p,
:global(html[data-dashboard-theme="dark"]) .schedule-summary-card small,
:global(html[data-dashboard-theme="dark"]) .schedule-summary-card p,
:global(html[data-dashboard-theme="dark"]) .schedule-field,
:global(html[data-dashboard-theme="dark"]) .schedule-weekdays {
  color: #aebbd0;
}

:global(html[data-dashboard-theme="dark"]) .schedule-control,
:global(html[data-dashboard-theme="dark"]) .schedule-control :is(input, select),
:global(html[data-dashboard-theme="dark"]) .schedule-calendar-actions button,
:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day {
  color: #e7eef8;
  border-color: #3a4656;
  background: #111821;
}

:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day.available {
  color: #baf3dd;
  border-color: #276957;
  background: #173f38;
}

:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day.fully-booked {
  color: #ffc2cb;
  border-color: #7d3542;
  background: #4b2530;
}

:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day.selected {
  color: #fff;
  border-color: #18b8d0;
  background: #078da5;
}

:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day.unavailable,
:global(html[data-dashboard-theme="dark"]) .schedule-calendar-day.past {
  color: #69788d;
  border-color: #2c3748;
  background: #202a39;
}

:global(html[data-dashboard-theme="dark"]) .schedule-calendar-legend {
  color: #c9d4e3;
  background: #202b3b;
}

:global(html[data-dashboard-theme="dark"]) .clear-appointments-trigger {
  color: #ffb7c2;
  border-color: #7d3542;
  background: #321e28;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-panel,
:global(html[data-dashboard-theme="dark"]) .appointment-list-footer,
:global(html[data-dashboard-theme="dark"]) .appointment-search,
:global(html[data-dashboard-theme="dark"]) .appointment-filter,
:global(html[data-dashboard-theme="dark"]) .appointment-pagination button {
  color: #dbe6f3;
  border-color: #344154;
  background: #1d2635;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-heading {
  border-color: #344154;
  background: #202b3b;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-heading h2 {
  color: #edf3fb;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-heading p,
:global(html[data-dashboard-theme="dark"]) .add-appointment-action small {
  color: #9eacc0;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-toolbar,
:global(html[data-dashboard-theme="dark"]) .appointment-list-footer {
  border-color: #344154;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-table th {
  color: #aebbd0;
  background: #202b3b;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-table tbody tr {
  border-color: #344154;
}

:global(html[data-dashboard-theme="dark"])
  .appointment-list-table
  tbody
  tr:not(.appointment-empty-row):hover {
  background: #222e3e;
}

:global(html[data-dashboard-theme="dark"]) .appointment-list-table td,
:global(html[data-dashboard-theme="dark"]) .appointment-patient strong {
  color: #e5edf7;
}

:global(html[data-dashboard-theme="dark"]) .appointment-patient small,
:global(html[data-dashboard-theme="dark"]) .appointment-empty-row td {
  color: #9baac0;
}

:global(html[data-dashboard-theme="dark"]) .appointment-refresh-button {
  color: #8cc9ff;
  border-color: #345878;
  background: #1c344b;
}

:global(html[data-dashboard-theme="dark"]) .appointment-pagination button.active {
  color: #fff;
  border-color: #1597e5;
  background: #0878cf;
}

@media (max-width: 1180px) {
  .schedule-builder {
    grid-template-columns: 1fr;
  }

  .appointment-list-toolbar {
    grid-template-columns: minmax(260px, 1fr) repeat(2, minmax(150px, 0.42fr)) auto;
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
    font-size: 0.58rem;
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
    padding: 16px;
  }

  .appointment-list-heading > span {
    width: 46px;
    height: 46px;
    flex-basis: 46px;
  }

  .appointment-list-heading h2 {
    font-size: 1.08rem;
  }

  .appointment-search,
  .appointment-refresh-button {
    grid-column: auto;
  }

  .appointment-table-wrap {
    padding: 0 12px 12px;
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
    padding: 8px 12px;
    border: 1px solid #dfe8ef;
    border-radius: 7px;
    background: #fff;
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
    border-bottom: 1px solid #edf1f5;
  }

  .appointment-list-table td::before {
    content: attr(data-label);
    color: #6a7b92;
    font-size: 0.64rem;
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
    border-color: #344154;
    background: #1d2635;
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
