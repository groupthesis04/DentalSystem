<script setup>
import {
  Banknote,
  CalendarDays,
  ChartNoAxesColumnIncreasing,
  CircleDollarSign,
  CreditCard,
  Download,
  FileDown,
  FileSpreadsheet,
  LayoutDashboard,
  Lightbulb,
  ListFilter,
  Minus,
  Stethoscope,
  TrendingDown,
  TrendingUp,
  Users,
  X,
} from "lucide-vue-next";
import { computed, ref } from "vue";

import ActionIconButton from "../ActionIconButton.vue";
import StatusBadge from "../StatusBadge.vue";
import {
  formatDate,
  formatMoney,
  localDateIso,
  treatmentBalance,
  treatmentProcedure,
} from "../../services/format";
import { showToast } from "../../services/toast";

const props = defineProps({ state: { type: Object, required: true } });
const emit = defineEmits(["select-panel", "open-record", "open-appointment", "open-patient"]);

const today = new Date();
const startDate = ref(localDateIso(new Date(today.getFullYear(), today.getMonth() - 5, 1)));
const endDate = ref(localDateIso(new Date(today.getFullYear(), today.getMonth() + 1, 0)));
const activeTab = ref("overview");
const showAllRows = ref(false);
const tipVisible = ref(true);

const tabs = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "financial", label: "Financial", icon: CircleDollarSign },
  { id: "appointments", label: "Appointments", icon: CalendarDays },
  { id: "services", label: "Services", icon: Stethoscope },
  { id: "patients", label: "Patients", icon: Users },
];

const dateRangeValid = computed(() =>
  Boolean(startDate.value && endDate.value && startDate.value <= endDate.value),
);

function isInRange(value, start = startDate.value, end = endDate.value) {
  const date = String(value || "").slice(0, 10);
  return Boolean(date && start && end && date >= start && date <= end);
}

function shiftDate(value, days) {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + days);
  return localDateIso(date);
}

const previousRange = computed(() => {
  if (!dateRangeValid.value) return { start: "", end: "" };
  const start = new Date(`${startDate.value}T00:00:00`);
  const end = new Date(`${endDate.value}T00:00:00`);
  const days = Math.round((end - start) / 86_400_000) + 1;
  const previousEnd = shiftDate(startDate.value, -1);
  return { start: shiftDate(previousEnd, -(days - 1)), end: previousEnd };
});

const filteredRecords = computed(() =>
  props.state.records
    .filter((item) => dateRangeValid.value && isInRange(item.treatment_date))
    .sort((a, b) =>
      `${b.treatment_date || ""} ${b.created_at || ""}`.localeCompare(
        `${a.treatment_date || ""} ${a.created_at || ""}`,
      ),
    ),
);

const previousRecords = computed(() =>
  props.state.records.filter((item) =>
    isInRange(item.treatment_date, previousRange.value.start, previousRange.value.end),
  ),
);

const filteredAppointments = computed(() =>
  props.state.appointments
    .filter((item) => dateRangeValid.value && isInRange(item.date))
    .sort((a, b) =>
      `${b.date || ""} ${b.time || ""}`.localeCompare(`${a.date || ""} ${a.time || ""}`),
    ),
);

const previousAppointments = computed(() =>
  props.state.appointments.filter((item) =>
    isInRange(item.date, previousRange.value.start, previousRange.value.end),
  ),
);

function totalRecords(records) {
  return records.reduce(
    (sum, item) => {
      sum.charged += Number(item.amount_charged || 0);
      sum.paid += Number(item.amount_paid || 0);
      sum.balance += treatmentBalance(item);
      return sum;
    },
    { charged: 0, paid: 0, balance: 0 },
  );
}

const totals = computed(() => totalRecords(filteredRecords.value));
const previousTotals = computed(() => totalRecords(previousRecords.value));
const collectionRate = computed(() =>
  totals.value.charged
    ? Math.min(100, Math.round((totals.value.paid / totals.value.charged) * 100))
    : 0,
);
const previousCollectionRate = computed(() =>
  previousTotals.value.charged
    ? Math.min(100, Math.round((previousTotals.value.paid / previousTotals.value.charged) * 100))
    : 0,
);

function countStatus(items, status) {
  return items.filter((item) => item.status === status).length;
}

const appointmentCounts = computed(() => ({
  total: filteredAppointments.value.length,
  pending: countStatus(filteredAppointments.value, "pending"),
  approved: countStatus(filteredAppointments.value, "approved"),
  completed: countStatus(filteredAppointments.value, "completed"),
}));

const previousAppointmentCounts = computed(() => ({
  total: previousAppointments.value.length,
  pending: countStatus(previousAppointments.value, "pending"),
  approved: countStatus(previousAppointments.value, "approved"),
  completed: countStatus(previousAppointments.value, "completed"),
}));

function trend(current, previous, inverse = false) {
  if (current === previous) {
    return { icon: Minus, label: "No change vs. previous period", tone: "neutral" };
  }
  const rising = current > previous;
  const percent = previous
    ? Math.round((Math.abs(current - previous) / Math.abs(previous)) * 100)
    : 100;
  return {
    icon: rising ? TrendingUp : TrendingDown,
    label: `${percent}% vs. previous period`,
    tone: inverse ? (rising ? "negative" : "positive") : rising ? "positive" : "negative",
  };
}

const servicePerformance = computed(() => {
  const rows = new Map(
    props.state.services.map((service) => [
      String(service.name || "").toLowerCase(),
      {
        name: service.name,
        treatments: 0,
        patientIds: new Set(),
        charged: 0,
        paid: 0,
        balance: 0,
      },
    ]),
  );
  for (const record of filteredRecords.value) {
    const name = treatmentProcedure(record);
    const key = name.toLowerCase();
    if (!rows.has(key)) {
      rows.set(key, {
        name,
        treatments: 0,
        patientIds: new Set(),
        charged: 0,
        paid: 0,
        balance: 0,
      });
    }
    const row = rows.get(key);
    row.treatments += 1;
    if (record.patient_id) row.patientIds.add(record.patient_id);
    row.charged += Number(record.amount_charged || 0);
    row.paid += Number(record.amount_paid || 0);
    row.balance += treatmentBalance(record);
  }
  return [...rows.values()]
    .map((row) => ({ ...row, patients: row.patientIds.size }))
    .sort((a, b) => b.treatments - a.treatments || a.name.localeCompare(b.name));
});

function buildPatientPerformance(records) {
  const rows = new Map(
    props.state.patients.map((patient) => [
      patient.id,
      {
        id: patient.id,
        name: patient.name,
        contact: patient.mobile_number || patient.phone || patient.email || "-",
        treatments: 0,
        charged: 0,
        paid: 0,
        balance: 0,
        lastVisit: "",
      },
    ]),
  );
  for (const record of records) {
    const key = record.patient_id || `record-${record.patient_name}`;
    if (!rows.has(key)) {
      rows.set(key, {
        id: record.patient_id || "",
        name: record.patient_name || "Patient",
        contact: record.patient_email || record.patient_phone || "-",
        treatments: 0,
        charged: 0,
        paid: 0,
        balance: 0,
        lastVisit: "",
      });
    }
    const row = rows.get(key);
    row.treatments += 1;
    row.charged += Number(record.amount_charged || 0);
    row.paid += Number(record.amount_paid || 0);
    row.balance += treatmentBalance(record);
    if (String(record.treatment_date || "") > row.lastVisit) {
      row.lastVisit = record.treatment_date;
    }
  }
  return [...rows.values()].sort(
    (a, b) => b.treatments - a.treatments || String(a.name).localeCompare(String(b.name)),
  );
}

const patientPerformance = computed(() => buildPatientPerformance(filteredRecords.value));
const previousPatientPerformance = computed(() => buildPatientPerformance(previousRecords.value));

const patientsTreated = computed(
  () => patientPerformance.value.filter((patient) => patient.treatments > 0).length,
);
const previousPatientsTreated = computed(
  () => previousPatientPerformance.value.filter((patient) => patient.treatments > 0).length,
);
const patientsWithBalance = computed(
  () => patientPerformance.value.filter((patient) => patient.balance > 0).length,
);
const previousPatientsWithBalance = computed(
  () => previousPatientPerformance.value.filter((patient) => patient.balance > 0).length,
);

const servicesUsed = computed(
  () => servicePerformance.value.filter((service) => service.treatments > 0).length,
);
const previousServicesUsed = computed(
  () => new Set(previousRecords.value.map((record) => treatmentProcedure(record))).size,
);

const monthlyCollections = computed(() => {
  if (!dateRangeValid.value) return [];
  const rangeStart = new Date(`${startDate.value}T00:00:00`);
  const rangeEnd = new Date(`${endDate.value}T00:00:00`);
  let cursor = new Date(rangeStart.getFullYear(), rangeStart.getMonth(), 1);
  const endMonth = new Date(rangeEnd.getFullYear(), rangeEnd.getMonth(), 1);
  const months = [];
  while (cursor <= endMonth) {
    months.push({
      key: `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}`,
      label: cursor.toLocaleDateString(undefined, { month: "short" }),
      charged: 0,
      paid: 0,
    });
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
  }
  const visibleMonths = months.slice(-6);
  const map = new Map(visibleMonths.map((month) => [month.key, month]));
  for (const record of filteredRecords.value) {
    const month = map.get(String(record.treatment_date || "").slice(0, 7));
    if (!month) continue;
    month.charged += Number(record.amount_charged || 0);
    month.paid += Number(record.amount_paid || 0);
  }
  const maximum = Math.max(1, ...visibleMonths.flatMap((month) => [month.charged, month.paid]));
  return visibleMonths.map((month) => ({
    ...month,
    chargedHeight: Math.max(month.charged ? 5 : 1, (month.charged / maximum) * 100),
    paidHeight: Math.max(month.paid ? 5 : 1, (month.paid / maximum) * 100),
  }));
});

const paidPercent = computed(() =>
  totals.value.charged
    ? Math.min(100, Math.round((totals.value.paid / totals.value.charged) * 1000) / 10)
    : 0,
);
const outstandingPercent = computed(() =>
  totals.value.charged ? Math.max(0, Math.round((100 - paidPercent.value) * 10) / 10) : 0,
);
const donutStyle = computed(() => ({
  background: totals.value.charged
    ? `conic-gradient(#22c55e 0 ${paidPercent.value}%, #f43f5e ${paidPercent.value}% 100%)`
    : "#dce3ec",
}));

function metric(label, value, icon, color, current, previous, inverse = false) {
  return { label, value, icon, color, trend: trend(current, previous, inverse) };
}

const metricCards = computed(() => {
  if (activeTab.value === "appointments") {
    return [
      metric(
        "Total Appointments",
        appointmentCounts.value.total,
        CalendarDays,
        "blue",
        appointmentCounts.value.total,
        previousAppointmentCounts.value.total,
      ),
      metric(
        "Pending",
        appointmentCounts.value.pending,
        ListFilter,
        "amber",
        appointmentCounts.value.pending,
        previousAppointmentCounts.value.pending,
        true,
      ),
      metric(
        "Accepted",
        appointmentCounts.value.approved,
        ChartNoAxesColumnIncreasing,
        "purple",
        appointmentCounts.value.approved,
        previousAppointmentCounts.value.approved,
      ),
      metric(
        "Completed",
        appointmentCounts.value.completed,
        Banknote,
        "green",
        appointmentCounts.value.completed,
        previousAppointmentCounts.value.completed,
      ),
    ];
  }
  if (activeTab.value === "services") {
    return [
      metric(
        "Services Used",
        servicesUsed.value,
        Stethoscope,
        "blue",
        servicesUsed.value,
        previousServicesUsed.value,
      ),
      metric(
        "Treatments",
        filteredRecords.value.length,
        ListFilter,
        "purple",
        filteredRecords.value.length,
        previousRecords.value.length,
      ),
      metric(
        "Amount Charged",
        formatMoney(totals.value.charged),
        CircleDollarSign,
        "rose",
        totals.value.charged,
        previousTotals.value.charged,
      ),
      metric(
        "Amount Paid",
        formatMoney(totals.value.paid),
        Banknote,
        "green",
        totals.value.paid,
        previousTotals.value.paid,
      ),
    ];
  }
  if (activeTab.value === "patients") {
    const average = patientsTreated.value ? totals.value.charged / patientsTreated.value : 0;
    const previousAverage = previousPatientsTreated.value
      ? previousTotals.value.charged / previousPatientsTreated.value
      : 0;
    return [
      metric(
        "Patients Treated",
        patientsTreated.value,
        Users,
        "blue",
        patientsTreated.value,
        previousPatientsTreated.value,
      ),
      metric(
        "Treatment Records",
        filteredRecords.value.length,
        ListFilter,
        "purple",
        filteredRecords.value.length,
        previousRecords.value.length,
      ),
      metric(
        "With Balance",
        patientsWithBalance.value,
        CreditCard,
        "rose",
        patientsWithBalance.value,
        previousPatientsWithBalance.value,
        true,
      ),
      metric(
        "Average Charged",
        formatMoney(average),
        CircleDollarSign,
        "green",
        average,
        previousAverage,
      ),
    ];
  }

  const cards = [
    metric(
      "Total Amount Charged",
      formatMoney(totals.value.charged),
      CircleDollarSign,
      "blue",
      totals.value.charged,
      previousTotals.value.charged,
    ),
    metric(
      "Total Amount Paid",
      formatMoney(totals.value.paid),
      Banknote,
      "green",
      totals.value.paid,
      previousTotals.value.paid,
    ),
    metric(
      "Outstanding Balance",
      formatMoney(totals.value.balance),
      CreditCard,
      "rose",
      totals.value.balance,
      previousTotals.value.balance,
      true,
    ),
  ];
  cards.push(
    activeTab.value === "financial"
      ? metric(
          "Collection Rate",
          `${collectionRate.value}%`,
          ChartNoAxesColumnIncreasing,
          "purple",
          collectionRate.value,
          previousCollectionRate.value,
        )
      : metric(
          "Total Appointments",
          appointmentCounts.value.total,
          CalendarDays,
          "purple",
          appointmentCounts.value.total,
          previousAppointmentCounts.value.total,
        ),
  );
  return cards;
});

const tableTitle = computed(() => {
  const titles = {
    overview: "Recent Transactions",
    financial: "Financial Transactions",
    appointments: "Appointment Report",
    services: "Service Performance",
    patients: "Patient Report",
  };
  return titles[activeTab.value];
});

const tableDescription = computed(() => {
  const descriptions = {
    overview: "Latest treatments and their payment status",
    financial: "Charges, payments, and balances for the selected period",
    appointments: "Clinic appointments within the selected period",
    services: "Treatment and collection totals grouped by service",
    patients: "Patient activity and balances within the selected period",
  };
  return descriptions[activeTab.value];
});

const tableRowCount = computed(() => {
  if (activeTab.value === "appointments") return filteredAppointments.value.length;
  if (activeTab.value === "services") return servicePerformance.value.length;
  if (activeTab.value === "patients") return patientPerformance.value.length;
  return filteredRecords.value.length;
});

const visibleRecords = computed(() =>
  showAllRows.value ? filteredRecords.value : filteredRecords.value.slice(0, 5),
);
const visibleAppointments = computed(() =>
  showAllRows.value ? filteredAppointments.value : filteredAppointments.value.slice(0, 5),
);
const visibleServices = computed(() =>
  showAllRows.value ? servicePerformance.value : servicePerformance.value.slice(0, 5),
);
const visiblePatients = computed(() =>
  showAllRows.value ? patientPerformance.value : patientPerformance.value.slice(0, 5),
);

function selectTab(tab) {
  activeTab.value = tab;
  showAllRows.value = false;
}

function paymentStatus(record) {
  return treatmentBalance(record) > 0 ? "unpaid" : "paid";
}

function exportRows() {
  if (activeTab.value === "appointments") {
    return filteredAppointments.value.map((item) => ({
      Date: item.date,
      Time: item.time,
      Patient: item.patient_name,
      Service: item.service,
      Status: item.status === "approved" ? "Accepted" : item.status,
    }));
  }
  if (activeTab.value === "services") {
    return servicePerformance.value.map((item) => ({
      Service: item.name,
      Treatments: item.treatments,
      Patients: item.patients,
      Charged: item.charged.toFixed(2),
      Paid: item.paid.toFixed(2),
      Balance: item.balance.toFixed(2),
    }));
  }
  if (activeTab.value === "patients") {
    return patientPerformance.value.map((item) => ({
      Patient: item.name,
      Contact: item.contact,
      Treatments: item.treatments,
      Last_Visit: item.lastVisit,
      Charged: item.charged.toFixed(2),
      Paid: item.paid.toFixed(2),
      Balance: item.balance.toFixed(2),
    }));
  }
  return filteredRecords.value.map((item) => ({
    Date: item.treatment_date,
    Patient: item.patient_name,
    Service: treatmentProcedure(item),
    Amount_Charged: Number(item.amount_charged || 0).toFixed(2),
    Amount_Paid: Number(item.amount_paid || 0).toFixed(2),
    Balance: treatmentBalance(item).toFixed(2),
    Payment_Status: paymentStatus(item),
  }));
}

function csvCell(value) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function downloadCsv() {
  const rows = exportRows();
  if (!rows.length) {
    showToast("There is no report data in the selected date range.", "error");
    return;
  }
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.map(csvCell).join(","),
    ...rows.map((row) => headers.map((header) => csvCell(row[header])).join(",")),
  ].join("\r\n");
  const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `dental-${activeTab.value}-report-${startDate.value}-to-${endDate.value}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
  showToast("Report exported.");
}

function printReport() {
  window.print();
}
</script>

<template>
  <section class="workspace-panel reports-page" aria-labelledby="reports-title">
    <header class="reports-page-heading">
      <div>
        <h1 id="reports-title">Reports</h1>
        <p>Track clinic performance, collections, appointments, services, and patients.</p>
      </div>
      <div class="reports-toolbar">
        <div class="report-date-range" aria-label="Report date range">
          <CalendarDays :size="18" aria-hidden="true" />
          <label>
            <span>From</span>
            <input v-model="startDate" type="date" @change="showAllRows = false" />
          </label>
          <span aria-hidden="true">-</span>
          <label>
            <span>To</span>
            <input v-model="endDate" type="date" @change="showAllRows = false" />
          </label>
        </div>
        <button
          class="report-export-button"
          type="button"
          :disabled="!dateRangeValid"
          @click="downloadCsv"
        >
          <Download :size="17" aria-hidden="true" /> Export Report
        </button>
      </div>
    </header>

    <p v-if="!dateRangeValid" class="report-date-error" role="alert">
      The start date must be on or before the end date.
    </p>

    <nav class="report-tabs" role="tablist" aria-label="Report type">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.id"
        :class="{ active: activeTab === tab.id }"
        @click="selectTab(tab.id)"
      >
        <component :is="tab.icon" :size="16" aria-hidden="true" />
        {{ tab.label }}
      </button>
    </nav>

    <section class="report-metric-grid" aria-label="Report summary">
      <article
        v-for="card in metricCards"
        :key="card.label"
        class="report-metric-card"
        :class="`report-metric-${card.color}`"
      >
        <span class="report-metric-icon">
          <component :is="card.icon" :size="21" aria-hidden="true" />
        </span>
        <div class="report-metric-copy">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small :class="card.trend.tone">
            <component :is="card.trend.icon" :size="13" aria-hidden="true" />
            {{ card.trend.label }}
          </small>
        </div>
      </article>
    </section>

    <div v-if="activeTab === 'overview' || activeTab === 'financial'" class="report-chart-grid">
      <section class="report-panel report-collections-panel" aria-labelledby="collections-title">
        <header class="report-panel-heading">
          <div>
            <h2 id="collections-title">Monthly Collections</h2>
            <p>Up to the latest six months in the selected period</p>
          </div>
          <div class="report-chart-legend" aria-label="Chart legend">
            <span><i class="charged"></i>Amount Charged</span>
            <span><i class="paid"></i>Amount Paid</span>
          </div>
        </header>
        <div
          v-if="monthlyCollections.length"
          class="report-bar-chart"
          role="img"
          aria-label="Monthly charged and paid amounts"
        >
          <div v-for="month in monthlyCollections" :key="month.key" class="report-month-group">
            <div class="report-month-bars">
              <span
                class="charged"
                :style="{ height: `${month.chargedHeight}%` }"
                :title="`${month.label} charged: ${formatMoney(month.charged)}`"
              ></span>
              <span
                class="paid"
                :style="{ height: `${month.paidHeight}%` }"
                :title="`${month.label} paid: ${formatMoney(month.paid)}`"
              ></span>
            </div>
            <small>{{ month.label }}</small>
          </div>
        </div>
        <p v-else class="report-empty">Choose a valid date range to display collections.</p>
      </section>

      <section class="report-panel report-payment-panel" aria-labelledby="payment-title">
        <header class="report-panel-heading">
          <div>
            <h2 id="payment-title">Payment Status</h2>
            <p>Paid and outstanding treatment charges</p>
          </div>
        </header>
        <div class="report-payment-content">
          <div
            class="report-donut"
            :style="donutStyle"
            role="img"
            aria-label="Payment status chart"
          >
            <span>
              <strong>{{ formatMoney(totals.charged) }}</strong>
              <small>Total Charged</small>
            </span>
          </div>
          <dl class="report-payment-legend">
            <div>
              <dt><i class="paid"></i>Paid</dt>
              <dd>
                <strong>{{ formatMoney(totals.paid) }}</strong>
                <span>{{ paidPercent }}%</span>
              </dd>
            </div>
            <div>
              <dt><i class="outstanding"></i>Outstanding</dt>
              <dd>
                <strong>{{ formatMoney(totals.balance) }}</strong>
                <span>{{ outstandingPercent }}%</span>
              </dd>
            </div>
          </dl>
        </div>
      </section>
    </div>

    <div class="report-bottom-grid">
      <section class="report-panel report-table-panel" aria-labelledby="report-table-title">
        <header class="report-panel-heading">
          <div>
            <h2 id="report-table-title">{{ tableTitle }}</h2>
            <p>{{ tableDescription }}</p>
          </div>
          <span class="report-row-count"
            >{{ tableRowCount }} {{ tableRowCount === 1 ? "record" : "records" }}</span
          >
        </header>

        <div class="report-table-wrap">
          <table v-if="activeTab === 'overview' || activeTab === 'financial'" class="report-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Patient Name</th>
                <th>Date</th>
                <th>Service</th>
                <th>Paid</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(record, index) in visibleRecords" :key="record.id">
                <td>{{ index + 1 }}</td>
                <td>
                  <strong>{{ record.patient_name }}</strong>
                </td>
                <td>{{ formatDate(record.treatment_date) }}</td>
                <td>{{ treatmentProcedure(record) }}</td>
                <td>{{ formatMoney(record.amount_paid) }}</td>
                <td><StatusBadge :status="paymentStatus(record)" /></td>
                <td>
                  <ActionIconButton
                    action="view"
                    :label="`View ${record.patient_name}'s record`"
                    @click="emit('open-record', record.id)"
                  />
                </td>
              </tr>
              <tr v-if="!visibleRecords.length">
                <td colspan="7" class="table-empty">No transactions in this date range.</td>
              </tr>
            </tbody>
          </table>

          <table v-else-if="activeTab === 'appointments'" class="report-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Patient Name</th>
                <th>Date</th>
                <th>Time</th>
                <th>Service</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(appointment, index) in visibleAppointments" :key="appointment.id">
                <td>{{ index + 1 }}</td>
                <td>
                  <strong>{{ appointment.patient_name }}</strong>
                </td>
                <td>{{ formatDate(appointment.date) }}</td>
                <td>{{ appointment.time }}</td>
                <td>{{ appointment.service }}</td>
                <td><StatusBadge :status="appointment.status" /></td>
                <td>
                  <ActionIconButton
                    action="view"
                    :label="`View appointment for ${appointment.patient_name}`"
                    @click="emit('open-appointment', appointment.id)"
                  />
                </td>
              </tr>
              <tr v-if="!visibleAppointments.length">
                <td colspan="7" class="table-empty">No appointments in this date range.</td>
              </tr>
            </tbody>
          </table>

          <table v-else-if="activeTab === 'services'" class="report-table service-report-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Service</th>
                <th>Treatments</th>
                <th>Patients</th>
                <th>Charged</th>
                <th>Paid</th>
                <th>Balance</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(service, index) in visibleServices" :key="service.name">
                <td>{{ index + 1 }}</td>
                <td>
                  <strong>{{ service.name }}</strong>
                </td>
                <td>{{ service.treatments }}</td>
                <td>{{ service.patients }}</td>
                <td>{{ formatMoney(service.charged) }}</td>
                <td>{{ formatMoney(service.paid) }}</td>
                <td>{{ formatMoney(service.balance) }}</td>
              </tr>
              <tr v-if="!visibleServices.length">
                <td colspan="7" class="table-empty">No services are available.</td>
              </tr>
            </tbody>
          </table>

          <table v-else class="report-table patient-report-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Patient Name</th>
                <th>Contact</th>
                <th>Treatments</th>
                <th>Last Visit</th>
                <th>Balance</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(patient, index) in visiblePatients" :key="patient.id || patient.name">
                <td>{{ index + 1 }}</td>
                <td>
                  <strong>{{ patient.name }}</strong>
                </td>
                <td>{{ patient.contact }}</td>
                <td>{{ patient.treatments }}</td>
                <td>{{ formatDate(patient.lastVisit) }}</td>
                <td>{{ formatMoney(patient.balance) }}</td>
                <td>
                  <ActionIconButton
                    action="view"
                    :label="`View ${patient.name}`"
                    @click="emit('open-patient', patient.id)"
                  />
                </td>
              </tr>
              <tr v-if="!visiblePatients.length">
                <td colspan="7" class="table-empty">No patient records are available.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <button
          v-if="tableRowCount > 5"
          class="report-more-button"
          type="button"
          @click="showAllRows = !showAllRows"
        >
          {{ showAllRows ? "Show Less" : "More" }}
        </button>
      </section>

      <aside class="report-side-column">
        <section class="report-panel report-quick-panel" aria-labelledby="quick-actions-title">
          <header class="report-panel-heading">
            <div>
              <h2 id="quick-actions-title">Quick Actions</h2>
              <p>Export or open a focused report</p>
            </div>
          </header>
          <div class="report-quick-actions">
            <button class="pdf-action" type="button" @click="printReport">
              <span><FileDown :size="20" aria-hidden="true" /></span>
              <strong>Export to PDF</strong>
              <small>Open the printable report</small>
            </button>
            <button
              class="excel-action"
              type="button"
              :disabled="!dateRangeValid"
              @click="downloadCsv"
            >
              <span><FileSpreadsheet :size="20" aria-hidden="true" /></span>
              <strong>Export to Excel</strong>
              <small>Download a spreadsheet-ready CSV</small>
            </button>
            <button class="detail-action" type="button" @click="selectTab('financial')">
              <span><ChartNoAxesColumnIncreasing :size="20" aria-hidden="true" /></span>
              <strong>View Financial Report</strong>
              <small>Collections and payment status</small>
            </button>
            <button class="appointment-action" type="button" @click="selectTab('appointments')">
              <span><CalendarDays :size="20" aria-hidden="true" /></span>
              <strong>Appointment Report</strong>
              <small>View schedule statistics</small>
            </button>
          </div>
        </section>

        <section v-if="tipVisible" class="report-tip" aria-label="Report tip">
          <Lightbulb :size="18" aria-hidden="true" />
          <p>
            <strong>Tip</strong>
            Use the date range to focus every metric, chart, table, and exported report.
          </p>
          <button
            type="button"
            title="Dismiss tip"
            aria-label="Dismiss tip"
            @click="tipVisible = false"
          >
            <X :size="16" aria-hidden="true" />
          </button>
        </section>
      </aside>
    </div>
  </section>
</template>
