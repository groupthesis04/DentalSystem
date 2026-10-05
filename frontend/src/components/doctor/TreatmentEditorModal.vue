<script setup>
import {
  CalendarDays,
  Check,
  ChevronDown,
  CircleDollarSign,
  ClipboardPlus,
  FileText,
  Pill,
  Save,
  Stethoscope,
  UserRound,
} from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from "vue";

import AvailabilityDatePicker from "../AvailabilityDatePicker.vue";
import { calculateAge, formatDate } from "../../services/format";
import { availableSlotDates, futureOpenSlots } from "../../services/availability";
import AvatarBadge from "../AvatarBadge.vue";
import BaseModal from "../BaseModal.vue";

const props = defineProps({
  form: { type: Object, required: true },
  patient: { type: Object, required: true },
  records: { type: Array, default: () => [] },
  appointments: { type: Array, default: () => [] },
  availability: { type: Array, default: () => [] },
  doctor: { type: String, default: "" },
  procedures: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
  maxDate: { type: String, default: "" },
  allowFollowUpDate: { type: Boolean, default: false },
});
const emit = defineEmits(["close", "submit"]);
const servicePicker = ref(null);
const serviceTrigger = ref(null);
const servicePickerOpen = ref(false);
const serviceError = ref("");
const serviceListId = `treatment-services-${useId().replaceAll(":", "")}`;
const followUpDateError = ref("");
const availableFollowUpDates = computed(() =>
  availableSlotDates(futureOpenSlots(props.availability, props.doctor)),
);

const selectedServices = computed(() =>
  Array.isArray(props.form.procedures) ? props.form.procedures : [],
);
const availableServices = computed(() => [
  ...new Set([...props.procedures, ...selectedServices.value].filter(Boolean)),
]);
const serviceSummary = computed(() => {
  if (!selectedServices.value.length) {
    return availableServices.value.length ? "Select services" : "No services available";
  }
  if (selectedServices.value.length === 1) return selectedServices.value[0];
  return `${selectedServices.value[0]} +${selectedServices.value.length - 1} more`;
});

function toggleService(service) {
  const selected = selectedServices.value;
  props.form.procedures = selected.includes(service)
    ? selected.filter((item) => item !== service)
    : [...selected, service];
  if (props.form.procedures.length) serviceError.value = "";
}

function focusServiceOption(index) {
  const options = servicePicker.value?.querySelectorAll('[role="checkbox"]');
  options?.[index]?.focus();
}

function onServiceTriggerKeydown(event) {
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  event.preventDefault();
  servicePickerOpen.value = true;
  nextTick(() =>
    focusServiceOption(event.key === "ArrowDown" ? 0 : availableServices.value.length - 1),
  );
}

function onServicePickerKeydown(event) {
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  const options = [...(servicePicker.value?.querySelectorAll('[role="checkbox"]') || [])];
  const current = options.indexOf(document.activeElement);
  if (current < 0 || !options.length) return;
  event.preventDefault();
  const next =
    event.key === "Home"
      ? 0
      : event.key === "End"
        ? options.length - 1
        : (current + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
  options[next].focus();
}

function onOutsidePointerDown(event) {
  if (servicePickerOpen.value && !servicePicker.value?.contains(event.target)) {
    servicePickerOpen.value = false;
  }
}

function onServiceFocusOut(event) {
  if (!servicePicker.value?.contains(event.relatedTarget)) servicePickerOpen.value = false;
}

function onDocumentKeydown(event) {
  if (event.key !== "Escape" || !servicePickerOpen.value) return;
  event.preventDefault();
  event.stopPropagation();
  servicePickerOpen.value = false;
  serviceTrigger.value?.focus();
}

function submitForm() {
  if (!selectedServices.value.length) {
    serviceError.value = "Select at least one service.";
    servicePickerOpen.value = true;
    nextTick(() => serviceTrigger.value?.focus());
    return;
  }
  if (
    (!props.form.id || props.allowFollowUpDate) &&
    props.form.next_visit &&
    !availableFollowUpDates.value.includes(props.form.next_visit)
  ) {
    followUpDateError.value = "Choose a next-visit date with an available clinic schedule.";
    return;
  }
  followUpDateError.value = "";
  emit("submit");
}

onMounted(() => {
  document.addEventListener("pointerdown", onOutsidePointerDown);
  document.addEventListener("keydown", onDocumentKeydown, true);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onOutsidePointerDown);
  document.removeEventListener("keydown", onDocumentKeydown, true);
});

const patientAge = computed(() => {
  const age = props.patient.age ?? calculateAge(props.patient.birthdate);
  return age === "" || age === null || age === undefined ? "Not recorded" : `${age} years old`;
});
const lastVisit = computed(() => {
  const latestRecordDate = [...props.records]
    .map((record) => record.treatment_date)
    .filter(Boolean)
    .sort()
    .at(-1);
  return formatDate(props.patient.last_visit || latestRecordDate) || "-";
});
const appointmentDate = computed(() => {
  const latestAppointment = [...props.appointments]
    .filter((appointment) => appointment.date)
    .sort((a, b) =>
      `${b.date || ""} ${b.time || ""}`.localeCompare(`${a.date || ""} ${a.time || ""}`),
    )[0];
  return latestAppointment?.date ? formatDate(latestAppointment.date) : "No linked appointment";
});
const remainingBalance = computed(() => {
  const charged = Number(props.form.amount_charged || 0);
  const paid = Number(props.form.amount_paid || 0);
  if (!Number.isFinite(charged) || !Number.isFinite(paid)) return 0;
  return Math.max(0, charged - paid);
});
</script>

<template>
  <BaseModal
    :title="form.id ? 'Edit Treatment' : 'Add Treatment'"
    eyebrow="Treatment Record"
    size-class="patient-treatment-editor-dialog"
    @close="emit('close')"
  >
    <template #header-icon>
      <span class="treatment-modal-header-icon" aria-hidden="true">
        <ClipboardPlus :size="30" />
      </span>
    </template>
    <template #subtitle>
      <p class="treatment-modal-subtitle">
        Record the details of the treatment provided to the patient.
      </p>
    </template>

    <form class="treatment-editor-form" @submit.prevent="submitForm">
      <label class="hp-field" aria-hidden="true">
        Website
        <input v-model="form._website" tabindex="-1" autocomplete="off" />
      </label>

      <section class="treatment-patient-summary" aria-label="Selected patient summary">
        <div class="treatment-patient-identity">
          <AvatarBadge :name="patient.name" :image="patient.profile_image || ''" large />
          <span>
            <strong>{{ patient.name }}</strong>
            <small>Email: {{ patient.email || "Not recorded" }}</small>
          </span>
        </div>
        <div class="treatment-summary-item">
          <UserRound :size="28" aria-hidden="true" />
          <span
            ><small>Age</small><strong>{{ patientAge }}</strong></span
          >
        </div>
        <div class="treatment-summary-item">
          <Stethoscope :size="28" aria-hidden="true" />
          <span
            ><small>Last Visit</small><strong>{{ lastVisit }}</strong></span
          >
        </div>
        <div class="treatment-summary-item">
          <CalendarDays :size="28" aria-hidden="true" />
          <span
            ><small>Appointment Date</small><strong>{{ appointmentDate }}</strong></span
          >
        </div>
      </section>

      <section class="treatment-editor-section" aria-labelledby="treatment-details-title">
        <header>
          <Stethoscope :size="23" aria-hidden="true" />
          <h3 id="treatment-details-title">Treatment Details</h3>
        </header>

        <div class="treatment-main-grid">
          <label>
            <span>Treatment Date <b aria-hidden="true">*</b></span>
            <input v-model="form.treatment_date" type="date" :max="maxDate" required />
          </label>
          <div class="treatment-service-field">
            <span>Procedure / Services <b aria-hidden="true">*</b></span>
            <div
              ref="servicePicker"
              class="treatment-service-picker"
              @keydown="onServicePickerKeydown"
              @focusout="onServiceFocusOut"
            >
              <button
                ref="serviceTrigger"
                class="treatment-service-trigger"
                type="button"
                :aria-controls="serviceListId"
                :aria-expanded="servicePickerOpen"
                :aria-invalid="Boolean(serviceError)"
                :aria-describedby="serviceError ? `${serviceListId}-error` : undefined"
                :aria-label="`Procedure or services: ${serviceSummary}. Select one or more services`"
                @click="servicePickerOpen = !servicePickerOpen"
                @keydown="onServiceTriggerKeydown"
              >
                <span class="treatment-service-summary">{{ serviceSummary }}</span>
                <ChevronDown :size="17" aria-hidden="true" />
              </button>
              <div
                v-show="servicePickerOpen"
                :id="serviceListId"
                class="treatment-service-options"
                role="group"
                aria-label="Available services"
              >
                <button
                  v-for="service in availableServices"
                  :key="service"
                  class="treatment-service-option"
                  type="button"
                  role="checkbox"
                  :aria-checked="selectedServices.includes(service)"
                  @click="toggleService(service)"
                >
                  <span class="treatment-service-checkbox" aria-hidden="true">
                    <Check v-if="selectedServices.includes(service)" :size="13" />
                  </span>
                  <span>{{ service }}</span>
                </button>
                <p v-if="!availableServices.length" class="treatment-service-empty">
                  No active services available.
                </p>
              </div>
            </div>
            <small
              v-if="serviceError"
              :id="`${serviceListId}-error`"
              class="treatment-service-error"
              role="alert"
            >
              {{ serviceError }}
            </small>
          </div>
          <label>
            <span>Tooth Number(s)</span>
            <input v-model="form.tooth_numbers" maxlength="120" placeholder="e.g. 11, 12, 13" />
          </label>
        </div>

        <div class="treatment-clinical-grid">
          <label>
            <span class="treatment-field-heading">
              <FileText :size="21" aria-hidden="true" />
              Diagnosis / Clinical Findings <b aria-hidden="true">*</b>
            </span>
            <textarea
              v-model="form.diagnosis"
              rows="3"
              maxlength="700"
              placeholder="Enter the diagnosis, findings, or reason for treatment..."
              required
            ></textarea>
          </label>
          <label>
            <span class="treatment-field-heading">
              <Pill :size="21" aria-hidden="true" />
              Medical Instruction <small>Optional</small>
            </span>
            <textarea
              v-model="form.prescription"
              rows="3"
              maxlength="700"
              placeholder="Enter medical instruction (e.g., take medicine, avoid certain foods, etc.)..."
            ></textarea>
          </label>
        </div>

        <div
          v-if="!form.id || allowFollowUpDate"
          class="treatment-next-visit"
          :class="{ active: form.next_visit }"
        >
          <div class="treatment-next-visit-copy">
            <CalendarDays :size="21" aria-hidden="true" />
            <div>
              <strong>Next Visit <small>Optional</small></strong>
              <p>
                Choose an open clinic date. After saving the treatment, select a time to book the
                follow-up appointment.
              </p>
            </div>
          </div>
          <div class="treatment-next-visit-control">
            <AvailabilityDatePicker
              v-model="form.next_visit"
              :available-dates="availableFollowUpDates"
              placeholder="Select an available date"
              aria-label="Select an available next-visit date"
              clearable
              @update:model-value="followUpDateError = ''"
            />
            <small v-if="followUpDateError" class="treatment-next-visit-error" role="alert">
              {{ followUpDateError }}
            </small>
            <small v-else-if="!availableFollowUpDates.length" class="treatment-next-visit-hint">
              Add clinic availability before scheduling a next visit.
            </small>
          </div>
        </div>
      </section>

      <section
        class="treatment-editor-section treatment-billing-section"
        aria-labelledby="billing-title"
      >
        <header>
          <CircleDollarSign :size="23" aria-hidden="true" />
          <h3 id="billing-title">Billing Information</h3>
        </header>

        <div class="treatment-billing-grid">
          <label>
            <span>Amount Charged <b aria-hidden="true">*</b></span>
            <span class="treatment-money-input">
              <i>PHP</i>
              <input
                v-model="form.amount_charged"
                type="number"
                min="0"
                max="100000000"
                step="0.01"
                required
              />
            </span>
          </label>
          <label>
            <span>Amount Paid <b aria-hidden="true">*</b></span>
            <span class="treatment-money-input">
              <i>PHP</i>
              <input
                v-model="form.amount_paid"
                type="number"
                min="0"
                max="100000000"
                step="0.01"
                required
              />
            </span>
          </label>
          <label>
            <span>Remaining Balance</span>
            <span class="treatment-money-input readonly">
              <i>PHP</i>
              <input :value="Number(remainingBalance).toFixed(2)" readonly />
            </span>
          </label>
        </div>
      </section>

      <label class="treatment-remarks-field">
        <span class="treatment-field-heading">
          <FileText :size="21" aria-hidden="true" />
          Remarks <small>Optional</small>
        </span>
        <textarea
          v-model="form.remarks"
          rows="3"
          maxlength="500"
          placeholder="Enter treatment notes, patient response, and any additional remarks..."
        ></textarea>
        <small class="treatment-character-count">{{ form.remarks.length }}/500</small>
      </label>

      <footer class="treatment-editor-actions">
        <button class="secondary-button" type="button" :disabled="busy" @click="emit('close')">
          Cancel
        </button>
        <button class="primary-button" type="submit" :disabled="busy">
          <Save :size="18" aria-hidden="true" />
          {{ busy ? "Saving..." : form.id ? "Update Treatment" : "Save Treatment" }}
        </button>
      </footer>
    </form>
  </BaseModal>
</template>

<style scoped>
:global(.patient-treatment-editor-dialog) {
  width: min(1060px, calc(100% - 32px));
  border-color: #f4e7cd;
  border-radius: 8px;
  color: #171511;
}

:global(.patient-treatment-editor-dialog .crud-dialog-header) {
  padding: 20px 26px;
  border-bottom-color: #f4e7cd;
}

:global(.patient-treatment-editor-dialog .crud-dialog-header h2) {
  margin-top: 4px;
  color: #171511;
  font-size: 1.65rem;
  line-height: 1.08;
}

.treatment-modal-header-icon {
  display: inline-grid;
  width: 66px;
  height: 66px;
  flex: 0 0 66px;
  place-items: center;
  border-radius: 8px;
  background: #f4e7cd;
  color: #8a6526;
}

.treatment-modal-subtitle {
  margin: 6px 0 0;
  color: #706b61;
  font-size: 0.9rem;
  font-weight: 500;
}

.treatment-editor-form {
  display: grid;
  gap: 16px;
  padding: 14px 26px 0;
}

.treatment-patient-summary {
  display: grid;
  grid-template-columns: minmax(280px, 1.4fr) repeat(3, minmax(140px, 0.8fr));
  align-items: center;
  overflow: hidden;
  border: 1px solid #f4e7cd;
  border-radius: 8px;
  background: #f8f1e2;
  padding: 15px;
}

.treatment-patient-identity {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 14px;
  padding-right: 15px;
}

.treatment-patient-identity :deep(.profile-avatar.large) {
  width: 58px;
  height: 58px;
  flex: 0 0 58px;
  margin: 0;
  border: 0;
  background: #f4e7cd;
  color: #8a6526;
  font-size: 1.15rem;
}

.treatment-patient-identity > span,
.treatment-summary-item > span {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.treatment-patient-identity strong {
  overflow-wrap: anywhere;
  color: #171511;
  font-size: 0.96rem;
}

.treatment-patient-identity small {
  overflow: hidden;
  color: #706b61;
  font-size: 0.75rem;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.treatment-summary-item {
  display: flex;
  min-width: 0;
  min-height: 56px;
  align-items: center;
  gap: 10px;
  border-left: 1px solid #f4e7cd;
  padding: 0 14px;
  color: #8a6526;
}

.treatment-summary-item small {
  color: #706b61;
  font-size: 0.72rem;
  font-weight: 600;
}

.treatment-summary-item strong {
  overflow: hidden;
  color: #171511;
  font-size: 0.78rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.treatment-editor-section {
  display: grid;
  gap: 11px;
}

.treatment-editor-section > header {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #8a6526;
}

.treatment-editor-section h3 {
  margin: 0;
  color: #171511;
  font-size: 0.96rem;
}

.treatment-main-grid,
.treatment-billing-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.treatment-service-field {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: 7px;
  color: #171511;
  font-size: 0.78rem;
  font-weight: 800;
}

.treatment-service-field > span {
  min-height: 18px;
}

.treatment-service-field b {
  color: #e43955;
}

.treatment-service-picker {
  position: relative;
  min-width: 0;
}

.treatment-service-trigger {
  display: flex;
  width: 100%;
  min-height: 44px;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid #f4e7cd;
  border-radius: 7px;
  background: #ffffff;
  padding: 0 13px;
  color: #171511;
  cursor: pointer;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 650;
  text-align: left;
}

.treatment-service-trigger:focus-visible,
.treatment-service-trigger[aria-expanded="true"] {
  border-color: #8a6526;
  outline: 0;
  box-shadow: 0 0 0 3px rgba(138, 101, 38, 12%);
}

.treatment-service-trigger svg {
  flex: 0 0 auto;
}

.treatment-service-summary {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.treatment-service-options {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  left: 0;
  z-index: 5;
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid #f4e7cd;
  border-radius: 7px;
  background: #ffffff;
  padding: 5px;
  box-shadow: 0 12px 30px rgba(23, 21, 17, 16%);
}

.treatment-service-option {
  display: flex;
  width: 100%;
  min-height: 38px;
  align-items: center;
  gap: 9px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  padding: 7px 8px;
  color: #171511;
  cursor: pointer;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 600;
  overflow-wrap: anywhere;
  text-align: left;
}

.treatment-service-option:hover,
.treatment-service-option:focus-visible {
  outline: 0;
  background: #f8f1e2;
}

.treatment-service-checkbox {
  display: grid;
  width: 17px;
  height: 17px;
  flex: 0 0 17px;
  place-items: center;
  border: 1px solid #aaa194;
  border-radius: 4px;
  background: #ffffff;
  color: #ffffff;
}

.treatment-service-option[aria-checked="true"] .treatment-service-checkbox {
  border-color: #8a6526;
  background: #8a6526;
}

.treatment-service-empty {
  margin: 0;
  padding: 10px;
  color: #706b61;
  font-size: 0.78rem;
  font-weight: 500;
}

.treatment-service-error {
  color: #b4233d;
  font-size: 0.72rem;
  font-weight: 600;
}

.treatment-clinical-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.treatment-next-visit {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(230px, 320px);
  align-items: center;
  gap: 18px;
  border: 1px solid #f4e7cd;
  border-radius: 8px;
  background: #f8f1e2;
  padding: 13px 15px;
}

.treatment-next-visit.active {
  border-color: #dfc48a;
}

.treatment-next-visit-copy {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
}

.treatment-next-visit-copy > svg {
  flex: 0 0 auto;
  color: #8a6526;
}

.treatment-next-visit-copy strong {
  color: #171511;
  font-size: 0.8rem;
}

.treatment-next-visit-copy strong small {
  margin-left: 5px;
  color: #706b61;
  font-size: 0.72rem;
  font-weight: 600;
}

.treatment-next-visit-copy p {
  margin: 4px 0 0;
  color: #706b61;
  font-size: 0.74rem;
  font-weight: 500;
  line-height: 1.45;
}

.treatment-next-visit-control {
  display: grid;
  min-width: 0;
  gap: 5px;
  font-size: 0.8rem;
  font-weight: 650;
}

.treatment-next-visit-control :deep(.availability-date-trigger) {
  border-color: #f4e7cd;
  color: #171511;
}

.treatment-next-visit-control > small {
  font-size: 0.72rem;
  font-weight: 600;
}

.treatment-next-visit-hint {
  color: #706b61;
}

.treatment-next-visit-error {
  color: #b4233d;
}

.treatment-editor-form label {
  display: grid;
  min-width: 0;
  gap: 7px;
  color: #171511;
  font-size: 0.78rem;
  font-weight: 800;
}

.treatment-editor-form label > span:first-child {
  min-height: 18px;
}

.treatment-editor-form label b {
  color: #e43955;
}

.treatment-editor-form label small {
  color: #706b61;
  font-size: 0.72rem;
  font-weight: 600;
}

.treatment-editor-form :is(input, select, textarea) {
  width: 100%;
  min-width: 0;
  border: 1px solid #f4e7cd;
  border-radius: 7px;
  outline: 0;
  background: #ffffff;
  color: #171511;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 650;
}

.treatment-editor-form :is(input, select) {
  min-height: 44px;
  padding: 0 13px;
}

.treatment-editor-form textarea {
  resize: vertical;
  padding: 11px 13px;
  line-height: 1.45;
}

.treatment-editor-form :is(input, select, textarea):focus {
  border-color: #8a6526;
  box-shadow: 0 0 0 3px rgba(138, 101, 38, 12%);
}

.treatment-field-heading {
  display: flex;
  align-items: center;
  gap: 9px;
}

.treatment-field-heading svg {
  flex: 0 0 auto;
  color: #8a6526;
}

.treatment-billing-section {
  border-top: 1px solid #f4e7cd;
  padding-top: 14px;
}

.treatment-money-input {
  position: relative;
  display: flex;
  min-width: 0;
  align-items: center;
}

.treatment-money-input i {
  position: absolute;
  left: 13px;
  color: #171511;
  font-size: 0.74rem;
  font-style: normal;
  font-weight: 800;
  pointer-events: none;
}

.treatment-money-input input {
  padding-left: 51px;
}

.treatment-money-input.readonly input {
  background: #f8f1e2;
  color: #514b42;
}

.treatment-remarks-field {
  position: relative;
}

.treatment-remarks-field textarea {
  min-height: 88px;
  padding-bottom: 25px;
}

.treatment-character-count {
  position: absolute;
  right: 7px;
  bottom: 7px;
  color: #706b61;
  font-size: 0.7rem;
  font-weight: 500;
}

.treatment-editor-actions {
  position: sticky;
  bottom: 0;
  z-index: 2;
  display: flex;
  justify-content: flex-end;
  gap: 11px;
  margin: 0 -26px;
  border-top: 1px solid #f4e7cd;
  background: #ffffff;
  padding: 14px 26px 16px;
}

.treatment-editor-actions button {
  display: inline-flex;
  min-width: 150px;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.treatment-editor-actions .secondary-button {
  border-color: #e8dfd0;
  background: #f8f1e2;
  color: #171511;
}

.treatment-editor-actions .primary-button {
  border-color: #8a6526;
  background: #8a6526;
  color: #ffffff;
}

:global(html[data-dashboard-theme="dark"]) :is(.treatment-patient-summary) {
  border-color: var(--dashboard-border);
  background: #241e17;
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .treatment-patient-identity strong,
    .treatment-summary-item strong,
    .treatment-editor-section h3,
    .treatment-editor-form label
  ) {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .treatment-editor-form :is(input, select, textarea) {
  border-color: var(--dashboard-border);
  background: #241e17;
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .treatment-service-field {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"])
  :is(.treatment-service-trigger, .treatment-service-options) {
  border-color: var(--dashboard-border);
  background: #241e17;
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .treatment-service-option {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .treatment-service-option:is(:hover, :focus-visible) {
  background: #3f321e;
}

:global(html[data-dashboard-theme="dark"]) .treatment-next-visit {
  border-color: var(--dashboard-border);
  background: #241e17;
}

:global(html[data-dashboard-theme="dark"]) .treatment-next-visit-copy strong {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .treatment-editor-actions {
  border-color: var(--dashboard-border);
  background: #171511;
}

@media (max-width: 820px) {
  .treatment-patient-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .treatment-patient-identity {
    grid-column: 1 / -1;
    margin-bottom: 12px;
    padding: 0 0 13px;
    border-bottom: 1px solid #f4e7cd;
  }

  .treatment-summary-item {
    border-left: 0;
    padding: 0 8px;
  }
}

@media (max-width: 620px) {
  :global(.patient-treatment-editor-dialog) {
    width: calc(100% - 12px);
    max-height: calc(100dvh - 12px);
  }

  :global(.patient-treatment-editor-dialog .crud-dialog-shell) {
    max-height: calc(100dvh - 12px);
  }

  :global(.patient-treatment-editor-dialog .crud-dialog-header) {
    align-items: flex-start;
    padding: 15px;
  }

  :global(.patient-treatment-editor-dialog .crud-dialog-header h2) {
    font-size: 1.22rem;
  }

  .treatment-modal-header-icon {
    width: 48px;
    height: 48px;
    flex-basis: 48px;
  }

  .treatment-modal-subtitle {
    max-width: 210px;
    font-size: 0.76rem;
  }

  .treatment-editor-form {
    gap: 14px;
    padding: 14px 14px 0;
  }

  .treatment-patient-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 13px;
  }

  .treatment-summary-item:last-child {
    grid-column: 1 / -1;
  }

  .treatment-main-grid,
  .treatment-clinical-grid,
  .treatment-billing-grid {
    grid-template-columns: 1fr;
    gap: 13px;
  }

  .treatment-next-visit {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .treatment-editor-actions {
    margin: 0 -14px;
    padding: 12px 14px;
  }

  .treatment-editor-actions button {
    min-width: 0;
    flex: 1;
  }

  .treatment-editor-actions .primary-button {
    flex: 1.25;
    font-size: 0.78rem;
    white-space: nowrap;
  }
}
</style>
