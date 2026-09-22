<script setup>
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Plus,
  Search,
  Stethoscope,
  Trash2,
  UserRound,
  X,
} from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { formatDate, localDateIso, statusLabel } from "../../services/format";
import StatusBadge from "../StatusBadge.vue";

const props = defineProps({
  appointments: { type: Array, default: () => [] },
  services: { type: Array, default: () => [] },
  highlightedId: { type: String, default: "" },
});

const emit = defineEmits(["book", "cancel"]);

const activeFilter = ref("all");
const searchQuery = ref("");
const selectedDate = ref("");
const currentPage = ref(1);
const pageSize = 7;
const todayIso = localDateIso();
const activeStatuses = new Set(["pending", "approved", "accepted"]);

const filters = [
  { value: "all", label: "All" },
  { value: "upcoming", label: "Upcoming" },
  { value: "past", label: "Past" },
  { value: "cancelled", label: "Cancelled" },
];

function normalizedStatus(item) {
  return String(item?.status || "").toLowerCase();
}

function formatTime(value) {
  const text = String(value || "").trim();
  if (!text) return "-";
  if (/\b(?:am|pm)\b/i.test(text)) {
    return text.replace(/\b(am|pm)\b/i, (part) => part.toUpperCase());
  }
  const match = /^(\d{1,2}):(\d{2})/.exec(text);
  if (!match) return text;
  const hours = Number(match[1]);
  const suffix = hours >= 12 ? "PM" : "AM";
  return `${String(hours % 12 || 12).padStart(2, "0")}:${match[2]} ${suffix}`;
}

function sortableTime(value) {
  const text = String(value || "").trim();
  const twentyFourHour = /^(\d{1,2}):(\d{2})/.exec(text);
  if (twentyFourHour && !/\b(?:am|pm)\b/i.test(text)) {
    return `${String(Number(twentyFourHour[1])).padStart(2, "0")}:${twentyFourHour[2]}`;
  }
  const twelveHour = /^(\d{1,2}):(\d{2})\s*(am|pm)$/i.exec(text);
  if (!twelveHour) return text;
  let hours = Number(twelveHour[1]) % 12;
  if (twelveHour[3].toLowerCase() === "pm") hours += 12;
  return `${String(hours).padStart(2, "0")}:${twelveHour[2]}`;
}

function appointmentKey(item) {
  return `${String(item?.date || "").slice(0, 10)} ${sortableTime(item?.time)}`;
}

function serviceCategory(serviceName) {
  const name = String(serviceName || "").toLowerCase();
  const service = props.services.find((item) => String(item?.name || "").toLowerCase() === name);
  if (service?.category) return service.category;
  if (/brace|aligner|retainer|space maintainer|expander|orthodont/.test(name)) {
    return "Orthodontics";
  }
  if (/denture|bridge|crown|veneer/.test(name)) return "Prosthodontics";
  if (/odontectomy|apicoectomy|extract|gingiv/.test(name)) return "Oral Surgery";
  if (/root canal/.test(name)) return "Endodontics";
  if (/whitening/.test(name)) return "Cosmetic Dentistry";
  if (/prophylaxis|fluoride|sealant/.test(name)) return "Preventive Care";
  return "General Dentistry";
}

function serviceTone(serviceName) {
  const tones = ["blue", "gold", "purple", "coral", "mint"];
  const hash = [...String(serviceName || "")].reduce(
    (total, character) => total + character.charCodeAt(0),
    0,
  );
  return tones[hash % tones.length];
}

function matchesFilter(item) {
  const status = normalizedStatus(item);
  const appointmentDate = String(item?.date || "").slice(0, 10);
  if (activeFilter.value === "upcoming") {
    return appointmentDate >= todayIso && activeStatuses.has(status);
  }
  if (activeFilter.value === "past") {
    return status !== "cancelled" && (appointmentDate < todayIso || status === "completed");
  }
  if (activeFilter.value === "cancelled") return status === "cancelled";
  return true;
}

function matchesSearch(item) {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) return true;
  return [
    item?.service,
    serviceCategory(item?.service),
    item?.doctor,
    item?.date,
    formatDate(item?.date),
    item?.time,
    formatTime(item?.time),
    statusLabel(normalizedStatus(item)),
  ].some((value) =>
    String(value || "")
      .toLowerCase()
      .includes(query),
  );
}

const filteredAppointments = computed(() => {
  const items = props.appointments.filter((item) => {
    const dateMatches =
      !selectedDate.value || String(item?.date || "").slice(0, 10) === selectedDate.value;
    return matchesFilter(item) && dateMatches && matchesSearch(item);
  });
  const direction = activeFilter.value === "upcoming" ? 1 : -1;
  return [...items].sort((a, b) => direction * appointmentKey(a).localeCompare(appointmentKey(b)));
});

const pageCount = computed(() =>
  Math.max(1, Math.ceil(filteredAppointments.value.length / pageSize)),
);
const pageStart = computed(() =>
  filteredAppointments.value.length ? (currentPage.value - 1) * pageSize + 1 : 0,
);
const pageEnd = computed(() =>
  Math.min(currentPage.value * pageSize, filteredAppointments.value.length),
);
const pagedAppointments = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredAppointments.value.slice(start, start + pageSize);
});

const visiblePages = computed(() => {
  const total = pageCount.value;
  if (total <= 3) return Array.from({ length: total }, (_, index) => index + 1);
  const start = Math.min(Math.max(1, currentPage.value - 1), total - 2);
  return [start, start + 1, start + 2];
});

function canCancel(item) {
  return !["cancelled", "completed"].includes(normalizedStatus(item));
}

function selectFilter(value) {
  activeFilter.value = value;
}

function clearDate() {
  selectedDate.value = "";
}

watch([activeFilter, searchQuery, selectedDate], () => {
  currentPage.value = 1;
});

watch(pageCount, (total) => {
  currentPage.value = Math.min(currentPage.value, total);
});

watch(
  () => props.highlightedId,
  (id) => {
    if (!id) return;
    activeFilter.value = "all";
    searchQuery.value = "";
    selectedDate.value = "";
    const index = filteredAppointments.value.findIndex((item) => item.id === id);
    currentPage.value = index < 0 ? 1 : Math.floor(index / pageSize) + 1;
  },
  { immediate: true },
);
</script>

<template>
  <section class="workspace-panel patient-visits-page">
    <div class="patient-visits-surface">
      <header class="patient-visits-header">
        <div class="patient-visits-title">
          <span class="patient-visits-title-icon">
            <CalendarDays :size="30" aria-hidden="true" />
          </span>
          <div>
            <span class="patient-visits-kicker">Appointments</span>
            <h1>My schedule</h1>
            <p>View and manage your upcoming and past appointments.</p>
          </div>
        </div>
        <button class="patient-new-appointment" type="button" @click="emit('book')">
          <Plus :size="20" aria-hidden="true" />
          <span>Book New Appointment</span>
        </button>
      </header>

      <div class="patient-visits-toolbar">
        <div class="patient-visit-tabs" role="tablist" aria-label="Filter appointments">
          <button
            v-for="filter in filters"
            :key="filter.value"
            type="button"
            role="tab"
            :aria-selected="activeFilter === filter.value"
            :class="{ active: activeFilter === filter.value }"
            @click="selectFilter(filter.value)"
          >
            {{ filter.label }}
          </button>
        </div>

        <div class="patient-visit-tools">
          <label class="patient-visit-search">
            <span class="sr-only">Search appointments</span>
            <Search :size="19" aria-hidden="true" />
            <input
              v-model="searchQuery"
              type="search"
              placeholder="Search service, date, or status..."
            />
          </label>
          <label class="patient-visit-date">
            <span class="sr-only">Filter appointments by date</span>
            <CalendarDays :size="19" aria-hidden="true" />
            <input v-model="selectedDate" type="date" title="Filter appointments by date" />
            <button
              v-if="selectedDate"
              type="button"
              aria-label="Clear date filter"
              title="Clear date filter"
              @click.prevent="clearDate"
            >
              <X :size="16" aria-hidden="true" />
            </button>
          </label>
        </div>
      </div>

      <div class="patient-visits-table-wrap">
        <table class="patient-visits-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Service</th>
              <th>Dentist</th>
              <th>Date &amp; Time</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(item, index) in pagedAppointments"
              :key="item.id"
              :data-entity-id="item.id"
              :class="{ 'notification-target-glow': highlightedId === item.id }"
            >
              <td class="patient-visit-number" data-label="#">{{ pageStart + index }}</td>
              <td class="patient-visit-service" data-label="Service">
                <div class="patient-service-content">
                  <span class="patient-service-icon" :class="`tone-${serviceTone(item.service)}`">
                    <Stethoscope :size="21" aria-hidden="true" />
                  </span>
                  <span>
                    <strong>{{ item.service }}</strong>
                    <small>{{ serviceCategory(item.service) }}</small>
                  </span>
                </div>
              </td>
              <td class="patient-visit-dentist" data-label="Dentist">
                <span class="patient-dentist-content">
                  <UserRound :size="18" aria-hidden="true" />
                  <span>{{ item.doctor || "Clinic dentist" }}</span>
                </span>
              </td>
              <td class="patient-visit-when" data-label="Date & Time">
                <span class="patient-date-time">
                  <span
                    ><CalendarDays :size="16" aria-hidden="true" />{{ formatDate(item.date) }}</span
                  >
                  <span><Clock3 :size="16" aria-hidden="true" />{{ formatTime(item.time) }}</span>
                </span>
              </td>
              <td class="patient-visit-status" data-label="Status">
                <StatusBadge :status="item.status" />
              </td>
              <td class="patient-visit-action" data-label="Actions">
                <button
                  v-if="canCancel(item)"
                  type="button"
                  :aria-label="`Cancel ${item.service} appointment`"
                  @click="emit('cancel', item)"
                >
                  <Trash2 :size="16" aria-hidden="true" />
                  Cancel
                </button>
                <span v-else>No action</span>
              </td>
            </tr>
            <tr v-if="!pagedAppointments.length" class="patient-visits-empty-row">
              <td colspan="6">
                <span><CalendarDays :size="28" aria-hidden="true" /></span>
                <strong>No appointments found</strong>
                <small>Try another filter or book a new appointment.</small>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="patient-visits-footer">
        <p>
          Showing {{ pageStart }} to {{ pageEnd }} of {{ filteredAppointments.length }}
          {{ filteredAppointments.length === 1 ? "appointment" : "appointments" }}
        </p>
        <nav v-if="filteredAppointments.length" aria-label="Appointment pages">
          <button
            type="button"
            aria-label="Previous page"
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
            :aria-label="`Page ${page}`"
            @click="currentPage = page"
          >
            {{ page }}
          </button>
          <button
            type="button"
            aria-label="Next page"
            :disabled="currentPage === pageCount"
            @click="currentPage += 1"
          >
            <ChevronRight :size="18" aria-hidden="true" />
          </button>
        </nav>
      </footer>
    </div>
  </section>
</template>

<style scoped>
.patient-visits-page {
  color: #172d50;
}

.patient-visits-surface {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #dce7f2;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 6px 20px rgb(31 64 102 / 5%);
}

.patient-visits-header {
  display: flex;
  min-height: 112px;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 17px 22px;
  border-bottom: 1px solid #e4edf5;
  background: linear-gradient(90deg, #f5faff 0%, #fbfdff 68%, #eef7ff 100%);
}

.patient-visits-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 18px;
}

.patient-visits-title-icon {
  display: grid;
  width: 66px;
  height: 66px;
  flex: 0 0 66px;
  place-items: center;
  border: 1px solid #c8defa;
  border-radius: 8px;
  background: #e6f1ff;
  color: #1875e4;
}

.patient-visits-title > div {
  min-width: 0;
}

.patient-visits-kicker,
.patient-visits-header h1,
.patient-visits-header p {
  margin: 0;
}

.patient-visits-kicker {
  color: #1470dc;
  font-size: 0.72rem;
  font-weight: 850;
  text-transform: uppercase;
}

.patient-visits-header h1 {
  margin-top: 2px;
  color: #12294d;
  font-size: 1.45rem;
  line-height: 1.18;
}

.patient-visits-header p {
  margin-top: 3px;
  color: #687d98;
  font-size: 0.76rem;
}

.patient-new-appointment {
  display: inline-flex;
  min-height: 48px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px solid #126dd8;
  border-radius: 7px;
  background: #1477e8;
  padding: 10px 20px;
  color: #fff;
  font-size: 0.77rem;
  font-weight: 800;
  cursor: pointer;
  transition:
    background 160ms ease,
    box-shadow 160ms ease,
    transform 160ms ease;
}

.patient-new-appointment:hover,
.patient-new-appointment:focus-visible {
  background: #105fbe;
  box-shadow: 0 0 0 3px rgb(20 119 232 / 16%);
  outline: none;
  transform: translateY(-1px);
}

.patient-visits-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 22px;
  border-bottom: 1px solid #e5edf5;
}

.patient-visit-tabs {
  display: flex;
  min-width: 0;
  gap: 6px;
}

.patient-visit-tabs button {
  min-width: 92px;
  min-height: 38px;
  border: 1px solid #e0e8f1;
  border-radius: 6px;
  background: #f3f6fa;
  padding: 8px 13px;
  color: #526a88;
  font-size: 0.7rem;
  font-weight: 750;
  cursor: pointer;
}

.patient-visit-tabs button:hover,
.patient-visit-tabs button:focus-visible,
.patient-visit-tabs button.active {
  border-color: #1575e4;
  background: #1575e4;
  color: #fff;
  outline: none;
}

.patient-visit-tools {
  display: grid;
  grid-template-columns: minmax(240px, 330px) minmax(190px, 220px);
  gap: 10px;
}

.patient-visit-search,
.patient-visit-date {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 42px;
  align-items: center;
  gap: 10px;
  border: 1px solid #d7e2ee;
  border-radius: 7px;
  background: #fff;
  padding: 0 12px;
  color: #516987;
}

.patient-visit-search:focus-within,
.patient-visit-date:focus-within {
  border-color: #1475e4;
  box-shadow: 0 0 0 3px rgb(20 117 228 / 12%);
}

.patient-visit-search > svg,
.patient-visit-date > svg {
  flex: 0 0 auto;
}

.patient-visit-search input,
.patient-visit-date input {
  width: 100%;
  min-width: 0;
  height: 40px;
  border: 0;
  background: transparent;
  padding: 0;
  color: #263f61;
  font: inherit;
  font-size: 0.7rem;
  outline: none;
  box-shadow: none !important;
}

.patient-visit-search input::placeholder {
  color: #8494a8;
}

.patient-visit-date button {
  display: grid;
  width: 26px;
  height: 26px;
  flex: 0 0 26px;
  place-items: center;
  border: 0;
  border-radius: 6px;
  background: #eef4fb;
  padding: 0;
  color: #536b88;
  cursor: pointer;
}

.patient-visits-table-wrap {
  width: 100%;
  min-width: 0;
  overflow-x: auto;
}

.patient-visits-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  color: #2a4365;
  font-size: 0.72rem;
}

.patient-visits-table th,
.patient-visits-table td {
  border-bottom: 1px solid #e5edf4;
  padding: 11px 14px;
  text-align: left;
  vertical-align: middle;
}

.patient-visits-table th {
  background: #eff5fa;
  color: #536985;
  font-size: 0.63rem;
  font-weight: 850;
  text-transform: uppercase;
}

.patient-visits-table th:nth-child(1) {
  width: 5%;
  text-align: center;
}

.patient-visits-table th:nth-child(2) {
  width: 30%;
}

.patient-visits-table th:nth-child(3) {
  width: 19%;
}

.patient-visits-table th:nth-child(4) {
  width: 17%;
}

.patient-visits-table th:nth-child(5) {
  width: 14%;
}

.patient-visits-table th:nth-child(6) {
  width: 15%;
  text-align: right;
}

.patient-visits-table tbody tr {
  transition:
    background 150ms ease,
    box-shadow 150ms ease;
}

.patient-visits-table tbody tr:hover {
  background: #f9fcff;
}

.patient-visit-number {
  color: #344f73;
  font-weight: 750;
  text-align: center !important;
}

.patient-service-content {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
}

.patient-service-icon {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 50%;
  background: #e4f1ff;
  color: #1d78e8;
}

.patient-service-icon.tone-gold {
  background: #fff2db;
  color: #c57d08;
}

.patient-service-icon.tone-purple {
  background: #eee9ff;
  color: #6655da;
}

.patient-service-icon.tone-coral {
  background: #ffe9e6;
  color: #d75b51;
}

.patient-service-icon.tone-mint {
  background: #ddf6ef;
  color: #0a9871;
}

.patient-service-content > span:last-child,
.patient-visit-service strong,
.patient-visit-service small {
  display: block;
  min-width: 0;
}

.patient-visit-service strong {
  overflow-wrap: anywhere;
  color: #142e53;
  font-size: 0.75rem;
  line-height: 1.25;
}

.patient-visit-service small {
  margin-top: 3px;
  color: #6c809a;
  font-size: 0.64rem;
}

.patient-dentist-content,
.patient-date-time > span {
  display: flex;
  align-items: center;
  gap: 8px;
}

.patient-dentist-content svg,
.patient-date-time svg {
  flex: 0 0 auto;
  color: #496482;
}

.patient-dentist-content > span {
  overflow-wrap: anywhere;
}

.patient-date-time {
  display: grid;
  gap: 4px;
}

.patient-visit-status :deep(.status) {
  min-width: 92px;
  justify-content: center;
  font-size: 0.64rem;
}

.patient-visit-action {
  text-align: right !important;
}

.patient-visit-action button {
  display: inline-flex;
  min-width: 92px;
  min-height: 34px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid #ff9aa4;
  border-radius: 6px;
  background: #fff8f8;
  padding: 7px 11px;
  color: #df2436;
  font-size: 0.66rem;
  font-weight: 800;
  cursor: pointer;
}

.patient-visit-action button:hover,
.patient-visit-action button:focus-visible {
  border-color: #df2436;
  background: #fff0f1;
  outline: 3px solid rgb(223 36 54 / 12%);
}

.patient-visit-action > span {
  color: #71839a;
  font-size: 0.68rem;
}

.patient-visits-empty-row:hover {
  background: transparent !important;
}

.patient-visits-empty-row td {
  height: 230px;
  text-align: center;
}

.patient-visits-empty-row td > span {
  display: grid;
  width: 52px;
  height: 52px;
  margin: 0 auto 10px;
  place-items: center;
  border-radius: 8px;
  background: #eaf3fe;
  color: #1d75df;
}

.patient-visits-empty-row strong,
.patient-visits-empty-row small {
  display: block;
}

.patient-visits-empty-row strong {
  color: #253f63;
  font-size: 0.82rem;
}

.patient-visits-empty-row small {
  margin-top: 4px;
  color: #70839b;
  font-size: 0.68rem;
}

.patient-visits-footer {
  display: flex;
  min-height: 66px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 22px;
}

.patient-visits-footer p {
  margin: 0;
  color: #667c98;
  font-size: 0.7rem;
}

.patient-visits-footer nav {
  display: flex;
  gap: 7px;
}

.patient-visits-footer nav button {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border: 1px solid #dce6f0;
  border-radius: 6px;
  background: #fff;
  padding: 0;
  color: #3f5a7c;
  font-size: 0.7rem;
  font-weight: 800;
  cursor: pointer;
}

.patient-visits-footer nav button:hover:not(:disabled),
.patient-visits-footer nav button:focus-visible,
.patient-visits-footer nav button.active {
  border-color: #1475e4;
  background: #1475e4;
  color: #fff;
  outline: none;
}

.patient-visits-footer nav button:disabled {
  color: #b4c0ce;
  cursor: not-allowed;
}

:global(html[data-dashboard-theme="dark"]) .patient-visits-page {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"]) .patient-visits-surface,
:global(html[data-dashboard-theme="dark"]) .patient-visit-search,
:global(html[data-dashboard-theme="dark"]) .patient-visit-date,
:global(html[data-dashboard-theme="dark"]) .patient-visits-footer nav button {
  border-color: var(--dashboard-border);
  background: var(--dashboard-surface);
}

:global(html[data-dashboard-theme="dark"]) .patient-visits-header {
  border-color: var(--dashboard-border);
  background: #19283a;
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .patient-visits-header h1,
    .patient-visit-search input,
    .patient-visit-date input,
    .patient-visits-table,
    .patient-visit-service strong
  ) {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .patient-visits-header p,
    .patient-visit-service small,
    .patient-visit-action > span,
    .patient-visits-footer p
  ) {
  color: var(--dashboard-muted);
}

:global(html[data-dashboard-theme="dark"]) .patient-visits-toolbar,
:global(html[data-dashboard-theme="dark"]) .patient-visits-header,
:global(html[data-dashboard-theme="dark"]) .patient-visits-table th,
:global(html[data-dashboard-theme="dark"]) .patient-visits-table td {
  border-color: var(--dashboard-border);
}

:global(html[data-dashboard-theme="dark"]) .patient-visits-table th,
:global(html[data-dashboard-theme="dark"]) .patient-visit-tabs button {
  border-color: var(--dashboard-border);
  background: #1e2d3f;
  color: var(--dashboard-muted);
}

:global(html[data-dashboard-theme="dark"]) .patient-visits-table tbody tr:hover {
  background: #1b293a;
}

@media (max-width: 1180px) {
  .patient-visits-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .patient-visit-tools {
    grid-template-columns: minmax(240px, 1fr) minmax(180px, 0.55fr);
  }
}

@media (max-width: 820px) {
  .patient-visits-header {
    align-items: stretch;
    flex-direction: column;
  }

  .patient-new-appointment {
    align-self: flex-start;
  }

  .patient-visit-tabs {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .patient-visit-tabs button {
    min-width: 0;
  }

  .patient-visits-table {
    min-width: 870px;
  }
}

@media (max-width: 620px) {
  .patient-visits-surface {
    overflow: visible;
    border: 0;
    background: transparent;
    box-shadow: none;
  }

  .patient-visits-header {
    min-height: 0;
    gap: 16px;
    border: 1px solid #dce7f2;
    border-radius: 8px;
    padding: 16px;
  }

  .patient-visits-title {
    align-items: flex-start;
    gap: 12px;
  }

  .patient-visits-title-icon {
    width: 50px;
    height: 50px;
    flex-basis: 50px;
  }

  .patient-visits-header h1 {
    font-size: 1.2rem;
  }

  .patient-visits-header p {
    font-size: 0.69rem;
    line-height: 1.45;
  }

  .patient-new-appointment {
    width: 100%;
  }

  .patient-visits-toolbar {
    gap: 10px;
    margin-top: 10px;
    border: 1px solid #dce7f2;
    border-radius: 8px;
    background: #fff;
    padding: 12px;
  }

  .patient-visit-tabs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .patient-visit-tools {
    grid-template-columns: 1fr;
  }

  .patient-visits-table-wrap {
    overflow: visible;
    margin-top: 10px;
  }

  .patient-visits-table,
  .patient-visits-table tbody,
  .patient-visits-table tr,
  .patient-visits-table td {
    display: block;
    width: 100%;
    min-width: 0;
  }

  .patient-visits-table thead {
    display: none;
  }

  .patient-visits-table tbody {
    display: grid;
    gap: 10px;
  }

  .patient-visits-table tbody tr {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow: hidden;
    border: 1px solid #dce7f2;
    border-radius: 8px;
    background: #fff;
    box-shadow: 0 4px 14px rgb(31 64 102 / 4%);
  }

  .patient-visits-table td {
    display: grid;
    grid-template-columns: 76px minmax(0, 1fr);
    align-items: center;
    gap: 8px;
    border: 0;
    padding: 9px 12px;
    text-align: left !important;
  }

  .patient-visits-table td::before {
    color: #71849c;
    font-size: 0.57rem;
    font-weight: 850;
    text-transform: uppercase;
    content: attr(data-label);
  }

  .patient-visit-number {
    display: none !important;
  }

  .patient-visit-service,
  .patient-visit-dentist,
  .patient-visit-when {
    grid-column: 1 / -1;
  }

  .patient-visits-table td.patient-visit-service {
    display: block;
    border-bottom: 1px solid #e8eef5 !important;
    padding-block: 12px !important;
  }

  .patient-visit-service::before {
    display: none;
  }

  .patient-dentist-content,
  .patient-date-time {
    grid-column: 2;
  }

  .patient-dentist-content {
    min-width: 0;
  }

  .patient-date-time {
    display: grid;
  }

  .patient-visit-when::before {
    grid-row: 1;
  }

  .patient-visit-status,
  .patient-visit-action {
    display: flex;
    flex-direction: column;
    align-content: center;
    align-items: stretch;
  }

  .patient-visit-status::before,
  .patient-visit-action::before {
    align-self: flex-start;
  }

  .patient-visit-status :deep(.status),
  .patient-visit-action button {
    width: 100%;
    min-width: 0;
  }

  .patient-visit-action > span {
    text-align: center;
  }

  .patient-visits-empty-row {
    display: block !important;
  }

  .patient-visits-empty-row td {
    display: block !important;
    height: auto;
    padding: 42px 20px !important;
  }

  .patient-visits-empty-row td::before {
    display: none;
  }

  .patient-visits-footer {
    align-items: stretch;
    flex-direction: column;
    margin-top: 10px;
    border: 1px solid #dce7f2;
    border-radius: 8px;
    background: #fff;
    padding: 12px;
  }

  .patient-visits-footer p {
    text-align: center;
  }

  .patient-visits-footer nav {
    justify-content: center;
  }

  :global(html[data-dashboard-theme="dark"]) .patient-visits-header,
  :global(html[data-dashboard-theme="dark"]) .patient-visits-toolbar,
  :global(html[data-dashboard-theme="dark"]) .patient-visits-table tbody tr,
  :global(html[data-dashboard-theme="dark"]) .patient-visits-footer {
    border-color: var(--dashboard-border);
    background: var(--dashboard-surface);
  }
}
</style>
