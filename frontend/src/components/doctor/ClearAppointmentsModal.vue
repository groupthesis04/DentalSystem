<script setup>
import { CalendarDays, ChevronLeft, ChevronRight, CircleAlert, Trash2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import BaseModal from "../BaseModal.vue";
import { formatDate, localDateIso } from "../../services/format";

const props = defineProps({
  state: { type: Object, required: true },
  doctor: { type: String, required: true },
  initialMonth: { type: String, default: "" },
  busy: { type: Boolean, default: false },
});
const emit = defineEmits(["close", "clear"]);

const today = localDateIso();
const currentMonth = today.slice(0, 7);
const latestDate = new Date();
latestDate.setDate(latestDate.getDate() + 365);
const latestMonth = localDateIso(latestDate).slice(0, 7);
const month = ref(
  /^\d{4}-\d{2}$/.test(props.initialMonth) &&
    props.initialMonth >= currentMonth &&
    props.initialMonth <= latestMonth
    ? props.initialMonth
    : currentMonth,
);
const selectedDates = ref(new Set());
const notifyPatients = ref(true);
const message = ref(
  "We regret to inform you that your appointment on {date} has been cancelled. Please book a new schedule at your convenience.",
);

const monthLabel = computed(() => {
  const [year, monthNumber] = month.value.split("-").map(Number);
  return new Date(year, monthNumber - 1, 1).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
});
const canGoPrevious = computed(() => month.value > currentMonth);
const canGoNext = computed(() => month.value < latestMonth);
const doctorKey = computed(() => props.doctor.trim().toLowerCase());
const activeAppointments = computed(() =>
  props.state.appointments.filter(
    (item) =>
      item.doctor?.trim().toLowerCase() === doctorKey.value &&
      ["pending", "approved"].includes(item.status),
  ),
);
const clearableDates = computed(() => {
  const dates = new Set(
    props.state.availability
      .filter((slot) => slot.doctor?.trim().toLowerCase() === doctorKey.value)
      .map((slot) => slot.date),
  );
  for (const appointment of activeAppointments.value) dates.add(appointment.date);
  return dates;
});
const calendarCells = computed(() => {
  const [year, monthNumber] = month.value.split("-").map(Number);
  const firstWeekday = new Date(year, monthNumber - 1, 1).getDay();
  const dayCount = new Date(year, monthNumber, 0).getDate();
  const cellCount = Math.ceil((firstWeekday + dayCount) / 7) * 7;

  return Array.from({ length: cellCount }, (_, index) => {
    const dateValue = new Date(year, monthNumber - 1, 1 - firstWeekday + index);
    const date = localDateIso(dateValue);
    const current = date.slice(0, 7) === month.value;
    const slots = props.state.availability.filter(
      (slot) => slot.doctor?.trim().toLowerCase() === doctorKey.value && slot.date === date,
    );
    const appointments = activeAppointments.value.filter((item) => item.date === date);
    const fullyBooked =
      appointments.some((item) => item.status === "approved") ||
      (slots.length > 0 && slots.every((slot) => slot.booked));
    const clearable = clearableDates.value.has(date);
    return {
      key: date,
      date,
      day: dateValue.getDate(),
      current,
      clearable,
      fullyBooked,
      disabled: !current || date < today || !clearable,
    };
  });
});
const selectedDateList = computed(() => [...selectedDates.value].sort());
const selectedAppointmentCount = computed(
  () => activeAppointments.value.filter((item) => selectedDates.value.has(item.date)).length,
);
const selectedSlotCount = computed(
  () =>
    props.state.availability.filter(
      (slot) =>
        slot.doctor?.trim().toLowerCase() === doctorKey.value && selectedDates.value.has(slot.date),
    ).length,
);
const dialogTitle = computed(() => {
  if (selectedDates.value.size === 1) return "Clear One Date";
  if (selectedDates.value.size > 1) return "Clear Multiple Dates";
  return "Clear Appointment Dates";
});

watch(month, () => {
  selectedDates.value = new Set();
});

function changeMonth(offset) {
  const [year, monthNumber] = month.value.split("-").map(Number);
  const candidate = new Date(year, monthNumber - 1 + offset, 1);
  const value = `${candidate.getFullYear()}-${String(candidate.getMonth() + 1).padStart(2, "0")}`;
  if (value >= currentMonth && value <= latestMonth) month.value = value;
}

function toggleDate(cell) {
  if (cell.disabled) return;
  const next = new Set(selectedDates.value);
  if (next.has(cell.date)) next.delete(cell.date);
  else next.add(cell.date);
  selectedDates.value = next;
}

function submitClear() {
  if (!selectedDates.value.size || props.busy) return;
  emit("clear", {
    dates: selectedDateList.value.join(","),
    notify_patients: String(notifyPatients.value),
    message: notifyPatients.value ? message.value : "",
    _website: "",
  });
}
</script>

<template>
  <BaseModal
    :title="dialogTitle"
    eyebrow="Schedule cleanup"
    size-class="clear-appointments-dialog"
    @close="emit('close')"
  >
    <form class="clear-appointments-form" @submit.prevent="submitClear">
      <section class="clear-calendar-section">
        <header class="clear-calendar-heading">
          <button
            type="button"
            aria-label="Previous month"
            :disabled="!canGoPrevious"
            @click="changeMonth(-1)"
          >
            <ChevronLeft :size="21" />
          </button>
          <h3>{{ monthLabel }}</h3>
          <button
            type="button"
            aria-label="Next month"
            :disabled="!canGoNext"
            @click="changeMonth(1)"
          >
            <ChevronRight :size="21" />
          </button>
        </header>

        <div class="clear-calendar-weekdays" aria-hidden="true">
          <span>Sun</span><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span
          ><span>Fri</span><span>Sat</span>
        </div>
        <div class="clear-calendar-grid" role="group" aria-label="Dates to clear">
          <button
            v-for="cell in calendarCells"
            :key="cell.key"
            type="button"
            :class="{
              selected: selectedDates.has(cell.date),
              available: cell.clearable && !cell.fullyBooked,
              'fully-booked': cell.fullyBooked,
              unavailable: !cell.current || !cell.clearable,
            }"
            :disabled="cell.disabled"
            :aria-label="formatDate(cell.date)"
            :aria-pressed="selectedDates.has(cell.date)"
            @click="toggleDate(cell)"
          >
            <span>{{ cell.day }}</span>
            <i v-if="selectedDates.has(cell.date)" aria-hidden="true">&#10003;</i>
          </button>
        </div>

        <div class="clear-calendar-legend" aria-label="Calendar status legend">
          <span><i class="selected"></i>Selected</span>
          <span><i class="available"></i>Available</span>
          <span><i class="fully-booked"></i>Fully Booked</span>
          <span><i class="unavailable"></i>Unavailable</span>
        </div>
      </section>

      <section class="clear-options-section">
        <div class="clear-selection-summary" aria-live="polite">
          <span><CalendarDays :size="25" /></span>
          <div>
            <strong>{{ selectedDates.size }} date(s) selected</strong>
            <p v-if="selectedDateList.length">
              {{ selectedDateList.map(formatDate).join(", ") }}
            </p>
            <p v-else>Select one or more highlighted schedule dates.</p>
            <small>
              {{ selectedAppointmentCount }} active appointment(s) and {{ selectedSlotCount }} time
              slot(s)
            </small>
          </div>
        </div>

        <div class="clear-warning">
          <CircleAlert :size="26" />
          <div>
            <strong>This action will:</strong>
            <ul>
              <li>Cancel active appointments on the selected dates</li>
              <li>Remove those dates and time slots from availability</li>
              <li>Keep completed appointments in the clinic history</li>
            </ul>
          </div>
        </div>

        <label class="clear-notify-control">
          <span>
            <strong>Notify Patients</strong>
            <small>Send a cancellation notification to affected patients.</small>
          </span>
          <input v-model="notifyPatients" type="checkbox" role="switch" />
          <i aria-hidden="true"></i>
        </label>

        <label class="clear-message-field">
          Message (optional)
          <textarea
            v-model="message"
            rows="5"
            maxlength="200"
            :disabled="!notifyPatients"
            placeholder="Write a short cancellation message..."
          ></textarea>
          <small>{{ message.length }}/200</small>
        </label>

        <div class="clear-dialog-actions">
          <button class="secondary-button" type="button" :disabled="busy" @click="emit('close')">
            Cancel
          </button>
          <button
            class="clear-confirm-button"
            type="submit"
            :disabled="!selectedDates.size || busy"
          >
            <Trash2 :size="18" />
            {{ busy ? "Clearing..." : "Clear Appointments" }}
          </button>
        </div>
      </section>
    </form>
  </BaseModal>
</template>

<style scoped>
:global(.clear-appointments-dialog) {
  width: min(960px, calc(100% - 32px));
  border-color: #d6e3ed;
}

.clear-appointments-form {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(320px, 0.88fr);
}

.clear-calendar-section,
.clear-options-section {
  min-width: 0;
  padding: 18px 20px 20px;
}

.clear-calendar-section {
  border-right: 1px solid #e0e8ef;
}

.clear-options-section {
  display: grid;
  align-content: start;
  gap: 14px;
}

.clear-calendar-heading {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) 44px;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.clear-calendar-heading h3 {
  margin: 0;
  color: #14284b;
  font-size: 1.25rem;
  text-align: center;
}

.clear-calendar-heading button {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  color: #173052;
  border: 1px solid #d5e1ec;
  border-radius: 7px;
  background: #fff;
  cursor: pointer;
}

.clear-calendar-heading button:disabled {
  cursor: default;
  opacity: 0.35;
}

.clear-calendar-weekdays,
.clear-calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 7px;
}

.clear-calendar-weekdays {
  margin-bottom: 8px;
  color: #536987;
  font-size: 0.69rem;
  font-weight: 800;
  text-align: center;
  text-transform: uppercase;
}

.clear-calendar-grid button {
  position: relative;
  display: grid;
  min-width: 0;
  min-height: 54px;
  place-items: center;
  color: #172c4d;
  border: 1px solid #d5e1ec;
  border-radius: 7px;
  background: #fff;
  font-size: 0.78rem;
  font-weight: 800;
  cursor: pointer;
}

.clear-calendar-grid button.available {
  border-color: #b7ddcf;
  background: #edf9f5;
}

.clear-calendar-grid button.fully-booked {
  color: #c9273e;
  border-color: #f5c6cf;
  background: #ffe9ed;
}

.clear-calendar-grid button.selected {
  color: #0757c5;
  border-color: #4b9af1;
  background: #d9ecff;
  box-shadow: inset 0 0 0 1px #8fc4fa;
}

.clear-calendar-grid button.unavailable {
  color: #aeb9c8;
  border-color: #edf1f5;
  background: #f3f6f9;
}

.clear-calendar-grid button:disabled {
  cursor: default;
}

.clear-calendar-grid button i {
  position: absolute;
  right: 5px;
  bottom: 5px;
  display: grid;
  width: 19px;
  height: 19px;
  place-items: center;
  color: #fff;
  border-radius: 50%;
  background: #0876e8;
  font-size: 0.66rem;
  font-style: normal;
}

.clear-calendar-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 22px;
  margin-top: 18px;
  padding-top: 16px;
  color: #2a4161;
  border-top: 1px solid #e1e9f0;
  font-size: 0.7rem;
  font-weight: 700;
}

.clear-calendar-legend span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.clear-calendar-legend i {
  width: 18px;
  height: 18px;
  border: 1px solid #bfd0df;
  border-radius: 5px;
}

.clear-calendar-legend i.selected {
  border-color: #0876e8;
  background: #0876e8;
}

.clear-calendar-legend i.available {
  border-color: #9bd8c1;
  background: #dff5ed;
}

.clear-calendar-legend i.fully-booked {
  border-color: #ff98aa;
  background: #ffb8c5;
}

.clear-calendar-legend i.unavailable {
  border-color: #d9e1e9;
  background: #dfe6ed;
}

.clear-selection-summary,
.clear-warning {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  align-items: start;
  gap: 12px;
  padding: 14px;
  border-radius: 8px;
}

.clear-selection-summary {
  color: #1b4d8d;
  background: #edf6ff;
}

.clear-selection-summary > span {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border-radius: 8px;
  background: #dceeff;
}

.clear-selection-summary strong,
.clear-warning strong {
  color: #152b4d;
  font-size: 0.9rem;
}

.clear-selection-summary p,
.clear-selection-summary small {
  display: block;
  margin: 4px 0 0;
  overflow-wrap: anywhere;
  color: #506783;
  font-size: 0.7rem;
  line-height: 1.45;
}

.clear-selection-summary small {
  color: #29639d;
  font-weight: 700;
}

.clear-warning {
  grid-template-columns: 28px minmax(0, 1fr);
  color: #d71935;
  background: #fff0f2;
}

.clear-warning strong {
  color: #d71935;
}

.clear-warning ul {
  display: grid;
  gap: 5px;
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 0.72rem;
  line-height: 1.4;
}

.clear-notify-control {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  cursor: pointer;
}

.clear-notify-control > span {
  display: grid;
  gap: 3px;
}

.clear-notify-control strong {
  color: #172c4d;
  font-size: 0.82rem;
}

.clear-notify-control small {
  color: #60728a;
  font-size: 0.68rem;
}

.clear-notify-control input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.clear-notify-control > i {
  position: relative;
  width: 46px;
  height: 26px;
  flex: 0 0 46px;
  border-radius: 13px;
  background: #cbd5df;
  transition: background 140ms ease;
}

.clear-notify-control > i::after {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 4px rgb(20 43 77 / 22%);
  content: "";
  transition: transform 140ms ease;
}

.clear-notify-control input:checked + i {
  background: #0876e8;
}

.clear-notify-control input:checked + i::after {
  transform: translateX(20px);
}

.clear-notify-control input:focus-visible + i {
  outline: 3px solid rgb(8 118 232 / 20%);
  outline-offset: 2px;
}

.clear-message-field {
  position: relative;
  display: grid;
  gap: 7px;
  color: #172c4d;
  font-size: 0.76rem;
  font-weight: 750;
}

.clear-message-field textarea {
  min-height: 126px;
  resize: vertical;
  padding: 12px;
  color: #283f60;
  border: 1px solid #cfdae5;
  border-radius: 7px;
  background: #fff;
  font: inherit;
  font-weight: 500;
  line-height: 1.5;
}

.clear-message-field textarea:disabled {
  color: #8b98a8;
  background: #f2f5f8;
}

.clear-message-field > small {
  position: absolute;
  right: 10px;
  bottom: 8px;
  color: #6a7d94;
  font-size: 0.65rem;
  font-weight: 600;
}

.clear-dialog-actions {
  display: grid;
  grid-template-columns: minmax(120px, 0.7fr) minmax(190px, 1.3fr);
  gap: 10px;
  margin-top: auto;
  padding-top: 2px;
}

.clear-dialog-actions button {
  min-height: 46px;
}

.clear-confirm-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  border: 1px solid #e31d33;
  border-radius: 7px;
  background: #e51e35;
  font-size: 0.78rem;
  font-weight: 800;
  cursor: pointer;
}

.clear-confirm-button:hover:not(:disabled),
.clear-confirm-button:focus-visible {
  border-color: #bd1024;
  outline: none;
  background: #c9162b;
}

.clear-confirm-button:disabled {
  cursor: default;
  opacity: 0.48;
}

:global(html[data-dashboard-theme="dark"]) .clear-calendar-section,
:global(html[data-dashboard-theme="dark"]) .clear-options-section {
  color: #d9e8f5;
  background: #132235;
}

:global(html[data-dashboard-theme="dark"]) .clear-calendar-heading h3,
:global(html[data-dashboard-theme="dark"]) .clear-notify-control strong,
:global(html[data-dashboard-theme="dark"]) .clear-message-field {
  color: #e6f1fb;
}

@media (max-width: 760px) {
  :global(.clear-appointments-dialog) {
    width: calc(100% - 16px);
  }

  .clear-appointments-form {
    grid-template-columns: 1fr;
  }

  .clear-calendar-section {
    border-right: 0;
    border-bottom: 1px solid #e0e8ef;
  }
}

@media (max-width: 430px) {
  .clear-calendar-section,
  .clear-options-section {
    padding: 14px;
  }

  .clear-calendar-grid,
  .clear-calendar-weekdays {
    gap: 4px;
  }

  .clear-calendar-grid button {
    min-height: 44px;
  }

  .clear-calendar-grid button i {
    right: 3px;
    bottom: 3px;
    width: 16px;
    height: 16px;
    font-size: 0.56rem;
  }

  .clear-dialog-actions {
    grid-template-columns: 1fr;
  }
}
</style>
