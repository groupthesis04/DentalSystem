<script setup>
import { CalendarPlus, ChevronDown, LockKeyhole, Search, UserRound } from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

import BaseModal from "../BaseModal.vue";
import AvailabilityDatePicker from "../AvailabilityDatePicker.vue";
import { availableSlotDates, futureOpenSlots } from "../../services/availability";
import { apiRequest } from "../../services/api";
import { formatDate, localDateIso } from "../../services/format";
import { showToast } from "../../services/toast";
import { validatedPayload } from "../../services/validation";

const props = defineProps({
  state: { type: Object, required: true },
  doctor: { type: String, required: true },
});
const emit = defineEmits(["close", "created"]);

const patientType = ref("existing");
const patientQuery = ref("");
const selectedPatientId = ref("");
const patientPickerOpen = ref(false);
const patientSearchInput = ref(null);
const busy = ref(false);
const errorMessage = ref("");
const today = localDateIso();
let pickerCloseTimer = 0;

const appointment = reactive({
  service: "",
  date: "",
  time: "",
  notes: "",
  _website: "",
});
const newPatient = reactive({
  name: "",
  phone: "",
  email: "",
  birthdate: "",
  sex: "",
});

const patients = computed(() =>
  [...props.state.patients].sort((a, b) =>
    String(a.name || "").localeCompare(String(b.name || "")),
  ),
);
const patientResults = computed(() => {
  const query = patientQuery.value.trim().toLowerCase();
  return patients.value
    .filter((patient) => {
      if (!query) return true;
      return `${patient.name || ""} ${patient.email || ""} ${patient.phone || ""}`
        .toLowerCase()
        .includes(query);
    })
    .slice(0, 8);
});
const selectedPatient = computed(
  () => patients.value.find((patient) => patient.id === selectedPatientId.value) || null,
);
const clinicSlots = computed(() => futureOpenSlots(props.state.availability, props.doctor));
const availableDates = computed(() => availableSlotDates(clinicSlots.value));
const availableTimes = computed(() =>
  clinicSlots.value.filter((slot) => slot.date === appointment.date),
);
const selectedSlot = computed(
  () => availableTimes.value.find((slot) => slot.time === appointment.time) || null,
);

watch(
  () => appointment.date,
  () => {
    appointment.time = "";
  },
);
watch(clinicSlots, (slots) => {
  if (appointment.date && !slots.some((slot) => slot.date === appointment.date)) {
    appointment.date = "";
    appointment.time = "";
  } else if (
    appointment.date &&
    appointment.time &&
    !slots.some((slot) => slot.date === appointment.date && slot.time === appointment.time)
  ) {
    appointment.time = "";
  }
});

onMounted(() => {
  nextTick(() => patientSearchInput.value?.focus());
});
onBeforeUnmount(() => window.clearTimeout(pickerCloseTimer));

function formatClock(value) {
  const [hours, minutes] = String(value || "00:00")
    .split(":")
    .map(Number);
  const suffix = hours >= 12 ? "PM" : "AM";
  return `${hours % 12 || 12}:${String(minutes || 0).padStart(2, "0")} ${suffix}`;
}

function setPatientType(type) {
  patientType.value = type;
  errorMessage.value = "";
  if (type === "existing") {
    nextTick(() => patientSearchInput.value?.focus());
    return;
  }
  selectedPatientId.value = "";
  patientQuery.value = "";
  patientPickerOpen.value = false;
}

function openPatientPicker() {
  window.clearTimeout(pickerCloseTimer);
  patientPickerOpen.value = true;
}

function closePatientPicker() {
  pickerCloseTimer = window.setTimeout(() => {
    patientPickerOpen.value = false;
  }, 120);
}

function updatePatientQuery() {
  selectedPatientId.value = "";
  patientPickerOpen.value = true;
}

function selectPatient(patient) {
  window.clearTimeout(pickerCloseTimer);
  selectedPatientId.value = patient.id;
  patientQuery.value = patient.name;
  patientPickerOpen.value = false;
  errorMessage.value = "";
}

async function submitAppointment() {
  errorMessage.value = "";
  if (patientType.value === "existing" && !selectedPatient.value) {
    errorMessage.value = "Select an existing patient before saving the appointment.";
    patientSearchInput.value?.focus();
    return;
  }
  if (patientType.value === "new" && (!newPatient.name.trim() || !newPatient.phone.trim())) {
    errorMessage.value = "Enter the new patient's full name and contact number.";
    return;
  }
  if (!appointment.service || !appointment.date || !appointment.time) {
    errorMessage.value = "Choose a service, available date, and time.";
    return;
  }

  busy.value = true;
  try {
    const payload = validatedPayload({
      patient_id: patientType.value === "existing" ? selectedPatient.value.id : "",
      name: patientType.value === "new" ? newPatient.name : "",
      phone: patientType.value === "new" ? newPatient.phone : "",
      email: patientType.value === "new" ? newPatient.email : "",
      birthdate: patientType.value === "new" ? newPatient.birthdate : "",
      sex: patientType.value === "new" ? newPatient.sex : "",
      doctor: props.doctor,
      service: appointment.service,
      date: appointment.date,
      time: appointment.time,
      notes: appointment.notes,
      _website: appointment._website,
    });
    const data = await apiRequest("/api/appointments", { method: "POST", body: payload });
    showToast("Appointment added successfully.");
    emit("created", data);
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <BaseModal
    title="Add New Appointment"
    eyebrow="Walk-in or manual booking"
    size-class="manual-appointment-dialog"
    @close="emit('close')"
  >
    <form class="manual-appointment-form" @submit.prevent="submitAppointment">
      <label class="hp-field" aria-hidden="true">
        Website
        <input v-model="appointment._website" tabindex="-1" autocomplete="off" />
      </label>

      <section class="manual-form-section" aria-labelledby="patient-information-title">
        <header class="manual-section-heading">
          <span><UserRound :size="21" /></span>
          <div>
            <h3 id="patient-information-title">Patient Information</h3>
            <p>Choose an existing record or add a walk-in patient.</p>
          </div>
          <button
            v-if="patientType === 'existing'"
            class="manual-search-shortcut"
            type="button"
            @click="patientSearchInput?.focus()"
          >
            <Search :size="17" />
            Search Existing Patient
          </button>
        </header>

        <div class="manual-form-grid">
          <fieldset class="patient-type-control">
            <legend>Patient Type</legend>
            <div>
              <label :class="{ active: patientType === 'existing' }">
                <input
                  type="radio"
                  name="patient-type"
                  value="existing"
                  :checked="patientType === 'existing'"
                  @change="setPatientType('existing')"
                />
                Existing Patient
              </label>
              <label :class="{ active: patientType === 'new' }">
                <input
                  type="radio"
                  name="patient-type"
                  value="new"
                  :checked="patientType === 'new'"
                  @change="setPatientType('new')"
                />
                New Patient
              </label>
            </div>
          </fieldset>

          <label v-if="patientType === 'existing'" class="manual-field manual-patient-picker">
            <span>Full Name <b>*</b></span>
            <span class="manual-control">
              <Search :size="17" />
              <input
                ref="patientSearchInput"
                v-model="patientQuery"
                type="search"
                role="combobox"
                aria-controls="manual-patient-results"
                :aria-expanded="patientPickerOpen"
                autocomplete="off"
                placeholder="Search name, email, or phone"
                required
                @input="updatePatientQuery"
                @focus="openPatientPicker"
                @blur="closePatientPicker"
              />
            </span>
            <span
              v-if="patientPickerOpen"
              id="manual-patient-results"
              class="manual-patient-results"
              role="listbox"
            >
              <button
                v-for="patient in patientResults"
                :key="patient.id"
                type="button"
                role="option"
                :aria-selected="selectedPatientId === patient.id"
                @mousedown.prevent="selectPatient(patient)"
              >
                <strong>{{ patient.name }}</strong>
                <small>{{ patient.email || patient.phone || "No contact details" }}</small>
              </button>
              <small v-if="!patientResults.length" class="manual-no-patients">
                No matching patients found.
              </small>
            </span>
          </label>

          <label v-else class="manual-field">
            <span>Full Name <b>*</b></span>
            <span class="manual-control">
              <UserRound :size="17" />
              <input
                v-model="newPatient.name"
                type="text"
                maxlength="120"
                autocomplete="name"
                placeholder="Enter patient name"
                required
              />
            </span>
          </label>

          <label class="manual-field">
            <span>Contact Number <b v-if="patientType === 'new'">*</b></span>
            <span class="manual-control">
              <input
                v-if="patientType === 'new'"
                v-model="newPatient.phone"
                type="tel"
                maxlength="24"
                autocomplete="tel"
                placeholder="09XXXXXXXXX"
                required
              />
              <input
                v-else
                :value="selectedPatient?.phone || ''"
                type="text"
                placeholder="Select a patient"
                readonly
              />
            </span>
          </label>

          <label class="manual-field">
            <span>Email Address</span>
            <span class="manual-control">
              <input
                v-if="patientType === 'new'"
                v-model="newPatient.email"
                type="email"
                maxlength="254"
                autocomplete="email"
                placeholder="Enter email (optional)"
              />
              <input
                v-else
                :value="selectedPatient?.email || ''"
                type="text"
                placeholder="No email recorded"
                readonly
              />
            </span>
          </label>

          <label class="manual-field">
            <span>Date of Birth</span>
            <span class="manual-control">
              <input
                v-if="patientType === 'new'"
                v-model="newPatient.birthdate"
                type="date"
                :max="today"
              />
              <input
                v-else
                :value="selectedPatient?.birthdate ? formatDate(selectedPatient.birthdate) : ''"
                type="text"
                placeholder="Not recorded"
                readonly
              />
            </span>
          </label>

          <label class="manual-field">
            <span>Gender</span>
            <span class="manual-control select-control">
              <select v-if="patientType === 'new'" v-model="newPatient.sex">
                <option value="">Select gender</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
                <option value="prefer not to say">Prefer not to say</option>
              </select>
              <input
                v-else
                :value="selectedPatient?.sex || ''"
                type="text"
                placeholder="Not recorded"
                readonly
              />
              <ChevronDown v-if="patientType === 'new'" :size="16" aria-hidden="true" />
            </span>
          </label>
        </div>
      </section>

      <section class="manual-form-section" aria-labelledby="appointment-details-title">
        <header class="manual-section-heading">
          <span><CalendarPlus :size="21" /></span>
          <div>
            <h3 id="appointment-details-title">Appointment Details</h3>
            <p>Select an open clinic schedule for this visit.</p>
          </div>
        </header>

        <div class="manual-form-grid">
          <label class="manual-field">
            <span>Service <b>*</b></span>
            <span class="manual-control select-control">
              <select v-model="appointment.service" required>
                <option value="">Select a service</option>
                <option
                  v-for="service in state.services"
                  :key="service.id || service.name"
                  :value="service.name"
                >
                  {{ service.name }}
                </option>
              </select>
              <ChevronDown :size="16" aria-hidden="true" />
            </span>
          </label>

          <label class="manual-field">
            <span>Dentist <b>*</b></span>
            <span class="manual-control readonly-control">
              <input :value="doctor" type="text" readonly required />
              <LockKeyhole :size="15" aria-hidden="true" />
            </span>
            <small>Only the clinic dentist is assigned.</small>
          </label>

          <label class="manual-field">
            <span>Date <b>*</b></span>
            <AvailabilityDatePicker
              v-model="appointment.date"
              :available-dates="availableDates"
              placeholder="Select a date"
              aria-label="Select an available appointment date"
            />
          </label>

          <label class="manual-field">
            <span>Time <b>*</b></span>
            <span class="manual-control select-control">
              <select
                v-model="appointment.time"
                :disabled="!appointment.date || !availableTimes.length"
                required
              >
                <option value="">
                  {{ appointment.date ? "Select time" : "Choose a date first" }}
                </option>
                <option v-for="slot in availableTimes" :key="slot.id" :value="slot.time">
                  {{ formatClock(slot.time) }}
                  {{ slot.pending_count ? `(${slot.pending_count} pending)` : "" }}
                </option>
              </select>
              <ChevronDown :size="16" aria-hidden="true" />
            </span>
          </label>

          <p v-if="!availableDates.length" class="manual-slot-message">
            Add clinic availability before creating a manual appointment.
          </p>
          <p v-else-if="selectedSlot?.pending_count" class="manual-slot-message warning">
            This slot has {{ selectedSlot.pending_count }} pending online request(s). Saving this
            accepted appointment will cancel those competing requests.
          </p>

          <label class="manual-field manual-notes-field">
            <span>Notes</span>
            <textarea
              v-model="appointment.notes"
              rows="3"
              maxlength="300"
              placeholder="Add notes, symptoms, or concerns (optional)"
            ></textarea>
            <small>{{ appointment.notes.length }}/300</small>
          </label>
        </div>
      </section>

      <p v-if="errorMessage" class="manual-form-error" role="alert">{{ errorMessage }}</p>

      <footer class="manual-form-actions">
        <button class="secondary-button" type="button" :disabled="busy" @click="emit('close')">
          Cancel
        </button>
        <button class="primary-button" type="submit" :disabled="busy || !availableDates.length">
          <CalendarPlus :size="18" />
          {{ busy ? "Saving..." : "Save Appointment" }}
        </button>
      </footer>
    </form>
  </BaseModal>
</template>

<style scoped>
:global(.manual-appointment-dialog) {
  width: min(760px, calc(100% - 32px));
  border-color: #d7e3ed;
}

.manual-appointment-form {
  color: #14284b;
}

.manual-form-section {
  padding: 18px 24px 20px;
  border-bottom: 1px solid #e2e9f0;
}

.manual-section-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.manual-section-heading > span {
  display: grid;
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  place-items: center;
  color: #0879df;
  border-radius: 7px;
  background: #edf5ff;
}

.manual-section-heading > div {
  min-width: 0;
}

.manual-section-heading h3,
.manual-section-heading p {
  margin: 0;
}

.manual-section-heading h3 {
  color: #14284b;
  font-size: 1rem;
}

.manual-section-heading p {
  margin-top: 2px;
  color: #697b94;
  font-size: 0.72rem;
}

.manual-search-shortcut {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  gap: 7px;
  margin-left: auto;
  padding: 0 13px;
  color: #0874d3;
  border: 1px solid #bdddf8;
  border-radius: 6px;
  background: #eef6ff;
  font: inherit;
  font-size: 0.72rem;
  font-weight: 800;
  cursor: pointer;
}

.manual-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 13px 16px;
}

.patient-type-control {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.patient-type-control legend,
.manual-field > span:first-child {
  margin-bottom: 6px;
  color: #14284b;
  font-size: 0.72rem;
  font-weight: 800;
}

.patient-type-control > div {
  display: grid;
  height: 43px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  overflow: hidden;
  border: 1px solid #d6e1ec;
  border-radius: 6px;
  background: #fff;
}

.patient-type-control label {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: #546b88;
  font-size: 0.7rem;
  font-weight: 750;
  cursor: pointer;
}

.patient-type-control label + label {
  border-left: 1px solid #d6e1ec;
}

.patient-type-control label.active {
  color: #0871d4;
  background: #edf5ff;
}

.patient-type-control input {
  width: 15px;
  height: 15px;
  accent-color: #0878df;
}

.manual-field {
  position: relative;
  display: grid;
  min-width: 0;
  align-content: start;
}

.manual-field b {
  color: #e13b53;
}

.manual-control {
  position: relative;
  display: flex;
  height: 43px;
  align-items: center;
  gap: 9px;
  padding: 0 12px;
  color: #637894;
  border: 1px solid #d6e1ec;
  border-radius: 6px;
  background: #fff;
}

.manual-control:focus-within {
  border-color: #278cdc;
  box-shadow: 0 0 0 3px rgb(39 140 220 / 12%);
}

.manual-control :is(input, select) {
  width: 100%;
  min-width: 0;
  height: 100%;
  color: #223b5d;
  border: 0;
  outline: 0;
  background: transparent;
  font: inherit;
  font-size: 0.75rem;
}

.manual-control input::placeholder {
  color: #8797aa;
}

.manual-control input:read-only {
  color: #5c6f87;
}

.select-control select {
  padding-right: 22px;
  appearance: none;
  cursor: pointer;
}

.select-control > svg:last-child,
.readonly-control > svg:last-child {
  flex: 0 0 auto;
  pointer-events: none;
}

.manual-field > small {
  margin-top: 5px;
  color: #6e7f95;
  font-size: 0.63rem;
}

.manual-patient-picker {
  z-index: 1;
}

.manual-patient-results {
  position: absolute;
  z-index: 5;
  top: calc(100% + 5px);
  right: 0;
  left: 0;
  display: grid;
  max-height: 220px;
  overflow-y: auto;
  padding: 5px;
  border: 1px solid #cbdce9;
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 12px 28px rgb(23 61 92 / 18%);
}

.manual-patient-results button {
  display: grid;
  gap: 2px;
  padding: 9px 10px;
  color: #203958;
  border: 0;
  border-radius: 5px;
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.manual-patient-results button:hover,
.manual-patient-results button[aria-selected="true"] {
  background: #edf6ff;
}

.manual-patient-results strong {
  font-size: 0.72rem;
}

.manual-patient-results small,
.manual-no-patients {
  color: #74859b;
  font-size: 0.64rem;
}

.manual-no-patients {
  padding: 14px 10px;
  text-align: center;
}

.manual-slot-message {
  grid-column: 1 / -1;
  margin: 0;
  padding: 10px 12px;
  color: #176795;
  border: 1px solid #c9e8f8;
  border-radius: 6px;
  background: #eef9ff;
  font-size: 0.68rem;
  line-height: 1.45;
}

.manual-slot-message.warning {
  color: #8d5800;
  border-color: #f2d696;
  background: #fff8e8;
}

.manual-notes-field {
  grid-column: 1 / -1;
}

.manual-notes-field textarea {
  min-height: 86px;
  resize: vertical;
  padding: 11px 12px;
  color: #223b5d;
  border: 1px solid #d6e1ec;
  border-radius: 6px;
  outline: 0;
  background: #fff;
  font: inherit;
  font-size: 0.75rem;
  line-height: 1.45;
}

.manual-notes-field textarea:focus {
  border-color: #278cdc;
  box-shadow: 0 0 0 3px rgb(39 140 220 / 12%);
}

.manual-notes-field > small {
  justify-self: end;
}

.manual-form-error {
  margin: 14px 24px 0;
  padding: 10px 12px;
  color: #bd1d35;
  border: 1px solid #f5c3cd;
  border-radius: 6px;
  background: #fff1f3;
  font-size: 0.7rem;
}

.manual-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px 18px;
}

.manual-form-actions button {
  min-width: 150px;
}

:global(html[data-dashboard-theme="dark"]) .manual-appointment-form,
:global(html[data-dashboard-theme="dark"]) .manual-section-heading h3,
:global(html[data-dashboard-theme="dark"]) .patient-type-control legend,
:global(html[data-dashboard-theme="dark"]) .manual-field > span:first-child {
  color: #e7eef8;
}

:global(html[data-dashboard-theme="dark"]) .manual-form-section {
  border-color: #344154;
}

:global(html[data-dashboard-theme="dark"]) .manual-section-heading p,
:global(html[data-dashboard-theme="dark"]) .manual-field > small {
  color: #9eacc0;
}

:global(html[data-dashboard-theme="dark"]) .manual-control,
:global(html[data-dashboard-theme="dark"]) .patient-type-control > div,
:global(html[data-dashboard-theme="dark"]) .manual-patient-results,
:global(html[data-dashboard-theme="dark"]) .manual-notes-field textarea {
  color: #dce7f4;
  border-color: #3a485b;
  background: #111821;
}

:global(html[data-dashboard-theme="dark"]) .manual-control :is(input, select),
:global(html[data-dashboard-theme="dark"]) .manual-notes-field textarea,
:global(html[data-dashboard-theme="dark"]) .manual-patient-results button {
  color: #dce7f4;
}

:global(html[data-dashboard-theme="dark"]) .manual-patient-results button[aria-selected="true"],
:global(html[data-dashboard-theme="dark"]) .manual-patient-results button:hover,
:global(html[data-dashboard-theme="dark"]) .patient-type-control label.active {
  background: #1d3852;
}

@media (max-width: 680px) {
  :global(.manual-appointment-dialog) {
    width: calc(100% - 16px);
  }

  .manual-form-section {
    padding: 16px;
  }

  .manual-section-heading {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .manual-search-shortcut {
    width: 100%;
    justify-content: center;
    margin-left: 0;
  }

  .manual-form-grid {
    grid-template-columns: 1fr;
  }

  .manual-notes-field,
  .manual-slot-message {
    grid-column: auto;
  }

  .manual-form-error {
    margin: 12px 16px 0;
  }

  .manual-form-actions {
    padding: 14px 16px 16px;
  }

  .manual-form-actions button {
    min-width: 0;
    flex: 1;
  }
}

@media (max-width: 390px) {
  .patient-type-control > div {
    height: auto;
    grid-template-columns: 1fr;
  }

  .patient-type-control label {
    min-height: 40px;
  }

  .patient-type-control label + label {
    border-top: 1px solid #d6e1ec;
    border-left: 0;
  }
}
</style>
