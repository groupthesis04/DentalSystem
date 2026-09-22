<script setup>
import {
  CalendarCheck2,
  CalendarDays,
  CalendarPlus,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Info,
  Stethoscope,
  UserRound,
} from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";

import BaseModal from "../BaseModal.vue";
import { apiRequest } from "../../services/api";
import { formatDate, localDateIso } from "../../services/format";
import { validatedPayload } from "../../services/validation";

const props = defineProps({
  state: { type: Object, required: true },
  appointment: { type: Object, required: true },
  record: { type: Object, required: true },
  preferredDate: { type: String, required: true },
  doctor: { type: String, required: true },
});
const emit = defineEmits(["close", "back", "scheduled"]);

const today = localDateIso();
const now = new Date();
const currentTime = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
const busy = ref(false);
const errorMessage = ref("");
const scheduledAppointment = ref(null);
const form = reactive({
  service: "",
  time: "",
  _website: "",
});

const serviceOptions = computed(() =>
  [...props.state.services]
    .filter((service) => service?.name)
    .sort((a, b) => a.name.localeCompare(b.name)),
);
const availableTimes = computed(() =>
  props.state.availability
    .filter(
      (slot) =>
        !slot.booked &&
        slot.date === props.preferredDate &&
        (slot.date > today || slot.time > currentTime) &&
        String(slot.doctor || "").toLowerCase() === props.doctor.toLowerCase(),
    )
    .sort((a, b) => a.time.localeCompare(b.time)),
);
const selectedSlot = computed(
  () => availableTimes.value.find((slot) => slot.time === form.time) || null,
);
const modalTitle = computed(() =>
  scheduledAppointment.value ? "Appointment Completed!" : "Schedule Next Visit",
);
const modalEyebrow = computed(() =>
  scheduledAppointment.value ? "Follow-up Scheduled" : "Next Visit",
);

watch(
  serviceOptions,
  (services) => {
    if (services.some((service) => service.name === form.service)) return;
    form.service = services.some((service) => service.name === props.appointment.service)
      ? props.appointment.service
      : services[0]?.name || "";
  },
  { immediate: true },
);

function formatClock(value) {
  const [hours, minutes] = String(value || "00:00")
    .split(":")
    .map(Number);
  const suffix = hours >= 12 ? "PM" : "AM";
  return `${hours % 12 || 12}:${String(minutes || 0).padStart(2, "0")} ${suffix}`;
}

function formatLongDate(value) {
  if (!value) return "";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? formatDate(value)
    : date.toLocaleDateString(undefined, {
        month: "long",
        day: "numeric",
        year: "numeric",
      });
}

async function scheduleFollowUp() {
  errorMessage.value = "";
  if (!form.service) {
    errorMessage.value = "Choose the service or purpose for the next visit.";
    return;
  }
  if (!selectedSlot.value) {
    errorMessage.value = "Choose an available time slot for the next visit.";
    return;
  }

  busy.value = true;
  try {
    const payload = validatedPayload({
      patient_id: props.appointment.patient_id,
      doctor: props.doctor,
      service: form.service,
      date: props.preferredDate,
      time: form.time,
      notes: `Follow-up visit after ${props.appointment.service}.`,
      source: "follow_up",
      _website: form._website,
    });
    const data = await apiRequest("/api/appointments", { method: "POST", body: payload });
    scheduledAppointment.value = data.appointment;
    emit("scheduled", data);
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <BaseModal
    :title="modalTitle"
    :eyebrow="modalEyebrow"
    size-class="follow-up-dialog"
    @close="emit('close')"
  >
    <section v-if="scheduledAppointment" class="follow-up-success" aria-live="polite">
      <span class="follow-up-success-icon"><CheckCircle2 :size="32" aria-hidden="true" /></span>
      <div>
        <h3>Treatment saved and appointment completed</h3>
        <p>The patient's treatment record is secure and the next visit is now scheduled.</p>
      </div>

      <dl>
        <div>
          <dt><UserRound :size="17" aria-hidden="true" /> Patient</dt>
          <dd>{{ appointment.patient_name }}</dd>
        </div>
        <div>
          <dt><Stethoscope :size="17" aria-hidden="true" /> Service</dt>
          <dd>{{ scheduledAppointment.service }}</dd>
        </div>
        <div>
          <dt><CalendarDays :size="17" aria-hidden="true" /> Next Visit</dt>
          <dd>{{ formatLongDate(scheduledAppointment.date) }}</dd>
        </div>
        <div>
          <dt><Clock3 :size="17" aria-hidden="true" /> Time</dt>
          <dd>{{ formatClock(scheduledAppointment.time) }}</dd>
        </div>
      </dl>

      <p class="follow-up-success-note">
        <CalendarCheck2 :size="19" aria-hidden="true" />
        The follow-up appears in the clinic schedule and in the patient's upcoming visits.
      </p>

      <footer>
        <button class="primary-button" type="button" @click="emit('close')">OK</button>
      </footer>
    </section>

    <form v-else class="follow-up-form" @submit.prevent="scheduleFollowUp">
      <label class="hp-field" aria-hidden="true">
        Website
        <input v-model="form._website" tabindex="-1" autocomplete="off" />
      </label>

      <section class="follow-up-intro">
        <span><CalendarPlus :size="25" aria-hidden="true" /></span>
        <div>
          <h3>Choose the patient's follow-up slot</h3>
          <p>The treatment record is saved. Select an available time to finish scheduling.</p>
        </div>
      </section>

      <dl class="follow-up-patient-summary">
        <div>
          <dt><UserRound :size="16" aria-hidden="true" /> Patient</dt>
          <dd>{{ appointment.patient_name }}</dd>
          <small>{{ appointment.patient_email || "Patient record" }}</small>
        </div>
        <div>
          <dt><Stethoscope :size="16" aria-hidden="true" /> Dentist</dt>
          <dd>{{ doctor }}</dd>
        </div>
        <div>
          <dt><CalendarDays :size="16" aria-hidden="true" /> Preferred Date</dt>
          <dd>{{ formatLongDate(preferredDate) }}</dd>
        </div>
      </dl>

      <section class="follow-up-details" aria-labelledby="follow-up-details-title">
        <header>
          <div>
            <h3 id="follow-up-details-title">Appointment Details</h3>
            <p>Only services currently offered by the clinic can be selected.</p>
          </div>
          <button class="follow-up-change-date" type="button" @click="emit('back')">
            <CalendarDays :size="16" aria-hidden="true" />
            Change Date
          </button>
        </header>

        <div class="follow-up-fields">
          <label>
            <span>Service / Purpose <b aria-hidden="true">*</b></span>
            <span class="follow-up-select">
              <select v-model="form.service" required>
                <option value="">Select a service</option>
                <option
                  v-for="service in serviceOptions"
                  :key="service.id || service.name"
                  :value="service.name"
                >
                  {{ service.name }}
                </option>
              </select>
              <ChevronDown :size="16" aria-hidden="true" />
            </span>
          </label>
          <label>
            <span>Appointment Date</span>
            <span class="follow-up-date-display">
              <CalendarDays :size="17" aria-hidden="true" />
              {{ formatDate(preferredDate) }}
            </span>
          </label>
        </div>

        <div class="follow-up-slots-heading">
          <h3><Clock3 :size="18" aria-hidden="true" /> Available Time Slots</h3>
          <span>{{ availableTimes.length }} available</span>
        </div>

        <div v-if="availableTimes.length" class="follow-up-slots">
          <button
            v-for="slot in availableTimes"
            :key="slot.id"
            type="button"
            :class="{ active: form.time === slot.time }"
            :aria-pressed="form.time === slot.time"
            @click="form.time = slot.time"
          >
            {{ formatClock(slot.time) }}
            <small v-if="slot.pending_count">{{ slot.pending_count }} pending</small>
          </button>
        </div>
        <div v-else class="follow-up-empty-slots">
          <CalendarDays :size="25" aria-hidden="true" />
          <div>
            <strong>No available slots on {{ formatLongDate(preferredDate) }}</strong>
            <p>Go back and choose another Next Visit date from the treatment record.</p>
          </div>
        </div>

        <p v-if="selectedSlot?.pending_count" class="follow-up-slot-warning">
          <Info :size="18" aria-hidden="true" />
          This slot has {{ selectedSlot.pending_count }} pending online request(s). Scheduling this
          accepted follow-up will cancel those competing requests.
        </p>
        <p v-else class="follow-up-slot-note">
          <Info :size="18" aria-hidden="true" />
          Unavailable and fully booked clinic slots are hidden.
        </p>
      </section>

      <p v-if="errorMessage" class="follow-up-error" role="alert">{{ errorMessage }}</p>

      <footer class="follow-up-actions">
        <button class="secondary-button" type="button" :disabled="busy" @click="emit('back')">
          Back
        </button>
        <button class="primary-button" type="submit" :disabled="busy || !availableTimes.length">
          <CalendarPlus :size="18" aria-hidden="true" />
          {{ busy ? "Scheduling..." : "Schedule Follow-up" }}
        </button>
      </footer>
    </form>
  </BaseModal>
</template>

<style scoped>
:global(.crud-dialog.follow-up-dialog) {
  width: min(760px, calc(100% - 32px));
}

.follow-up-form {
  display: grid;
}

.follow-up-intro {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 16px 20px;
  border-bottom: 1px solid #dce8e5;
  background: #f0fbf7;
}

.follow-up-intro > span {
  display: grid;
  width: 48px;
  height: 48px;
  flex: 0 0 48px;
  place-items: center;
  border-radius: 7px;
  background: #d8f5e9;
  color: #07966d;
}

.follow-up-intro h3,
.follow-up-intro p,
.follow-up-details h3,
.follow-up-details p,
.follow-up-empty-slots p,
.follow-up-success h3,
.follow-up-success p {
  margin: 0;
}

.follow-up-intro h3 {
  color: #142b4d;
  font-size: 0.96rem;
}

.follow-up-intro p {
  margin-top: 3px;
  color: #647b98;
  font-size: 0.72rem;
}

.follow-up-patient-summary {
  display: grid;
  grid-template-columns: 1.35fr 1fr 1fr;
  gap: 10px;
  margin: 0;
  padding: 15px 20px;
  border-bottom: 1px solid #e1e9f1;
}

.follow-up-patient-summary > div {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #dce6ef;
  border-radius: 6px;
  background: #fff;
}

.follow-up-patient-summary dt,
.follow-up-success dt {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #6c8099;
  font-size: 0.61rem;
  font-weight: 800;
  text-transform: uppercase;
}

.follow-up-patient-summary dd,
.follow-up-success dd {
  overflow: hidden;
  margin: 5px 0 0;
  color: #172d4e;
  font-size: 0.73rem;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.follow-up-patient-summary small {
  display: block;
  overflow: hidden;
  margin-top: 3px;
  color: #73849a;
  font-size: 0.62rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.follow-up-details {
  padding: 17px 20px 4px;
}

.follow-up-details > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.follow-up-details h3 {
  color: #162d50;
  font-size: 0.88rem;
}

.follow-up-details header p {
  margin-top: 3px;
  color: #7789a0;
  font-size: 0.64rem;
}

.follow-up-change-date {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid #bddcf6;
  border-radius: 6px;
  background: #f2f8ff;
  color: #0875cf;
  font: inherit;
  font-size: 0.66rem;
  font-weight: 800;
  cursor: pointer;
}

.follow-up-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.follow-up-fields label {
  display: grid;
  gap: 6px;
  color: #263e60;
  font-size: 0.68rem;
  font-weight: 800;
}

.follow-up-fields b {
  color: #e33b55;
}

.follow-up-select,
.follow-up-date-display {
  position: relative;
  display: flex;
  min-height: 42px;
  align-items: center;
  border: 1px solid #d3e0ec;
  border-radius: 6px;
  background: #fff;
}

.follow-up-select select {
  width: 100%;
  height: 42px;
  appearance: none;
  border: 0;
  outline: 0;
  background: transparent;
  color: #233b5d;
  padding: 0 36px 0 12px;
  font: inherit;
  cursor: pointer;
}

.follow-up-select svg {
  position: absolute;
  right: 11px;
  color: #5f7896;
  pointer-events: none;
}

.follow-up-date-display {
  gap: 9px;
  padding: 0 12px;
  color: #233b5d;
}

.follow-up-slots-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 18px 0 10px;
}

.follow-up-slots-heading h3 {
  display: flex;
  align-items: center;
  gap: 7px;
}

.follow-up-slots-heading span {
  color: #71849b;
  font-size: 0.63rem;
  font-weight: 750;
}

.follow-up-slots {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.follow-up-slots button {
  display: grid;
  min-height: 42px;
  place-content: center;
  gap: 1px;
  border: 1px solid #cdddea;
  border-radius: 6px;
  background: #fff;
  color: #1d385e;
  font: inherit;
  font-size: 0.67rem;
  font-weight: 800;
  cursor: pointer;
}

.follow-up-slots button:hover,
.follow-up-slots button.active {
  border-color: #1183df;
  background: #eaf4ff;
  color: #086fc9;
}

.follow-up-slots button.active {
  box-shadow: 0 0 0 2px rgb(17 131 223 / 12%);
}

.follow-up-slots small {
  color: #bf7a08;
  font-size: 0.52rem;
}

.follow-up-empty-slots {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 86px;
  padding: 14px;
  border: 1px dashed #c9d9e7;
  border-radius: 7px;
  background: #f7fafc;
  color: #7589a0;
}

.follow-up-empty-slots strong {
  color: #294565;
  font-size: 0.71rem;
}

.follow-up-empty-slots p {
  margin-top: 4px;
  font-size: 0.64rem;
}

.follow-up-slot-note,
.follow-up-slot-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 13px 0 0;
  padding: 10px 12px;
  border: 1px solid #c8e5fb;
  border-radius: 6px;
  background: #edf8ff;
  color: #3e658b;
  font-size: 0.64rem;
  line-height: 1.45;
}

.follow-up-slot-warning {
  border-color: #f5d492;
  background: #fff7e6;
  color: #9d6506;
}

.follow-up-error {
  margin: 12px 20px 0;
  padding: 10px 12px;
  border: 1px solid #ffc7d0;
  border-radius: 6px;
  background: #fff1f3;
  color: #c52742;
  font-size: 0.68rem;
  font-weight: 750;
}

.follow-up-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 15px;
  padding: 14px 20px 18px;
  border-top: 1px solid #e1e9f1;
}

.follow-up-actions button {
  display: inline-flex;
  min-width: 150px;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.follow-up-success {
  display: grid;
  justify-items: center;
  padding: 28px 24px 22px;
  text-align: center;
}

.follow-up-success-icon {
  display: grid;
  width: 62px;
  height: 62px;
  place-items: center;
  border-radius: 50%;
  background: #dff8ed;
  color: #079669;
}

.follow-up-success > div h3 {
  margin-top: 13px;
  color: #152f51;
  font-size: 1rem;
}

.follow-up-success > div p {
  margin-top: 4px;
  color: #6d8098;
  font-size: 0.7rem;
}

.follow-up-success dl {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  margin: 20px 0 0;
}

.follow-up-success dl > div {
  padding: 11px 12px;
  border: 1px solid #dce6ef;
  border-radius: 6px;
  background: #fff;
  text-align: left;
}

.follow-up-success-note {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 14px !important;
  padding: 11px;
  border: 1px solid #c9eadc;
  border-radius: 6px;
  background: #effbf6;
  color: #267459;
  font-size: 0.66rem;
  font-weight: 700;
}

.follow-up-success footer {
  width: 100%;
  margin-top: 18px;
  padding-top: 15px;
  border-top: 1px solid #e1e9f1;
  text-align: right;
}

.follow-up-success footer button {
  min-width: 110px;
  min-height: 40px;
}

:global(html[data-dashboard-theme="dark"])
  :is(.follow-up-intro, .follow-up-slot-note, .follow-up-success-note) {
  border-color: var(--dashboard-border);
  background: #1b2b3e;
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .follow-up-patient-summary,
    .follow-up-actions,
    .follow-up-success footer,
    .follow-up-patient-summary > div,
    .follow-up-select,
    .follow-up-date-display,
    .follow-up-slots button,
    .follow-up-success dl > div,
    .follow-up-empty-slots
  ) {
  border-color: var(--dashboard-border);
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .follow-up-patient-summary > div,
    .follow-up-select,
    .follow-up-date-display,
    .follow-up-slots button,
    .follow-up-success dl > div,
    .follow-up-empty-slots
  ) {
  background: #172334;
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .follow-up-intro h3,
    .follow-up-details h3,
    .follow-up-patient-summary dd,
    .follow-up-select select,
    .follow-up-date-display,
    .follow-up-success h3,
    .follow-up-success dd,
    .follow-up-empty-slots strong
  ) {
  color: var(--dashboard-text);
}

@media (max-width: 640px) {
  .follow-up-intro,
  .follow-up-patient-summary,
  .follow-up-details,
  .follow-up-actions {
    padding-inline: 14px;
  }

  .follow-up-patient-summary,
  .follow-up-fields,
  .follow-up-success dl {
    grid-template-columns: 1fr;
  }

  .follow-up-details > header {
    align-items: flex-start;
  }

  .follow-up-slots {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .follow-up-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .follow-up-actions .primary-button {
    grid-row: 1;
  }
}
</style>
