<script setup>
import {
  CalendarCheck2,
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileText,
  LayoutDashboard,
  Pencil,
  ShieldCheck,
  Stethoscope,
  Trash2,
  UserRound,
} from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";

import { dashboardPath, navigate } from "../router";
import { apiRequest, refreshSession, session } from "../services/api";
import { clearPendingAppointment, pendingAppointmentForUser } from "../services/pendingAppointment";
import { consumeQueuedToast, queueToast, showToast } from "../services/toast";
import { validatedPayload } from "../services/validation";

const draft = ref(null);
const services = ref([]);
const availability = ref([]);
const loading = ref(true);
const checking = ref(false);
const confirming = ref(false);
const validationError = ref("");

const details = computed(() => draft.value?.appointment || null);

function formatDate(value) {
  if (!value) return "Not selected";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-PH", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function formatTime(value) {
  const match = /^(\d{2}):(\d{2})$/.exec(value || "");
  if (!match) return value || "Not selected";
  const date = new Date(2000, 0, 1, Number(match[1]), Number(match[2]));
  return new Intl.DateTimeFormat("en-PH", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function currentValidationError() {
  if (!details.value) return "There is no appointment waiting for confirmation.";
  try {
    validatedPayload({ ...details.value, booking_token: draft.value.bookingToken, _website: "" });
  } catch (error) {
    return error.message;
  }
  const serviceExists = services.value.some(
    (service) => service.name?.trim().toLowerCase() === details.value.service.toLowerCase(),
  );
  if (!serviceExists) {
    return "This dental service is no longer offered. Please choose another service.";
  }
  const slotExists = availability.value.some(
    (slot) =>
      !slot.booked &&
      slot.doctor?.trim().toLowerCase() === details.value.doctor.toLowerCase() &&
      slot.date === details.value.date &&
      slot.time === details.value.time,
  );
  if (!slotExists) {
    return "This appointment slot is no longer available. Please choose another date or time.";
  }
  return "";
}

async function refreshValidation() {
  checking.value = true;
  validationError.value = "";
  try {
    const [serviceData, availabilityData] = await Promise.all([
      apiRequest("/api/services"),
      apiRequest("/api/availability"),
    ]);
    services.value = serviceData.services || [];
    availability.value = availabilityData.availability || [];
    validationError.value = currentValidationError();
  } catch (error) {
    validationError.value = `We could not recheck this appointment. ${error.message}`;
  } finally {
    checking.value = false;
  }
}

function editAppointment() {
  navigate("/?edit-booking=1#home");
}

function cancelAppointment() {
  if (!window.confirm("Discard this saved appointment?")) return;
  if (!clearPendingAppointment(draft.value?.bookingToken || "")) {
    showToast("The saved appointment changed. Refresh the page and try again.", "error");
    return;
  }
  queueToast("Saved appointment cancelled.");
  navigate("/");
}

async function confirmAppointment() {
  if (!draft.value || confirming.value) return;
  confirming.value = true;
  try {
    await refreshValidation();
    if (validationError.value) throw new Error(validationError.value);
    const payload = validatedPayload({
      ...details.value,
      booking_token: draft.value.bookingToken,
      _website: "",
    });
    const data = await apiRequest("/api/appointments", { method: "POST", body: payload });
    clearPendingAppointment(draft.value.bookingToken);
    queueToast(
      data.replayed
        ? "Your appointment was already submitted and is pending approval."
        : "Appointment request submitted and pending clinic approval.",
    );
    navigate("/patient-dashboard.html");
  } catch (error) {
    if (error.status === 401) {
      queueToast("Log in again to confirm your saved appointment.", "error");
      navigate("/?login=1&booking=1");
      return;
    }
    if (
      error.status === 409 ||
      /not available|already booked|already requested/i.test(error.message)
    ) {
      validationError.value = `${error.message} Please edit your appointment and choose another available time.`;
    }
    showToast(error.message, "error");
  } finally {
    confirming.value = false;
  }
}

onMounted(async () => {
  consumeQueuedToast();
  try {
    await refreshSession();
    if (!session.user) {
      queueToast("Log in to continue your saved appointment.", "error");
      navigate("/?login=1&booking=1");
      return;
    }
    if (session.user.role !== "patient") {
      queueToast("Only patient accounts can confirm appointments.", "error");
      navigate(dashboardPath(session.user.role));
      return;
    }
    draft.value = pendingAppointmentForUser(session.user.id);
    if (draft.value?.ownerUserId !== session.user.id) draft.value = null;
    if (draft.value) await refreshValidation();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="booking-confirmation-page">
    <header class="booking-confirmation-header">
      <button class="confirmation-brand" type="button" @click="navigate('/')">
        <img src="/assets/logo.png" alt="" />
        <span><strong>BORJA</strong><small>Dental Clinic</small></span>
      </button>
      <div v-if="session.user" class="confirmation-account">
        <span><UserRound :size="19" aria-hidden="true" />{{ session.user.name }}</span>
        <button class="secondary-button" type="button" @click="navigate(dashboardPath('patient'))">
          <LayoutDashboard :size="17" aria-hidden="true" />Dashboard
        </button>
      </div>
    </header>

    <main class="booking-confirmation-main">
      <section v-if="loading" class="confirmation-state" aria-live="polite">
        <span class="confirmation-spinner" aria-hidden="true"></span>
        <h1>Restoring your appointment...</h1>
      </section>

      <section v-else-if="!draft" class="confirmation-state">
        <span class="confirmation-state-icon"><CalendarDays :size="34" /></span>
        <h1>No Appointment to Confirm</h1>
        <p>This saved appointment is missing, expired, or belongs to another patient account.</p>
        <div class="confirmation-empty-actions">
          <button class="primary-button" type="button" @click="navigate('/#home')">
            Book an Appointment
          </button>
          <button
            class="secondary-button"
            type="button"
            @click="navigate(dashboardPath('patient'))"
          >
            Go to Dashboard
          </button>
        </div>
      </section>

      <template v-else>
        <header class="confirmation-intro">
          <span class="confirmation-intro-icon"><CalendarCheck2 :size="30" /></span>
          <div>
            <p>Final step</p>
            <h1>Confirm Your Appointment</h1>
            <span>Review your saved details before sending the request to the clinic.</span>
          </div>
        </header>

        <ol class="confirmation-progress" aria-label="Booking progress">
          <li class="complete"><CheckCircle2 :size="18" />Appointment details</li>
          <li class="complete"><CheckCircle2 :size="18" />Patient account</li>
          <li class="active"><span>3</span>Confirmation</li>
        </ol>

        <section class="confirmation-summary" aria-labelledby="appointment-summary-title">
          <header>
            <div>
              <p>Saved appointment</p>
              <h2 id="appointment-summary-title">Appointment Summary</h2>
            </div>
            <span class="confirmation-secure"
              ><ShieldCheck :size="18" />Secure patient request</span
            >
          </header>

          <dl class="confirmation-details">
            <div>
              <dt><Stethoscope :size="20" />Dental Service</dt>
              <dd>{{ details.service }}</dd>
            </div>
            <div>
              <dt><UserRound :size="20" />Dentist</dt>
              <dd>{{ details.doctor }}</dd>
            </div>
            <div>
              <dt><CalendarDays :size="20" />Preferred Date</dt>
              <dd>{{ formatDate(details.date) }}</dd>
            </div>
            <div>
              <dt><Clock3 :size="20" />Preferred Time</dt>
              <dd>{{ formatTime(details.time) }}</dd>
            </div>
            <div class="confirmation-notes">
              <dt><FileText :size="20" />Notes / Symptoms / Concerns</dt>
              <dd>{{ details.notes || "No notes provided" }}</dd>
            </div>
          </dl>

          <div v-if="checking" class="confirmation-check" role="status">
            <span class="confirmation-spinner small" aria-hidden="true"></span>
            Checking current clinic availability...
          </div>
          <div v-else-if="validationError" class="confirmation-warning" role="alert">
            <strong>Appointment update needed</strong>
            <p>{{ validationError }}</p>
            <button class="secondary-button" type="button" @click="editAppointment">
              <Pencil :size="17" />Choose Another Time
            </button>
          </div>
          <div v-else class="confirmation-available">
            <CheckCircle2 :size="20" />This service and appointment slot are currently available.
          </div>

          <footer class="confirmation-actions">
            <button class="danger-outline-button" type="button" @click="cancelAppointment">
              <Trash2 :size="18" />Cancel
            </button>
            <button class="secondary-button" type="button" @click="editAppointment">
              <Pencil :size="18" />Edit Appointment
            </button>
            <button
              class="primary-button confirmation-submit"
              type="button"
              :disabled="checking || confirming || Boolean(validationError)"
              @click="confirmAppointment"
            >
              <CalendarCheck2 :size="19" />
              {{ confirming ? "Confirming..." : "Confirm Appointment" }}
            </button>
          </footer>
        </section>
      </template>
    </main>
  </div>
</template>

<style scoped>
.booking-confirmation-page {
  min-height: 100vh;
  overflow-x: hidden;
  color: #102849;
  background: #f3f8fb;
}

.booking-confirmation-header {
  display: flex;
  min-height: 78px;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 12px clamp(20px, 5vw, 72px);
  background: #fff;
  border-bottom: 1px solid #dbe7ef;
}

.confirmation-brand {
  display: inline-flex;
  align-items: center;
  gap: 11px;
  padding: 0;
  color: #102849;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.confirmation-brand img {
  width: 54px;
  height: 54px;
  object-fit: contain;
}

.confirmation-brand span {
  display: grid;
  text-align: left;
}

.confirmation-brand strong {
  font-size: 1.35rem;
}

.confirmation-brand small {
  color: #087d94;
  font-size: 0.84rem;
}

.confirmation-account,
.confirmation-account > span {
  display: flex;
  align-items: center;
  gap: 9px;
}

.confirmation-account > span {
  color: #4a5f79;
  font-weight: 700;
}

.confirmation-account .secondary-button,
.confirmation-actions button,
.confirmation-warning button,
.confirmation-empty-actions button {
  gap: 8px;
}

.booking-confirmation-main {
  width: min(920px, calc(100% - 32px));
  margin: 0 auto;
  padding: clamp(36px, 7vw, 70px) 0 64px;
}

.confirmation-intro {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-bottom: 26px;
}

.confirmation-intro-icon,
.confirmation-state-icon {
  display: grid;
  width: 62px;
  height: 62px;
  flex: 0 0 auto;
  place-items: center;
  color: #087d94;
  background: #dff6fa;
  border-radius: 50%;
}

.confirmation-intro p,
.confirmation-summary header p {
  margin: 0 0 4px;
  color: #087d94;
  font-size: 0.76rem;
  font-weight: 800;
  text-transform: uppercase;
}

.confirmation-intro h1 {
  margin: 0 0 5px;
  font-size: clamp(1.75rem, 3vw, 2.35rem);
  letter-spacing: 0;
}

.confirmation-intro span:last-child {
  color: #5c6f87;
}

.confirmation-progress {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
  padding: 0;
  margin: 0 0 18px;
  list-style: none;
}

.confirmation-progress li {
  display: flex;
  min-height: 46px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #61738a;
  background: #e8f0f5;
  border-right: 2px solid #f3f8fb;
  font-size: 0.84rem;
  font-weight: 700;
}

.confirmation-progress li:first-child {
  border-radius: 6px 0 0 6px;
}

.confirmation-progress li:last-child {
  border-right: 0;
  border-radius: 0 6px 6px 0;
}

.confirmation-progress li.complete {
  color: #087358;
  background: #e2f7ef;
}

.confirmation-progress li.active {
  color: #fff;
  background: #087d94;
}

.confirmation-progress li.active span {
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  color: #087d94;
  background: #fff;
  border-radius: 50%;
}

.confirmation-summary {
  overflow: hidden;
  background: #fff;
  border: 1px solid #dce8ef;
  border-radius: 8px;
  box-shadow: 0 14px 34px rgb(32 75 103 / 9%);
}

.confirmation-summary > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px;
  border-bottom: 1px solid #e1ebf1;
}

.confirmation-summary h2 {
  margin: 0;
  font-size: 1.3rem;
}

.confirmation-secure {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #087358;
  font-size: 0.82rem;
  font-weight: 700;
}

.confirmation-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin: 0;
}

.confirmation-details > div {
  min-width: 0;
  padding: 23px 28px;
  border-bottom: 1px solid #e7eef3;
}

.confirmation-details > div:nth-child(odd):not(.confirmation-notes) {
  border-right: 1px solid #e7eef3;
}

.confirmation-details dt {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: #60728a;
  font-size: 0.79rem;
  font-weight: 700;
  text-transform: uppercase;
}

.confirmation-details dt svg {
  color: #087d94;
}

.confirmation-details dd {
  margin: 0;
  overflow-wrap: anywhere;
  font-size: 1.05rem;
  font-weight: 750;
  line-height: 1.45;
}

.confirmation-details .confirmation-notes {
  grid-column: 1 / -1;
  border-bottom: 0;
}

.confirmation-notes dd {
  color: #38516f;
  font-size: 0.95rem;
  font-weight: 500;
  white-space: pre-wrap;
}

.confirmation-check,
.confirmation-warning,
.confirmation-available {
  margin: 0 28px 24px;
  padding: 15px 17px;
  border-radius: 6px;
}

.confirmation-check,
.confirmation-available {
  display: flex;
  align-items: center;
  gap: 9px;
}

.confirmation-check {
  color: #536981;
  background: #edf5f8;
}

.confirmation-available {
  color: #087358;
  background: #e7f8f1;
  font-weight: 700;
}

.confirmation-warning {
  color: #7a4a0b;
  background: #fff5e3;
  border: 1px solid #f5d99f;
}

.confirmation-warning p {
  margin: 5px 0 13px;
  line-height: 1.5;
}

.confirmation-actions {
  display: grid;
  grid-template-columns: auto auto 1fr;
  gap: 12px;
  padding: 22px 28px;
  background: #f8fbfd;
  border-top: 1px solid #e1ebf1;
}

.confirmation-submit {
  justify-self: end;
  min-width: 230px;
}

.danger-outline-button {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  color: #c52f45;
  background: #fff;
  border: 1px solid #e6a8b2;
  border-radius: 6px;
  font: inherit;
  font-weight: 750;
  cursor: pointer;
}

.confirmation-state {
  display: grid;
  min-height: 420px;
  place-items: center;
  align-content: center;
  gap: 14px;
  padding: 34px;
  text-align: center;
  background: #fff;
  border: 1px solid #dce8ef;
  border-radius: 8px;
}

.confirmation-state h1,
.confirmation-state p {
  margin: 0;
}

.confirmation-state p {
  max-width: 520px;
  color: #5c6f87;
  line-height: 1.6;
}

.confirmation-empty-actions {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}

.confirmation-spinner {
  width: 34px;
  height: 34px;
  border: 3px solid #d8ebf0;
  border-top-color: #087d94;
  border-radius: 50%;
  animation: confirmation-spin 700ms linear infinite;
}

.confirmation-spinner.small {
  width: 19px;
  height: 19px;
  border-width: 2px;
}

@keyframes confirmation-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 680px) {
  .booking-confirmation-header {
    min-height: 68px;
    padding: 9px 16px;
  }

  .confirmation-brand img {
    width: 45px;
    height: 45px;
  }

  .confirmation-brand strong {
    font-size: 1.05rem;
  }

  .confirmation-account > span {
    display: none;
  }

  .confirmation-account .secondary-button {
    width: 42px;
    min-height: 42px;
    padding: 0;
    font-size: 0;
  }

  .booking-confirmation-main {
    width: min(100% - 24px, 920px);
    padding: 28px 0 40px;
  }

  .confirmation-intro {
    align-items: flex-start;
    gap: 13px;
  }

  .confirmation-intro-icon {
    width: 50px;
    height: 50px;
  }

  .confirmation-intro h1 {
    font-size: 1.65rem;
  }

  .confirmation-progress li {
    min-height: 40px;
    font-size: 0;
  }

  .confirmation-progress li svg,
  .confirmation-progress li.active span {
    width: 20px;
    height: 20px;
  }

  .confirmation-progress li.active span {
    font-size: 0.75rem;
  }

  .confirmation-summary > header {
    align-items: flex-start;
    padding: 20px;
  }

  .confirmation-secure {
    font-size: 0;
  }

  .confirmation-secure svg {
    width: 24px;
    height: 24px;
  }

  .confirmation-details {
    grid-template-columns: 1fr;
  }

  .confirmation-details > div {
    padding: 18px 20px;
  }

  .confirmation-details > div:nth-child(odd):not(.confirmation-notes) {
    border-right: 0;
  }

  .confirmation-details .confirmation-notes {
    grid-column: auto;
  }

  .confirmation-check,
  .confirmation-warning,
  .confirmation-available {
    margin: 0 20px 20px;
  }

  .confirmation-actions {
    grid-template-columns: 1fr 1fr;
    padding: 18px 20px;
  }

  .confirmation-submit {
    grid-column: 1 / -1;
    grid-row: 1;
    width: 100%;
    min-width: 0;
  }

  .confirmation-empty-actions {
    width: 100%;
    flex-direction: column;
  }
}

@media (max-width: 480px) {
  .confirmation-actions {
    grid-template-columns: minmax(0, 1fr);
  }

  .confirmation-actions button,
  .confirmation-submit {
    grid-column: auto;
    width: 100%;
    min-width: 0;
    max-width: 100%;
    white-space: normal;
  }

  .confirmation-submit {
    grid-row: 1;
    order: 1;
  }

  .confirmation-actions .secondary-button {
    order: 2;
  }

  .confirmation-actions .danger-outline-button {
    order: 3;
  }
}
</style>
