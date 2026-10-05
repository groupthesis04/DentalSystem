<script setup>
import {
  CalendarCheck2,
  Check,
  ChevronDown,
  CircleDollarSign,
  ClipboardPlus,
  FileText,
  Stethoscope,
  UserRound,
} from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, useId, watch } from "vue";

import AvailabilityDatePicker from "../AvailabilityDatePicker.vue";
import BaseModal from "../BaseModal.vue";
import { availableSlotDates, futureOpenSlots } from "../../services/availability";
import { apiRequest } from "../../services/api";
import {
  appointmentService,
  appointmentServices,
  formatDate,
  formatMoney,
  localDateIso,
} from "../../services/format";
import { validatedPayload } from "../../services/validation";

const props = defineProps({
  appointment: { type: Object, required: true },
  existingRecord: { type: Object, default: null },
  availability: { type: Array, default: () => [] },
  services: { type: Array, default: () => [] },
  doctor: { type: String, default: "" },
});
const emit = defineEmits(["close", "completed", "follow-up"]);

const today = localDateIso();
const busy = ref(false);
const errorMessage = ref("");
const serviceError = ref("");
const servicePicker = ref(null);
const serviceTrigger = ref(null);
const servicePickerOpen = ref(false);
const serviceListId = `completion-services-${useId().replaceAll(":", "")}`;
const form = reactive({
  appointment_id: "",
  patient_id: "",
  treatment_date: today,
  tooth_numbers: "",
  procedures: [],
  procedure: "",
  diagnosis: "",
  prescription: "",
  amount_charged: "0.00",
  amount_paid: "0.00",
  remarks: "",
  next_visit: "",
  _website: "",
});

const modalTitle = computed(() =>
  props.existingRecord ? "Review Treatment Record" : "Complete Appointment",
);
const submitLabel = computed(() => {
  if (form.next_visit) {
    return props.existingRecord ? "Update Record & Continue" : "Save Record & Continue";
  }
  return props.existingRecord ? "Update Record & Complete" : "Save Record & Complete";
});
const remainingBalance = computed(() => {
  const charged = Number(form.amount_charged || 0);
  const paid = Number(form.amount_paid || 0);
  if (!Number.isFinite(charged) || !Number.isFinite(paid)) return 0;
  return Math.max(0, charged - paid);
});
const followUpSlots = computed(() =>
  futureOpenSlots(props.availability, props.doctor || props.appointment.doctor),
);
const availableFollowUpDates = computed(() => availableSlotDates(followUpSlots.value));
const selectedServices = computed(() => (Array.isArray(form.procedures) ? form.procedures : []));
const availableServices = computed(() => [
  ...new Set([...props.services, ...selectedServices.value].filter(Boolean)),
]);
const serviceSummary = computed(() => {
  if (!selectedServices.value.length) {
    return availableServices.value.length ? "Select services" : "No services available";
  }
  if (selectedServices.value.length === 1) return selectedServices.value[0];
  return `${selectedServices.value[0]} +${selectedServices.value.length - 1} more`;
});

function initialServices(record) {
  const stored = Array.isArray(record?.procedures) ? record.procedures : [];
  const names = stored.length
    ? stored
    : record?.procedure || record?.treatment
      ? [record.procedure || record.treatment]
      : appointmentServices(props.appointment);
  return [...new Set(names.map((name) => String(name || "").trim()).filter(Boolean))];
}

function toggleService(service) {
  form.procedures = selectedServices.value.includes(service)
    ? selectedServices.value.filter((name) => name !== service)
    : [...selectedServices.value, service];
  if (form.procedures.length) serviceError.value = "";
}

function focusServiceOption(index) {
  servicePicker.value?.querySelectorAll('[role="checkbox"]')?.[index]?.focus();
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

function onServiceFocusOut(event) {
  if (!servicePicker.value?.contains(event.relatedTarget)) servicePickerOpen.value = false;
}

function onOutsidePointerDown(event) {
  if (servicePickerOpen.value && !servicePicker.value?.contains(event.target)) {
    servicePickerOpen.value = false;
  }
}

function onDocumentKeydown(event) {
  if (event.key !== "Escape" || !servicePickerOpen.value) return;
  event.preventDefault();
  event.stopPropagation();
  servicePickerOpen.value = false;
  serviceTrigger.value?.focus();
}

onMounted(() => {
  document.addEventListener("pointerdown", onOutsidePointerDown);
  document.addEventListener("keydown", onDocumentKeydown, true);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onOutsidePointerDown);
  document.removeEventListener("keydown", onDocumentKeydown, true);
});

function moneyInput(value) {
  const amount = Number(value || 0);
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00";
}

function hydrateForm() {
  const record = props.existingRecord;
  const procedures = initialServices(record);
  Object.assign(form, {
    appointment_id: props.appointment.id || "",
    patient_id: props.appointment.patient_id || record?.patient_id || "",
    treatment_date:
      record?.treatment_date ||
      (props.appointment.date && props.appointment.date <= today ? props.appointment.date : today),
    tooth_numbers: record?.tooth_numbers || "",
    procedures,
    procedure: procedures[0] || "",
    diagnosis: record?.diagnosis || "",
    prescription: record?.prescription || "",
    amount_charged: moneyInput(record?.amount_charged),
    amount_paid: moneyInput(record?.amount_paid),
    remarks: record?.remarks || record?.notes || "",
    next_visit: record?.next_visit || "",
    _website: "",
  });
  errorMessage.value = "";
  serviceError.value = "";
  servicePickerOpen.value = false;
}

watch([() => props.appointment, () => props.existingRecord], hydrateForm, { immediate: true });

async function submitTreatmentRecord() {
  errorMessage.value = "";
  serviceError.value = "";
  const procedures = [
    ...new Set(selectedServices.value.map((name) => String(name || "").trim()).filter(Boolean)),
  ];
  if (!procedures.length) {
    serviceError.value = "Select at least one service.";
    servicePickerOpen.value = true;
    nextTick(() => serviceTrigger.value?.focus());
    return;
  }
  if (!form.diagnosis.trim()) {
    errorMessage.value = "Enter the diagnosis or clinical findings before completing the visit.";
    return;
  }
  if (form.next_visit && !availableFollowUpDates.value.includes(form.next_visit)) {
    errorMessage.value = "Choose a next-visit date that has an open clinic schedule.";
    return;
  }

  busy.value = true;
  try {
    const payload = validatedPayload({
      ...form,
      procedures,
      procedure: procedures[0],
      id: props.existingRecord?.id || undefined,
      treatment: procedures[0],
      schedule_follow_up: Boolean(form.next_visit),
    });
    const data = await apiRequest("/api/records", {
      method: props.existingRecord ? "PATCH" : "POST",
      body: payload,
    });
    if (form.next_visit) {
      emit("follow-up", { record: data.record, date: form.next_visit });
    } else {
      emit("completed", data.record);
    }
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
    eyebrow="Treatment Record Required"
    size-class="complete-appointment-dialog"
    @close="emit('close')"
  >
    <form class="completion-record-form" @submit.prevent="submitTreatmentRecord">
      <label class="hp-field" aria-hidden="true">
        Website
        <input v-model="form._website" tabindex="-1" autocomplete="off" />
      </label>

      <section class="completion-record-intro">
        <span><ClipboardPlus :size="24" aria-hidden="true" /></span>
        <div>
          <h3>Add the patient's treatment record</h3>
          <p>The appointment will be marked completed only after this record is saved.</p>
        </div>
      </section>

      <dl class="completion-appointment-summary">
        <div>
          <dt><UserRound :size="16" aria-hidden="true" /> Patient</dt>
          <dd>{{ appointment.patient_name || "Patient" }}</dd>
        </div>
        <div>
          <dt><Stethoscope :size="16" aria-hidden="true" /> Service</dt>
          <dd>{{ appointmentService(appointment) }}</dd>
        </div>
        <div>
          <dt><CalendarCheck2 :size="16" aria-hidden="true" /> Appointment</dt>
          <dd>{{ formatDate(appointment.date) }} at {{ appointment.time }}</dd>
        </div>
        <div>
          <dt><UserRound :size="16" aria-hidden="true" /> Dentist</dt>
          <dd>{{ appointment.doctor || "Clinic dentist" }}</dd>
        </div>
      </dl>

      <section class="completion-form-section" aria-labelledby="clinical-details-title">
        <header>
          <FileText :size="19" aria-hidden="true" />
          <h3 id="clinical-details-title">Clinical Details</h3>
        </header>
        <div class="completion-field-grid">
          <label>
            <span>Treatment Date <b aria-hidden="true">*</b></span>
            <input v-model="form.treatment_date" type="date" :max="today" required />
          </label>
          <label>
            <span>Tooth Number(s) <small>Optional</small></span>
            <input v-model="form.tooth_numbers" maxlength="120" placeholder="Example: 11, 12, 13" />
          </label>
          <div class="completion-service-field wide-field">
            <span>Procedure / Services <b aria-hidden="true">*</b></span>
            <div
              ref="servicePicker"
              class="completion-service-picker"
              @keydown="onServicePickerKeydown"
              @focusout="onServiceFocusOut"
            >
              <button
                ref="serviceTrigger"
                class="completion-service-trigger"
                type="button"
                :aria-controls="serviceListId"
                :aria-expanded="servicePickerOpen"
                :aria-invalid="Boolean(serviceError)"
                :aria-describedby="serviceError ? `${serviceListId}-error` : undefined"
                :aria-label="`Procedure or services: ${serviceSummary}. Select one or more services`"
                @click="servicePickerOpen = !servicePickerOpen"
                @keydown="onServiceTriggerKeydown"
              >
                <span class="completion-service-summary">{{ serviceSummary }}</span>
                <ChevronDown :size="17" aria-hidden="true" />
              </button>
              <div
                v-show="servicePickerOpen"
                :id="serviceListId"
                class="completion-service-options"
                role="group"
                aria-label="Available services"
              >
                <button
                  v-for="service in availableServices"
                  :key="service"
                  class="completion-service-option"
                  type="button"
                  role="checkbox"
                  :aria-checked="selectedServices.includes(service)"
                  @click="toggleService(service)"
                >
                  <span class="completion-service-checkbox" aria-hidden="true">
                    <Check v-if="selectedServices.includes(service)" :size="13" />
                  </span>
                  <span>{{ service }}</span>
                </button>
                <p v-if="!availableServices.length" class="completion-service-empty">
                  No active services available.
                </p>
              </div>
            </div>
            <small
              v-if="serviceError"
              :id="`${serviceListId}-error`"
              class="completion-service-error"
              role="alert"
            >
              {{ serviceError }}
            </small>
          </div>
          <label class="wide-field">
            <span>Diagnosis / Clinical Findings <b aria-hidden="true">*</b></span>
            <textarea
              v-model="form.diagnosis"
              rows="3"
              maxlength="700"
              placeholder="Enter the diagnosis, findings, or reason for treatment"
              required
            ></textarea>
          </label>
          <label class="wide-field">
            <span>Medical Instruction <small>Optional</small></span>
            <textarea
              v-model="form.prescription"
              rows="2"
              maxlength="700"
              placeholder="Medication and dosage, when applicable"
            ></textarea>
          </label>
        </div>
      </section>

      <section class="completion-form-section" aria-labelledby="billing-details-title">
        <header>
          <CircleDollarSign :size="19" aria-hidden="true" />
          <h3 id="billing-details-title">Billing & Follow-up</h3>
        </header>
        <div class="completion-field-grid billing-grid">
          <label>
            <span>Amount Charged <b aria-hidden="true">*</b></span>
            <span class="money-input"
              ><i>PHP</i
              ><input
                v-model="form.amount_charged"
                type="number"
                min="0"
                max="100000000"
                step="0.01"
                required
            /></span>
          </label>
          <label>
            <span>Amount Paid <b aria-hidden="true">*</b></span>
            <span class="money-input"
              ><i>PHP</i
              ><input
                v-model="form.amount_paid"
                type="number"
                min="0"
                max="100000000"
                step="0.01"
                required
            /></span>
          </label>
          <label>
            <span>Remaining Balance</span>
            <input :value="formatMoney(remainingBalance)" readonly />
          </label>
          <div class="next-visit-field" :class="{ active: form.next_visit }">
            <span>Next Visit <small>Optional</small></span>
            <AvailabilityDatePicker
              v-model="form.next_visit"
              :available-dates="availableFollowUpDates"
              placeholder="Select an available date"
              aria-label="Select an available follow-up appointment date"
              clearable
            />
            <small>
              {{
                form.next_visit
                  ? "You will choose an available follow-up time after saving this record."
                  : availableFollowUpDates.length
                    ? "Leave blank when no follow-up appointment is needed."
                    : "Add clinic availability before assigning a follow-up visit."
              }}
            </small>
          </div>
          <label class="wide-field">
            <span>Remarks <small>Optional</small></span>
            <textarea
              v-model="form.remarks"
              rows="3"
              maxlength="1000"
              placeholder="Treatment performed, patient response, and care instructions"
            ></textarea>
          </label>
        </div>
      </section>

      <p v-if="errorMessage" class="completion-form-error" role="alert">{{ errorMessage }}</p>

      <footer class="completion-form-actions">
        <button class="secondary-button" type="button" :disabled="busy" @click="emit('close')">
          Cancel
        </button>
        <button class="primary-button" type="submit" :disabled="busy">
          <CalendarCheck2 :size="18" aria-hidden="true" />
          {{ busy ? "Saving Record..." : submitLabel }}
        </button>
      </footer>
    </form>
  </BaseModal>
</template>

<style scoped>
:global(.complete-appointment-dialog) {
  width: min(900px, calc(100% - 32px));
}

.completion-record-form {
  display: grid;
  gap: 0;
}

.completion-record-intro {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 16px 20px;
  border-bottom: 1px solid #f4e7cd;
  background: #f8f1e2;
}

.completion-record-intro > span {
  display: grid;
  width: 46px;
  height: 46px;
  flex: 0 0 46px;
  place-items: center;
  border-radius: 7px;
  background: #f4e7cd;
  color: #8a6526;
}

.completion-record-intro h3,
.completion-record-intro p,
.completion-form-section h3 {
  margin: 0;
}

.completion-record-intro h3 {
  color: #171511;
  font-size: 0.95rem;
}

.completion-record-intro p {
  margin-top: 3px;
  color: #706b61;
  font-size: 0.72rem;
}

.completion-appointment-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
  margin: 0;
  padding: 14px 20px;
  border-bottom: 1px solid #f4e7cd;
}

.completion-appointment-summary > div {
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid #f4e7cd;
  border-radius: 6px;
  background: #ffffff;
}

.completion-appointment-summary dt {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #706b61;
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
}

.completion-appointment-summary dd {
  overflow: hidden;
  margin: 5px 0 0;
  color: #171511;
  font-size: 0.72rem;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.completion-form-section {
  padding: 16px 20px 4px;
}

.completion-form-section + .completion-form-section {
  margin-top: 8px;
  border-top: 1px solid #f5f2eb;
}

.completion-form-section > header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: #8a6526;
}

.completion-form-section h3 {
  color: #171511;
  font-size: 0.86rem;
}

.completion-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.completion-field-grid :is(label, .next-visit-field, .completion-service-field) {
  display: grid;
  min-width: 0;
  gap: 6px;
  color: #171511;
  font-size: 0.72rem;
  font-weight: 800;
}

.completion-field-grid :is(label, .next-visit-field, .completion-service-field) > span:first-child {
  min-height: 16px;
}

.completion-field-grid :is(label, .next-visit-field, .completion-service-field) b {
  color: #e33b55;
}

.completion-field-grid :is(label, .next-visit-field, .completion-service-field) small {
  color: #706b61;
  font-size: 0.72rem;
  font-weight: 650;
}

.completion-field-grid input,
.completion-field-grid textarea {
  width: 100%;
  min-width: 0;
  border: 1px solid #f4e7cd;
  border-radius: 6px;
  outline: 0;
  background: #ffffff;
  color: #171511;
  font: inherit;
  font-weight: 650;
}

.completion-field-grid input {
  min-height: 42px;
  padding: 0 12px;
}

.completion-field-grid textarea {
  resize: vertical;
  padding: 10px 12px;
  line-height: 1.45;
}

.completion-field-grid input:focus,
.completion-field-grid textarea:focus {
  border-color: #8a6526;
  box-shadow: 0 0 0 3px rgba(138, 101, 38, 12%);
}

.completion-field-grid input[readonly] {
  background: #f8f1e2;
  color: #514b42;
}

.completion-field-grid .wide-field {
  grid-column: 1 / -1;
}

.completion-service-picker {
  position: relative;
  min-width: 0;
}

.completion-service-trigger {
  display: flex;
  width: 100%;
  min-height: 42px;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid #f4e7cd;
  border-radius: 6px;
  background: #ffffff;
  padding: 0 12px;
  color: #171511;
  cursor: pointer;
  font: inherit;
  font-weight: 650;
  text-align: left;
}

.completion-service-trigger:focus-visible,
.completion-service-trigger[aria-expanded="true"] {
  border-color: #8a6526;
  outline: 0;
  box-shadow: 0 0 0 3px rgba(138, 101, 38, 12%);
}

.completion-service-trigger svg {
  flex: 0 0 auto;
}

.completion-service-summary {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.completion-service-options {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  left: 0;
  z-index: 5;
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid #f4e7cd;
  border-radius: 6px;
  background: #ffffff;
  padding: 5px;
  box-shadow: 0 12px 30px rgba(23, 21, 17, 16%);
}

.completion-service-option {
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
  font-weight: 650;
  overflow-wrap: anywhere;
  text-align: left;
}

.completion-service-option:hover,
.completion-service-option:focus-visible {
  outline: 0;
  background: #f8f1e2;
}

.completion-service-checkbox {
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

.completion-service-option[aria-checked="true"] .completion-service-checkbox {
  border-color: #8a6526;
  background: #8a6526;
}

.completion-service-empty {
  margin: 0;
  padding: 10px;
  color: #706b61;
  font-weight: 500;
}

.completion-field-grid .completion-service-error {
  color: #b4233d;
  font-size: 0.72rem;
}

.completion-field-grid .next-visit-field {
  align-content: start;
  padding: 10px;
  border: 1px solid #f4e7cd;
  border-radius: 7px;
  background: #f8f1e2;
}

.completion-field-grid .next-visit-field.active {
  border-color: #dfc48a;
  background: #f8f1e2;
}

.completion-field-grid .next-visit-field > small {
  color: #706b61;
  line-height: 1.4;
}

.money-input {
  position: relative;
  display: flex;
  align-items: center;
}

.money-input i {
  position: absolute;
  left: 12px;
  color: #706b61;
  font-size: 0.72rem;
  font-style: normal;
  pointer-events: none;
}

.money-input input {
  padding-left: 42px;
}

.completion-form-error {
  margin: 12px 20px 0;
  padding: 10px 12px;
  border: 1px solid #ffc7d0;
  border-radius: 6px;
  background: #fff1f3;
  color: #c52742;
  font-size: 0.72rem;
  font-weight: 750;
}

.completion-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
  padding: 14px 20px 18px;
  border-top: 1px solid #f4e7cd;
}

.completion-form-actions button {
  display: inline-flex;
  min-width: 150px;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

:global(html[data-dashboard-theme="dark"]) .completion-record-intro {
  border-color: var(--dashboard-border);
  background: #241e17;
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .completion-appointment-summary,
    .completion-form-section + .completion-form-section,
    .completion-form-actions
  ) {
  border-color: var(--dashboard-border);
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .completion-record-intro h3,
    .completion-form-section h3,
    .completion-appointment-summary dd
  ) {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .completion-appointment-summary > div,
    .completion-field-grid input,
    .completion-field-grid textarea
  ) {
  border-color: var(--dashboard-border);
  background: #241e17;
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .completion-field-grid input[readonly] {
  background: #28241e;
  color: var(--dashboard-muted);
}

:global(html[data-dashboard-theme="dark"]) .completion-field-grid .next-visit-field {
  border-color: var(--dashboard-border);
  background: #241e17;
}

:global(html[data-dashboard-theme="dark"]) .completion-service-field {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"])
  :is(.completion-service-trigger, .completion-service-options) {
  border-color: var(--dashboard-border);
  background: #241e17;
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .completion-service-option {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .completion-service-option:is(:hover, :focus-visible) {
  background: #3f321e;
}

@media (max-width: 760px) {
  .completion-appointment-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .completion-record-intro,
  .completion-appointment-summary,
  .completion-form-section,
  .completion-form-actions {
    padding-inline: 14px;
  }

  .completion-appointment-summary,
  .completion-field-grid {
    grid-template-columns: 1fr;
  }

  .completion-field-grid .wide-field {
    grid-column: auto;
  }

  .completion-form-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .completion-form-actions .primary-button {
    grid-row: 1;
  }
}
</style>
