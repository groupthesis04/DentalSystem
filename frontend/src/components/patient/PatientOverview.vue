<script setup>
import {
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  CircleUserRound,
  Clock3,
  FileText,
  HeartPulse,
  MapPin,
  Phone,
  Stethoscope,
  XCircle,
  Zap,
} from "lucide-vue-next";
import { computed, ref } from "vue";

import { appointmentService, formatDate, localDateIso } from "../../services/format";
import StatusBadge from "../StatusBadge.vue";

const props = defineProps({
  appointments: { type: Array, default: () => [] },
  records: { type: Array, default: () => [] },
  highlightedId: { type: String, default: "" },
});

const emit = defineEmits([
  "book",
  "open-appointments",
  "open-records",
  "open-profile",
  "open-services",
]);

const appointmentFilter = ref("all");
const todayIso = localDateIso();
const activeStatuses = new Set(["pending", "approved", "accepted"]);

function normalizedStatus(item) {
  return String(item?.status || "").toLowerCase();
}

function formatTime(value) {
  const text = String(value || "").trim();
  if (!text) return "-";
  if (/\b(?:am|pm)\b/i.test(text))
    return text.replace(/\b(am|pm)\b/i, (part) => part.toUpperCase());
  const match = /^(\d{1,2}):(\d{2})/.exec(text);
  if (!match) return text;
  const hours = Number(match[1]);
  const suffix = hours >= 12 ? "PM" : "AM";
  return `${String(hours % 12 || 12).padStart(2, "0")}:${match[2]} ${suffix}`;
}

function appointmentKey(item) {
  return `${item?.date || ""} ${item?.time || ""}`;
}

const upcomingAppointments = computed(() =>
  props.appointments
    .filter((item) => item.date >= todayIso && activeStatuses.has(normalizedStatus(item)))
    .sort((a, b) => appointmentKey(a).localeCompare(appointmentKey(b))),
);

const nextVisit = computed(() => upcomingAppointments.value[0] || null);
const completedVisits = computed(
  () => props.appointments.filter((item) => normalizedStatus(item) === "completed").length,
);
const cancelledVisits = computed(
  () => props.appointments.filter((item) => normalizedStatus(item) === "cancelled").length,
);

const summaryCards = computed(() => [
  {
    key: "total",
    label: "Total Appointments",
    value: props.appointments.length,
    icon: CalendarDays,
  },
  {
    key: "completed",
    label: "Completed Visits",
    value: completedVisits.value,
    icon: CheckCircle2,
  },
  {
    key: "upcoming",
    label: "Upcoming Visits",
    value: upcomingAppointments.value.length,
    icon: Clock3,
  },
  {
    key: "cancelled",
    label: "Cancelled Visits",
    value: cancelledVisits.value,
    icon: XCircle,
  },
]);

const appointmentFilters = computed(() => [
  { value: "all", label: "All", count: props.appointments.length },
  { value: "upcoming", label: "Upcoming", count: upcomingAppointments.value.length },
  { value: "completed", label: "Completed", count: completedVisits.value },
  { value: "cancelled", label: "Cancelled", count: cancelledVisits.value },
]);

const visibleAppointments = computed(() => {
  let items = [...props.appointments];
  if (appointmentFilter.value === "upcoming") {
    items = items.filter(
      (item) => item.date >= todayIso && activeStatuses.has(normalizedStatus(item)),
    );
    items.sort((a, b) => appointmentKey(a).localeCompare(appointmentKey(b)));
  } else {
    if (appointmentFilter.value !== "all") {
      items = items.filter((item) => normalizedStatus(item) === appointmentFilter.value);
    }
    items.sort((a, b) => appointmentKey(b).localeCompare(appointmentKey(a)));
  }
  return items.slice(0, 5);
});

const nextVisitDate = computed(() => {
  if (!nextVisit.value?.date) return { month: "NEXT", day: "--", year: "" };
  const [year, month, day] = nextVisit.value.date.slice(0, 10).split("-").map(Number);
  const parsed = new Date(year, month - 1, day);
  return {
    month: parsed.toLocaleDateString(undefined, { month: "short" }).toUpperCase(),
    day: String(day).padStart(2, "0"),
    year: String(year),
  };
});

function openAppointment(item) {
  emit("open-appointments", item || null);
}
</script>

<template>
  <section class="workspace-panel patient-home-dashboard">
    <section class="patient-summary-cards" aria-label="Appointment summary">
      <article
        v-for="card in summaryCards"
        :key="card.key"
        class="patient-summary-card"
        :class="`summary-${card.key}`"
      >
        <span class="patient-summary-icon"><component :is="card.icon" :size="26" /></span>
        <span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.label }}</small>
        </span>
      </article>
    </section>

    <div class="patient-home-content">
      <div class="patient-home-primary">
        <section class="patient-home-panel patient-upcoming-panel" aria-labelledby="upcoming-title">
          <header class="patient-panel-heading">
            <div>
              <span class="patient-heading-icon"
                ><CalendarDays :size="20" aria-hidden="true"
              /></span>
              <span class="patient-heading-copy">
                <h2 id="upcoming-title">Upcoming Appointment</h2>
                <small>Your next scheduled visit</small>
              </span>
            </div>
            <button type="button" @click="openAppointment(nextVisit)">View All</button>
          </header>

          <div v-if="nextVisit" class="patient-upcoming-body" :data-entity-id="nextVisit.id">
            <time class="patient-date-tile" :datetime="nextVisit.date">
              <span>{{ nextVisitDate.month }}</span>
              <strong>{{ nextVisitDate.day }}</strong>
              <small>{{ nextVisitDate.year }}</small>
            </time>
            <div class="patient-upcoming-copy">
              <h3>{{ appointmentService(nextVisit) }}</h3>
              <dl>
                <div>
                  <dt>Dentist</dt>
                  <dd>{{ nextVisit.doctor || "Clinic dentist" }}</dd>
                </div>
                <div>
                  <dt>Time</dt>
                  <dd>{{ formatTime(nextVisit.time) }}</dd>
                </div>
                <div>
                  <dt>Location</dt>
                  <dd>BORJA Dental Clinic</dd>
                </div>
              </dl>
            </div>
            <button class="patient-view-details" type="button" @click="openAppointment(nextVisit)">
              View Details <ChevronRight :size="18" aria-hidden="true" />
            </button>
          </div>
          <div v-else class="patient-upcoming-empty">
            <span><CalendarDays :size="28" aria-hidden="true" /></span>
            <div>
              <h3>No upcoming appointment</h3>
              <p>Choose an available clinic schedule when you are ready.</p>
            </div>
            <button type="button" @click="emit('book')">Book Appointment</button>
          </div>
        </section>

        <section
          class="patient-home-panel patient-appointments-panel"
          aria-labelledby="home-appointments-title"
        >
          <header class="patient-panel-heading appointment-heading">
            <div>
              <span class="patient-heading-icon"
                ><CalendarDays :size="20" aria-hidden="true"
              /></span>
              <span class="patient-heading-copy">
                <h2 id="home-appointments-title">My Appointments</h2>
                <small>Your clinic visit history</small>
              </span>
            </div>
            <button type="button" @click="openAppointment(null)">View All</button>
          </header>

          <div class="patient-filter-tabs" role="tablist" aria-label="Filter appointments">
            <button
              v-for="filter in appointmentFilters"
              :key="filter.value"
              type="button"
              role="tab"
              :aria-selected="appointmentFilter === filter.value"
              :class="{ active: appointmentFilter === filter.value }"
              @click="appointmentFilter = filter.value"
            >
              {{ filter.label }} <span>{{ filter.count }}</span>
            </button>
          </div>

          <div class="patient-home-table-wrap">
            <table class="patient-home-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Service</th>
                  <th>Dentist</th>
                  <th>Date &amp; Time</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(item, index) in visibleAppointments"
                  :key="item.id"
                  :data-entity-id="item.id"
                  :class="{ 'notification-target-glow': highlightedId === item.id }"
                >
                  <td data-label="#">{{ index + 1 }}</td>
                  <td data-label="Service">
                    <strong>{{ appointmentService(item) }}</strong>
                  </td>
                  <td data-label="Dentist">{{ item.doctor || "Clinic dentist" }}</td>
                  <td data-label="Date & Time">
                    {{ formatDate(item.date) }}<small>{{ formatTime(item.time) }}</small>
                  </td>
                  <td data-label="Status"><StatusBadge :status="item.status" /></td>
                  <td data-label="Action">
                    <button type="button" @click="openAppointment(item)">View</button>
                  </td>
                </tr>
                <tr v-if="!visibleAppointments.length">
                  <td class="patient-table-empty" colspan="6">
                    No {{ appointmentFilter === "all" ? "" : appointmentFilter }} appointments to
                    show.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <ul class="patient-mobile-appointments" aria-label="Recent appointments">
            <li v-for="item in visibleAppointments" :key="item.id" :data-entity-id="item.id">
              <button
                type="button"
                :class="{ 'notification-target-glow': highlightedId === item.id }"
                @click="openAppointment(item)"
              >
                <span class="patient-mobile-appointment-date">
                  <strong>{{ formatDate(item.date) }}</strong>
                  <small>{{ formatTime(item.time) }}</small>
                </span>
                <span class="patient-mobile-appointment-copy">
                  <strong>{{ appointmentService(item) }}</strong>
                  <small>{{ item.doctor || "Clinic dentist" }}</small>
                </span>
                <StatusBadge :status="item.status" />
                <ChevronRight :size="16" aria-hidden="true" />
              </button>
            </li>
            <li v-if="!visibleAppointments.length" class="patient-mobile-appointment-empty">
              No {{ appointmentFilter === "all" ? "" : appointmentFilter }} appointments to show.
            </li>
          </ul>
        </section>
      </div>

      <aside class="patient-home-rail" aria-label="Patient shortcuts and clinic details">
        <section
          class="patient-home-panel patient-quick-panel"
          aria-labelledby="quick-actions-title"
        >
          <header class="patient-panel-heading compact">
            <div>
              <span class="patient-heading-icon"><Zap :size="20" aria-hidden="true" /></span>
              <span class="patient-heading-copy">
                <h2 id="quick-actions-title">Quick Actions</h2>
                <small>What would you like to do?</small>
              </span>
            </div>
          </header>
          <div class="patient-quick-grid">
            <button type="button" @click="emit('book')">
              <span><CalendarDays :size="22" /></span>
              <span><strong>Book Appointment</strong><small>Schedule a new visit</small></span>
              <ChevronRight :size="17" />
            </button>
            <button type="button" @click="emit('open-records')">
              <span><FileText :size="22" /></span>
              <span
                ><strong>View Records</strong
                ><small>{{ records.length }} treatment records</small></span
              >
              <ChevronRight :size="17" />
            </button>
            <button type="button" @click="emit('open-services')">
              <span><Stethoscope :size="22" /></span>
              <span><strong>Our Services</strong><small>Explore treatments</small></span>
              <ChevronRight :size="17" />
            </button>
            <button type="button" @click="emit('open-profile')">
              <span><CircleUserRound :size="22" /></span>
              <span><strong>Update Profile</strong><small>Edit your information</small></span>
              <ChevronRight :size="17" />
            </button>
          </div>
        </section>

        <section
          class="patient-home-panel patient-clinic-panel"
          aria-labelledby="clinic-information-title"
        >
          <header class="patient-panel-heading compact">
            <div>
              <span class="patient-heading-icon"><MapPin :size="20" aria-hidden="true" /></span>
              <span class="patient-heading-copy">
                <h2 id="clinic-information-title">Clinic Information</h2>
                <small>Visit or contact our clinic</small>
              </span>
            </div>
          </header>
          <address>
            <div>
              <MapPin :size="18" aria-hidden="true" />
              <span
                ><strong>BORJA Dental Clinic</strong
                ><small
                  >Stall #4, R.J. Montano Bldg., National Road, Brgy. Banica, Roxas City,
                  Capiz</small
                ></span
              >
            </div>
            <div>
              <Phone :size="18" aria-hidden="true" />
              <a href="tel:+639364510141">+63 936 451 0141</a>
            </div>
            <div>
              <Clock3 :size="18" aria-hidden="true" />
              <span>Clinic visits are by appointment</span>
            </div>
          </address>
          <HeartPulse class="patient-clinic-watermark" :size="108" aria-hidden="true" />
        </section>

        <section class="patient-care-note">
          <span><HeartPulse :size="27" aria-hidden="true" /></span>
          <div>
            <strong>Take care of your smile!</strong>
            <p>Regular dental visits support a healthier and happier you.</p>
          </div>
        </section>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.patient-home-dashboard {
  display: grid;
  gap: 14px;
  color: #14284a;
}

.patient-summary-card,
.patient-home-panel,
.patient-care-note {
  border: 1px solid #dce8f3;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 5px 18px rgb(31 64 102 / 5%);
}

.patient-summary-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.patient-summary-card {
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr);
  min-width: 0;
  min-height: 96px;
  align-items: center;
  gap: 14px;
  padding: 16px;
}

.patient-summary-icon {
  display: grid;
  width: 54px;
  height: 54px;
  place-items: center;
  border-radius: 8px;
  background: #e5f0ff;
  color: #2678e9;
}

.patient-summary-card > span:last-child,
.patient-summary-card strong,
.patient-summary-card small {
  display: block;
  min-width: 0;
}

.patient-summary-card strong {
  overflow: hidden;
  color: #10274b;
  font-size: 1.55rem;
  line-height: 1.1;
  text-overflow: ellipsis;
}

.patient-summary-card small {
  margin-top: 5px;
  color: #5f7491;
  font-size: 0.76rem;
}

.summary-completed .patient-summary-icon {
  background: #ddf7ec;
  color: #0f9f6e;
}

.summary-upcoming .patient-summary-icon {
  background: #fff2d8;
  color: #dc9410;
}

.summary-cancelled .patient-summary-icon {
  background: #ffe6e9;
  color: #df5262;
}

.patient-home-content {
  display: grid;
  grid-template-columns: minmax(0, 2.15fr) minmax(320px, 0.95fr);
  align-items: start;
  gap: 14px;
}

.patient-home-primary,
.patient-home-rail {
  display: grid;
  min-width: 0;
  gap: 14px;
}

.patient-home-panel {
  min-width: 0;
  overflow: hidden;
}

.patient-panel-heading {
  display: flex;
  min-height: 56px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 18px;
}

.patient-panel-heading > div {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
  color: #1876e7;
}

.patient-heading-icon {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
}

.patient-heading-copy {
  display: block;
  min-width: 0;
}

.patient-heading-copy > small {
  display: none;
}

.patient-panel-heading h2 {
  margin: 0;
  color: #14284a;
  font-size: 0.94rem;
}

.patient-panel-heading > button {
  border: 0;
  background: transparent;
  padding: 5px;
  color: #126fe1;
  font-size: 0.72rem;
  font-weight: 750;
  cursor: pointer;
}

.patient-panel-heading > button:hover,
.patient-panel-heading > button:focus-visible {
  color: #0e4fa6;
  text-decoration: underline;
  outline: none;
}

.patient-panel-heading.compact {
  min-height: 50px;
  padding-block: 10px;
}

.patient-upcoming-body {
  display: grid;
  grid-template-columns: 78px minmax(0, 1fr) auto;
  align-items: center;
  gap: 20px;
  min-height: 132px;
  margin: 0 18px 16px;
  background: #eef7ff;
  padding: 18px;
}

.patient-date-tile {
  display: grid;
  width: 72px;
  height: 82px;
  align-content: center;
  overflow: hidden;
  border: 1px solid #bdd8fb;
  border-radius: 7px;
  background: #fff;
  color: #17335a;
  text-align: center;
}

.patient-date-tile span {
  align-self: stretch;
  margin: -13px -1px 6px;
  background: #2178e6;
  padding: 5px;
  color: #fff;
  font-size: 0.63rem;
  font-weight: 800;
}

.patient-date-tile strong {
  font-size: 1.35rem;
  line-height: 1;
}

.patient-date-tile small {
  margin-top: 5px;
  color: #667c99;
  font-size: 0.64rem;
}

.patient-upcoming-copy {
  min-width: 0;
}

.patient-upcoming-copy h3 {
  overflow: hidden;
  margin: 0 0 8px;
  color: #14284a;
  font-size: 0.95rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.patient-upcoming-copy dl {
  display: flex;
  flex-wrap: wrap;
  gap: 7px 20px;
  margin: 0;
}

.patient-upcoming-copy dl > div {
  display: flex;
  align-items: center;
  gap: 5px;
}

.patient-upcoming-copy dt {
  color: #6e8098;
  font-size: 0.65rem;
}

.patient-upcoming-copy dd {
  margin: 0;
  color: #405776;
  font-size: 0.7rem;
  font-weight: 750;
}

.patient-view-details,
.patient-upcoming-empty > button {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid #176dd8;
  border-radius: 7px;
  background: #1876e7;
  padding: 9px 16px;
  color: #fff;
  font-size: 0.73rem;
  font-weight: 800;
  cursor: pointer;
}

.patient-view-details:hover,
.patient-view-details:focus-visible,
.patient-upcoming-empty > button:hover,
.patient-upcoming-empty > button:focus-visible {
  background: #115cbe;
  outline: 3px solid rgb(24 118 231 / 16%);
}

.patient-upcoming-empty {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  min-height: 118px;
  margin: 0 18px 16px;
  background: #f5f9fe;
  padding: 18px;
}

.patient-upcoming-empty > span {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border-radius: 50%;
  background: #e2efff;
  color: #1d73dd;
}

.patient-upcoming-empty h3,
.patient-upcoming-empty p {
  margin: 0;
}

.patient-upcoming-empty h3 {
  font-size: 0.86rem;
}

.patient-upcoming-empty p {
  margin-top: 3px;
  color: #697d98;
  font-size: 0.7rem;
}

.appointment-heading {
  padding-bottom: 7px;
}

.patient-filter-tabs {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding: 0 18px 11px;
}

.patient-filter-tabs button {
  display: inline-flex;
  min-width: 92px;
  min-height: 32px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid #dce6f1;
  border-radius: 6px;
  background: #f3f6fa;
  padding: 6px 11px;
  color: #526986;
  font-size: 0.68rem;
  font-weight: 750;
  cursor: pointer;
}

.patient-filter-tabs button span {
  min-width: 19px;
  border-radius: 50%;
  background: rgb(255 255 255 / 72%);
  padding: 1px 5px;
  font-size: 0.58rem;
}

.patient-filter-tabs button:hover,
.patient-filter-tabs button:focus-visible,
.patient-filter-tabs button.active {
  border-color: #1d75e4;
  background: #1d75e4;
  color: #fff;
  outline: none;
}

.patient-home-table-wrap {
  overflow-x: auto;
  padding: 0 18px 16px;
}

.patient-mobile-appointments {
  display: none;
}

.patient-home-table {
  width: 100%;
  border-collapse: collapse;
  color: #263f61;
  font-size: 0.68rem;
}

.patient-home-table th,
.patient-home-table td {
  border-bottom: 1px solid #e6edf4;
  padding: 9px 11px;
  text-align: left;
  vertical-align: middle;
}

.patient-home-table th {
  background: #f1f6fb;
  color: #516883;
  font-size: 0.61rem;
  text-transform: uppercase;
}

.patient-home-table td:first-child,
.patient-home-table th:first-child {
  width: 38px;
  text-align: center;
}

.patient-home-table td strong {
  color: #193458;
}

.patient-home-table td small {
  display: block;
  color: #667d98;
  font-size: 0.61rem;
}

.patient-home-table td:last-child button {
  min-width: 60px;
  min-height: 28px;
  border: 1px solid #d6e7fb;
  border-radius: 6px;
  background: #f0f6ff;
  color: #126bd6;
  font-size: 0.63rem;
  font-weight: 800;
  cursor: pointer;
}

.patient-home-table td:last-child button:hover,
.patient-home-table td:last-child button:focus-visible {
  border-color: #1774e1;
  background: #e4f0ff;
  outline: none;
}

.patient-home-table :deep(.status) {
  min-width: 82px;
  justify-content: center;
  font-size: 0.59rem;
}

.patient-table-empty {
  height: 86px;
  color: #708199;
  text-align: center !important;
}

.patient-quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 0 14px 14px;
}

.patient-quick-grid button {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 15px;
  min-width: 0;
  min-height: 66px;
  align-items: center;
  gap: 9px;
  border: 1px solid #dce6f1;
  border-radius: 7px;
  background: #fff;
  padding: 9px;
  color: #14284a;
  text-align: left;
  cursor: pointer;
}

.patient-quick-grid button:hover,
.patient-quick-grid button:focus-visible {
  border-color: #a9caf2;
  background: #f7fbff;
  outline: none;
}

.patient-quick-grid button > span:first-child {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 7px;
  background: #eaf4ff;
  color: #1c75e1;
}

.patient-quick-grid button > span:nth-child(2),
.patient-quick-grid strong,
.patient-quick-grid small {
  display: block;
  min-width: 0;
}

.patient-quick-grid strong {
  overflow: hidden;
  font-size: 0.68rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.patient-quick-grid small {
  overflow: hidden;
  margin-top: 3px;
  color: #6d8098;
  font-size: 0.58rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.patient-quick-grid button > svg {
  color: #7890ac;
}

.patient-clinic-panel {
  position: relative;
  min-height: 210px;
}

.patient-clinic-panel address {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 14px;
  padding: 2px 18px 20px;
  color: #334d70;
  font-size: 0.7rem;
  font-style: normal;
}

.patient-clinic-panel address > div {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.patient-clinic-panel address svg {
  flex: 0 0 18px;
  color: #1977e7;
}

.patient-clinic-panel address span,
.patient-clinic-panel address strong,
.patient-clinic-panel address small {
  display: block;
}

.patient-clinic-panel address strong {
  color: #1c3659;
}

.patient-clinic-panel address small {
  max-width: 255px;
  margin-top: 3px;
  color: #6b7e97;
  font-size: 0.62rem;
  line-height: 1.45;
}

.patient-clinic-panel address a {
  color: #334d70;
  font-weight: 700;
}

.patient-clinic-watermark {
  position: absolute;
  right: -11px;
  bottom: -14px;
  color: #eaf2fb;
  pointer-events: none;
}

.patient-care-note {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  min-height: 104px;
  align-items: center;
  gap: 14px;
  overflow: hidden;
  background: #eff8ff;
  padding: 16px;
}

.patient-care-note > span {
  display: grid;
  width: 52px;
  height: 52px;
  place-items: center;
  border-radius: 8px;
  background: #dceeff;
  color: #1978e8;
}

.patient-care-note strong,
.patient-care-note p {
  margin: 0;
}

.patient-care-note strong {
  color: #155bab;
  font-size: 0.8rem;
}

.patient-care-note p {
  margin-top: 4px;
  color: #617893;
  font-size: 0.67rem;
}

:global(html[data-dashboard-theme="dark"]) .patient-home-dashboard {
  color: #edf4ff;
}

:global(html[data-dashboard-theme="dark"]) .patient-summary-card,
:global(html[data-dashboard-theme="dark"]) .patient-home-panel,
:global(html[data-dashboard-theme="dark"]) .patient-care-note {
  border-color: var(--dashboard-border);
  background-color: var(--dashboard-surface);
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .patient-summary-card strong,
    .patient-panel-heading h2,
    .patient-upcoming-copy h3,
    .patient-upcoming-copy dd,
    .patient-home-table,
    .patient-home-table td strong,
    .patient-quick-grid button,
    .patient-clinic-panel address strong
  ) {
  color: var(--dashboard-text);
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .patient-summary-card small,
    .patient-upcoming-copy dt,
    .patient-upcoming-empty p,
    .patient-home-table td small,
    .patient-quick-grid small,
    .patient-clinic-panel address,
    .patient-clinic-panel address small,
    .patient-care-note p
  ) {
  color: var(--dashboard-muted);
}

:global(html[data-dashboard-theme="dark"])
  :is(
    .patient-upcoming-body,
    .patient-upcoming-empty,
    .patient-filter-tabs button,
    .patient-quick-grid button,
    .patient-home-table th
  ) {
  border-color: var(--dashboard-border);
  background: #1d2a3a;
}

:global(html[data-dashboard-theme="dark"]) .patient-home-table th,
:global(html[data-dashboard-theme="dark"]) .patient-home-table td {
  border-color: var(--dashboard-border);
}

:global(html[data-dashboard-theme="dark"]) .patient-clinic-watermark {
  color: #25364b;
}

@media (max-width: 1180px) {
  .patient-home-content {
    grid-template-columns: minmax(0, 1.65fr) minmax(290px, 0.9fr);
  }

  .patient-quick-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 980px) {
  .patient-home-content {
    grid-template-columns: 1fr;
  }

  .patient-home-rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .patient-care-note {
    grid-column: 1 / -1;
  }

  .patient-quick-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .patient-summary-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 620px) {
  .patient-summary-card {
    grid-template-columns: 44px minmax(0, 1fr);
    min-height: 82px;
    gap: 10px;
    padding: 12px;
  }

  .patient-summary-icon {
    width: 44px;
    height: 44px;
  }

  .patient-summary-card strong {
    font-size: 1.2rem;
  }

  .patient-summary-card small {
    font-size: 0.62rem;
  }

  .patient-upcoming-body,
  .patient-upcoming-empty {
    grid-template-columns: 62px minmax(0, 1fr);
    gap: 14px;
    margin-inline: 12px;
    padding: 14px;
  }

  .patient-view-details,
  .patient-upcoming-empty > button {
    grid-column: 1 / -1;
    width: 100%;
  }

  .patient-date-tile {
    width: 60px;
    height: 76px;
  }

  .patient-upcoming-copy dl {
    display: grid;
    gap: 4px;
  }

  .patient-home-rail {
    grid-template-columns: 1fr;
  }

  .patient-care-note {
    grid-column: auto;
  }

  .patient-home-table-wrap {
    overflow: visible;
    padding-inline: 12px;
  }

  .patient-filter-tabs {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 4px;
    overflow: visible;
    padding-inline: 12px;
  }

  .patient-filter-tabs button {
    min-width: 0;
    gap: 3px;
    padding-inline: 3px;
    font-size: 0.58rem;
  }

  .patient-filter-tabs button span {
    min-width: 16px;
    padding-inline: 3px;
    font-size: 0.52rem;
  }

  .patient-home-table,
  .patient-home-table tbody,
  .patient-home-table tr,
  .patient-home-table td {
    display: block;
    width: 100%;
  }

  .patient-home-table thead {
    display: none;
  }

  .patient-home-table tbody {
    display: grid;
    gap: 9px;
  }

  .patient-home-table tbody tr:not(:last-child),
  .patient-home-table tbody tr:last-child {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    border: 1px solid #e2eaf3;
    border-radius: 7px;
    background: #fbfdff;
    padding: 8px;
  }

  .patient-home-table td {
    display: grid;
    grid-template-columns: 74px minmax(0, 1fr);
    align-items: center;
    gap: 8px;
    border: 0;
    padding: 5px;
    text-align: left !important;
  }

  .patient-home-table td::before {
    color: #71839a;
    font-size: 0.55rem;
    font-weight: 800;
    text-transform: uppercase;
    content: attr(data-label);
  }

  .patient-home-table td:nth-child(1) {
    display: none;
  }

  .patient-home-table td:nth-child(2),
  .patient-home-table td:nth-child(3) {
    grid-column: span 2;
  }

  .patient-home-table td:last-child button {
    width: 100%;
  }

  .patient-table-empty {
    display: block !important;
    grid-column: 1 / -1 !important;
    height: auto;
    padding: 24px !important;
  }

  .patient-table-empty::before {
    display: none;
  }

  :global(html[data-dashboard-theme="dark"]) .patient-home-table tbody tr:not(:last-child),
  :global(html[data-dashboard-theme="dark"]) .patient-home-table tbody tr:last-child {
    border-color: var(--dashboard-border);
    background: #1d2a3a;
  }
}

@media (max-width: 420px) {
  .patient-summary-card {
    grid-template-columns: 38px minmax(0, 1fr);
    gap: 8px;
    padding: 10px;
  }

  .patient-summary-icon {
    width: 38px;
    height: 38px;
  }

  .patient-summary-icon :deep(svg) {
    width: 21px;
    height: 21px;
  }
}

@media (max-width: 620px) {
  .patient-home-dashboard,
  .patient-home-content,
  .patient-home-primary,
  .patient-home-rail {
    gap: 10px;
  }

  .patient-summary-cards {
    gap: 8px;
  }

  .patient-summary-card {
    min-height: 100px;
    border-radius: 11px;
    box-shadow: 0 6px 17px rgb(31 64 102 / 5%);
  }

  .patient-summary-card > span:last-child {
    display: flex;
    min-width: 0;
    flex-direction: column;
    justify-content: center;
  }

  .patient-summary-card small {
    order: -1;
    margin: 0 0 5px;
    font-size: 0.7rem;
    line-height: 1.16;
  }

  .patient-summary-card strong {
    font-size: 1.35rem;
    line-height: 1;
  }

  .patient-summary-icon {
    border-radius: 50%;
  }

  .patient-summary-card.summary-total {
    border-color: #d7e8ff;
    background: #f1f7ff;
  }

  .patient-summary-card.summary-completed {
    border-color: #d1efe5;
    background: #effaf6;
  }

  .patient-summary-card.summary-upcoming {
    border-color: #f8e9cb;
    background: #fff8ed;
  }

  .patient-summary-card.summary-cancelled {
    border-color: #f8dfe4;
    background: #fff4f5;
  }

  .patient-home-panel,
  .patient-care-note {
    border-radius: 11px;
  }

  .patient-panel-heading,
  .patient-panel-heading.compact {
    min-height: 66px;
    gap: 7px;
    padding: 12px;
  }

  .patient-panel-heading > div {
    gap: 8px;
  }

  .patient-heading-icon {
    width: 39px;
    height: 39px;
    border-radius: 50%;
    background: #dff5f9;
    color: #0089a3;
  }

  .patient-heading-icon :deep(svg) {
    width: 19px;
    height: 19px;
  }

  .patient-heading-copy > small {
    display: block;
    margin-top: 2px;
    color: #6b7f99;
    font-size: 0.62rem;
    line-height: 1.25;
  }

  .patient-panel-heading h2 {
    font-size: 0.83rem;
    line-height: 1.15;
  }

  .patient-panel-heading > button {
    flex: 0 0 auto;
    border-radius: 6px;
    background: #625af1;
    padding: 7px 9px;
    color: #fff;
    font-size: 0.63rem;
    text-decoration: none;
  }

  .patient-panel-heading > button:hover,
  .patient-panel-heading > button:focus-visible {
    background: #4e45dd;
    color: #fff;
    text-decoration: none;
  }

  .patient-upcoming-body,
  .patient-upcoming-empty {
    border-radius: 9px;
    background: #eef7ff;
  }

  .patient-upcoming-body {
    min-height: 0;
  }

  .patient-upcoming-copy h3 {
    margin-bottom: 5px;
    font-size: 0.85rem;
    white-space: normal;
  }

  .patient-view-details,
  .patient-upcoming-empty > button {
    min-height: 35px;
    border-radius: 7px;
  }

  .patient-home-table-wrap {
    display: none;
  }

  .patient-mobile-appointments {
    display: grid;
    gap: 7px;
    margin: 0;
    padding: 0 12px 13px;
    list-style: none;
  }

  .patient-mobile-appointments > li {
    min-width: 0;
  }

  .patient-mobile-appointments > li > button {
    display: grid;
    width: 100%;
    min-width: 0;
    grid-template-columns: 67px minmax(0, 1fr) auto 14px;
    align-items: center;
    gap: 7px;
    border: 1px solid #e1eaf3;
    border-radius: 8px;
    background: #fbfdff;
    padding: 9px 7px;
    color: #14284a;
    text-align: left;
    cursor: pointer;
  }

  .patient-mobile-appointments > li > button:hover,
  .patient-mobile-appointments > li > button:focus-visible {
    border-color: #99bfec;
    background: #f2f8ff;
    outline: none;
  }

  .patient-mobile-appointment-date,
  .patient-mobile-appointment-copy {
    display: grid;
    min-width: 0;
    gap: 3px;
  }

  .patient-mobile-appointment-date strong,
  .patient-mobile-appointment-copy strong {
    overflow: hidden;
    font-size: 0.63rem;
    line-height: 1.2;
    text-overflow: ellipsis;
  }

  .patient-mobile-appointment-date small,
  .patient-mobile-appointment-copy small {
    overflow: hidden;
    color: #6b7e96;
    font-size: 0.56rem;
    line-height: 1.2;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .patient-mobile-appointment-copy strong {
    white-space: nowrap;
  }

  .patient-mobile-appointments :deep(.status) {
    min-width: 0;
    padding: 3px 5px;
    font-size: 0.52rem;
  }

  .patient-mobile-appointments button > svg {
    color: #7790ac;
  }

  .patient-mobile-appointment-empty {
    border: 1px dashed #dce8f3;
    border-radius: 8px;
    padding: 20px 12px;
    color: #6b7e96;
    font-size: 0.7rem;
    text-align: center;
  }

  .patient-quick-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    padding: 0 12px 12px;
  }

  .patient-quick-grid button {
    grid-template-columns: 29px minmax(0, 1fr);
    min-height: 60px;
    gap: 6px;
    border-radius: 8px;
    padding: 7px;
  }

  .patient-quick-grid button > span:first-child {
    width: 29px;
    height: 29px;
    border-radius: 7px;
  }

  .patient-quick-grid button > span:first-child :deep(svg) {
    width: 17px;
    height: 17px;
  }

  .patient-quick-grid button > svg {
    display: none;
  }

  .patient-quick-grid strong {
    font-size: 0.62rem;
    line-height: 1.15;
    white-space: normal;
  }

  .patient-quick-grid small {
    font-size: 0.54rem;
    line-height: 1.15;
  }

  .patient-clinic-panel {
    min-height: 0;
  }

  .patient-clinic-panel address {
    gap: 10px;
    padding: 2px 14px 17px;
  }
}

@media (max-width: 359px) {
  .patient-summary-card {
    grid-template-columns: 32px minmax(0, 1fr);
    gap: 5px;
    padding: 7px;
  }

  .patient-summary-icon {
    width: 32px;
    height: 32px;
  }

  .patient-summary-card small {
    font-size: 0.62rem;
  }

  .patient-mobile-appointments > li > button {
    grid-template-columns: 58px minmax(0, 1fr) auto;
  }

  .patient-mobile-appointments button > svg {
    display: none;
  }
}
</style>
