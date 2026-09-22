<script setup>
import {
  CalendarRange,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Search,
  Stethoscope,
  Users,
  WalletCards,
  X,
} from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import ActionIconButton from "../ActionIconButton.vue";
import AvatarBadge from "../AvatarBadge.vue";
import BaseModal from "../BaseModal.vue";
import StatusBadge from "../StatusBadge.vue";
import {
  formatDate,
  formatMoney,
  localDateIso,
  treatmentBalance,
  treatmentProcedure,
} from "../../services/format";

const props = defineProps({
  state: { type: Object, required: true },
  highlightedId: { type: String, default: "" },
});

const serviceSearch = ref("");
const selectedServiceId = ref("");
const startDate = ref("");
const endDate = ref("");
const currentPage = ref(1);
const detailRecord = ref(null);
const pageSize = 5;

function normalize(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

const filteredServices = computed(() => {
  const query = normalize(serviceSearch.value);
  if (!query) return props.state.services;
  return props.state.services.filter((service) =>
    normalize(`${service.name} ${service.description}`).includes(query),
  );
});

const selectedService = computed(
  () => props.state.services.find((service) => service.id === selectedServiceId.value) || null,
);

const dateRangeValid = computed(
  () => !startDate.value || !endDate.value || startDate.value <= endDate.value,
);

const selectedRecords = computed(() => {
  if (!selectedService.value || !dateRangeValid.value) return [];
  const serviceName = normalize(selectedService.value.name);
  return props.state.records
    .filter((record) => {
      const date = String(record.treatment_date || "").slice(0, 10);
      const matchesService = normalize(treatmentProcedure(record)) === serviceName;
      const afterStart = !startDate.value || (date && date >= startDate.value);
      const beforeEnd = !endDate.value || (date && date <= endDate.value);
      return matchesService && afterStart && beforeEnd;
    })
    .sort((a, b) =>
      `${b.treatment_date || ""} ${b.created_at || ""}`.localeCompare(
        `${a.treatment_date || ""} ${a.created_at || ""}`,
      ),
    );
});

const patientById = computed(
  () => new Map(props.state.patients.map((patient) => [patient.id, patient])),
);

const totalPatients = computed(
  () =>
    new Set(
      selectedRecords.value.map(
        (record) => record.patient_id || normalize(record.patient_name || "Patient"),
      ),
    ).size,
);
const completedRecords = computed(
  () => selectedRecords.value.filter((record) => treatmentBalance(record) <= 0).length,
);
const recordsWithBalance = computed(
  () => selectedRecords.value.filter((record) => treatmentBalance(record) > 0).length,
);

const pageCount = computed(() => Math.max(1, Math.ceil(selectedRecords.value.length / pageSize)));
const visibleRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return selectedRecords.value.slice(start, start + pageSize);
});
const pageNumbers = computed(() => {
  const visibleCount = Math.min(5, pageCount.value);
  let first = Math.max(1, currentPage.value - Math.floor(visibleCount / 2));
  first = Math.min(first, pageCount.value - visibleCount + 1);
  return Array.from({ length: visibleCount }, (_, index) => first + index);
});
const firstVisibleRecord = computed(() =>
  selectedRecords.value.length ? (currentPage.value - 1) * pageSize + 1 : 0,
);
const lastVisibleRecord = computed(() =>
  Math.min(currentPage.value * pageSize, selectedRecords.value.length),
);

watch(
  () => props.state.services.map((service) => service.id),
  (serviceIds) => {
    if (!serviceIds.length) {
      selectedServiceId.value = "";
      return;
    }
    if (!serviceIds.includes(selectedServiceId.value)) {
      selectedServiceId.value = serviceIds[0];
    }
  },
  { immediate: true },
);

watch(filteredServices, (services) => {
  if (services.length && !services.some((service) => service.id === selectedServiceId.value)) {
    selectedServiceId.value = services[0].id;
  }
});

watch([selectedServiceId, startDate, endDate], () => {
  currentPage.value = 1;
});

watch(pageCount, (count) => {
  if (currentPage.value > count) currentPage.value = count;
});

watch(
  () => props.highlightedId,
  (recordId) => {
    if (!recordId) return;
    const record = props.state.records.find((item) => item.id === recordId);
    if (!record) return;
    const service = props.state.services.find(
      (item) => normalize(item.name) === normalize(treatmentProcedure(record)),
    );
    if (service) selectedServiceId.value = service.id;
  },
  { immediate: true },
);

function recordStatus(record) {
  return record.payment_status || (treatmentBalance(record) > 0 ? "unpaid" : "paid");
}

function patientImage(record) {
  return patientById.value.get(record.patient_id)?.profile_image || "";
}

function clearDateRange() {
  startDate.value = "";
  endDate.value = "";
}

function selectPage(page) {
  currentPage.value = Math.min(Math.max(page, 1), pageCount.value);
}
</script>

<template>
  <section class="workspace-panel service-records-page">
    <header class="service-records-heading">
      <div>
        <span class="section-kicker">Clinic treatments</span>
        <h1>Service Records</h1>
        <p>Select a clinic service to see every patient treatment recorded for it.</p>
      </div>
    </header>

    <section class="service-records-catalog" aria-labelledby="service-catalog-title">
      <div class="service-records-catalog-heading">
        <div>
          <span class="service-records-title-icon">
            <Stethoscope :size="20" aria-hidden="true" />
          </span>
          <div>
            <h2 id="service-catalog-title">Dental Services</h2>
            <p>Choose a service to view its patient records.</p>
          </div>
        </div>
        <label class="service-records-search">
          <Search :size="17" aria-hidden="true" />
          <span class="sr-only">Search services</span>
          <input v-model="serviceSearch" type="search" placeholder="Search services..." />
        </label>
      </div>

      <div v-if="filteredServices.length" class="service-records-service-grid">
        <button
          v-for="service in filteredServices"
          :key="service.id"
          class="service-records-service-button"
          :class="{ active: selectedServiceId === service.id }"
          type="button"
          :aria-pressed="selectedServiceId === service.id"
          @click="selectedServiceId = service.id"
        >
          <Stethoscope :size="16" aria-hidden="true" />
          <span>{{ service.name }}</span>
        </button>
      </div>
      <p v-else class="service-records-empty-catalog">
        {{ state.services.length ? "No services match your search." : "No clinic services yet." }}
      </p>
    </section>

    <template v-if="selectedService">
      <div class="service-records-selection-heading">
        <div>
          <span class="service-records-selected-icon">
            <Stethoscope :size="21" aria-hidden="true" />
          </span>
          <div>
            <h2>{{ selectedService.name }}</h2>
            <p>
              {{ selectedService.description || "Patient treatment records for this service." }}
            </p>
          </div>
        </div>

        <div class="service-records-date-filter" :class="{ invalid: !dateRangeValid }">
          <CalendarRange :size="18" aria-hidden="true" />
          <label>
            <span>From</span>
            <input v-model="startDate" type="date" :max="endDate || localDateIso()" />
          </label>
          <span aria-hidden="true">to</span>
          <label>
            <span>To</span>
            <input v-model="endDate" type="date" :min="startDate" :max="localDateIso()" />
          </label>
          <button
            v-if="startDate || endDate"
            class="service-records-clear-dates"
            type="button"
            title="Clear date range"
            aria-label="Clear date range"
            @click="clearDateRange"
          >
            <X :size="16" aria-hidden="true" />
          </button>
        </div>
      </div>
      <p v-if="!dateRangeValid" class="service-records-date-error">
        The start date must be before the end date.
      </p>

      <div class="service-records-summary-grid" aria-label="Service record totals">
        <article class="service-records-summary-card total-patients">
          <span><Users :size="21" aria-hidden="true" /></span>
          <div>
            <strong>{{ totalPatients }}</strong>
            <small>Total Patients</small>
          </div>
        </article>
        <article class="service-records-summary-card total-records">
          <span><ClipboardList :size="21" aria-hidden="true" /></span>
          <div>
            <strong>{{ selectedRecords.length }}</strong>
            <small>Treatment Records</small>
          </div>
        </article>
        <article class="service-records-summary-card completed-records">
          <span><CheckCircle2 :size="21" aria-hidden="true" /></span>
          <div>
            <strong>{{ completedRecords }}</strong>
            <small>Fully Paid</small>
          </div>
        </article>
        <article class="service-records-summary-card balance-records">
          <span><WalletCards :size="21" aria-hidden="true" /></span>
          <div>
            <strong>{{ recordsWithBalance }}</strong>
            <small>With Balance</small>
          </div>
        </article>
      </div>

      <section class="service-records-table-panel" aria-labelledby="service-record-table-title">
        <div class="service-records-table-heading">
          <div>
            <h3 id="service-record-table-title">Patient Treatment History</h3>
            <p>Recorded visits for {{ selectedService.name }}.</p>
          </div>
          <span
            >{{ selectedRecords.length }} record{{ selectedRecords.length === 1 ? "" : "s" }}</span
          >
        </div>

        <div class="service-records-table-wrap">
          <table class="service-records-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Patient Name</th>
                <th>Date</th>
                <th>Dentist</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(record, index) in visibleRecords"
                :key="record.id"
                :data-entity-id="record.id"
                :class="{ 'notification-target-glow': highlightedId === record.id }"
              >
                <td>{{ (currentPage - 1) * pageSize + index + 1 }}</td>
                <td>
                  <div class="service-records-patient">
                    <AvatarBadge :name="record.patient_name" :image="patientImage(record)" />
                    <strong>{{ record.patient_name || "Patient" }}</strong>
                  </div>
                </td>
                <td>{{ formatDate(record.treatment_date) }}</td>
                <td>{{ record.doctor_name || state.clinicDoctor || "Clinic dentist" }}</td>
                <td><StatusBadge :status="recordStatus(record)" /></td>
                <td>
                  <ActionIconButton
                    action="view"
                    :label="`View ${record.patient_name || 'patient'} service record`"
                    @click="detailRecord = record"
                  />
                </td>
              </tr>
              <tr v-if="!visibleRecords.length">
                <td colspan="6" class="service-records-empty-table">
                  No patient treatment records found for this service and date range.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer v-if="selectedRecords.length" class="service-records-table-footer">
          <span>
            Showing {{ firstVisibleRecord }} to {{ lastVisibleRecord }} of
            {{ selectedRecords.length }} records
          </span>
          <nav v-if="pageCount > 1" class="service-records-pagination" aria-label="Record pages">
            <button
              type="button"
              title="Previous page"
              aria-label="Previous page"
              :disabled="currentPage === 1"
              @click="selectPage(currentPage - 1)"
            >
              <ChevronLeft :size="16" aria-hidden="true" />
            </button>
            <button
              v-for="page in pageNumbers"
              :key="page"
              type="button"
              :class="{ active: currentPage === page }"
              :aria-current="currentPage === page ? 'page' : undefined"
              :aria-label="`Page ${page}`"
              @click="selectPage(page)"
            >
              {{ page }}
            </button>
            <button
              type="button"
              title="Next page"
              aria-label="Next page"
              :disabled="currentPage === pageCount"
              @click="selectPage(currentPage + 1)"
            >
              <ChevronRight :size="16" aria-hidden="true" />
            </button>
          </nav>
        </footer>
      </section>
    </template>

    <section v-else class="service-records-no-service">
      <Stethoscope :size="30" aria-hidden="true" />
      <h2>No service selected</h2>
      <p>Add a clinic service in Services &amp; Content to begin organizing its records.</p>
    </section>

    <BaseModal
      v-if="detailRecord"
      title="Service Record Details"
      :eyebrow="treatmentProcedure(detailRecord)"
      @close="detailRecord = null"
    >
      <div class="detail-grid">
        <span
          ><strong>{{ detailRecord.patient_name || "Patient" }}</strong
          >Patient</span
        >
        <span
          ><strong>{{ formatDate(detailRecord.treatment_date) }}</strong
          >Date</span
        >
        <span
          ><strong>{{ detailRecord.doctor_name || state.clinicDoctor || "-" }}</strong
          >Dentist</span
        >
        <span
          ><strong>{{ detailRecord.tooth_numbers || "-" }}</strong
          >Tooth No./s</span
        >
        <span
          ><strong>{{ formatMoney(detailRecord.amount_charged) }}</strong
          >Charged</span
        >
        <span
          ><strong>{{ formatMoney(detailRecord.amount_paid) }}</strong
          >Paid</span
        >
        <span
          ><strong>{{ formatMoney(treatmentBalance(detailRecord)) }}</strong
          >Balance</span
        >
        <span
          ><strong>{{ detailRecord.remarks || detailRecord.notes || "-" }}</strong
          >Remarks</span
        >
      </div>
    </BaseModal>
  </section>
</template>

<style scoped>
.service-records-page {
  --records-soft: #f7f9fc;
  --records-hover: #f4f8ff;
  --records-header: #f0f5fb;
  --records-blue-soft: #eaf2ff;
  --records-green-soft: #e9f8f1;
  --records-amber-soft: #fff5e5;
  display: grid;
  gap: 18px;
}

.service-records-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 20px;
  padding: 2px 2px 0;
}

.service-records-heading h1,
.service-records-catalog h2,
.service-records-selection-heading h2,
.service-records-table-heading h3,
.service-records-no-service h2 {
  margin: 0;
  color: var(--dashboard-text);
}

.service-records-heading h1 {
  margin-top: 3px;
  font-size: 1.55rem;
}

.service-records-heading p,
.service-records-catalog-heading p,
.service-records-selection-heading p,
.service-records-table-heading p,
.service-records-no-service p {
  margin: 4px 0 0;
  color: var(--dashboard-muted);
  font-size: 0.82rem;
}

.service-records-catalog,
.service-records-table-panel,
.service-records-no-service {
  border: 1px solid var(--dashboard-border);
  border-radius: 8px;
  background: var(--dashboard-surface);
  box-shadow: 0 5px 18px rgba(25, 39, 68, 0.045);
}

.service-records-catalog {
  padding: 15px;
}

.service-records-catalog-heading,
.service-records-selection-heading,
.service-records-table-heading,
.service-records-table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.service-records-catalog-heading > div,
.service-records-selection-heading > div:first-child {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.service-records-catalog-heading h2,
.service-records-selection-heading h2 {
  font-size: 1rem;
}

.service-records-title-icon,
.service-records-selected-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border-radius: 8px;
  background: #dff7f2;
  color: #07806e;
}

.service-records-search {
  display: flex;
  width: min(100%, 300px);
  min-height: 40px;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--dashboard-border);
  border-radius: 7px;
  background: var(--dashboard-surface);
  padding: 0 11px;
  color: var(--dashboard-muted);
}

.service-records-search:focus-within {
  border-color: var(--dashboard-blue);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.service-records-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--dashboard-text);
  box-shadow: none;
}

.service-records-service-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
  gap: 7px;
  margin-top: 14px;
}

.service-records-service-button {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  min-height: 46px;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--dashboard-border);
  border-radius: 7px;
  background: var(--records-soft);
  padding: 8px 10px;
  color: var(--dashboard-text);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 150ms ease,
    background 150ms ease,
    color 150ms ease,
    transform 150ms ease;
}

.service-records-service-button svg {
  color: var(--dashboard-blue);
}

.service-records-service-button span {
  overflow-wrap: anywhere;
  font-size: 0.72rem;
  font-weight: 750;
  line-height: 1.22;
}

.service-records-service-button:hover,
.service-records-service-button:focus-visible {
  border-color: #a9c4f6;
  background: var(--records-hover);
  outline: 0;
  transform: translateY(-1px);
}

.service-records-service-button.active {
  border-color: var(--dashboard-blue);
  background: var(--dashboard-blue);
  color: #ffffff;
}

.service-records-service-button.active svg {
  color: #ffffff;
}

.service-records-empty-catalog {
  margin: 14px 0 0;
  border: 1px dashed var(--dashboard-border);
  border-radius: 7px;
  padding: 18px;
  color: var(--dashboard-muted);
  text-align: center;
}

.service-records-selection-heading {
  align-items: end;
  padding: 2px 2px 0;
}

.service-records-date-filter {
  display: flex;
  min-height: 42px;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--dashboard-border);
  border-radius: 7px;
  background: var(--dashboard-surface);
  padding: 5px 7px 5px 10px;
  color: var(--dashboard-muted);
}

.service-records-date-filter.invalid {
  border-color: #ef4444;
}

.service-records-date-filter label {
  display: flex;
  align-items: center;
  gap: 5px;
}

.service-records-date-filter label span {
  color: var(--dashboard-muted);
  font-size: 0.68rem;
  font-weight: 750;
}

.service-records-date-filter input {
  width: 126px;
  min-height: 30px;
  border: 0;
  background: transparent;
  padding: 2px;
  color: var(--dashboard-text);
  font-size: 0.75rem;
  box-shadow: none;
}

.service-records-clear-dates {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 0;
  border-radius: 6px;
  background: var(--records-soft);
  color: var(--dashboard-muted);
  cursor: pointer;
}

.service-records-clear-dates:hover,
.service-records-clear-dates:focus-visible {
  background: #fee2e2;
  color: #b91c1c;
  outline: 0;
}

.service-records-date-error {
  margin: -10px 2px 0;
  color: #b91c1c;
  font-size: 0.76rem;
  font-weight: 700;
  text-align: right;
}

.service-records-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.service-records-summary-card {
  display: flex;
  min-height: 82px;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--dashboard-border);
  border-radius: 8px;
  background: var(--dashboard-surface);
  padding: 13px 15px;
}

.service-records-summary-card > span {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  place-items: center;
  border-radius: 8px;
}

.service-records-summary-card > div {
  display: grid;
  gap: 2px;
}

.service-records-summary-card strong {
  color: var(--dashboard-text);
  font-size: 1.15rem;
}

.service-records-summary-card small {
  color: var(--dashboard-muted);
  font-size: 0.72rem;
}

.total-patients > span,
.total-records > span {
  background: var(--records-blue-soft);
  color: var(--dashboard-blue);
}

.completed-records > span {
  background: var(--records-green-soft);
  color: #059669;
}

.balance-records > span {
  background: var(--records-amber-soft);
  color: #d97706;
}

.service-records-table-panel {
  overflow: hidden;
}

.service-records-table-heading {
  padding: 14px 16px;
  border-bottom: 1px solid var(--dashboard-border);
}

.service-records-table-heading h3 {
  font-size: 0.92rem;
}

.service-records-table-heading > span {
  flex: 0 0 auto;
  color: var(--dashboard-muted);
  font-size: 0.72rem;
  font-weight: 750;
}

.service-records-table-wrap {
  overflow-x: auto;
}

.service-records-table {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
}

.service-records-table th,
.service-records-table td {
  padding: 11px 14px;
  border-bottom: 1px solid var(--dashboard-border);
  color: var(--dashboard-text);
  font-size: 0.76rem;
  text-align: left;
  vertical-align: middle;
}

.service-records-table th {
  background: var(--records-header);
  color: var(--dashboard-muted);
  font-size: 0.66rem;
  text-transform: uppercase;
}

.service-records-table th:first-child,
.service-records-table td:first-child {
  width: 46px;
  text-align: center;
}

.service-records-table th:last-child,
.service-records-table td:last-child {
  width: 74px;
  text-align: center;
}

.service-records-table tbody tr:hover {
  background: var(--records-hover);
}

.service-records-table tbody tr:last-child td {
  border-bottom: 0;
}

.service-records-patient {
  display: flex;
  min-width: 170px;
  align-items: center;
  gap: 9px;
}

.service-records-patient :deep(.profile-avatar) {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  margin: 0;
  font-size: 0.62rem;
}

.service-records-table :deep(.status) {
  min-width: 66px;
  justify-content: center;
  padding: 4px 8px;
  font-size: 0.62rem;
}

.service-records-table :deep(.action-icon-button) {
  width: 30px;
  height: 30px;
  min-height: 30px;
  padding: 0;
}

.service-records-empty-table {
  height: 96px;
  color: var(--dashboard-muted) !important;
  text-align: center !important;
}

.service-records-table-footer {
  min-height: 54px;
  padding: 9px 14px;
  border-top: 1px solid var(--dashboard-border);
}

.service-records-table-footer > span {
  color: var(--dashboard-muted);
  font-size: 0.7rem;
}

.service-records-pagination {
  display: flex;
  gap: 5px;
}

.service-records-pagination button {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 1px solid var(--dashboard-border);
  border-radius: 6px;
  background: var(--dashboard-surface);
  color: var(--dashboard-text);
  font-size: 0.72rem;
  font-weight: 750;
  cursor: pointer;
}

.service-records-pagination button:hover:not(:disabled),
.service-records-pagination button:focus-visible {
  border-color: var(--dashboard-blue);
  color: var(--dashboard-blue);
  outline: 0;
}

.service-records-pagination button.active {
  border-color: var(--dashboard-blue);
  background: var(--dashboard-blue);
  color: #ffffff;
}

.service-records-pagination button:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.service-records-no-service {
  display: grid;
  min-height: 230px;
  place-items: center;
  align-content: center;
  gap: 7px;
  padding: 28px;
  color: var(--dashboard-muted);
  text-align: center;
}

.service-records-no-service h2 {
  font-size: 1rem;
}

:global(html[data-dashboard-theme="dark"]) .service-records-page {
  --records-soft: #111823;
  --records-hover: #202938;
  --records-header: #121923;
  --records-blue-soft: #1d2d49;
  --records-green-soft: #123328;
  --records-amber-soft: #3a2b16;
}

:global(html[data-dashboard-theme="dark"]) .service-records-title-icon,
:global(html[data-dashboard-theme="dark"]) .service-records-selected-icon {
  background: #12362f;
  color: #5eead4;
}

@media (max-width: 1050px) {
  .service-records-selection-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .service-records-date-filter {
    align-self: start;
  }

  .service-records-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .service-records-heading,
  .service-records-catalog-heading,
  .service-records-table-heading,
  .service-records-table-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .service-records-search {
    width: 100%;
  }

  .service-records-service-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .service-records-date-filter {
    width: 100%;
    flex-wrap: wrap;
  }

  .service-records-date-filter label {
    flex: 1 1 130px;
  }

  .service-records-date-filter input {
    width: 100%;
  }

  .service-records-table-footer {
    gap: 10px;
  }

  .service-records-pagination {
    align-self: end;
  }
}

@media (max-width: 480px) {
  .service-records-page {
    gap: 14px;
  }

  .service-records-catalog {
    padding: 12px;
  }

  .service-records-service-grid,
  .service-records-summary-grid {
    grid-template-columns: 1fr;
  }

  .service-records-service-button {
    min-height: 42px;
  }

  .service-records-summary-card {
    min-height: 70px;
  }
}
</style>
