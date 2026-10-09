<script setup>
import { computed, nextTick, reactive, ref, watch } from "vue";
import { CalendarDays, Clock3, FileText, Info, Stethoscope, UserRound } from "lucide-vue-next";

import AvailabilityDatePicker from "./AvailabilityDatePicker.vue";
import AvatarBadge from "./AvatarBadge.vue";
import ServiceMultiSelect from "./ServiceMultiSelect.vue";
import SmsConsentModal from "./SmsConsentModal.vue";
import { availableSlotDates, futureOpenSlots } from "../services/availability";
import { apiRequest, session } from "../services/api";
import { pendingAppointmentForUser, savePendingAppointment } from "../services/pendingAppointment";
import { CLINIC_SMS_BOOKING_NOTICE_VERSION } from "../services/smsConsent";
import { validatedPayload } from "../services/validation";
import { showToast } from "../services/toast";

const props = defineProps({
  services: { type: Array, default: () => [] },
  availability: { type: Array, default: () => [] },
  clinicDoctor: { type: String, default: "" },
  initialService: { type: String, default: "" },
  submitLabel: { type: String, default: "Book Appointment" },
  compact: { type: Boolean, default: false },
  retainForAuthentication: { type: Boolean, default: false },
  patientSummary: { type: Object, default: null },
});
const emit = defineEmits(["created", "authentication-required", "confirmation-required", "cancel"]);

const form = reactive({ services: [], doctor: "", date: "", time: "", notes: "", _website: "" });
const busy = defineModel("busy", { type: Boolean, default: false });
const currentAvailability = ref(props.availability);
const currentClinicDoctor = ref(props.clinicDoctor);
const refreshingAvailability = ref(false);
const consentOpen = ref(false);
const submitButton = ref(null);
let restoringDraft = false;
let initialServiceObserved = false;
const bookableSlots = computed(() =>
  futureOpenSlots(currentAvailability.value, form.doctor || currentClinicDoctor.value),
);
const dates = computed(() => availableSlotDates(bookableSlots.value));
const slots = computed(() => bookableSlots.value.filter((slot) => slot.date === form.date));

function resetForm() {
  Object.assign(form, {
    services: [],
    date: "",
    time: "",
    notes: "",
    _website: "",
    doctor: currentClinicDoctor.value || currentAvailability.value[0]?.doctor || "",
  });
}

async function refreshAvailability() {
  if (refreshingAvailability.value) return;
  refreshingAvailability.value = true;
  try {
    const data = await apiRequest("/api/availability");
    currentAvailability.value = data.availability || [];
    currentClinicDoctor.value =
      data.clinic_doctor || currentAvailability.value[0]?.doctor || currentClinicDoctor.value;
    if (!form.doctor) form.doctor = currentClinicDoctor.value;
  } catch {
    // Keep the last successfully loaded schedule; submission is revalidated by the server.
  } finally {
    refreshingAvailability.value = false;
  }
}

function restorePendingDraft() {
  if (!props.retainForAuthentication || (session.user && session.user.role !== "patient")) return;
  const draft = pendingAppointmentForUser(session.user?.id || "");
  if (!draft) return;
  restoringDraft = true;
  Object.assign(form, {
    services: [...draft.appointment.services],
    doctor: draft.appointment.doctor,
    date: draft.appointment.date,
    time: draft.appointment.time,
    notes: draft.appointment.notes,
    _website: "",
  });
  restoringDraft = false;
}

restorePendingDraft();

watch(
  () => props.clinicDoctor,
  (doctor) => {
    currentClinicDoctor.value = doctor || currentClinicDoctor.value;
    if (!form.doctor) form.doctor = doctor || currentAvailability.value[0]?.doctor || "";
  },
  { immediate: true },
);
watch(
  () => props.availability,
  (items) => {
    currentAvailability.value = items;
  },
  { deep: true },
);
watch(
  () => props.initialService,
  (service) => {
    if (service && (initialServiceObserved || !form.services.length)) form.services = [service];
    initialServiceObserved = true;
  },
  { immediate: true },
);
watch(
  () => form.date,
  (date, previousDate) => {
    if (!restoringDraft && date !== previousDate) form.time = "";
  },
  { flush: "sync" },
);
watch(() => session.user?.id, restorePendingDraft);
watch(
  bookableSlots,
  (items) => {
    if (!form.doctor) form.doctor = currentClinicDoctor.value || items[0]?.doctor || "";
    if (form.date && !items.some((slot) => slot.date === form.date)) {
      form.date = "";
      form.time = "";
    } else if (
      form.date &&
      form.time &&
      !items.some((slot) => slot.date === form.date && slot.time === form.time)
    ) {
      form.time = "";
    }
  },
  { deep: true },
);

function submit() {
  if (busy.value) return;
  try {
    const payload = validatedPayload({ ...form, service: form.services[0] || "" });
    if (!payload.services.length) throw new Error("Select at least one dental service.");
    if (!payload.date || !payload.time) throw new Error("Choose an available date and time.");
    if (props.retainForAuthentication && session.user?.role === "doctor") {
      throw new Error("Use a patient account to book an appointment.");
    }
    consentOpen.value = true;
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function cancelConsent() {
  consentOpen.value = false;
  await nextTick();
  submitButton.value?.focus();
}

async function continueBooking(consentChoice) {
  if (!consentOpen.value || consentChoice?.appointmentSmsConsent !== true || busy.value) return;
  consentOpen.value = false;
  busy.value = true;
  try {
    const payload = validatedPayload({
      ...form,
      service: form.services[0] || "",
      appointment_sms_consent: true,
      clinic_sms_consent: consentChoice.clinicSmsConsent === true,
      sms_consent_notice_version:
        consentChoice.clinicSmsConsent === true ? CLINIC_SMS_BOOKING_NOTICE_VERSION : "",
    });
    if (!payload.services.length) throw new Error("Select at least one dental service.");
    if (!payload.date || !payload.time) throw new Error("Choose an available date and time.");
    if (props.retainForAuthentication) {
      if (session.user?.role === "doctor")
        throw new Error("Use a patient account to book an appointment.");
      const draft = savePendingAppointment(payload, {
        userId: session.user?.role === "patient" ? session.user.id : "",
      });
      if (session.user?.role === "patient") emit("confirmation-required", draft);
      else emit("authentication-required", draft);
      return;
    }
    const data = await apiRequest("/api/appointments", { method: "POST", body: payload });
    showToast("Appointment request submitted.");
    resetForm();
    emit("created", data.appointment);
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <form
    class="stacked-form"
    :class="{
      'appointment-panel': !compact,
      'patient-booking-form': patientSummary,
    }"
    aria-label="Appointment booking form"
    @submit.prevent="submit"
  >
    <label class="hp-field" aria-hidden="true"
      >Website<input v-model="form._website" tabindex="-1" autocomplete="off"
    /></label>
    <div v-if="!compact" class="panel-heading">
      <span class="appointment-heading-icon"><CalendarDays :size="24" /></span>
      <div>
        <h2>Book an Appointment</h2>
        <p>Quick and easy scheduling</p>
      </div>
    </div>
    <template v-if="patientSummary">
      <section class="patient-booking-summary" aria-label="Patient information">
        <div class="patient-booking-identity">
          <AvatarBadge :name="patientSummary.name" :image="patientSummary.profileImage" large />
          <span>
            <strong>{{ patientSummary.name }}</strong>
            <small>{{ patientSummary.email }}</small>
          </span>
        </div>
        <div class="patient-booking-summary-item">
          <UserRound :size="27" aria-hidden="true" />
          <span
            ><small>Age</small><strong>{{ patientSummary.age }}</strong></span
          >
        </div>
        <div class="patient-booking-summary-item">
          <Stethoscope :size="27" aria-hidden="true" />
          <span
            ><small>Last Visit</small><strong>{{ patientSummary.lastVisit }}</strong></span
          >
        </div>
        <div class="patient-booking-summary-item">
          <FileText :size="27" aria-hidden="true" />
          <span
            ><small>Recall / Notes</small><strong>{{ patientSummary.notes }}</strong></span
          >
        </div>
      </section>

      <div class="patient-booking-fields">
        <div class="patient-booking-field">
          <span class="patient-booking-label"
            ><Stethoscope :size="21" aria-hidden="true" /> Dental Services</span
          >
          <ServiceMultiSelect
            v-model="form.services"
            :services="services"
            label="Dental services"
          />
        </div>
        <label class="patient-booking-field single-doctor-field">
          <span class="patient-booking-label"
            ><UserRound :size="21" aria-hidden="true" /> Clinic Dentist</span
          >
          <input v-model="form.doctor" readonly required />
        </label>
        <div class="patient-booking-field appointment-date-field">
          <span class="patient-booking-label"
            ><CalendarDays :size="21" aria-hidden="true" /> Preferred Date</span
          >
          <AvailabilityDatePicker
            v-model="form.date"
            :available-dates="dates"
            placeholder="Select a date"
            aria-label="Select a preferred appointment date"
            @open="refreshAvailability"
          />
        </div>
        <label class="patient-booking-field">
          <span class="patient-booking-label"
            ><Clock3 :size="21" aria-hidden="true" /> Preferred Time</span
          >
          <select v-model="form.time" required :disabled="!form.date || !slots.length">
            <option value="">
              {{
                !form.date
                  ? "Select a date first"
                  : slots.length
                    ? "Select a time slot"
                    : "No available times"
              }}
            </option>
            <option v-for="slot in slots" :key="slot.id" :value="slot.time">
              {{ slot.time }}
            </option>
          </select>
        </label>
      </div>

      <div class="patient-booking-info" role="status">
        <Info :size="21" aria-hidden="true" />
        <span>
          {{
            form.date
              ? slots.length
                ? "Choose one of the available appointment times."
                : "No appointment times are available for this date."
              : "Available times will show after you select a date."
          }}
        </span>
      </div>

      <label class="patient-booking-notes">
        <span class="patient-booking-label"
          ><FileText :size="21" aria-hidden="true" /> Additional Notes
          <small>(Optional)</small></span
        >
        <textarea
          v-model="form.notes"
          rows="3"
          maxlength="500"
          placeholder="Symptoms, concerns, or preferred details..."
        ></textarea>
        <small class="patient-booking-character-count">{{ form.notes.length }}/500</small>
      </label>
    </template>

    <template v-else>
      <div class="booking-services-field">
        <span class="booking-services-label">Dental services</span>
        <ServiceMultiSelect v-model="form.services" :services="services" label="Dental services" />
      </div>
      <label class="single-doctor-field"
        >Clinic dentist<input v-model="form.doctor" readonly required
      /></label>
      <div class="form-grid two">
        <div class="appointment-date-field">
          <span class="form-label">Preferred date</span>
          <AvailabilityDatePicker
            v-model="form.date"
            :available-dates="dates"
            placeholder="Select a date"
            aria-label="Select a preferred appointment date"
            @open="refreshAvailability"
          />
        </div>
        <label
          >Preferred time<input v-model="form.time" type="hidden" required /><span
            class="selected-time"
            >{{ form.time || "Select slot" }}</span
          ></label
        >
      </div>
      <div class="booking-time-group">
        <span v-if="compact" class="form-label">Available times</span>
        <div class="time-slots" aria-label="Available appointment times">
          <button
            v-for="slot in slots"
            :key="slot.id"
            class="time-slot"
            type="button"
            :class="{ active: form.time === slot.time }"
            @click="form.time = slot.time"
          >
            {{ slot.time }}
          </button>
          <span v-if="form.date && !slots.length" class="meta"
            >No available times for this date.</span
          >
          <span v-else-if="!form.date" class="meta">Choose a date to view times.</span>
        </div>
      </div>
      <label
        >Notes (optional)<textarea
          v-model="form.notes"
          rows="3"
          maxlength="500"
          placeholder="Symptoms, concerns, or preferred details"
        ></textarea>
      </label>
    </template>
    <div v-if="compact" class="crud-dialog-actions">
      <button class="secondary-button" type="button" @click="emit('cancel')">Cancel</button>
      <button ref="submitButton" class="primary-button" type="submit" :disabled="busy">
        <CalendarDays :size="18" aria-hidden="true" />
        {{ busy ? (retainForAuthentication ? "Saving..." : "Submitting...") : submitLabel }}
      </button>
    </div>
    <template v-else>
      <button ref="submitButton" class="primary-button full" type="submit" :disabled="busy">
        <CalendarDays :size="18" aria-hidden="true" />
        {{ busy ? (retainForAuthentication ? "Saving..." : "Submitting...") : submitLabel }}
      </button>
      <div class="booking-note">
        <Info :size="20" />
        <slot name="note" />
      </div>
    </template>
  </form>
  <SmsConsentModal
    v-if="consentOpen"
    @agree="continueBooking"
    @cancel="cancelConsent"
  />
</template>

<style scoped>
.booking-services-field {
  display: grid;
  min-width: 0;
  gap: 7px;
}

.booking-services-label {
  color: var(--ink);
  font-size: 0.9rem;
  font-weight: 800;
}

.appointment-date-field {
  display: grid;
  min-width: 0;
  gap: 7px;
  color: var(--ink);
  font-size: 0.9rem;
  font-weight: 800;
}
</style>
