<script setup>
import {
  ArrowRight,
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
import { appointmentService, formatDate, formatMoney, localDateIso } from "../../services/format";

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
    approved: "Accepted",
    accepted: "Accepted",
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
const mobileChartTicks = computed(() =>
  [4, 3, 2, 1, 0].map((step) => ({
    value: (chartMaximum.value * step) / 4,
    y: 40 + ((4 - step) / 4) * 65,
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

const mobileChartPoints = computed(() => {
  const periods = collectionSeries.value;
  const availableWidth = 274;
  return periods.map((period, index) => ({
    ...period,
    x: periods.length === 1 ? 172 : 38 + (index * availableWidth) / (periods.length - 1),
    y: 105 - (period.value / chartMaximum.value) * 65,
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
const mobileCollectionLinePath = computed(() =>
  mobileChartPoints.value
    .map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`)
    .join(" "),
);
const mobileCollectionAreaPath = computed(() => {
  const points = mobileChartPoints.value;
  if (!points.length) return "";
  return `${mobileCollectionLinePath.value} L ${points.at(-1).x} 105 L ${points[0].x} 105 Z`;
});

const appointmentsForOverview = computed(() =>
  props.state.appointments.filter((item) => isInRange(item.date, appointmentRange.value)),
);
const appointmentRangeLabel = computed(() => rangeLabel(appointmentRange.value));
const appointmentStatus = computed(() => {
  const statuses = [
    { key: "pending", label: "Pending", color: "var(--status-pending)" },
    { key: "approved", label: "Accepted", color: "var(--status-accepted)" },
    { key: "completed", label: "Completed", color: "var(--status-completed)" },
    { key: "cancelled", label: "Cancelled", color: "var(--status-cancelled)" },
  ];
  const total = appointmentsForOverview.value.length;
  return statuses.map((status) => {
    const value = appointmentsForOverview.value.filter((item) =>
      status.key === "approved"
        ? ["approved", "accepted"].includes(item.status)
        : item.status === status.key,
    ).length;
    return { ...status, value, percent: total ? Math.round((value / total) * 100) : 0 };
  });
});
const appointmentTotal = computed(() => appointmentsForOverview.value.length);
const donutStyle = computed(() => {
  if (!appointmentTotal.value) return { background: "#e8dfd0" };
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
        <span class="home-metric-arrow" aria-hidden="true"><ArrowRight :size="19" /></span>
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
          <svg
            class="collection-chart-mobile"
            viewBox="0 0 330 140"
            role="img"
            :aria-label="`Treatment payments for ${collectionRangeLabel}: ${formatMoney(selectedCollectionTotal)}`"
          >
            <g v-for="tick in mobileChartTicks" :key="tick.y">
              <line x1="34" x2="318" :y1="tick.y" :y2="tick.y" class="chart-grid-line" />
              <text x="29" :y="tick.y + 4" text-anchor="end" class="chart-axis-label">
                {{ formatCompactMoney(tick.value) }}
              </text>
            </g>
            <path :d="mobileCollectionAreaPath" class="chart-area" />
            <path :d="mobileCollectionLinePath" class="chart-line" />
            <g v-for="point in mobileChartPoints" :key="point.key">
              <circle :cx="point.x" :cy="point.y" r="3.5" class="chart-point">
                <title>{{ point.label }}: {{ formatMoney(point.value) }}</title>
              </circle>
              <text :x="point.x" y="130" text-anchor="middle" class="chart-month-label">
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
                <td>{{ appointmentService(item) }}</td>
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
        <ul class="home-mobile-preview" aria-label="Today's appointments">
          <li v-for="item in todayAppointments" :key="item.id">
            <time class="home-mobile-appointment-time">{{ formatTime(item.time) }}</time>
            <span class="home-mobile-item-main">
              <strong>{{ item.patient_name }}</strong>
              <small>{{ appointmentService(item) }}</small>
            </span>
            <span class="home-status" :class="item.status">{{ statusLabel(item.status) }}</span>
          </li>
          <li v-if="!todayAppointments.length" class="home-mobile-empty">
            No appointments scheduled for today.
          </li>
        </ul>
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
        <ul class="home-mobile-preview" aria-label="Recent patients">
          <li v-for="patient in recentPatients" :key="patient.id">
            <AvatarBadge :name="patientName(patient)" :image="patient.profile_image" />
            <span class="home-mobile-item-main">
              <strong>{{ patientName(patient) }}</strong>
              <small>{{ patientContact(patient) }}</small>
              <small>{{ formatDate(patientRegisteredAt(patient)) }}</small>
            </span>
          </li>
          <li v-if="!recentPatients.length" class="home-mobile-empty">
            No patient records have been added yet.
          </li>
        </ul>
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
  color: #171511;
  text-align: left;
  border: 1px solid #f4e7cd;
  border-radius: 8px;
  background: #f8f1e2;
  cursor: pointer;
  transition:
    transform 160ms ease,
    box-shadow 160ms ease,
    border-color 160ms ease;
}

.home-metric-card:hover,
.home-metric-card:focus-visible {
  border-color: #dfc48a;
  box-shadow: 0 8px 20px rgba(138, 101, 38, 9%);
  outline: none;
  transform: translateY(-2px);
}

.home-metric-card.home-tone-appointments {
  border-color: #f4e7cd;
  background: #f8f1e2;
}

.home-metric-card.home-tone-treatments {
  border-color: #f4e7cd;
  background: #f8f1e2;
}

.home-metric-card.home-tone-collections {
  border-color: #f4e7cd;
  background: #f8f1e2;
}

.home-metric-icon {
  display: grid;
  width: 58px;
  height: 58px;
  place-items: center;
  color: #8a6526;
  border-radius: 50%;
  background: #f4e7cd;
}

.home-tone-appointments .home-metric-icon {
  color: #8a6526;
  background: #f4e7cd;
}

.home-tone-treatments .home-metric-icon {
  color: #8a6526;
  background: #f4e7cd;
}

.home-tone-collections .home-metric-icon {
  color: #8a6526;
  background: #f4e7cd;
}

.home-metric-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.home-metric-copy > small {
  color: #514b42;
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
  color: #514b42;
  font-size: 0.74rem;
  font-weight: 650;
}

.home-metric-trend.up {
  color: #8a6526;
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
  border: 1px solid #f4e7cd;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 5px 18px rgba(23, 21, 17, 5%);
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
  color: #8a6526;
  border-radius: 50%;
  background: #f4e7cd;
}

.home-panel-title h2,
.home-panel-title p {
  margin: 0;
}

.home-panel-title h2 {
  color: #171511;
  font-size: 1rem;
}

.home-panel-title p {
  color: #706b61;
  font-size: 0.72rem;
}

.home-period-select {
  display: flex;
  min-width: 132px;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  color: #8a6526;
  border: 1px solid #f4e7cd;
  border-radius: 6px;
  background: #ffffff;
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

.collection-chart-mobile,
.home-mobile-preview {
  display: none;
}

.chart-grid-line {
  stroke: #f4e7cd;
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.chart-axis-label,
.chart-month-label {
  fill: #706b61;
  font-family: inherit;
  font-size: 10px;
}

.chart-area {
  fill: #f4e7cd;
  opacity: 0.8;
}

.chart-line {
  fill: none;
  stroke: #8a6526;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chart-point {
  fill: #ffffff;
  stroke: #8a6526;
  stroke-width: 3;
}

.collection-current-value {
  position: absolute;
  top: 2px;
  right: 26px;
  display: grid;
  gap: 1px;
  padding: 7px 10px;
  color: #ffffff;
  border-radius: 6px;
  background: #8a6526;
  pointer-events: none;
}

.collection-current-value small {
  font-size: 0.7rem;
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
  color: #171511;
  border-radius: 50%;
  background: #ffffff;
}

.donut-center strong {
  font-size: 1.35rem;
  line-height: 1;
}

.donut-center small {
  margin-top: 4px;
  font-size: 0.72rem;
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
  border-bottom: 1px solid #f5f2eb;
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
  color: #171511;
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
  color: #171511;
  font-size: 0.72rem;
}

.appointment-legend dd small {
  min-width: 30px;
  color: #706b61;
  text-align: right;
}

.home-view-all {
  min-height: 34px;
  padding: 7px 13px;
  color: #8a6526;
  border: 1px solid #f4e7cd;
  border-radius: 6px;
  background: #f8f1e2;
  font-size: 0.7rem;
  font-weight: 750;
  cursor: pointer;
}

.home-view-all:hover,
.home-view-all:focus-visible {
  color: #ffffff;
  border-color: #8a6526;
  outline: none;
  background: #8a6526;
}

.home-table-scroll {
  overflow-x: auto;
  padding: 0 12px 14px;
}

.home-data-table {
  width: 100%;
  min-width: 560px;
  border-collapse: collapse;
  color: #171511;
  font-size: 0.72rem;
}

.home-data-table th {
  padding: 7px 11px;
  color: #514b42;
  background: #f8f1e2;
  font-size: 0.72rem;
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
  border-bottom: 1px solid #f5f2eb;
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
  color: #8a6526;
  border: 1px solid #dfc48a;
  border-radius: 999px;
  background: #f8f1e2;
  font-size: 0.7rem;
  font-weight: 750;
}

.home-status.pending {
  color: #8a6526;
  border-color: #dfc48a;
  background: #f8f1e2;
}

.home-status.approved {
  color: #12659e;
  border-color: #a6d4ed;
  background: #e9f5fc;
}

.home-status.accepted {
  color: #12659e;
  border-color: #a6d4ed;
  background: #e9f5fc;
}

.home-status.completed {
  color: #147347;
  border-color: #a7dcc0;
  background: #e9f9ef;
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
  color: #8a6526;
  background: #f4e7cd;
  font-size: 0.72rem;
}

.home-patient-cell strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-table-empty {
  height: 104px;
  color: #706b61;
  text-align: center;
}

:global(html[data-dashboard-theme="dark"]) .home-metric-card,
:global(html[data-dashboard-theme="dark"]) .home-dashboard-panel {
  color: #edddbd;
  border-color: #514b42;
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .home-metric-copy > small,
:global(html[data-dashboard-theme="dark"]) .home-metric-trend,
:global(html[data-dashboard-theme="dark"]) .home-panel-title p,
:global(html[data-dashboard-theme="dark"]) .appointment-legend dt,
:global(html[data-dashboard-theme="dark"]) .home-data-table,
:global(html[data-dashboard-theme="dark"]) .home-data-table th {
  color: #cfc5b3;
}

:global(html[data-dashboard-theme="dark"]) .home-panel-title h2,
:global(html[data-dashboard-theme="dark"]) .donut-center,
:global(html[data-dashboard-theme="dark"]) .appointment-legend dd {
  color: #f8f1e2;
}

:global(html[data-dashboard-theme="dark"]) .donut-center,
:global(html[data-dashboard-theme="dark"]) .home-period-select {
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .home-data-table th {
  background: #28241e;
}

:global(html[data-dashboard-theme="dark"]) .home-data-table td,
:global(html[data-dashboard-theme="dark"]) .appointment-legend > div {
  border-color: #514b42;
}

:global(html[data-dashboard-theme="dark"]) .home-period-select,
:global(html[data-dashboard-theme="dark"]) .home-metric-trend.up {
  color: #e3c985;
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
  .clinic-home-dashboard {
    gap: 10px;
  }

  .home-metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .home-metric-card {
    grid-template-columns: 42px minmax(0, 1fr);
    min-height: 98px;
    gap: 9px;
    padding: 10px;
    border-radius: 10px;
  }

  .home-metric-icon {
    width: 42px;
    height: 42px;
  }

  .home-metric-icon :deep(svg) {
    width: 22px;
    height: 22px;
  }

  .home-metric-copy > small {
    font-size: 0.74rem;
  }

  .home-metric-copy > strong {
    overflow: visible;
    font-size: clamp(0.94rem, 4vw, 1.25rem);
    line-height: 1.14;
    text-overflow: initial;
    white-space: normal;
  }

  .home-tone-collections .home-metric-copy > strong {
    font-size: clamp(0.78rem, 3.35vw, 1.06rem);
    overflow-wrap: anywhere;
  }

  .home-metric-trend {
    align-items: flex-start;
    gap: 3px;
    margin-top: 4px;
    font-size: 0.7rem;
    line-height: 1.25;
  }

  .home-metric-trend :deep(svg) {
    width: 12px;
    height: 12px;
    flex: 0 0 12px;
  }

  .home-analytics-grid {
    gap: 10px;
  }

  .home-table-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .home-dashboard-panel {
    border-radius: 10px;
  }

  .home-panel-heading {
    min-height: 65px;
    align-items: center;
    flex-direction: row;
    gap: 6px;
    padding: 11px 12px;
  }

  .home-panel-title {
    gap: 8px;
  }

  .home-panel-title > span {
    width: 38px;
    height: 38px;
    flex-basis: 38px;
  }

  .home-panel-title > span :deep(svg) {
    width: 20px;
    height: 20px;
  }

  .home-panel-title h2 {
    font-size: 0.82rem;
    line-height: 1.2;
  }

  .home-panel-title p {
    font-size: 0.72rem;
    line-height: 1.3;
  }

  .home-period-select,
  .home-period-select.compact {
    width: auto;
    min-width: 98px;
    flex: 0 0 auto;
    padding-inline: 5px;
  }

  .home-period-select select {
    min-height: 34px;
    font-size: 0.73rem;
  }

  .collection-chart-wrap {
    min-height: 0;
    padding: 0 12px 6px;
  }

  .collection-chart {
    display: none;
  }

  .collection-chart-mobile {
    display: block;
    width: 100%;
    height: auto;
    max-height: 140px;
  }

  .collection-current-value {
    top: 4px;
    right: 14px;
    padding: 5px 7px;
  }

  .collection-current-value strong {
    font-size: 0.75rem;
  }

  .appointment-overview-body {
    grid-template-columns: minmax(100px, 0.88fr) minmax(0, 1.12fr);
    min-height: 0;
    gap: 9px;
    padding: 4px 13px 17px;
  }

  .appointment-donut {
    width: min(135px, 100%);
  }

  .appointment-legend > div {
    min-height: 37px;
    gap: 4px;
  }

  .appointment-legend dt {
    gap: 5px;
    font-size: 0.73rem;
  }

  .appointment-legend dt span {
    width: 8px;
    height: 8px;
    flex-basis: 8px;
  }

  .appointment-legend dd {
    min-width: 44px;
    gap: 5px;
    font-size: 0.72rem;
  }

  .appointment-legend dd small {
    min-width: 25px;
  }

  .home-table-panel .home-panel-heading {
    align-items: flex-start;
    gap: 3px;
    padding: 10px 8px 6px;
  }

  .home-table-panel .home-panel-title {
    align-items: flex-start;
    gap: 5px;
  }

  .home-table-panel .home-panel-title > span {
    width: 27px;
    height: 27px;
    flex-basis: 27px;
  }

  .home-table-panel .home-panel-title > span :deep(svg) {
    width: 16px;
    height: 16px;
  }

  .home-table-panel .home-panel-title h2 {
    font-size: 0.72rem;
    line-height: 1.2;
  }

  .home-table-panel .home-panel-title p {
    margin-top: 2px;
    font-size: 0.72rem;
  }

  .home-view-all {
    min-height: 25px;
    padding: 3px 5px;
    font-size: 0.72rem;
    white-space: nowrap;
  }

  .home-table-scroll {
    display: none;
  }

  .home-mobile-preview {
    display: grid;
    gap: 0;
    margin: 0;
    padding: 0 9px 10px;
    list-style: none;
  }

  .home-mobile-preview li {
    display: flex;
    min-width: 0;
    align-items: flex-start;
    gap: 5px;
    padding: 7px 0;
    border-top: 1px solid #f5f2eb;
  }

  .home-mobile-appointment-time {
    width: 30px;
    flex: 0 0 30px;
    color: #171511;
    font-size: 0.72rem;
    font-weight: 750;
    line-height: 1.2;
  }

  .home-mobile-item-main {
    display: grid;
    min-width: 0;
    gap: 2px;
    flex: 1 1 auto;
  }

  .home-mobile-item-main strong,
  .home-mobile-item-main small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .home-mobile-item-main strong {
    color: #171511;
    font-size: 0.72rem;
  }

  .home-mobile-item-main small {
    color: #706b61;
    font-size: 0.72rem;
  }

  .home-mobile-preview .home-status {
    min-width: 0;
    min-height: 20px;
    padding: 2px 4px;
    font-size: 0.72rem;
  }

  .home-mobile-preview :deep(.profile-avatar) {
    width: 25px;
    height: 25px;
    flex: 0 0 25px;
    font-size: 0.72rem;
  }

  .home-mobile-preview .home-mobile-empty {
    color: #706b61;
    font-size: 0.72rem;
  }
}

@media (max-width: 480px) {
  .home-table-grid {
    grid-template-columns: 1fr;
  }

  .home-metric-card {
    grid-template-columns: 34px minmax(0, 1fr);
    gap: 6px;
    padding: 8px;
  }

  .home-metric-icon {
    width: 34px;
    height: 34px;
  }

  .home-metric-icon :deep(svg) {
    width: 19px;
    height: 19px;
  }

  .home-panel-title h2 {
    font-size: 0.76rem;
  }

  .home-panel-title p {
    font-size: 0.72rem;
  }

  .home-period-select,
  .home-period-select.compact {
    min-width: 90px;
  }

  .home-period-select select {
    font-size: 0.73rem;
  }

  .home-table-panel .home-panel-heading {
    align-items: center;
    padding: 11px 12px;
  }

  .home-table-panel .home-panel-title h2,
  .home-mobile-item-main strong {
    font-size: 0.78rem;
  }

  .home-table-panel .home-panel-title p,
  .home-mobile-item-main small,
  .home-mobile-appointment-time,
  .home-mobile-preview .home-status {
    font-size: 0.72rem;
  }

  .home-view-all {
    min-height: 32px;
    padding: 6px 9px;
    font-size: 0.72rem;
  }

  .home-mobile-appointment-time {
    width: 42px;
    flex-basis: 42px;
  }
}

@media (max-width: 359px) {
  .home-table-grid {
    grid-template-columns: 1fr;
  }

  .home-table-panel .home-panel-title h2 {
    font-size: 0.78rem;
  }

  .home-mobile-preview .home-status {
    font-size: 0.72rem;
  }
}

/* The overview uses the same quiet ivory and gold surfaces as the public pages. */
.clinic-home-dashboard {
  gap: 18px;
}

.home-metric-grid,
.home-analytics-grid,
.home-table-grid {
  gap: 14px;
}

.home-metric-card {
  position: relative;
  grid-template-columns: 64px minmax(0, 1fr);
  min-height: 134px;
  gap: 15px;
  overflow: hidden;
  padding: 20px 22px;
  border-color: #e9d9bc;
  border-radius: 14px;
  background: linear-gradient(145deg, #fffefa 0%, #ffffff 64%, #fbf4e7 100%);
  box-shadow: 0 7px 22px rgba(73, 48, 17, 0.055);
}

.home-metric-card::after {
  position: absolute;
  right: -32px;
  bottom: -54px;
  width: 156px;
  height: 78px;
  border-top: 1px solid #eed7a8;
  border-radius: 50%;
  content: "";
  pointer-events: none;
  transform: rotate(-18deg);
}

.home-metric-card.home-tone-appointments,
.home-metric-card.home-tone-treatments,
.home-metric-card.home-tone-collections {
  border-color: #e9d9bc;
  background: linear-gradient(145deg, #fffefa 0%, #ffffff 64%, #fbf4e7 100%);
}

.home-metric-card:hover,
.home-metric-card:focus-visible {
  border-color: #bd9043;
  box-shadow: 0 12px 28px rgba(88, 57, 20, 0.13);
}

.home-metric-icon,
.home-tone-appointments .home-metric-icon,
.home-tone-treatments .home-metric-icon,
.home-tone-collections .home-metric-icon {
  width: 64px;
  height: 64px;
  color: #8b5e17;
  background: linear-gradient(135deg, #fff8e9, #f2d79b);
}

.home-metric-copy {
  position: relative;
  z-index: 1;
  gap: 3px;
}

.home-metric-copy > small {
  color: #474039;
  font-size: 0.84rem;
}

.home-metric-copy > strong {
  color: #11100e;
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(1.75rem, 2.4vw, 2.15rem);
  font-weight: 700;
  letter-spacing: -0.025em;
  line-height: 1.05;
}

.home-tone-collections .home-metric-copy > strong {
  font-size: clamp(1.3rem, 1.7vw, 1.75rem);
  overflow: visible;
  overflow-wrap: anywhere;
  text-overflow: clip;
  white-space: normal;
}

.home-metric-trend {
  margin-top: 5px;
  font-size: 0.79rem;
  font-weight: 700;
}

.home-metric-trend.up {
  color: #137a42;
}

.home-metric-trend.down {
  color: #c83336;
}

.home-metric-arrow {
  position: absolute;
  z-index: 1;
  right: 17px;
  top: 50%;
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  color: #805412;
  border-radius: 50%;
  background: #f7e7c4;
  transform: translateY(-50%);
}

@media (max-width: 1500px) {
  .home-metric-arrow {
    display: none;
  }
}

.home-dashboard-panel {
  border-color: #eee0cc;
  border-radius: 14px;
  background: #fffefa;
  box-shadow: 0 8px 26px rgba(78, 52, 20, 0.055);
}

.home-panel-heading {
  min-height: 86px;
  padding: 18px 20px;
}

.home-panel-title {
  gap: 12px;
}

.home-panel-title > span {
  width: 58px;
  height: 58px;
  flex-basis: 58px;
  color: #865815;
  background: linear-gradient(135deg, #fcf3df, #f6dfac);
}

.home-panel-title h2 {
  color: #14110e;
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(1.17rem, 1.5vw, 1.48rem);
  font-weight: 700;
  letter-spacing: -0.025em;
}

.home-panel-title p {
  margin-top: 4px;
  color: #66615b;
  font-size: 0.84rem;
}

.home-period-select {
  min-width: 142px;
  color: #734b16;
  border-color: #e7cfaa;
  border-radius: 8px;
  background: #fffefa;
}

.home-period-select select {
  min-height: 42px;
  color: #32271a;
  font-size: 0.79rem;
}

.collection-chart-wrap {
  min-height: 255px;
  padding: 2px 20px 10px;
}

.collection-chart {
  height: 235px;
}

.chart-grid-line {
  stroke: #e9e1d4;
}

.chart-area {
  fill: #f2d69e;
  opacity: 0.65;
}

.chart-line,
.chart-point {
  stroke: #926016;
}

.collection-current-value {
  top: 3px;
  right: 28px;
  padding: 9px 12px;
  border-radius: 7px;
  background: #91601d;
  box-shadow: 0 5px 12px rgba(76, 45, 9, 0.13);
}

.collection-current-value small,
.collection-current-value strong {
  font-size: 0.77rem;
}

.appointment-overview-body {
  min-height: 255px;
  padding: 10px 22px 28px;
}

.appointment-donut {
  width: min(180px, 100%);
}

.donut-center {
  inset: 29%;
  background: #fffefa;
}

.donut-center strong {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.65rem;
}

.appointment-legend dt,
.appointment-legend dd {
  font-size: 0.82rem;
}

.home-view-all {
  min-height: 39px;
  padding: 8px 17px;
  color: #ffffff;
  border-color: #936118;
  border-radius: 7px;
  background: linear-gradient(115deg, #a2762e, #80541b);
  box-shadow: 0 4px 10px rgba(94, 55, 11, 0.12);
  font-size: 0.77rem;
}

.home-view-all:hover,
.home-view-all:focus-visible {
  border-color: #5c3b10;
  background: #5c3b10;
}

.home-table-scroll {
  padding: 0 18px 17px;
}

.home-data-table {
  font-size: 0.78rem;
}

.home-data-table th {
  padding: 11px 13px;
  color: #3c352b;
  background: #fbf2e4;
  font-size: 0.72rem;
}

.home-data-table td {
  padding: 11px 13px;
  border-color: #eee6da;
}

.home-status.approved,
.home-status.accepted {
  color: #12659e;
  border-color: #a6d4ed;
  background: #e9f5fc;
}

.home-status.completed {
  color: #147347;
  border-color: #a7dcc0;
  background: #e9f9ef;
}

.home-status.pending {
  color: #865500;
  border-color: #f0d496;
  background: #fff4db;
}

.home-patient-cell :deep(.profile-avatar) {
  width: 36px;
  height: 36px;
  flex-basis: 36px;
  color: #805413;
  background: #f9ebce;
}

@media (max-width: 1180px) {
  .home-metric-card {
    grid-template-columns: 54px minmax(0, 1fr);
    min-height: 118px;
    gap: 11px;
    padding: 17px;
  }

  .home-metric-icon,
  .home-tone-appointments .home-metric-icon,
  .home-tone-treatments .home-metric-icon,
  .home-tone-collections .home-metric-icon {
    width: 54px;
    height: 54px;
  }

  .home-metric-arrow {
    right: 10px;
    width: 28px;
    height: 28px;
  }
}

@media (max-width: 720px) {
  .clinic-home-dashboard {
    gap: 12px;
  }

  .home-metric-grid,
  .home-analytics-grid,
  .home-table-grid {
    gap: 9px;
  }

  .home-metric-card {
    grid-template-columns: 42px minmax(0, 1fr);
    min-height: 105px;
    gap: 9px;
    padding: 11px;
  }

  .home-metric-icon,
  .home-tone-appointments .home-metric-icon,
  .home-tone-treatments .home-metric-icon,
  .home-tone-collections .home-metric-icon {
    width: 42px;
    height: 42px;
  }

  .home-metric-copy > small {
    font-size: 0.73rem;
  }

  .home-metric-copy > strong {
    font-size: clamp(1.08rem, 4vw, 1.4rem);
  }

  .home-metric-trend {
    font-size: 0.68rem;
  }

  .home-metric-arrow {
    display: none;
  }

  .home-panel-heading {
    min-height: 68px;
    padding: 12px;
  }

  .home-panel-title > span {
    width: 38px;
    height: 38px;
    flex-basis: 38px;
  }

  .home-panel-title h2 {
    font-size: 1rem;
  }

  .home-panel-title p {
    font-size: 0.73rem;
  }

  .home-period-select,
  .home-period-select.compact {
    min-width: 98px;
  }

  .home-period-select select {
    min-height: 34px;
    font-size: 0.73rem;
  }

  .collection-chart-wrap {
    min-height: 0;
    padding: 0 12px 7px;
  }

  .appointment-overview-body {
    min-height: 0;
    padding: 5px 13px 17px;
  }

  .appointment-donut {
    width: min(138px, 100%);
  }

  .appointment-legend dt,
  .appointment-legend dd {
    font-size: 0.73rem;
  }

  .home-table-panel .home-panel-title h2 {
    font-size: 0.77rem;
  }

  .home-view-all {
    min-height: 31px;
    padding: 5px 9px;
    font-size: 0.71rem;
  }
}

@media (max-width: 480px) {
  .home-metric-card {
    grid-template-columns: 35px minmax(0, 1fr);
    min-height: 103px;
    gap: 7px;
    padding: 9px;
  }

  .home-metric-icon,
  .home-tone-appointments .home-metric-icon,
  .home-tone-treatments .home-metric-icon,
  .home-tone-collections .home-metric-icon {
    width: 35px;
    height: 35px;
  }

  .home-metric-copy > strong {
    font-size: clamp(1rem, 4.2vw, 1.32rem);
  }

  .home-tone-collections .home-metric-copy > strong {
    font-size: clamp(0.8rem, 3.5vw, 1.08rem);
  }

  .home-table-panel .home-panel-title h2 {
    font-size: 0.96rem;
  }
}

:global(html[data-dashboard-theme="dark"]) .home-metric-card,
:global(html[data-dashboard-theme="dark"]) .home-metric-card.home-tone-appointments,
:global(html[data-dashboard-theme="dark"]) .home-metric-card.home-tone-treatments,
:global(html[data-dashboard-theme="dark"]) .home-metric-card.home-tone-collections,
:global(html[data-dashboard-theme="dark"]) .home-dashboard-panel {
  color: #f6ead3;
  border-color: #5c4d37;
  background: #26221d;
}

:global(html[data-dashboard-theme="dark"]) .home-metric-copy > strong,
:global(html[data-dashboard-theme="dark"]) .home-panel-title h2 {
  color: #fff4e2;
}

:global(html[data-dashboard-theme="dark"]) .home-metric-copy > small,
:global(html[data-dashboard-theme="dark"]) .home-panel-title p {
  color: #d4c9b9;
}

:global(html[data-dashboard-theme="dark"]) .home-period-select,
:global(html[data-dashboard-theme="dark"]) .donut-center {
  background: #29241d;
}

:global(html[data-dashboard-theme="dark"]) .home-period-select select {
  color: #f1d8a4;
}
</style>
