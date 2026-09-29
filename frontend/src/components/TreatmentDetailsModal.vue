<script setup>
import { computed } from "vue";

import {
  formatDate,
  formatMoney,
  statusLabel,
  treatmentBalance,
  treatmentProcedure,
} from "../services/format";
import BaseModal from "./BaseModal.vue";

const props = defineProps({
  record: { type: Object, required: true },
  showDentist: { type: Boolean, default: false },
  showStatus: { type: Boolean, default: false },
  showNextVisit: { type: Boolean, default: false },
  doctorFallback: { type: String, default: "Clinic dentist" },
});
const emit = defineEmits(["close"]);

const fields = computed(() => {
  const record = props.record;
  const core = [
    { label: "Patient", value: record.patient_name || "Patient" },
    { label: "Date", value: formatDate(record.treatment_date) },
    { label: "Tooth No./s", value: record.tooth_numbers || "-" },
    { label: "Procedure", value: treatmentProcedure(record) },
    { label: "Diagnosis", value: record.diagnosis || "-" },
    { label: "Medical Instruction", value: record.prescription || "-" },
    { label: "Charged", value: formatMoney(record.amount_charged) },
    { label: "Paid", value: formatMoney(record.amount_paid) },
    { label: "Balance", value: formatMoney(treatmentBalance(record)) },
    { label: "Remarks", value: record.remarks || record.notes || "-" },
  ];
  const additional = [];
  if (props.showDentist) {
    additional.push({ label: "Dentist", value: record.doctor_name || props.doctorFallback });
  }
  if (props.showStatus) {
    const status = String(record.status || "")
      .trim()
      .toLowerCase();
    additional.push({
      label: "Status",
      value: status && status !== "paid" && status !== "unpaid" ? statusLabel(status) : "Completed",
    });
  }
  if (props.showNextVisit) {
    additional.push({ label: "Next Visit", value: formatDate(record.next_visit) });
  }
  if (additional.length % 2) additional[additional.length - 1].wide = true;
  return [...core, ...additional];
});
</script>

<template>
  <BaseModal
    title="Treatment Details"
    eyebrow="Patient record"
    size-class="treatment-details-dialog"
    @close="emit('close')"
  >
    <div class="detail-grid treatment-detail-grid">
      <span v-for="field in fields" :key="field.label" :class="{ wide: field.wide }">
        <strong>{{ field.value }}</strong>
        {{ field.label }}
      </span>
    </div>
  </BaseModal>
</template>
