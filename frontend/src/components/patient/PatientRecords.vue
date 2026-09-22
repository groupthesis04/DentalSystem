<script setup>
import {
  Activity,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FileText,
  Search,
  Stethoscope,
  WalletCards,
} from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import {
  formatMoney,
  localDateIso,
  treatmentBalance,
  treatmentProcedure,
} from "../../services/format";
import BaseModal from "../BaseModal.vue";
import StatusBadge from "../StatusBadge.vue";

const props = defineProps({
  records: { type: Array, default: () => [] },
  appointments: { type: Array, default: () => [] },
  highlightedId: { type: String, default: "" },
});

const search = ref("");
const dateRange = ref("all");
const currentPage = ref(1);
const detailRecord = ref(null);
const pageSize = 5;
const todayIso = localDateIso();

function normalize(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function dateFromIso(value) {
  const [year, month, day] = String(value || "")
    .slice(0, 10)
    .split("-")
    .map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
}

function formatLongDate(value) {
  const date = dateFromIso(value);
  if (!date) return "-";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "2-digit",
    year: "numeric",
  });
}

function recordStatus(record) {
  const status = normalize(record?.status);
  return status && status !== "paid" && status !== "unpaid" ? status : "completed";
}

function diagnosisLine(record) {
  const procedure = normalize(treatmentProcedure(record));
  const diagnosis = String(record?.diagnosis || "").trim();
  if (diagnosis && normalize(diagnosis) !== procedure) return diagnosis;
  return String(record?.remarks || record?.notes || "Treatment completed").trim();
}

function notesLine(record) {
  const diagnosis = normalize(diagnosisLine(record));
  const remarks = String(record?.remarks || record?.notes || "").trim();
  return remarks && normalize(remarks) !== diagnosis ? remarks : "";
}

function matchesDateRange(record) {
  if (dateRange.value === "all") return true;
  const treatmentDate = dateFromIso(record?.treatment_date);
  if (!treatmentDate) return false;
  const today = dateFromIso(todayIso);
  if (dateRange.value === "year") return treatmentDate.getFullYear() === today.getFullYear();
  const days = Number(dateRange.value);
  const earliest = new Date(today);
  earliest.setDate(earliest.getDate() - days);
  return treatmentDate >= earliest && treatmentDate <= today;
}

const filteredRecords = computed(() => {
  const term = normalize(search.value);
  return [...props.records]
    .filter((record) => {
      if (!matchesDateRange(record)) return false;
      if (!term) return true;
      return normalize(
        [
          treatmentProcedure(record),
          record.treatment_date,
          formatLongDate(record.treatment_date),
          record.doctor_name,
          record.diagnosis,
          record.remarks,
          record.notes,
          record.prescription,
          record.tooth_numbers,
        ].join(" "),
      ).includes(term);
    })
    .sort((a, b) => String(b.treatment_date || "").localeCompare(String(a.treatment_date || "")));
});

const pageCount = computed(() => Math.max(1, Math.ceil(filteredRecords.value.length / pageSize)));
const pageStart = computed(() =>
  filteredRecords.value.length ? (currentPage.value - 1) * pageSize + 1 : 0,
);
const pageEnd = computed(() =>
  Math.min(currentPage.value * pageSize, filteredRecords.value.length),
);
const pagedRecords = computed(() =>
  filteredRecords.value.slice((currentPage.value - 1) * pageSize, currentPage.value * pageSize),
);
const visiblePages = computed(() =>
  Array.from({ length: pageCount.value }, (_, index) => index + 1).slice(
    Math.max(0, Math.min(currentPage.value - 2, pageCount.value - 3)),
    Math.max(0, Math.min(currentPage.value - 2, pageCount.value - 3)) + 3,
  ),
);

const upcomingTreatments = computed(
  () =>
    props.appointments.filter((item) => {
      const status = normalize(item.status);
      return item.date >= todayIso && ["pending", "approved", "accepted"].includes(status);
    }).length,
);
const ongoingTreatments = computed(
  () => props.records.filter((record) => record.next_visit && record.next_visit >= todayIso).length,
);
const completedTreatments = computed(
  () => props.records.filter((record) => recordStatus(record) === "completed").length,
);
const outstandingBalance = computed(() =>
  props.records.reduce((total, record) => total + Math.max(0, treatmentBalance(record)), 0),
);

const summaryItems = computed(() => [
  { label: "Total Treatments", value: props.records.length, icon: Stethoscope, tone: "blue" },
  { label: "Ongoing Treatments", value: ongoingTreatments.value, icon: Clock3, tone: "gold" },
  {
    label: "Completed Treatments",
    value: completedTreatments.value,
    icon: CheckCircle2,
    tone: "green",
  },
  {
    label: "Upcoming Treatments",
    value: upcomingTreatments.value,
    icon: CalendarDays,
    tone: "cyan",
  },
]);

watch([search, dateRange], () => {
  currentPage.value = 1;
});

watch(pageCount, (count) => {
  if (currentPage.value > count) currentPage.value = count;
});
</script>

<template>
  <section class="workspace-panel patient-records-page">
    <header class="patient-records-header" aria-labelledby="patient-records-title">
      <span class="patient-records-title-icon"><FileText :size="30" aria-hidden="true" /></span>
      <div>
        <span class="patient-records-kicker">Dental History</span>
        <h1 id="patient-records-title">My Records</h1>
        <p>View your dental history and treatments in one place.</p>
      </div>
    </header>

    <div class="patient-records-layout">
      <section class="patient-records-panel" aria-labelledby="treatment-history-title">
        <header class="patient-history-heading">
          <div class="patient-history-title">
            <span><Stethoscope :size="26" aria-hidden="true" /></span>
            <div>
              <h2 id="treatment-history-title">Treatment History</h2>
              <p>A list of your past and current dental treatments.</p>
            </div>
          </div>
          <div class="patient-record-tools">
            <label class="patient-record-search">
              <Search :size="19" aria-hidden="true" />
              <span class="sr-only">Search treatment records</span>
              <input
                v-model="search"
                type="search"
                placeholder="Search treatment, date, or notes..."
              />
            </label>
            <label class="patient-record-range">
              <CalendarDays :size="18" aria-hidden="true" />
              <span class="sr-only">Filter treatment records by date</span>
              <select v-model="dateRange" aria-label="Filter treatment records by date">
                <option value="all">All Dates</option>
                <option value="30">Last 30 Days</option>
                <option value="90">Last 90 Days</option>
                <option value="year">This Year</option>
              </select>
              <ChevronRight :size="16" aria-hidden="true" />
            </label>
          </div>
        </header>

        <div class="patient-record-table-wrap">
          <table class="patient-records-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Date</th>
                <th>Service / Treatment</th>
                <th>Dentist</th>
                <th>Diagnosis / Notes</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(record, index) in pagedRecords"
                :key="record.id"
                :data-entity-id="record.id"
                :class="{ 'notification-target-glow': highlightedId === record.id }"
              >
                <td class="patient-record-number" data-label="#">{{ pageStart + index }}</td>
                <td data-label="Date">{{ formatLongDate(record.treatment_date) }}</td>
                <td class="patient-record-treatment" data-label="Treatment">
                  <strong>{{ treatmentProcedure(record) }}</strong>
                  <small v-if="record.tooth_numbers">Tooth No./s: {{ record.tooth_numbers }}</small>
                </td>
                <td data-label="Dentist">{{ record.doctor_name || "Clinic dentist" }}</td>
                <td class="patient-record-notes" data-label="Diagnosis / Notes">
                  <span>{{ diagnosisLine(record) }}</span>
                  <small v-if="notesLine(record)">{{ notesLine(record) }}</small>
                </td>
                <td class="patient-record-status" data-label="Status">
                  <StatusBadge :status="recordStatus(record)" />
                </td>
                <td class="patient-record-actions" data-label="Actions">
                  <button type="button" @click="detailRecord = record">View</button>
                </td>
              </tr>
              <tr v-if="!pagedRecords.length" class="patient-records-empty-row">
                <td colspan="7">
                  <span><FileText :size="28" aria-hidden="true" /></span>
                  <strong>No treatment records found</strong>
                  <small>Try another search or date range.</small>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="patient-records-footer">
          <p>
            Showing {{ pageStart }} to {{ pageEnd }} of {{ filteredRecords.length }}
            {{ filteredRecords.length === 1 ? "record" : "records" }}
          </p>
          <nav v-if="filteredRecords.length" aria-label="Treatment record pages">
            <button
              type="button"
              aria-label="Previous record page"
              :disabled="currentPage === 1"
              @click="currentPage -= 1"
            >
              <ChevronLeft :size="18" aria-hidden="true" />
            </button>
            <button
              v-for="page in visiblePages"
              :key="page"
              type="button"
              :class="{ active: currentPage === page }"
              :aria-current="currentPage === page ? 'page' : undefined"
              :aria-label="`Record page ${page}`"
              @click="currentPage = page"
            >
              {{ page }}
            </button>
            <button
              type="button"
              aria-label="Next record page"
              :disabled="currentPage === pageCount"
              @click="currentPage += 1"
            >
              <ChevronRight :size="18" aria-hidden="true" />
            </button>
          </nav>
        </footer>
      </section>

      <aside class="patient-records-rail" aria-label="Dental record summary">
        <section class="patient-record-summary" aria-labelledby="dental-summary-title">
          <header>
            <Activity :size="22" aria-hidden="true" />
            <h2 id="dental-summary-title">Dental Summary</h2>
          </header>
          <div class="patient-record-summary-list">
            <div v-for="item in summaryItems" :key="item.label">
              <span :class="`tone-${item.tone}`"><component :is="item.icon" :size="21" /></span>
              <p>
                <strong>{{ item.value }}</strong
                ><small>{{ item.label }}</small>
              </p>
            </div>
          </div>
          <div class="patient-record-balance">
            <WalletCards :size="18" aria-hidden="true" />
            <span
              ><small>Outstanding Balance</small
              ><strong>{{ formatMoney(outstandingBalance) }}</strong></span
            >
          </div>
        </section>

        <section class="patient-record-care-note">
          <Stethoscope :size="27" aria-hidden="true" />
          <p>
            <strong>Keep Your Smile Healthy!</strong
            ><span>Regular dental checkups help prevent bigger problems.</span>
          </p>
        </section>
      </aside>
    </div>

    <BaseModal
      v-if="detailRecord"
      title="Treatment Details"
      :eyebrow="treatmentProcedure(detailRecord)"
      size-class="patient-record-dialog"
      @close="detailRecord = null"
    >
      <div class="patient-record-detail-grid">
        <span
          ><small>Date</small
          ><strong>{{ formatLongDate(detailRecord.treatment_date) }}</strong></span
        >
        <span
          ><small>Dentist</small
          ><strong>{{ detailRecord.doctor_name || "Clinic dentist" }}</strong></span
        >
        <span
          ><small>Tooth No./s</small><strong>{{ detailRecord.tooth_numbers || "-" }}</strong></span
        >
        <span><small>Status</small><StatusBadge :status="recordStatus(detailRecord)" /></span>
        <span class="wide"
          ><small>Diagnosis</small><strong>{{ detailRecord.diagnosis || "-" }}</strong></span
        >
        <span class="wide"
          ><small>Remarks</small
          ><strong>{{ detailRecord.remarks || detailRecord.notes || "-" }}</strong></span
        >
        <span class="wide"
          ><small>Prescription</small><strong>{{ detailRecord.prescription || "-" }}</strong></span
        >
        <span
          ><small>Amount Charged</small
          ><strong>{{ formatMoney(detailRecord.amount_charged) }}</strong></span
        >
        <span
          ><small>Amount Paid</small
          ><strong>{{ formatMoney(detailRecord.amount_paid) }}</strong></span
        >
        <span
          ><small>Balance</small
          ><strong>{{ formatMoney(treatmentBalance(detailRecord)) }}</strong></span
        >
        <span
          ><small>Next Visit</small
          ><strong>{{ formatLongDate(detailRecord.next_visit) }}</strong></span
        >
      </div>
      <div class="patient-record-modal-actions">
        <button type="button" class="secondary-button" @click="detailRecord = null">Close</button>
      </div>
    </BaseModal>
  </section>
</template>

<style scoped>
.patient-records-page {
  display: grid;
  gap: 14px;
  color: #172d50;
}

.patient-records-header {
  display: flex;
  min-height: 108px;
  align-items: center;
  gap: 18px;
  padding: 16px 22px;
  border-bottom: 1px solid #dce7f2;
  background: #f8fbff;
}

.patient-records-title-icon,
.patient-history-title > span {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid #cfe3fb;
  border-radius: 8px;
  background: #eaf4ff;
  color: #1475e4;
}

.patient-records-title-icon {
  width: 66px;
  height: 66px;
}

.patient-records-kicker,
.patient-records-header h1,
.patient-records-header p,
.patient-history-heading h2,
.patient-history-heading p {
  margin: 0;
}

.patient-records-kicker {
  color: #1470dc;
  font-size: 0.7rem;
  font-weight: 850;
  text-transform: uppercase;
}

.patient-records-header h1 {
  margin-top: 2px;
  color: #12294d;
  font-size: 1.5rem;
  line-height: 1.18;
}

.patient-records-header p,
.patient-history-heading p {
  margin-top: 4px;
  color: #697e99;
  font-size: 0.74rem;
}

.patient-records-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(245px, 0.29fr);
  align-items: start;
  gap: 14px;
}

.patient-records-panel,
.patient-record-summary,
.patient-record-care-note {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #dce7f2;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 6px 20px rgb(31 64 102 / 5%);
}

.patient-history-heading {
  display: flex;
  min-height: 98px;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 15px 18px;
  border-bottom: 1px solid #e4edf5;
}

.patient-history-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 13px;
}

.patient-history-title > span {
  width: 52px;
  height: 52px;
}

.patient-history-heading h2,
.patient-record-summary h2 {
  color: #142c50;
  font-size: 0.88rem;
}

.patient-record-tools {
  display: grid;
  width: min(480px, 51%);
  grid-template-columns: minmax(230px, 1fr) minmax(155px, 0.62fr);
  gap: 9px;
}

.patient-record-search,
.patient-record-range {
  display: flex;
  min-width: 0;
  min-height: 42px;
  align-items: center;
  gap: 9px;
  padding: 0 11px;
  color: #55708f;
  border: 1px solid #d7e3ef;
  border-radius: 7px;
  background: #fff;
}

.patient-record-search:focus-within,
.patient-record-range:focus-within {
  border-color: #1475e4;
  box-shadow: 0 0 0 3px rgb(20 117 228 / 12%);
}

.patient-record-search input,
.patient-record-range select {
  width: 100%;
  min-width: 0;
  height: 40px;
  border: 0;
  outline: 0;
  background: transparent;
  color: #294261;
  font: inherit;
  font-size: 0.68rem;
}

.patient-record-range select {
  appearance: none;
  cursor: pointer;
}

.patient-record-range > svg:last-child {
  flex: 0 0 auto;
  transform: rotate(90deg);
}

.patient-record-table-wrap {
  width: 100%;
  overflow-x: auto;
}

.patient-records-table {
  width: 100%;
  min-width: 900px;
  border-collapse: collapse;
  table-layout: fixed;
  color: #2a4365;
  font-size: 0.69rem;
}

.patient-records-table th,
.patient-records-table td {
  padding: 11px 12px;
  border-bottom: 1px solid #e5edf4;
  text-align: left;
  vertical-align: middle;
}

.patient-records-table th {
  background: #eff5fa;
  color: #536985;
  font-size: 0.59rem;
  font-weight: 850;
  text-transform: uppercase;
}

.patient-records-table th:nth-child(1) {
  width: 5%;
  text-align: center;
}
.patient-records-table th:nth-child(2) {
  width: 13%;
}
.patient-records-table th:nth-child(3) {
  width: 18%;
}
.patient-records-table th:nth-child(4) {
  width: 16%;
}
.patient-records-table th:nth-child(5) {
  width: 25%;
}
.patient-records-table th:nth-child(6) {
  width: 13%;
}
.patient-records-table th:nth-child(7) {
  width: 10%;
  text-align: right;
}

.patient-records-table tbody tr:hover {
  background: #f9fcff;
}

.patient-record-number {
  font-weight: 800;
  text-align: center !important;
}

.patient-record-treatment strong,
.patient-record-treatment small,
.patient-record-notes span,
.patient-record-notes small {
  display: block;
}

.patient-record-treatment strong {
  color: #142e53;
  line-height: 1.3;
}

.patient-record-treatment small,
.patient-record-notes small {
  margin-top: 3px;
  color: #70839b;
  font-size: 0.61rem;
}

.patient-record-notes {
  overflow-wrap: anywhere;
  line-height: 1.35;
}

.patient-record-status :deep(.status) {
  min-width: 92px;
  justify-content: center;
}

.patient-record-actions {
  text-align: right !important;
}

.patient-record-actions button {
  min-width: 68px;
  min-height: 34px;
  padding: 6px 12px;
  border: 1px solid #d4e7fb;
  border-radius: 6px;
  background: #eef6ff;
  color: #1170dd;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.patient-record-actions button:hover,
.patient-record-actions button:focus-visible {
  border-color: #1475e4;
  outline: 0;
  background: #1475e4;
  color: #fff;
}

.patient-records-empty-row:hover {
  background: transparent !important;
}

.patient-records-empty-row td {
  height: 210px;
  text-align: center;
}

.patient-records-empty-row span {
  display: grid;
  width: 52px;
  height: 52px;
  margin: 0 auto 10px;
  place-items: center;
  border-radius: 8px;
  background: #eaf4ff;
  color: #1475e4;
}

.patient-records-empty-row strong,
.patient-records-empty-row small {
  display: block;
}

.patient-records-empty-row small {
  margin-top: 4px;
  color: #70839b;
}

.patient-records-footer {
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  padding: 11px 18px;
}

.patient-records-footer p {
  margin: 0;
  color: #657c98;
  font-size: 0.68rem;
}

.patient-records-footer nav {
  display: flex;
  gap: 6px;
}

.patient-records-footer nav button {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  padding: 0;
  border: 1px solid #dce6f0;
  border-radius: 6px;
  background: #fff;
  color: #3f5a7c;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.patient-records-footer nav button:hover:not(:disabled),
.patient-records-footer nav button:focus-visible,
.patient-records-footer nav button.active {
  border-color: #1475e4;
  outline: 0;
  background: #1475e4;
  color: #fff;
}

.patient-records-footer nav button:disabled {
  color: #b4c0ce;
  cursor: not-allowed;
}

.patient-records-rail {
  display: grid;
  gap: 14px;
}

.patient-record-summary {
  padding: 15px;
}

.patient-record-summary > header {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #1475e4;
}

.patient-record-summary h2 {
  margin: 0;
}

.patient-record-summary-list {
  display: grid;
  gap: 9px;
  margin-top: 14px;
}

.patient-record-summary-list > div {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
}

.patient-record-summary-list > div > span {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 7px;
  background: #eaf4ff;
  color: #1475e4;
}

.patient-record-summary-list .tone-gold {
  background: #fff3dd;
  color: #d88900;
}
.patient-record-summary-list .tone-green {
  background: #e2f8ed;
  color: #0d9b5c;
}
.patient-record-summary-list .tone-cyan {
  background: #e4f7fb;
  color: #078ea7;
}

.patient-record-summary-list p,
.patient-record-care-note p {
  display: grid;
  gap: 2px;
  margin: 0;
}

.patient-record-summary-list strong {
  color: #172d50;
  font-size: 0.88rem;
}

.patient-record-summary-list small,
.patient-record-care-note span {
  color: #697e99;
  font-size: 0.65rem;
}

.patient-record-balance {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 14px;
  padding: 10px;
  border-radius: 7px;
  background: #f3f7fc;
  color: #5b7190;
}

.patient-record-balance span {
  display: grid;
  gap: 1px;
}

.patient-record-balance small {
  font-size: 0.59rem;
}

.patient-record-balance strong {
  color: #172d50;
  font-size: 0.72rem;
}

.patient-record-care-note {
  display: grid;
  min-height: 92px;
  grid-template-columns: 48px minmax(0, 1fr);
  align-items: center;
  gap: 11px;
  padding: 14px;
  background: #eff7ff;
  color: #1475e4;
}

.patient-record-care-note strong {
  color: #174d9b;
  font-size: 0.69rem;
}

.patient-record-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 18px;
}

.patient-record-detail-grid > span {
  display: grid;
  min-width: 0;
  gap: 4px;
  padding: 12px;
  border: 1px solid #e0e8f1;
  border-radius: 7px;
  background: #f8fbfe;
}

.patient-record-detail-grid > span.wide {
  grid-column: 1 / -1;
}

.patient-record-detail-grid small {
  color: #71839a;
  font-size: 0.62rem;
  font-weight: 750;
  text-transform: uppercase;
}

.patient-record-detail-grid strong {
  overflow-wrap: anywhere;
  color: #172d50;
  font-size: 0.74rem;
}

.patient-record-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding: 0 18px 18px;
}

:global(.patient-record-dialog) {
  width: min(94vw, 680px);
}

:global(html[data-dashboard-theme="dark"]) .patient-records-page {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .patient-records-header,
    .patient-records-panel,
    .patient-record-summary,
    .patient-record-search,
    .patient-record-range,
    .patient-records-footer nav button
  ) {
  border-color: var(--dashboard-border);
  background: var(--dashboard-surface);
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .patient-records-header h1,
    .patient-history-heading h2,
    .patient-record-summary h2,
    .patient-record-summary-list strong,
    .patient-record-balance strong,
    .patient-record-treatment strong,
    .patient-record-detail-grid strong
  ) {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .patient-history-heading,
:global(html[data-dashboard-theme="dark"]) .patient-records-table td {
  border-color: var(--dashboard-border);
}

:global(html[data-dashboard-theme="dark"]) .patient-records-table th {
  color: var(--dashboard-muted);
  background: #1e2d3f;
}

:global(html[data-dashboard-theme="dark"]) .patient-records-table {
  color: #dce7f5;
}

:global(html[data-dashboard-theme="dark"]) .patient-records-table tbody tr:hover {
  background: #1b293a;
}

:global(html[data-dashboard-theme="dark"]) .patient-record-detail-grid > span {
  color: var(--dashboard-muted);
  border-color: var(--dashboard-border);
  background: #1b2635;
}

:global(html[data-dashboard-theme="dark"]) :is(.patient-record-balance, .patient-record-care-note) {
  background: #1d2c3e;
}

@media (max-width: 1180px) {
  .patient-records-layout {
    grid-template-columns: 1fr;
  }

  .patient-records-rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .patient-history-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .patient-record-tools {
    width: 100%;
  }

  .patient-records-rail {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 620px) {
  .patient-records-header {
    min-height: 0;
    align-items: flex-start;
    gap: 12px;
    border: 1px solid #dce7f2;
    border-radius: 8px;
    padding: 16px;
  }

  .patient-records-title-icon {
    width: 50px;
    height: 50px;
  }

  .patient-records-header h1 {
    font-size: 1.2rem;
  }

  .patient-records-panel {
    overflow: visible;
    border: 0;
    background: transparent;
    box-shadow: none;
  }

  .patient-history-heading {
    border: 1px solid #dce7f2;
    border-radius: 8px;
    background: #fff;
    padding: 14px;
  }

  .patient-record-tools {
    grid-template-columns: 1fr;
  }

  .patient-record-table-wrap {
    overflow: visible;
    margin-top: 10px;
  }

  .patient-records-table,
  .patient-records-table tbody,
  .patient-records-table tr,
  .patient-records-table td {
    display: block;
    width: 100%;
    min-width: 0;
  }

  .patient-records-table thead {
    display: none;
  }

  .patient-records-table tbody {
    display: grid;
    gap: 10px;
  }

  .patient-records-table tbody tr {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow: hidden;
    border: 1px solid #dce7f2;
    border-radius: 8px;
    background: #fff;
  }

  .patient-records-table td {
    display: grid;
    grid-template-columns: 88px minmax(0, 1fr);
    align-items: center;
    gap: 8px;
    border: 0;
    padding: 9px 12px;
    text-align: left !important;
  }

  .patient-records-table td::before {
    color: #71849c;
    font-size: 0.56rem;
    font-weight: 850;
    text-transform: uppercase;
    content: attr(data-label);
  }

  .patient-record-number {
    display: none !important;
  }

  .patient-record-treatment,
  .patient-record-notes,
  .patient-records-table td:nth-child(2),
  .patient-records-table td:nth-child(4) {
    grid-column: 1 / -1;
  }

  .patient-record-status,
  .patient-record-actions {
    display: flex !important;
    flex-direction: column;
    align-items: stretch !important;
  }

  .patient-record-status::before,
  .patient-record-actions::before {
    align-self: flex-start;
  }

  .patient-record-status :deep(.status),
  .patient-record-actions button {
    width: 100%;
  }

  .patient-records-empty-row {
    display: block !important;
  }

  .patient-records-empty-row td {
    display: block !important;
    height: auto;
    padding: 38px 18px !important;
  }

  .patient-records-empty-row td::before {
    display: none;
  }

  .patient-records-footer {
    align-items: stretch;
    flex-direction: column;
    margin-top: 10px;
    border: 1px solid #dce7f2;
    border-radius: 8px;
    background: #fff;
  }

  .patient-records-footer p,
  .patient-records-footer nav {
    justify-content: center;
    text-align: center;
  }

  .patient-record-detail-grid {
    grid-template-columns: 1fr;
  }

  .patient-record-detail-grid > span.wide {
    grid-column: auto;
  }

  :global(html[data-dashboard-theme="dark"])
    :is(
      .patient-records-header,
      .patient-history-heading,
      .patient-records-table tbody tr,
      .patient-records-footer
    ) {
    border-color: var(--dashboard-border);
    background: var(--dashboard-surface);
  }
}
</style>
