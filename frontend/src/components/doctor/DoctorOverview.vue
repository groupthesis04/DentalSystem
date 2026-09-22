<script setup>
import {
  CalendarDays,
  ChartNoAxesColumnIncreasing,
  CircleMinus,
  CreditCard,
  Stethoscope,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-vue-next";
import { computed, ref } from "vue";

import AvatarBadge from "../AvatarBadge.vue";
import { formatDate, formatMoney, localDateIso } from "../../services/format";

const props = defineProps({
  state: { type: Object, required: true },
  highlightedId: { type: String, default: "" },
});
const emit = defineEmits(["select-panel", "status-change", "refresh"]);

const collectionRange = ref("year");
const appointmentRange = ref("today");
const today = new Date();
const todayIso = localDateIso(today);
const overviewRanges = [
  { value: "today", label: "Today" },
  { value: "week", label: "This Week" },
  { value: "six", label: "Last 6 Months" },
  { value: "year", label: "This Year" },
];

const weekStart = new Date(today);
weekStart.setDate(today.getDate() - ((today.getDay() + 6) % 7));
const weekDates = Array.from({ length: 7 }, (_, index) => {
  const date = new Date(weekStart);
  date.setDate(weekStart.getDate() + index);
  return date;
});
const weekDateKeys = new Set(weekDates.map((date) => localDateIso(date)));
const sixMonthKeys = new Set(
  Array.from({ length: 6 }, (_, index) =>
    monthKey(new Date(today.getFullYear(), today.getMonth() - (5 - index), 1)),
  ),
);

function monthKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function itemMonth(value) {
  return String(value || "").slice(0, 7);
}

function itemDate(value) {
  return String(value || "").slice(0, 10);
}

function isInRange(value, range) {
  const date = itemDate(value);
  if (!date) return false;
  if (range === "today") return date === todayIso;
  if (range === "week") return weekDateKeys.has(date);
  if (range === "six") return sixMonthKeys.has(itemMonth(date));
  return itemMonth(date).startsWith(String(today.getFullYear()));
}

function rangeLabel(range) {
  return overviewRanges.find((option) => option.value === range)?.label || "This Year";
}

function dateValue(value) {
  const parsed = new Date(value || 0);
  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
}

function patientName(patient) {
  if (patient.name) return patient.name;
  return [patient.first_name, patient.middle_name, patient.last_name].filter(Boolean).join(" ");
}

function patientContact(patient) {
  return (
    patient.mobile_number ||
    patient.phone_number ||
    patient.phone ||
    patient.email ||
    "No contact provided"
  );
}

function patientRegisteredAt(patient) {
  return patient.created_at || patient.updated_at || patient.birthdate || "";
}

function formatTime(value) {
  const match = /^(\d{2}):(\d{2})/.exec(String(value || ""));
  if (!match) return value || "-";
  const date = new Date(2000, 0, 1, Number(match[1]), Number(match[2]));
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function formatCompactMoney(value) {
  const amount = Number(value || 0);
  if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(1)}m`;
  if (amount >= 1_000) return `${Math.round(amount / 1_000)}k`;
  return Math.round(amount).toLocaleString();
}

function statusLabel(status) {
  const labels = {
    approved: "Confirmed",
    pending: "Pending",
    completed: "Completed",
    cancelled: "Cancelled",
  };
  return labels[String(status || "").toLowerCase()] || status || "Unknown";
}

const currentMonthKey = monthKey(today);
const previousMonthDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
const previousMonthKey = monthKey(previousMonthDate);

const currentMonthAppointments = computed(() =>
  props.state.appointments.filter((item) => itemMonth(item.date) === currentMonthKey),
);
const currentMonthRecords = computed(() =>
  props.state.records.filter((item) => itemMonth(item.treatment_date) === currentMonthKey),
);
const previousMonthRecords = computed(() =>
  props.state.records.filter((item) => itemMonth(item.treatment_date) === previousMonthKey),
);
const patientsAddedThisMonth = computed(
  () =>
    props.state.patients.filter(
      (patient) => itemMonth(patientRegisteredAt(patient)) === currentMonthKey,
    ).length,
);
const todayAppointments = computed(() =>
  props.state.appointments
    .filter((item) => item.date === todayIso && item.status !== "cancelled")
    .sort((a, b) => String(a.time).localeCompare(String(b.time)))
    .slice(0, 5),
);
const recentPatients = computed(() =>
  [...props.state.patients]
    .sort((a, b) => dateValue(patientRegisteredAt(b)) - dateValue(patientRegisteredAt(a)))
    .slice(0, 5),
);
const currentCollections = computed(() =>
  currentMonthRecords.value.reduce((sum, item) => sum + Number(item.amount_paid || 0), 0),
);
const previousCollections = computed(() =>
  previousMonthRecords.value.reduce((sum, item) => sum + Number(item.amount_paid || 0), 0),
);
const collectionTrend = computed(() => {
  if (!previousCollections.value) {
    return currentCollections.value
      ? { direction: "up", text: "New collections this month" }
      : { direction: "flat", text: "No collections this month" };
  }
  const percent = Math.round(
    ((currentCollections.value - previousCollections.value) / previousCollections.value) * 100,
  );
  return {
    direction: percent > 0 ? "up" : percent < 0 ? "down" : "flat",
    text: `${percent > 0 ? "+" : ""}${percent}% from last month`,
  };
});

const metricCards = computed(() => [
  {
    key: "patients",
    label: "Total Patients",
    value: props.state.patients.length.toLocaleString(),
    detail: `+${patientsAddedThisMonth.value} this month`,
    direction: patientsAddedThisMonth.value ? "up" : "flat",
    icon: Users,
    panel: "doctorPatients",
  },
  {
    key: "appointments",
    label: "Appointments",
    value: currentMonthAppointments.value.length.toLocaleString(),
    detail: `${todayAppointments.value.length} scheduled today`,
    direction: todayAppointments.value.length ? "up" : "flat",
    icon: CalendarDays,
    panel: "doctorAppointments",
  },
  {
    key: "treatments",
    label: "Treatments",
    value: props.state.records.length.toLocaleString(),
    detail: `+${currentMonthRecords.value.length} this month`,
    direction: currentMonthRecords.value.length ? "up" : "flat",
    icon: Stethoscope,
    panel: "doctorServiceRecords",
  },
  {
    key: "collections",
    label: "Net Collections",
    value: formatMoney(currentCollections.value),
    detail: collectionTrend.value.text,
    direction: collectionTrend.value.direction,
    icon: CreditCard,
    panel: "doctorStatistics",
  },
]);

const collectionSeries = computed(() => {
  let periods;
  if (collectionRange.value === "today") {
    periods = [{ key: todayIso, label: "Today", value: 0 }];
  } else if (collectionRange.value === "week") {
    periods = weekDates.map((date) => ({
      key: localDateIso(date),
      label: date.toLocaleDateString(undefined, { weekday: "short" }),
      value: 0,
    }));
  } else {
    const count = collectionRange.value === "six" ? 6 : today.getMonth() + 1;
    const startOffset = collectionRange.value === "six" ? count - 1 : today.getMonth();
    periods = Array.from({ length: count }, (_, index) => {
      const date = new Date(today.getFullYear(), today.getMonth() - startOffset + index, 1);
      return {
        key: monthKey(date),
        label: date.toLocaleDateString(undefined, { month: "short" }),
        value: 0,
      };
    });
  }

  const byKey = new Map(periods.map((period) => [period.key, period]));
  for (const record of props.state.records) {
    if (!isInRange(record.treatment_date, collectionRange.value)) continue;
    const key = ["today", "week"].includes(collectionRange.value)
      ? itemDate(record.treatment_date)
      : itemMonth(record.treatment_date);
    const period = byKey.get(key);
    if (period) period.value += Number(record.amount_paid || 0);
  }
  return periods;
});

const collectionRangeLabel = computed(() => rangeLabel(collectionRange.value));
const selectedCollectionTotal = computed(() =>
  collectionSeries.value.reduce((sum, period) => sum + period.value, 0),
);

const chartMaximum = computed(() => {
  const maximum = Math.max(0, ...collectionSeries.value.map((period) => period.value));
  if (!maximum) return 1000;
  const magnitude = 10 ** Math.floor(Math.log10(maximum));
  return Math.ceil(maximum / magnitude) * magnitude;
});

const chartTicks = computed(() =>
  [4, 3, 2, 1, 0].map((step) => ({
    value: (chartMaximum.value * step) / 4,
    y: 20 + ((4 - step) / 4) * 150,
  })),
);

const chartPoints = computed(() => {
  const periods = collectionSeries.value;
  const availableWidth = 674;
  return periods.map((period, index) => ({
    ...period,
    x: periods.length === 1 ? 390 : 58 + (index * availableWidth) / (periods.length - 1),
    y: 170 - (period.value / chartMaximum.value) * 150,
  }));
});

const collectionLinePath = computed(() =>
  chartPoints.value.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" "),
);
const collectionAreaPath = computed(() => {
  const points = chartPoints.value;
  if (!points.length) return "";
  return `${collectionLinePath.value} L ${points.at(-1).x} 170 L ${points[0].x} 170 Z`;
});

const appointmentsForOverview = computed(() =>
  props.state.appointments.filter((item) => isInRange(item.date, appointmentRange.value)),
);
const appointmentRangeLabel = computed(() => rangeLabel(appointmentRange.value));
const appointmentStatus = computed(() => {
  const statuses = [
    { key: "pending", label: "Pending", color: "#f59e0b" },
    { key: "approved", label: "Confirmed", color: "#4c8df6" },
    { key: "completed", label: "Completed", color: "#25b987" },
    { key: "cancelled", label: "Cancelled", color: "#ef476f" },
  ];
  const total = appointmentsForOverview.value.length;
  return statuses.map((status) => {
    const value = appointmentsForOverview.value.filter((item) => item.status === status.key).length;
    return { ...status, value, percent: total ? Math.round((value / total) * 100) : 0 };
  });
});
const appointmentTotal = computed(() => appointmentsForOverview.value.length);
const donutStyle = computed(() => {
  if (!appointmentTotal.value) return { background: "#e7edf4" };
  let start = 0;
  const segments = appointmentStatus.value.map((item) => {
    const end = start + (item.value / appointmentTotal.value) * 100;
    const segment = `${item.color} ${start}% ${end}%`;
    start = end;
    return segment;
  });
  return { background: `conic-gradient(${segments.join(", ")})` };
});

function trendIcon(direction) {
  if (direction === "up") return TrendingUp;
  if (direction === "down") return TrendingDown;
  return CircleMinus;
}
</script>

<template>
  <section class="workspace-panel clinic-home-dashboard">
    <section class="home-metric-grid" aria-label="Clinic dashboard summary">
      <button
        v-for="card in metricCards"
        :key="card.key"
        class="home-metric-card"
        :class="`home-tone-${card.key}`"
        type="button"
        @click="emit('select-panel', card.panel)"
      >
        <span class="home-metric-icon"><component :is="card.icon" :size="27" /></span>
        <span class="home-metric-copy">
          <small>{{ card.label }}</small>
          <strong>{{ card.value }}</strong>
          <span class="home-metric-trend" :class="card.direction">
            <component :is="trendIcon(card.direction)" :size="14" />{{ card.detail }}
          </span>
        </span>
      </button>
    </section>

    <section class="home-analytics-grid">
      <article class="home-dashboard-panel collection-panel">
        <header class="home-panel-heading">
          <div class="home-panel-title">
            <span><ChartNoAxesColumnIncreasing :size="23" /></span>
            <div>
              <h2>Collection Overview</h2>
              <p>Treatment payments for {{ collectionRangeLabel.toLowerCase() }}</p>
            </div>
          </div>
          <label class="home-period-select">
            <CalendarDays :size="16" aria-hidden="true" />
            <select v-model="collectionRange" aria-label="Collection chart period">
              <option v-for="option in overviewRanges" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
        </header>

        <div class="collection-chart-wrap">
          <svg
            class="collection-chart"
            viewBox="0 0 760 215"
            role="img"
            :aria-label="`Treatment payments for ${collectionRangeLabel}: ${formatMoney(selectedCollectionTotal)}`"
          >
            <g v-for="tick in chartTicks" :key="tick.y">
              <line x1="52" x2="742" :y1="tick.y" :y2="tick.y" class="chart-grid-line" />
              <text x="44" :y="tick.y + 4" text-anchor="end" class="chart-axis-label">
                {{ formatCompactMoney(tick.value) }}
              </text>
            </g>
            <path :d="collectionAreaPath" class="chart-area" />
            <path :d="collectionLinePath" class="chart-line" />
            <g v-for="point in chartPoints" :key="point.key">
              <circle :cx="point.x" :cy="point.y" r="4.5" class="chart-point">
                <title>{{ point.label }}: {{ formatMoney(point.value) }}</title>
              </circle>
              <text :x="point.x" y="202" text-anchor="middle" class="chart-month-label">
                {{ point.label }}
              </text>
            </g>
          </svg>
          <div class="collection-current-value">
            <small>{{ collectionRangeLabel }}</small>
            <strong>{{ formatMoney(selectedCollectionTotal) }}</strong>
          </div>
        </div>
      </article>

      <article class="home-dashboard-panel appointment-overview-panel">
        <header class="home-panel-heading">
          <div class="home-panel-title">
            <span><CalendarDays :size="23" /></span>
            <div>
              <h2>Appointment Overview</h2>
              <p>Status of appointments for {{ appointmentRangeLabel.toLowerCase() }}</p>
            </div>
          </div>
          <label class="home-period-select compact">
            <CalendarDays :size="16" aria-hidden="true" />
            <select v-model="appointmentRange" aria-label="Appointment overview period">
              <option v-for="option in overviewRanges" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
        </header>

        <div class="appointment-overview-body">
          <div
            class="appointment-donut"
            :style="donutStyle"
            role="img"
            aria-label="Appointment status chart"
          >
            <span class="donut-center">
              <strong>{{ appointmentTotal }}</strong>
              <small>Total</small>
            </span>
          </div>
          <dl class="appointment-legend">
            <div v-for="item in appointmentStatus" :key="item.key">
              <dt><span :style="{ background: item.color }"></span>{{ item.label }}</dt>
              <dd>
                <strong>{{ item.value }}</strong
                ><small>{{ item.percent }}%</small>
              </dd>
            </div>
          </dl>
        </div>
      </article>
    </section>

    <section class="home-table-grid">
      <article class="home-dashboard-panel home-table-panel">
        <header class="home-panel-heading">
          <div class="home-panel-title">
            <span><CalendarDays :size="23" /></span>
            <div>
              <h2>Today's Appointments</h2>
              <p>Your clinic schedule for today</p>
            </div>
          </div>
          <button
            class="home-view-all"
            type="button"
            @click="emit('select-panel', 'doctorAppointments')"
          >
            View All
          </button>
        </header>
        <div class="home-table-scroll">
          <table class="home-data-table appointments-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Patient</th>
                <th>Service</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in todayAppointments"
                :key="item.id"
                :data-entity-id="item.id"
                :class="{ 'notification-target-glow': highlightedId === item.id }"
              >
                <td>
                  <strong>{{ formatTime(item.time) }}</strong>
                </td>
                <td>{{ item.patient_name }}</td>
                <td>{{ item.service }}</td>
                <td>
                  <span class="home-status" :class="item.status">{{
                    statusLabel(item.status)
                  }}</span>
                </td>
              </tr>
              <tr v-if="!todayAppointments.length">
                <td class="home-table-empty" colspan="4">No appointments scheduled for today.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="home-dashboard-panel home-table-panel">
        <header class="home-panel-heading">
          <div class="home-panel-title">
            <span><Users :size="23" /></span>
            <div>
              <h2>Recent Patients</h2>
              <p>Latest registered patients</p>
            </div>
          </div>
          <button
            class="home-view-all"
            type="button"
            @click="emit('select-panel', 'doctorPatients')"
          >
            View All
          </button>
        </header>
        <div class="home-table-scroll">
          <table class="home-data-table recent-patient-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Contact</th>
                <th>Date Registered</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="patient in recentPatients"
                :key="patient.id"
                :data-entity-id="patient.id"
                :class="{ 'notification-target-glow': highlightedId === patient.id }"
              >
                <td>
                  <span class="home-patient-cell">
                    <AvatarBadge :name="patientName(patient)" :image="patient.profile_image" />
                    <strong>{{ patientName(patient) }}</strong>
                  </span>
                </td>
                <td>{{ patientContact(patient) }}</td>
                <td>{{ formatDate(patientRegisteredAt(patient)) }}</td>
              </tr>
              <tr v-if="!recentPatients.length">
                <td class="home-table-empty" colspan="3">
                  No patient records have been added yet.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.clinic-home-dashboard {
  display: grid;
  gap: 16px;
}

.home-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.home-metric-card {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  min-width: 0;
  min-height: 116px;
  align-items: center;
  gap: 14px;
  padding: 18px;
  color: #172b4d;
  text-align: left;
  border: 1px solid #dbe8f6;
  border-radius: 8px;
  background: #f2f7ff;
  cursor: pointer;
  transition:
    transform 160ms ease,
    box-shadow 160ms ease,
    border-color 160ms ease;
}

.home-metric-card:hover,
.home-metric-card:focus-visible {
  border-color: #9dbde8;
  box-shadow: 0 8px 20px rgb(50 91 141 / 9%);
  outline: none;
  transform: translateY(-2px);
}

.home-metric-card.home-tone-appointments {
  border-color: #d4eee5;
  background: #effaf6;
}

.home-metric-card.home-tone-treatments {
  border-color: #f0dfd0;
  background: #fff6ef;
}

.home-metric-card.home-tone-collections {
  border-color: #e4dafa;
  background: #f7f2ff;
}

.home-metric-icon {
  display: grid;
  width: 58px;
  height: 58px;
  place-items: center;
  color: #2f7de8;
  border-radius: 50%;
  background: #dceafe;
}

.home-tone-appointments .home-metric-icon {
  color: #0b9c6a;
  background: #d8f4e9;
}

.home-tone-treatments .home-metric-icon {
  color: #ef7c32;
  background: #ffe6d4;
}

.home-tone-collections .home-metric-icon {
  color: #7c4ee4;
  background: #e9defe;
}

.home-metric-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.home-metric-copy > small {
  color: #405474;
  font-size: 0.77rem;
}

.home-metric-copy > strong {
  overflow: hidden;
  font-size: clamp(1.25rem, 2vw, 1.62rem);
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-metric-trend {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 5px;
  margin-top: 6px;
  color: #4f647f;
  font-size: 0.68rem;
  font-weight: 650;
}

.home-metric-trend.up {
  color: #0b9566;
}

.home-metric-trend.down {
  color: #d44259;
}

.home-analytics-grid,
.home-table-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.42fr) minmax(360px, 0.92fr);
  gap: 14px;
}

.home-table-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.home-dashboard-panel {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #dfe8f0;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 5px 18px rgb(31 64 102 / 5%);
}

.home-panel-heading {
  display: flex;
  min-height: 74px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 15px 18px;
}

.home-panel-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.home-panel-title > span {
  display: grid;
  width: 46px;
  height: 46px;
  flex: 0 0 46px;
  place-items: center;
  color: #098ba2;
  border-radius: 50%;
  background: #ddf5f8;
}

.home-panel-title h2,
.home-panel-title p {
  margin: 0;
}

.home-panel-title h2 {
  color: #14284a;
  font-size: 1rem;
}

.home-panel-title p {
  color: #6d7e96;
  font-size: 0.72rem;
}

.home-period-select {
  display: flex;
  min-width: 132px;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  color: #344e72;
  border: 1px solid #cfdce8;
  border-radius: 6px;
  background: #fff;
}

.home-period-select select {
  width: 100%;
  min-height: 38px;
  padding: 0 3px;
  color: inherit;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 0.72rem;
  font-weight: 700;
}

.home-period-select.compact {
  min-width: 128px;
}

.collection-chart-wrap {
  position: relative;
  min-height: 235px;
  padding: 0 18px 8px;
}

.collection-chart {
  display: block;
  width: 100%;
  height: 225px;
  overflow: visible;
}

.chart-grid-line {
  stroke: #dfe8f0;
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.chart-axis-label,
.chart-month-label {
  fill: #708099;
  font-family: inherit;
  font-size: 10px;
}

.chart-area {
  fill: #dff4f7;
  opacity: 0.8;
}

.chart-line {
  fill: none;
  stroke: #078da4;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chart-point {
  fill: #fff;
  stroke: #078da4;
  stroke-width: 3;
}

.collection-current-value {
  position: absolute;
  top: 2px;
  right: 26px;
  display: grid;
  gap: 1px;
  padding: 7px 10px;
  color: #fff;
  border-radius: 6px;
  background: #08798d;
  pointer-events: none;
}

.collection-current-value small {
  font-size: 0.57rem;
}

.collection-current-value strong {
  font-size: 0.75rem;
}

.appointment-overview-body {
  display: grid;
  grid-template-columns: minmax(145px, 0.8fr) minmax(170px, 1.2fr);
  align-items: center;
  gap: 20px;
  min-height: 235px;
  padding: 12px 24px 26px;
}

.appointment-donut {
  position: relative;
  width: min(164px, 100%);
  aspect-ratio: 1;
  justify-self: center;
  border-radius: 50%;
}

.donut-center {
  position: absolute;
  inset: 28%;
  display: grid;
  place-items: center;
  align-content: center;
  color: #14284a;
  border-radius: 50%;
  background: #fff;
}

.donut-center strong {
  font-size: 1.35rem;
  line-height: 1;
}

.donut-center small {
  margin-top: 4px;
  font-size: 0.68rem;
}

.appointment-legend {
  display: grid;
  gap: 0;
  margin: 0;
}

.appointment-legend > div {
  display: flex;
  min-height: 42px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #e7edf3;
}

.appointment-legend > div:last-child {
  border-bottom: 0;
}

.appointment-legend dt,
.appointment-legend dd {
  display: flex;
  align-items: center;
  margin: 0;
}

.appointment-legend dt {
  gap: 9px;
  color: #243a5d;
  font-size: 0.75rem;
}

.appointment-legend dt span {
  width: 11px;
  height: 11px;
  flex: 0 0 11px;
  border-radius: 50%;
}

.appointment-legend dd {
  min-width: 70px;
  justify-content: space-between;
  gap: 12px;
  color: #14284a;
  font-size: 0.72rem;
}

.appointment-legend dd small {
  min-width: 30px;
  color: #718199;
  text-align: right;
}

.home-view-all {
  min-height: 34px;
  padding: 7px 13px;
  color: #1d6fd8;
  border: 1px solid #d7e7fb;
  border-radius: 6px;
  background: #f0f6ff;
  font-size: 0.7rem;
  font-weight: 750;
  cursor: pointer;
}

.home-view-all:hover,
.home-view-all:focus-visible {
  color: #fff;
  border-color: #2563eb;
  outline: none;
  background: #2563eb;
}

.home-table-scroll {
  overflow-x: auto;
  padding: 0 12px 14px;
}

.home-data-table {
  width: 100%;
  min-width: 560px;
  border-collapse: collapse;
  color: #263b5c;
  font-size: 0.72rem;
}

.home-data-table th {
  padding: 7px 11px;
  color: #5a6e89;
  background: #edf3f8;
  font-size: 0.63rem;
  text-align: left;
  text-transform: uppercase;
}

.home-data-table th:first-child {
  border-radius: 5px 0 0 5px;
}

.home-data-table th:last-child {
  border-radius: 0 5px 5px 0;
}

.home-data-table td {
  max-width: 210px;
  overflow: hidden;
  padding: 8px 11px;
  border-bottom: 1px solid #e7edf3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-data-table tbody tr:last-child td {
  border-bottom: 0;
}

.home-status {
  display: inline-flex;
  min-width: 76px;
  min-height: 25px;
  align-items: center;
  justify-content: center;
  padding: 3px 10px;
  color: #166534;
  border: 1px solid #a7e4c1;
  border-radius: 999px;
  background: #e9f9f0;
  font-size: 0.62rem;
  font-weight: 750;
}

.home-status.pending {
  color: #c25b08;
  border-color: #f7c486;
  background: #fff7e9;
}

.home-status.approved {
  color: #1d6fd8;
  border-color: #a8c9f8;
  background: #edf5ff;
}

.home-status.cancelled {
  color: #c7334c;
  border-color: #f3b8c2;
  background: #fff0f2;
}

.home-patient-cell {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
}

.home-patient-cell :deep(.profile-avatar) {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  color: #1d5d92;
  background: #dff3fa;
  font-size: 0.65rem;
}

.home-patient-cell strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-table-empty {
  height: 104px;
  color: #77879b;
  text-align: center;
}

:global(html[data-dashboard-theme="dark"]) .home-metric-card,
:global(html[data-dashboard-theme="dark"]) .home-dashboard-panel {
  color: #e8edf6;
  border-color: #344154;
  background: #1d2635;
}

:global(html[data-dashboard-theme="dark"]) .home-metric-copy > small,
:global(html[data-dashboard-theme="dark"]) .home-metric-trend,
:global(html[data-dashboard-theme="dark"]) .home-panel-title p,
:global(html[data-dashboard-theme="dark"]) .appointment-legend dt,
:global(html[data-dashboard-theme="dark"]) .home-data-table,
:global(html[data-dashboard-theme="dark"]) .home-data-table th {
  color: #aebbd0;
}

:global(html[data-dashboard-theme="dark"]) .home-panel-title h2,
:global(html[data-dashboard-theme="dark"]) .donut-center,
:global(html[data-dashboard-theme="dark"]) .appointment-legend dd {
  color: #edf3fb;
}

:global(html[data-dashboard-theme="dark"]) .donut-center,
:global(html[data-dashboard-theme="dark"]) .home-period-select {
  background: #202b3b;
}

:global(html[data-dashboard-theme="dark"]) .home-data-table th {
  background: #263246;
}

:global(html[data-dashboard-theme="dark"]) .home-data-table td,
:global(html[data-dashboard-theme="dark"]) .appointment-legend > div {
  border-color: #344154;
}

@media (max-width: 1280px) {
  .home-metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .home-analytics-grid,
  .home-table-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .home-metric-grid {
    grid-template-columns: 1fr;
  }

  .home-metric-card {
    min-height: 100px;
  }

  .home-panel-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .home-period-select,
  .home-period-select.compact {
    width: 100%;
  }

  .appointment-overview-body {
    grid-template-columns: 1fr;
  }

  .appointment-donut {
    width: 150px;
  }

  .collection-current-value {
    position: static;
    width: fit-content;
    margin: -8px 0 8px 34px;
  }
}

@media (max-width: 480px) {
  .home-metric-card {
    grid-template-columns: 50px minmax(0, 1fr);
    padding: 14px;
  }

  .home-metric-icon {
    width: 50px;
    height: 50px;
  }

  .home-panel-heading {
    padding: 14px;
  }

  .home-panel-title > span {
    width: 42px;
    height: 42px;
    flex-basis: 42px;
  }

  .home-data-table {
    min-width: 0;
    table-layout: fixed;
  }

  .appointments-table :is(th, td):nth-child(3),
  .recent-patient-table :is(th, td):nth-child(2) {
    display: none;
  }

  .appointments-table :is(th, td):first-child {
    width: 27%;
  }

  .appointments-table :is(th, td):nth-child(4),
  .recent-patient-table :is(th, td):nth-child(3) {
    width: 34%;
  }

  .home-data-table th,
  .home-data-table td {
    padding-inline: 7px;
  }

  .home-status {
    min-width: 66px;
    padding-inline: 7px;
  }
}
</style>
