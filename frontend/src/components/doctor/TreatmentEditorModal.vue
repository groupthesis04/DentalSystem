<script setup>
import {
  CalendarDays,
  CircleDollarSign,
  ClipboardPlus,
  FileText,
  Pill,
  Save,
  Stethoscope,
  UserRound,
} from "lucide-vue-next";
import { computed } from "vue";

import { calculateAge, formatDate } from "../../services/format";
import AvatarBadge from "../AvatarBadge.vue";
import BaseModal from "../BaseModal.vue";

const props = defineProps({
  form: { type: Object, required: true },
  patient: { type: Object, required: true },
  records: { type: Array, default: () => [] },
  appointments: { type: Array, default: () => [] },
  procedures: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
  maxDate: { type: String, default: "" },
});
const emit = defineEmits(["close", "submit"]);

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

    <form class="treatment-editor-form" @submit.prevent="emit('submit')">
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
          <label>
            <span>Procedure / Service <b aria-hidden="true">*</b></span>
            <select v-model="form.procedure" required>
              <option disabled value="">
                {{ procedures.length ? "Select a service" : "No active services available" }}
              </option>
              <option v-for="procedure in procedures" :key="procedure" :value="procedure">
                {{ procedure }}
              </option>
            </select>
          </label>
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
  border-color: #cbd9e9;
  border-radius: 8px;
  color: #102654;
}

:global(.patient-treatment-editor-dialog .crud-dialog-header) {
  padding: 20px 26px;
  border-bottom-color: #dbe4ee;
}

:global(.patient-treatment-editor-dialog .crud-dialog-header h2) {
  margin-top: 4px;
  color: #0b1f55;
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
  background: #dfedff;
  color: #0874e8;
}

.treatment-modal-subtitle {
  margin: 6px 0 0;
  color: #55709a;
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
  border: 1px solid #c5dbf5;
  border-radius: 8px;
  background: #f8fbff;
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
  background: #dbeafe;
  color: #0874e8;
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
  color: #0b1f55;
  font-size: 0.96rem;
}

.treatment-patient-identity small {
  overflow: hidden;
  color: #587097;
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
  border-left: 1px solid #d1dcea;
  padding: 0 14px;
  color: #0874e8;
}

.treatment-summary-item small {
  color: #617394;
  font-size: 0.72rem;
  font-weight: 600;
}

.treatment-summary-item strong {
  overflow: hidden;
  color: #102654;
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
  color: #0874e8;
}

.treatment-editor-section h3 {
  margin: 0;
  color: #0b1f55;
  font-size: 0.96rem;
}

.treatment-main-grid,
.treatment-billing-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.treatment-clinical-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.treatment-editor-form label {
  display: grid;
  min-width: 0;
  gap: 7px;
  color: #142954;
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
  color: #7183a0;
  font-size: 0.72rem;
  font-weight: 600;
}

.treatment-editor-form :is(input, select, textarea) {
  width: 100%;
  min-width: 0;
  border: 1px solid #cdd9e8;
  border-radius: 7px;
  outline: 0;
  background: #fff;
  color: #152b53;
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
  border-color: #1683da;
  box-shadow: 0 0 0 3px rgb(22 131 218 / 12%);
}

.treatment-field-heading {
  display: flex;
  align-items: center;
  gap: 9px;
}

.treatment-field-heading svg {
  flex: 0 0 auto;
  color: #0874e8;
}

.treatment-billing-section {
  border-top: 1px solid #e1e9f1;
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
  color: #0b2f68;
  font-size: 0.74rem;
  font-style: normal;
  font-weight: 800;
  pointer-events: none;
}

.treatment-money-input input {
  padding-left: 51px;
}

.treatment-money-input.readonly input {
  background: #f1f5f9;
  color: #526580;
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
  color: #657a9b;
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
  border-top: 1px solid #dbe4ee;
  background: #fff;
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
  border-color: #dce4ed;
  background: #eef2f7;
  color: #0b1f55;
}

.treatment-editor-actions .primary-button {
  border-color: #0874e8;
  background: #0874e8;
  color: #fff;
}

:global(html[data-dashboard-theme="dark"]) :is(.treatment-patient-summary) {
  border-color: var(--dashboard-border);
  background: #162334;
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
  background: #172334;
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .treatment-editor-actions {
  border-color: var(--dashboard-border);
  background: #111821;
}

@media (max-width: 820px) {
  .treatment-patient-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .treatment-patient-identity {
    grid-column: 1 / -1;
    margin-bottom: 12px;
    padding: 0 0 13px;
    border-bottom: 1px solid #d1dcea;
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
