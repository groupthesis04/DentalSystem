<script setup>
import {
  CalendarCheck2,
  CircleDollarSign,
  ClipboardPlus,
  FileText,
  Stethoscope,
  UserRound,
} from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";

import AvailabilityDatePicker from "../AvailabilityDatePicker.vue";
import BaseModal from "../BaseModal.vue";
import { availableSlotDates, futureOpenSlots } from "../../services/availability";
import { apiRequest } from "../../services/api";
import { formatDate, formatMoney, localDateIso } from "../../services/format";
import { validatedPayload } from "../../services/validation";

const props = defineProps({
  appointment: { type: Object, required: true },
  existingRecord: { type: Object, default: null },
  availability: { type: Array, default: () => [] },
  doctor: { type: String, default: "" },
});
const emit = defineEmits(["close", "completed", "follow-up"]);

const today = localDateIso();
const busy = ref(false);
const errorMessage = ref("");
const form = reactive({
  appointment_id: "",
  patient_id: "",
  treatment_date: today,
  tooth_numbers: "",
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

function moneyInput(value) {
  const amount = Number(value || 0);
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00";
}

function hydrateForm() {
  const record = props.existingRecord;
  Object.assign(form, {
    appointment_id: props.appointment.id || "",
    patient_id: props.appointment.patient_id || record?.patient_id || "",
    treatment_date:
      record?.treatment_date ||
      (props.appointment.date && props.appointment.date <= today ? props.appointment.date : today),
    tooth_numbers: record?.tooth_numbers || "",
    procedure: props.appointment.service || record?.procedure || record?.treatment || "",
    diagnosis: record?.diagnosis || "",
    prescription: record?.prescription || "",
    amount_charged: moneyInput(record?.amount_charged),
    amount_paid: moneyInput(record?.amount_paid),
    remarks: record?.remarks || record?.notes || "",
    next_visit: record?.next_visit || "",
    _website: "",
  });
  errorMessage.value = "";
}

watch([() => props.appointment, () => props.existingRecord], hydrateForm, { immediate: true });

async function submitTreatmentRecord() {
  errorMessage.value = "";
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
      id: props.existingRecord?.id || undefined,
      treatment: form.procedure,
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
          <dd>{{ appointment.service }}</dd>
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
  border-bottom: 1px solid #e1e9f1;
  background: #f3f9ff;
}

.completion-record-intro > span {
  display: grid;
  width: 46px;
  height: 46px;
  flex: 0 0 46px;
  place-items: center;
  border-radius: 7px;
  background: #dceeff;
  color: #0e78df;
}

.completion-record-intro h3,
.completion-record-intro p,
.completion-form-section h3 {
  margin: 0;
}

.completion-record-intro h3 {
  color: #142b4d;
  font-size: 0.95rem;
}

.completion-record-intro p {
  margin-top: 3px;
  color: #647b98;
  font-size: 0.72rem;
}

.completion-appointment-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
  margin: 0;
  padding: 14px 20px;
  border-bottom: 1px solid #e1e9f1;
}

.completion-appointment-summary > div {
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid #dce6ef;
  border-radius: 6px;
  background: #fff;
}

.completion-appointment-summary dt {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #6c8099;
  font-size: 0.62rem;
  font-weight: 800;
  text-transform: uppercase;
}

.completion-appointment-summary dd {
  overflow: hidden;
  margin: 5px 0 0;
  color: #172d4e;
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
  border-top: 1px solid #e5ecf2;
}

.completion-form-section > header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: #1379d7;
}

.completion-form-section h3 {
  color: #162d50;
  font-size: 0.86rem;
}

.completion-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.completion-field-grid :is(label, .next-visit-field) {
  display: grid;
  min-width: 0;
  gap: 6px;
  color: #263e60;
  font-size: 0.68rem;
  font-weight: 800;
}

.completion-field-grid :is(label, .next-visit-field) > span:first-child {
  min-height: 16px;
}

.completion-field-grid :is(label, .next-visit-field) b {
  color: #e33b55;
}

.completion-field-grid :is(label, .next-visit-field) small {
  color: #7e8da0;
  font-size: 0.58rem;
  font-weight: 650;
}

.completion-field-grid input,
.completion-field-grid textarea {
  width: 100%;
  min-width: 0;
  border: 1px solid #d3e0ec;
  border-radius: 6px;
  outline: 0;
  background: #fff;
  color: #233b5d;
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
  border-color: #1683da;
  box-shadow: 0 0 0 3px rgb(22 131 218 / 12%);
}

.completion-field-grid input[readonly] {
  background: #f4f7fa;
  color: #526985;
}

.completion-field-grid .wide-field {
  grid-column: 1 / -1;
}

.completion-field-grid .next-visit-field {
  align-content: start;
  padding: 10px;
  border: 1px solid #d9e5ef;
  border-radius: 7px;
  background: #f8fbfe;
}

.completion-field-grid .next-visit-field.active {
  border-color: #a8d5f6;
  background: #eef8ff;
}

.completion-field-grid .next-visit-field > small {
  color: #657f9d;
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
  color: #778aa2;
  font-size: 0.59rem;
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
  font-size: 0.68rem;
  font-weight: 750;
}

.completion-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
  padding: 14px 20px 18px;
  border-top: 1px solid #e1e9f1;
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
  background: #1b2b3e;
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
  background: #172334;
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .completion-field-grid input[readonly] {
  background: #202d3d;
  color: var(--dashboard-muted);
}

:global(html[data-dashboard-theme="dark"]) .completion-field-grid .next-visit-field {
  border-color: var(--dashboard-border);
  background: #1b2b3e;
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
