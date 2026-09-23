<script setup>
import {
  Briefcase,
  CalendarDays,
  ChevronRight,
  CircleDollarSign,
  ClipboardPlus,
  Clock3,
  FileText,
  Flag,
  Globe,
  Mail,
  MapPin,
  Phone,
  Plus,
  Save,
  Search,
  Smartphone,
  UserRound,
  UsersRound,
} from "lucide-vue-next";
import { computed, nextTick, reactive, ref, watch } from "vue";

import ActionIconButton from "../ActionIconButton.vue";
import AvatarBadge from "../AvatarBadge.vue";
import BaseModal from "../BaseModal.vue";
import StatusBadge from "../StatusBadge.vue";
import TreatmentEditorModal from "./TreatmentEditorModal.vue";
import { apiRequest } from "../../services/api";
import {
  calculateAge,
  formatDate,
  formatMoney,
  localDateIso,
  treatmentBalance,
  treatmentProcedure,
} from "../../services/format";
import { showToast } from "../../services/toast";
import { validatedPayload } from "../../services/validation";

const props = defineProps({
  state: { type: Object, required: true },
  highlightedId: { type: String, default: "" },
});
const emit = defineEmits(["refresh"]);

// Search, selection, dialogs, and forms for this screen.
const search = ref("");
const queueSort = ref("all");
const patientEditorOpen = ref(false);
const patientListOpen = ref(false);
const treatmentEditorOpen = ref(false);
const treatmentPromptOpen = ref(false);
const treatmentDetailOpen = ref(false);
const selectedPatientId = ref("");
const detailRecord = ref(null);
const busy = ref(false);
const sexLabels = {
  female: "Female",
  male: "Male",
  other: "Other",
  "prefer not to say": "Prefer not to say",
};

const emptyPatient = () => ({
  id: "",
  last_name: "",
  first_name: "",
  middle_name: "",
  birthdate: "",
  age: "",
  sex: "",
  nationality: "",
  occupation: "",
  phone_number: "",
  mobile_number: "",
  email: "",
  address: "",
  notes: "",
  _website: "",
});
const patientForm = reactive(emptyPatient());
const emptyTreatment = () => ({
  id: "",
  patient_id: "",
  treatment_date: localDateIso(),
  tooth_numbers: "",
  procedure: "",
  diagnosis: "",
  prescription: "",
  amount_charged: "0.00",
  amount_paid: "0.00",
  remarks: "",
  _website: "",
});
const treatmentForm = reactive(emptyTreatment());

watch(
  () => patientForm.birthdate,
  (value) => {
    patientForm.age = calculateAge(value);
  },
);
watch(
  () => props.highlightedId,
  (id) => {
    if (!id) return;
    const patient = props.state.patients.find((item) => item.id === id);
    if (patient) {
      selectedPatientId.value = patient.id;
      return;
    }
    const record = props.state.records.find((item) => item.id === id);
    if (record) selectedPatientId.value = record.patient_id;
  },
  { immediate: true },
);

// Lists and totals below are derived from the shared doctor dashboard data.
const filteredPatients = computed(() => {
  const query = search.value.trim().toLowerCase();
  const patients = props.state.patients.filter(
    (patient) =>
      !query ||
      [patient.name, patient.mobile_number, patient.phone, patient.email]
        .join(" ")
        .toLowerCase()
        .includes(query),
  );
  if (queueSort.value === "oldest") {
    return patients.sort(
      (a, b) =>
        String(a.created_at || "").localeCompare(String(b.created_at || "")) ||
        String(a.name).localeCompare(String(b.name)),
    );
  }
  if (queueSort.value === "newest") {
    return patients.sort(
      (a, b) =>
        String(b.created_at || "").localeCompare(String(a.created_at || "")) ||
        String(a.name).localeCompare(String(b.name)),
    );
  }
  return patients.sort((a, b) => String(a.name).localeCompare(String(b.name)));
});
const selectedPatient = computed(
  () => props.state.patients.find((item) => item.id === selectedPatientId.value) || null,
);
const patientRecords = computed(() =>
  props.state.records
    .filter((item) => item.patient_id === selectedPatientId.value)
    .sort((a, b) => String(a.treatment_date).localeCompare(String(b.treatment_date))),
);
const patientAppointments = computed(() => {
  const patient = selectedPatient.value;
  if (!patient) return [];
  const email = String(patient.email || "")
    .trim()
    .toLowerCase();
  return props.state.appointments
    .filter(
      (item) =>
        item.patient_id === patient.id ||
        (email &&
          String(item.patient_email || "")
            .trim()
            .toLowerCase() === email),
    )
    .sort((a, b) =>
      `${b.date || ""} ${b.time || ""}`.localeCompare(`${a.date || ""} ${a.time || ""}`),
    )
    .slice(0, 4);
});
const patientTotals = computed(() =>
  patientRecords.value.reduce(
    (sum, item) => {
      sum.charged += Number(item.amount_charged || 0);
      sum.paid += Number(item.amount_paid || 0);
      sum.balance += treatmentBalance(item);
      return sum;
    },
    { charged: 0, paid: 0, balance: 0 },
  ),
);
const procedures = computed(() => [
  ...new Set(props.state.services.map((item) => String(item.name || "").trim()).filter(Boolean)),
]);
watch(
  filteredPatients,
  (patients) => {
    if (!patients.length) {
      selectedPatientId.value = "";
      return;
    }
    if (!patients.some((patient) => patient.id === selectedPatientId.value)) {
      selectedPatientId.value = patients[0].id;
    }
  },
  { immediate: true },
);

function patientRegisteredDate(patient) {
  const value = patient?.created_at || patient?.updated_at || "";
  return value ? formatDate(String(value).slice(0, 10)) : "Date unavailable";
}

function resetPatientForm(patient = null) {
  Object.assign(
    patientForm,
    emptyPatient(),
    patient
      ? {
          id: patient.id,
          last_name: patient.last_name || "",
          first_name: patient.first_name || "",
          middle_name: patient.middle_name || "",
          birthdate: patient.birthdate || "",
          age: patient.age || calculateAge(patient.birthdate),
          sex: patient.sex || "",
          nationality: patient.nationality || "",
          occupation: patient.occupation || "",
          phone_number: patient.phone_number || "",
          mobile_number: patient.mobile_number || patient.phone || "",
          email: patient.email || "",
          address: patient.address || "",
          notes: patient.notes || "",
        }
      : {},
  );
  patientEditorOpen.value = true;
}

// Patient CRUD actions.
async function savePatient() {
  busy.value = true;
  try {
    const payload = validatedPayload({ ...patientForm }, { mobileRequired: true });
    const editing = Boolean(payload.id);
    const data = await apiRequest("/api/patients", {
      method: editing ? "PATCH" : "POST",
      body: payload,
    });
    const index = props.state.patients.findIndex((item) => item.id === data.patient.id);
    const merged = { ...(index >= 0 ? props.state.patients[index] : {}), ...data.patient };
    if (index >= 0) props.state.patients.splice(index, 1, merged);
    else props.state.patients.push(merged);
    selectedPatientId.value = data.patient.id;
    patientEditorOpen.value = false;
    showToast(editing ? "Patient record updated." : "Patient record saved.");
    if (!editing) treatmentPromptOpen.value = true;
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    busy.value = false;
  }
}

async function openProfile(patient) {
  selectedPatientId.value = patient.id;
  patientListOpen.value = false;
  await nextTick();
  if (window.matchMedia("(max-width: 900px)").matches) {
    document.querySelector(".patient-detail-workspace")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }
}

function editPatient(patient) {
  if (patient.source !== "profile") {
    showToast("Patient login accounts manage their own profile.", "error");
    return;
  }
  patientListOpen.value = false;
  resetPatientForm(patient);
}

async function deletePatient(patient) {
  if (
    patient.source !== "profile" ||
    !window.confirm(`Delete ${patient.name} and all linked treatment records?`)
  )
    return;
  try {
    await apiRequest("/api/patients", { method: "DELETE", body: { id: patient.id } });
    props.state.patients = props.state.patients.filter((item) => item.id !== patient.id);
    props.state.records = props.state.records.filter((item) => item.patient_id !== patient.id);
    showToast("Patient record deleted.");
  } catch (error) {
    showToast(error.message, "error");
  }
}

function resetTreatmentForm(record = null) {
  Object.assign(
    treatmentForm,
    emptyTreatment(),
    record
      ? {
          id: record.id,
          patient_id: record.patient_id,
          treatment_date: record.treatment_date || localDateIso(),
          tooth_numbers: record.tooth_numbers || "",
          procedure: procedures.value.includes(treatmentProcedure(record))
            ? treatmentProcedure(record)
            : "",
          diagnosis: record.diagnosis || "",
          prescription: record.prescription || "",
          amount_charged: Number(record.amount_charged || 0).toFixed(2),
          amount_paid: Number(record.amount_paid || 0).toFixed(2),
          remarks: record.remarks || record.notes || "",
        }
      : {
          patient_id: selectedPatientId.value,
          procedure: procedures.value[0] || "",
        },
  );
  treatmentPromptOpen.value = false;
  treatmentEditorOpen.value = true;
}

// Treatment CRUD actions.
async function saveTreatment() {
  busy.value = true;
  try {
    const payload = validatedPayload({ ...treatmentForm });
    payload.treatment = payload.procedure;
    const editing = Boolean(payload.id);
    const data = await apiRequest("/api/records", {
      method: editing ? "PATCH" : "POST",
      body: payload,
    });
    const index = props.state.records.findIndex((item) => item.id === data.record.id);
    if (index >= 0) props.state.records.splice(index, 1, data.record);
    else props.state.records.unshift(data.record);
    const patient = props.state.patients.find((item) => item.id === data.record.patient_id);
    if (patient) {
      const records = props.state.records.filter((item) => item.patient_id === patient.id);
      patient.record_count = records.length;
      patient.last_visit =
        records
          .map((item) => item.treatment_date)
          .sort()
          .at(-1) || "";
      patient.total_amount_charged = records.reduce(
        (sum, item) => sum + Number(item.amount_charged || 0),
        0,
      );
      patient.total_amount_paid = records.reduce(
        (sum, item) => sum + Number(item.amount_paid || 0),
        0,
      );
      patient.total_balance = records.reduce((sum, item) => sum + treatmentBalance(item), 0);
    }
    treatmentEditorOpen.value = false;
    showToast(editing ? "Treatment record updated." : "Treatment record added.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    busy.value = false;
  }
}

async function deleteTreatment(record) {
  if (!window.confirm(`Delete the ${treatmentProcedure(record)} treatment record?`)) return;
  try {
    await apiRequest("/api/records", { method: "DELETE", body: { id: record.id } });
    const index = props.state.records.findIndex((item) => item.id === record.id);
    if (index >= 0) props.state.records.splice(index, 1);
    showToast("Treatment record deleted.");
    emit("refresh");
  } catch (error) {
    showToast(error.message, "error");
  }
}

function viewTreatment(record) {
  detailRecord.value = record;
  treatmentDetailOpen.value = true;
}
</script>

<template>
  <section class="workspace-panel patient-management-page">
    <div class="patient-module">
      <div class="crud-page-heading patient-page-heading">
        <div>
          <span class="section-kicker">Patient management</span>
          <h1>Patient Records</h1>
          <p>Review patient information, appointments, balances, and treatment history.</p>
        </div>
        <button class="primary-button patient-add-button" type="button" @click="resetPatientForm()">
          <Plus :size="18" aria-hidden="true" />
          Add Patient
        </button>
      </div>

      <div class="patient-management-workspace">
        <aside class="patient-list-panel" aria-label="Patient list">
          <div class="patient-list-heading">
            <div>
              <span class="section-kicker">Records</span>
              <h2>Patient List</h2>
            </div>
            <strong :aria-label="`${filteredPatients.length} patients`">{{
              filteredPatients.length
            }}</strong>
          </div>

          <label class="patient-list-search">
            <Search :size="17" aria-hidden="true" />
            <span class="sr-only">Search patient records</span>
            <input
              v-model="search"
              type="search"
              placeholder="Search patients"
              autocomplete="off"
            />
          </label>

          <div class="patient-list-tabs" role="group" aria-label="Sort patient records">
            <button
              v-for="option in [
                { id: 'all', label: 'All' },
                { id: 'oldest', label: 'Oldest' },
                { id: 'newest', label: 'Newest' },
              ]"
              :key="option.id"
              :class="{ active: queueSort === option.id }"
              type="button"
              @click="queueSort = option.id"
            >
              {{ option.label }}
            </button>
          </div>

          <div class="patient-list-items">
            <button
              v-for="patient in filteredPatients.slice(0, 5)"
              :key="patient.id"
              class="patient-list-item"
              :class="{ active: selectedPatientId === patient.id }"
              type="button"
              @click="openProfile(patient)"
            >
              <AvatarBadge :name="patient.name" :image="patient.profile_image || ''" />
              <span class="patient-list-copy">
                <strong>{{ patient.name }}</strong>
                <small>{{
                  patient.mobile_number || patient.phone || patient.email || "No contact details"
                }}</small>
                <small>Registered: {{ patientRegisteredDate(patient) }}</small>
              </span>
              <ChevronRight :size="18" aria-hidden="true" />
            </button>
            <p v-if="!filteredPatients.length" class="patient-list-empty">
              No matching patient records.
            </p>
          </div>

          <div v-if="filteredPatients.length > 5" class="patient-list-footer">
            <button
              id="openPatientListDialog"
              class="primary-button compact-button"
              type="button"
              @click="patientListOpen = true"
            >
              More
            </button>
          </div>
        </aside>

        <section v-if="selectedPatient" class="patient-detail-workspace">
          <header class="patient-detail-header">
            <div class="patient-detail-identity">
              <AvatarBadge
                :name="selectedPatient.name"
                :image="selectedPatient.profile_image || ''"
                large
              />
              <div>
                <span class="section-kicker">Patient record</span>
                <h2>{{ selectedPatient.name }}</h2>
                <p>Registered {{ patientRegisteredDate(selectedPatient) }}</p>
              </div>
            </div>
            <div class="patient-detail-actions">
              <button
                class="primary-button compact-button patient-treatment-button"
                type="button"
                @click="resetTreatmentForm()"
              >
                <Plus :size="17" aria-hidden="true" />
                Add Treatment
              </button>
              <template v-if="selectedPatient.source === 'profile'">
                <ActionIconButton
                  action="edit"
                  :label="`Edit ${selectedPatient.name}`"
                  @click="editPatient(selectedPatient)"
                />
                <ActionIconButton
                  action="delete"
                  :label="`Delete ${selectedPatient.name}`"
                  @click="deletePatient(selectedPatient)"
                />
              </template>
            </div>
          </header>

          <div class="patient-detail-summary-grid">
            <section class="patient-detail-card patient-information-card">
              <div class="patient-card-heading">
                <div>
                  <span class="section-kicker">Profile</span>
                  <h3>Basic Information</h3>
                </div>
              </div>
              <dl class="patient-information-list">
                <div>
                  <CalendarDays :size="18" aria-hidden="true" />
                  <dt>Birthdate and Age</dt>
                  <dd>
                    {{ formatDate(selectedPatient.birthdate) }}
                    <span v-if="selectedPatient.birthdate"
                      >, {{ selectedPatient.age || calculateAge(selectedPatient.birthdate) }} years
                      old</span
                    >
                  </dd>
                </div>
                <div>
                  <UsersRound :size="18" aria-hidden="true" />
                  <dt>Sex</dt>
                  <dd>{{ sexLabels[selectedPatient.sex] || "Not provided" }}</dd>
                </div>
                <div>
                  <Flag :size="18" aria-hidden="true" />
                  <dt>Nationality</dt>
                  <dd>{{ selectedPatient.nationality || "Not provided" }}</dd>
                </div>
                <div>
                  <Briefcase :size="18" aria-hidden="true" />
                  <dt>Occupation</dt>
                  <dd>{{ selectedPatient.occupation || "Not provided" }}</dd>
                </div>
                <div>
                  <MapPin :size="18" aria-hidden="true" />
                  <dt>Home Address</dt>
                  <dd>{{ selectedPatient.address || "Not provided" }}</dd>
                </div>
              </dl>
            </section>

            <section class="patient-detail-card patient-appointments-card">
              <div class="patient-card-heading">
                <div>
                  <span class="section-kicker">Clinic visits</span>
                  <h3>Appointment Schedule</h3>
                </div>
                <strong>{{ patientAppointments.length }}</strong>
              </div>
              <div v-if="patientAppointments.length" class="patient-appointment-timeline">
                <article
                  v-for="appointment in patientAppointments"
                  :key="appointment.id"
                  class="patient-appointment-item"
                >
                  <span class="appointment-timeline-dot" aria-hidden="true"></span>
                  <div class="patient-appointment-date">
                    <strong>{{ formatDate(appointment.date) }}</strong>
                    <span
                      ><Clock3 :size="14" aria-hidden="true" />{{ appointment.time || "-" }}</span
                    >
                  </div>
                  <div class="patient-appointment-copy">
                    <strong>{{ appointment.service || "Dental appointment" }}</strong>
                    <span>{{ appointment.doctor || state.clinicDoctor || "Clinic dentist" }}</span>
                  </div>
                  <StatusBadge :status="appointment.status" />
                </article>
              </div>
              <p v-else class="patient-card-empty">No appointments recorded for this patient.</p>
            </section>

            <div class="patient-detail-side-stack">
              <section class="patient-financial-card" aria-label="Patient financial summary">
                <div class="patient-financial-heading">
                  <span>Outstanding Balance</span>
                  <CircleDollarSign :size="22" aria-hidden="true" />
                </div>
                <strong>{{ formatMoney(patientTotals.balance) }}</strong>
                <p>
                  {{ patientRecords.length }} treatment record{{
                    patientRecords.length === 1 ? "" : "s"
                  }}
                </p>
                <div class="patient-financial-breakdown">
                  <span
                    >Charged<strong>{{ formatMoney(patientTotals.charged) }}</strong></span
                  >
                  <span
                    >Paid<strong>{{ formatMoney(patientTotals.paid) }}</strong></span
                  >
                </div>
              </section>

              <section class="patient-detail-card patient-contact-card">
                <div class="patient-card-heading">
                  <div>
                    <span class="section-kicker">Reach patient</span>
                    <h3>Contact Details</h3>
                  </div>
                </div>
                <dl class="patient-contact-list">
                  <div>
                    <Phone :size="17" aria-hidden="true" />
                    <dt>Phone</dt>
                    <dd>{{ selectedPatient.phone_number || "Not provided" }}</dd>
                  </div>
                  <div>
                    <Smartphone :size="17" aria-hidden="true" />
                    <dt>Mobile</dt>
                    <dd>
                      {{ selectedPatient.mobile_number || selectedPatient.phone || "Not provided" }}
                    </dd>
                  </div>
                  <div>
                    <Mail :size="17" aria-hidden="true" />
                    <dt>Email</dt>
                    <dd>{{ selectedPatient.email || "Not provided" }}</dd>
                  </div>
                </dl>
              </section>
            </div>
          </div>

          <section class="patient-detail-card patient-treatment-history">
            <div class="patient-card-heading patient-treatment-heading">
              <div>
                <span class="section-kicker">Dental records</span>
                <h3>Treatment History</h3>
              </div>
              <strong
                >{{ patientRecords.length }} record{{
                  patientRecords.length === 1 ? "" : "s"
                }}</strong
              >
            </div>
            <div class="table-wrap">
              <table class="crud-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Tooth No./s</th>
                    <th>Procedure</th>
                    <th>Amount Charged</th>
                    <th>Amount Paid</th>
                    <th>Balance</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="record in patientRecords"
                    :key="record.id"
                    :data-entity-id="record.id"
                    :class="{ 'notification-target-glow': highlightedId === record.id }"
                  >
                    <td>{{ formatDate(record.treatment_date) }}</td>
                    <td>{{ record.tooth_numbers || "-" }}</td>
                    <td>
                      <strong>{{ treatmentProcedure(record) }}</strong>
                    </td>
                    <td>{{ formatMoney(record.amount_charged) }}</td>
                    <td>{{ formatMoney(record.amount_paid) }}</td>
                    <td>
                      <strong>{{ formatMoney(treatmentBalance(record)) }}</strong>
                    </td>
                    <td>
                      <div class="table-actions">
                        <ActionIconButton
                          action="view"
                          label="View treatment details"
                          @click="viewTreatment(record)"
                        />
                        <ActionIconButton
                          action="edit"
                          label="Edit treatment"
                          @click="resetTreatmentForm(record)"
                        />
                        <ActionIconButton
                          action="delete"
                          label="Delete treatment"
                          @click="deleteTreatment(record)"
                        />
                      </div>
                    </td>
                  </tr>
                  <tr v-if="!patientRecords.length">
                    <td colspan="7" class="table-empty">No treatment records yet.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </section>

        <section v-else class="patient-detail-empty">
          <div>
            <h2>No patient selected</h2>
            <p>Choose a patient record from the list or add a new patient.</p>
            <button class="primary-button" type="button" @click="resetPatientForm()">
              <Plus :size="18" aria-hidden="true" />
              Add Patient
            </button>
          </div>
        </section>
      </div>
    </div>

    <BaseModal
      v-if="patientEditorOpen"
      :title="patientForm.id ? 'Edit Patient' : 'Add Patient'"
      eyebrow="Patient record"
      size-class="patient-editor-dialog"
      @close="patientEditorOpen = false"
    >
      <template #header-icon>
        <span class="patient-editor-header-icon" aria-hidden="true">
          <ClipboardPlus :size="31" />
        </span>
      </template>
      <template #subtitle>
        <p class="patient-editor-subtitle">
          {{
            patientForm.id
              ? "Update this patient's clinic information."
              : "Add a new patient to the clinic records."
          }}
        </p>
      </template>
      <form class="patient-editor-form" @submit.prevent="savePatient">
        <div class="patient-editor-fields patient-form-grid">
          <label class="hp-field" aria-hidden="true"
            >Website<input v-model="patientForm._website" tabindex="-1"
          /></label>
          <label class="patient-editor-field patient-editor-third">
            <span>Last Name <b aria-hidden="true">*</b></span>
            <span class="patient-editor-control">
              <UserRound :size="18" aria-hidden="true" />
              <input
                v-model="patientForm.last_name"
                autocomplete="family-name"
                minlength="2"
                maxlength="80"
                placeholder="Enter last name"
                required
              />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-third">
            <span>First Name <b aria-hidden="true">*</b></span>
            <span class="patient-editor-control">
              <UserRound :size="18" aria-hidden="true" />
              <input
                v-model="patientForm.first_name"
                autocomplete="given-name"
                minlength="2"
                maxlength="80"
                placeholder="Enter first name"
                required
              />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-third">
            <span>Middle Name</span>
            <span class="patient-editor-control">
              <UserRound :size="18" aria-hidden="true" />
              <input
                v-model="patientForm.middle_name"
                autocomplete="additional-name"
                maxlength="80"
                placeholder="Enter middle name"
              />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-quarter">
            <span>Birthdate <b aria-hidden="true">*</b></span>
            <span class="patient-editor-control">
              <CalendarDays :size="18" aria-hidden="true" />
              <input v-model="patientForm.birthdate" type="date" required />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-quarter">
            <span>Age <b aria-hidden="true">*</b></span>
            <span class="patient-editor-control">
              <UsersRound :size="18" aria-hidden="true" />
              <input v-model="patientForm.age" placeholder="Auto-calculated" readonly />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-quarter">
            <span>Sex <b aria-hidden="true">*</b></span>
            <span class="patient-editor-control">
              <UsersRound :size="18" aria-hidden="true" />
              <select v-model="patientForm.sex" required>
                <option value="" disabled>Select sex</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
                <option value="prefer not to say">Prefer not to say</option>
              </select>
            </span>
          </label>
          <label class="patient-editor-field patient-editor-quarter">
            <span>Nationality <b aria-hidden="true">*</b></span>
            <span class="patient-editor-control">
              <Globe :size="18" aria-hidden="true" />
              <input
                v-model="patientForm.nationality"
                minlength="2"
                maxlength="80"
                placeholder="Enter nationality"
                required
              />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-third">
            <span>Occupation <b aria-hidden="true">*</b></span>
            <span class="patient-editor-control">
              <Briefcase :size="18" aria-hidden="true" />
              <input
                v-model="patientForm.occupation"
                minlength="2"
                maxlength="120"
                placeholder="Enter occupation"
                required
              />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-third">
            <span>Phone Number (optional)</span>
            <span class="patient-editor-control">
              <Phone :size="18" aria-hidden="true" />
              <input
                v-model="patientForm.phone_number"
                autocomplete="tel"
                maxlength="24"
                placeholder="Enter phone number"
              />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-third">
            <span>Mobile Number <b aria-hidden="true">*</b></span>
            <span class="patient-editor-control">
              <Smartphone :size="18" aria-hidden="true" />
              <input
                v-model="patientForm.mobile_number"
                autocomplete="tel"
                maxlength="24"
                placeholder="Enter mobile number"
                required
              />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-full">
            <span>Email Address <b aria-hidden="true">*</b></span>
            <span class="patient-editor-control">
              <Mail :size="18" aria-hidden="true" />
              <input
                v-model="patientForm.email"
                type="email"
                autocomplete="email"
                maxlength="254"
                placeholder="Enter email address"
                required
              />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-full">
            <span>Home Address <b aria-hidden="true">*</b></span>
            <span class="patient-editor-control">
              <MapPin :size="18" aria-hidden="true" />
              <input
                v-model="patientForm.address"
                autocomplete="street-address"
                minlength="5"
                maxlength="300"
                placeholder="Enter complete home address"
                required
              />
            </span>
          </label>
          <label class="patient-editor-field patient-editor-full">
            <span>Notes</span>
            <span class="patient-editor-control patient-editor-notes">
              <FileText :size="18" aria-hidden="true" />
              <textarea
                v-model="patientForm.notes"
                rows="2"
                maxlength="1000"
                placeholder="Add any additional notes here..."
              ></textarea>
            </span>
          </label>
        </div>
        <div class="crud-dialog-actions patient-editor-actions">
          <button class="secondary-button" type="button" @click="patientEditorOpen = false">
            Cancel
          </button>
          <button class="primary-button" type="submit" :disabled="busy">
            <Save :size="17" aria-hidden="true" />
            {{
              busy ? "Saving..." : patientForm.id ? "Update Patient Record" : "Save Patient Record"
            }}
          </button>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      v-if="treatmentPromptOpen"
      title="Add a treatment record?"
      eyebrow="Patient saved"
      size-class="patient-treatment-prompt"
      @close="treatmentPromptOpen = false"
    >
      <div class="patient-treatment-prompt-body">
        <p>
          <strong>{{ selectedPatient?.name || "The patient" }}</strong> was saved successfully.
          Would you like to add the first treatment record now?
        </p>
        <div class="crud-dialog-actions">
          <button class="secondary-button" type="button" @click="treatmentPromptOpen = false">
            No, Finish
          </button>
          <button class="primary-button" type="button" @click="resetTreatmentForm()">
            Yes, Add Treatment
          </button>
        </div>
      </div>
    </BaseModal>

    <BaseModal
      v-if="patientListOpen"
      :title="search ? 'Matching Patients' : 'All Patients'"
      eyebrow="Patient records"
      size-class="patient-list-dialog"
      @close="patientListOpen = false"
    >
      <div class="patient-list-dialog-body">
        <div class="table-wrap">
          <table class="crud-table patient-directory-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Contact</th>
                <th>Last Visit</th>
                <th>Balance</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="patient in filteredPatients" :key="patient.id">
                <td>
                  <strong>{{ patient.name }}</strong>
                  <div class="meta">{{ patient.email || "No email" }}</div>
                </td>
                <td>{{ patient.mobile_number || patient.phone || "-" }}</td>
                <td>{{ formatDate(patient.last_visit) }}</td>
                <td>
                  <strong>{{ formatMoney(patient.total_balance) }}</strong>
                </td>
                <td>
                  <div class="table-actions">
                    <ActionIconButton
                      action="view"
                      :label="`View ${patient.name}`"
                      @click="openProfile(patient)"
                    />
                    <ActionIconButton
                      v-if="patient.source === 'profile'"
                      action="edit"
                      :label="`Edit ${patient.name}`"
                      @click="editPatient(patient)"
                    />
                    <ActionIconButton
                      v-if="patient.source === 'profile'"
                      action="delete"
                      :label="`Delete ${patient.name}`"
                      @click="deletePatient(patient)"
                    />
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="crud-dialog-actions">
          <button class="secondary-button" type="button" @click="patientListOpen = false">
            Close
          </button>
        </div>
      </div>
    </BaseModal>

    <TreatmentEditorModal
      v-if="treatmentEditorOpen && selectedPatient"
      :form="treatmentForm"
      :patient="selectedPatient"
      :records="patientRecords"
      :appointments="patientAppointments"
      :procedures="procedures"
      :busy="busy"
      :max-date="localDateIso()"
      @close="treatmentEditorOpen = false"
      @submit="saveTreatment"
    />

    <BaseModal
      v-if="treatmentDetailOpen && detailRecord"
      title="Treatment Details"
      eyebrow="Patient record"
      @close="treatmentDetailOpen = false"
    >
      <div class="detail-grid">
        <span
          ><strong>{{ detailRecord.patient_name }}</strong
          >Patient</span
        >
        <span
          ><strong>{{ formatDate(detailRecord.treatment_date) }}</strong
          >Date</span
        >
        <span
          ><strong>{{ detailRecord.tooth_numbers || "-" }}</strong
          >Tooth No./s</span
        >
        <span
          ><strong>{{ treatmentProcedure(detailRecord) }}</strong
          >Procedure</span
        >
        <span
          ><strong>{{ detailRecord.diagnosis || "-" }}</strong
          >Diagnosis</span
        >
        <span
          ><strong>{{ detailRecord.prescription || "-" }}</strong
          >Medical Instruction</span
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
          ><strong>{{ detailRecord.remarks || "-" }}</strong
          >Remarks</span
        >
      </div>
    </BaseModal>
  </section>
</template>
