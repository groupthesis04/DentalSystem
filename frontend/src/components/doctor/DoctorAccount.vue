<script setup>
import {
  Bell,
  CalendarClock,
  CalendarDays,
  Camera,
  Check,
  ChevronRight,
  CircleUserRound,
  Eye,
  EyeOff,
  ImagePlus,
  Info,
  KeyRound,
  LockKeyhole,
  LogOut,
  Mail,
  MessageSquareText,
  Monitor,
  Phone,
  RefreshCw,
  Save,
  Settings,
  ShieldCheck,
  Trash2,
  UserRound,
  UserRoundPlus,
  Wallet,
  XCircle,
} from "lucide-vue-next";
import { computed, onMounted, reactive, ref } from "vue";

import { apiRequest, session } from "../../services/api";
import { showToast } from "../../services/toast";
import { imageToDataUrl, validatedPayload } from "../../services/validation";
import AvatarBadge from "../AvatarBadge.vue";
import ActivityLog from "./ActivityLog.vue";

const props = defineProps({
  mode: {
    type: String,
    default: "doctor",
    validator: (value) => ["doctor", "patient"].includes(value),
  },
});

const tabs = [
  { id: "profile", label: "Profile", icon: CircleUserRound },
  { id: "security", label: "Security", icon: LockKeyhole },
  { id: "notifications", label: "Notifications", icon: Bell },
];

const notificationOptions = [
  {
    key: "new_appointment_booking",
    title: "New Appointment Booking",
    description: "Notify me when a patient books a new appointment.",
    icon: CalendarDays,
    tone: "green",
  },
  {
    key: "appointment_confirmed",
    title: "Appointment Confirmed",
    description: "Notify me when an appointment is accepted/confirmed.",
    icon: Check,
    tone: "blue",
  },
  {
    key: "appointment_cancellation",
    title: "Appointment Cancellation",
    description: "Notify me when a patient cancels an appointment.",
    icon: XCircle,
    tone: "red",
  },
  {
    key: "new_walk_in_appointment",
    title: "New Walk-in Appointment",
    description: "Notify me when a walk-in appointment is added.",
    icon: UserRoundPlus,
    tone: "purple",
  },
  {
    key: "upcoming_appointment_reminder",
    title: "Upcoming Appointment Reminder",
    description: "Notify me about upcoming appointments (e.g. 1 day before).",
    icon: CalendarClock,
    tone: "amber",
  },
  {
    key: "next_visit",
    title: "Next Visit Reminder",
    description: "Notify me when a patient's next visit is due.",
    icon: RefreshCw,
    tone: "teal",
  },
  {
    key: "payment_balance_reminder",
    title: "Payment / Balance Reminder",
    description: "Notify me about pending or overdue payments.",
    icon: Wallet,
    tone: "amber",
  },
  {
    key: "sms_delivery_failure",
    title: "SMS Delivery Failure",
    description: "Notify me when an SMS message fails to send.",
    icon: MessageSquareText,
    tone: "purple",
  },
];

const activeTab = ref("profile");
const busy = ref(false);
const securityBusy = ref(false);
const recoveryBusy = ref(false);
const sessionsBusy = ref(false);
const notificationsBusy = ref(false);
const securityLoaded = ref(false);
const notificationsLoaded = ref(false);
const smsPreferenceLoaded = ref(false);
const smsPreferenceBusy = ref(false);
const smsChoice = ref(null);
const smsPreferenceAt = ref(null);
const editing = ref(false);
const editingRecovery = ref(false);
const fileInput = ref(null);
const selectedFileName = ref("");
const passwordVisible = reactive({ current: false, next: false, confirm: false, recovery: false });
const passwordForm = reactive({ current_password: "", new_password: "", confirm_password: "" });
const recoveryForm = reactive({ email: "", mobile_number: "", current_password: "" });
const securityData = reactive({
  is_active: null,
  last_login: null,
  login_activity: [],
  other_sessions_count: 0,
});
const notificationPreferences = reactive(
  Object.fromEntries(notificationOptions.map(({ key }) => [key, true])),
);
const form = reactive({
  name: session.user?.name || "",
  email: session.user?.email || "",
  phone: session.user?.phone || "",
  profile_image: session.user?.profile_image || "",
  _website: "",
});

const isPatient = computed(() => props.mode === "patient");
const accountCopy = computed(() =>
  isPatient.value
    ? {
        fallbackName: "Patient",
        role: "Patient",
        roleValue: "Patient",
        secondaryField: "Portal Access",
        secondaryValue: "Appointments & Records",
        accessLevel: "Patient",
        notificationDescription: "Appointment and dental record alerts",
        recordAlertTitle: "Dental records",
        recordAlertNote: "Treatment record updates",
      }
    : {
        fallbackName: "Clinic administrator",
        role: "Administrator",
        roleValue: "Dentist / Administrator",
        secondaryField: "Department",
        secondaryValue: "General Dentistry",
        accessLevel: "Administrator",
      },
);
const displayName = computed(() => form.name.trim() || accountCopy.value.fallbackName);
const lastLoginLabel = computed(() =>
  !securityLoaded.value
    ? "Unavailable"
    : securityData.last_login
      ? formatAccountDateTime(securityData.last_login)
      : "No login recorded",
);
const accountStatusLabel = computed(() => {
  if (securityData.is_active === null) return "Unavailable";
  return securityData.is_active ? "Active" : "Inactive";
});
const currentLogin = computed(
  () => securityData.login_activity.find((entry) => entry.is_current) || null,
);

function formatAccountDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const dateLabel = date.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
  const timeLabel = date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
  return `${dateLabel}, ${timeLabel}`;
}

async function loadSecurity(showErrors = false) {
  try {
    const data = await apiRequest("/api/account/security");
    securityData.is_active = typeof data.is_active === "boolean" ? data.is_active : null;
    securityData.last_login = data.last_login || null;
    securityData.login_activity = Array.isArray(data.login_activity) ? data.login_activity : [];
    securityData.other_sessions_count = Number(data.other_sessions_count || 0);
    recoveryForm.email = data.recovery_email || "";
    recoveryForm.mobile_number = data.recovery_mobile_number || "";
    recoveryForm.current_password = "";
    securityLoaded.value = true;
  } catch (error) {
    if (showErrors) showToast(error.message, "error");
  }
}

async function loadNotifications(showErrors = false) {
  if (isPatient.value) return;
  try {
    const data = await apiRequest("/api/notification-preferences");
    for (const { key } of notificationOptions) {
      if (Object.prototype.hasOwnProperty.call(data.preferences || {}, key)) {
        notificationPreferences[key] = Boolean(data.preferences[key]);
      }
    }
    notificationsLoaded.value = true;
  } catch (error) {
    if (showErrors) showToast(error.message, "error");
  }
}

async function loadSmsPreference(showErrors = false) {
  if (!isPatient.value) return;
  try {
    const data = await apiRequest("/api/account/sms-preference");
    smsChoice.value = data.sms_consent_at ? data.sms_consent : null;
    smsPreferenceAt.value = data.sms_consent_at;
    smsPreferenceLoaded.value = true;
  } catch (error) {
    if (showErrors) showToast(error.message, "error");
  }
}

async function saveSmsPreference() {
  if (typeof smsChoice.value !== "boolean") return;
  smsPreferenceBusy.value = true;
  try {
    const data = await apiRequest("/api/account/sms-preference", {
      method: "PATCH",
      body: { sms_consent: smsChoice.value },
    });
    smsChoice.value = data.sms_consent;
    smsPreferenceAt.value = data.sms_consent_at;
    showToast("SMS preference saved.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    smsPreferenceBusy.value = false;
  }
}

onMounted(() => {
  loadSecurity();
  if (isPatient.value) loadSmsPreference();
});

function syncForm() {
  Object.assign(form, {
    name: session.user?.name || "",
    email: session.user?.email || "",
    phone: session.user?.phone || "",
    profile_image: session.user?.profile_image || "",
    _website: "",
  });
  selectedFileName.value = "";
  if (fileInput.value) fileInput.value.value = "";
}

function selectTab(tab) {
  activeTab.value = tab;
  if (tab !== "profile") {
    editing.value = false;
    syncForm();
  }
  if (tab !== "security") {
    Object.assign(passwordForm, { current_password: "", new_password: "", confirm_password: "" });
    recoveryForm.current_password = "";
    editingRecovery.value = false;
    Object.assign(passwordVisible, {
      current: false,
      next: false,
      confirm: false,
      recovery: false,
    });
  }
  if (tab === "security") loadSecurity(true);
  if (tab === "notifications") loadNotifications(true);
  if (tab === "notifications") loadSmsPreference(true);
}

function beginEditing() {
  activeTab.value = "profile";
  editing.value = true;
}

function cancelEditing() {
  syncForm();
  editing.value = false;
}

function openFilePicker() {
  if (editing.value) fileInput.value?.click();
}

async function chooseImage(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    form.profile_image = await imageToDataUrl(file);
    selectedFileName.value = file.name;
  } catch (error) {
    event.target.value = "";
    showToast(error.message, "error");
  }
}

function removeImage() {
  form.profile_image = "";
  selectedFileName.value = "";
  if (fileInput.value) fileInput.value.value = "";
}

async function save() {
  if (!editing.value) return;
  busy.value = true;
  try {
    const data = await apiRequest("/api/profile", {
      method: "PATCH",
      body: validatedPayload({ ...form }),
    });
    session.user = data.user;
    syncForm();
    editing.value = false;
    showToast("Profile updated.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    busy.value = false;
  }
}

async function changePassword() {
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    showToast("New passwords do not match.", "error");
    return;
  }
  securityBusy.value = true;
  try {
    await apiRequest("/api/account/change-password", {
      method: "POST",
      body: { ...passwordForm },
    });
    Object.assign(passwordForm, { current_password: "", new_password: "", confirm_password: "" });
    await loadSecurity();
    showToast("Password updated.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    securityBusy.value = false;
  }
}

async function saveRecovery() {
  if (!recoveryForm.email.trim() && !recoveryForm.mobile_number.trim()) {
    showToast("Enter a recovery email or mobile number.", "error");
    return;
  }
  recoveryBusy.value = true;
  try {
    const data = await apiRequest("/api/account/recovery-contact", {
      method: "PATCH",
      body: { ...recoveryForm },
    });
    recoveryForm.email = data.recovery_email || "";
    recoveryForm.mobile_number = data.recovery_mobile_number || "";
    recoveryForm.current_password = "";
    editingRecovery.value = false;
    showToast("Recovery contact updated.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    recoveryBusy.value = false;
  }
}

async function logOutOtherDevices() {
  sessionsBusy.value = true;
  try {
    const data = await apiRequest("/api/account/logout-other-devices", {
      method: "POST",
      body: {},
    });
    await loadSecurity();
    showToast(data.revoked_count ? "Other devices logged out." : "No other devices are signed in.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    sessionsBusy.value = false;
  }
}

async function saveNotifications() {
  notificationsBusy.value = true;
  try {
    const data = await apiRequest("/api/notification-preferences", {
      method: "PATCH",
      body: { preferences: { ...notificationPreferences } },
    });
    Object.assign(notificationPreferences, data.preferences || {});
    showToast("Notification settings saved.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    notificationsBusy.value = false;
  }
}
</script>

<template>
  <section
    class="workspace-panel doctor-account-page"
    :class="{ 'patient-account-page': isPatient }"
    aria-labelledby="account-title"
  >
    <header class="account-page-heading">
      <div>
        <h1 id="account-title">My Profile</h1>
        <p>Manage your profile, security, and notifications.</p>
      </div>
      <div class="account-page-user">
        <AvatarBadge :name="displayName" :image="form.profile_image" />
        <span>
          <strong>{{ displayName }}</strong>
          <small>{{ accountCopy.role }}</small>
        </span>
      </div>
    </header>

    <nav class="account-tabs" role="tablist" aria-label="Account settings">
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

    <div class="account-content-grid">
      <form v-if="activeTab === 'profile'" class="account-profile-form" @submit.prevent="save">
        <label class="hp-field" aria-hidden="true">
          Website<input v-model="form._website" tabindex="-1" />
        </label>
        <section class="account-panel account-personal-panel" aria-labelledby="personal-title">
          <header class="account-panel-heading">
            <div class="account-heading-icon blue">
              <CircleUserRound :size="19" aria-hidden="true" />
            </div>
            <div>
              <h2 id="personal-title">Personal Information</h2>
              <p>Your account details and contact information.</p>
            </div>
            <button v-if="!editing" class="account-edit-button" type="button" @click="beginEditing">
              <UserRound :size="15" aria-hidden="true" /> Edit Profile
            </button>
            <span v-else class="account-editing-badge"><Check :size="14" /> Editing</span>
          </header>

          <div class="account-personal-layout">
            <div class="account-photo-column">
              <div class="account-photo-preview">
                <AvatarBadge :name="displayName" :image="form.profile_image" large />
                <button
                  class="account-photo-mark"
                  type="button"
                  aria-label="Change profile photo"
                  :disabled="!editing"
                  @click="openFilePicker"
                >
                  <Camera :size="19" aria-hidden="true" />
                </button>
              </div>
              <input
                ref="fileInput"
                class="account-file-input"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                :disabled="!editing"
                @change="chooseImage"
              />
              <button
                v-if="editing"
                class="account-change-photo"
                type="button"
                @click="openFilePicker"
              >
                <ImagePlus :size="15" aria-hidden="true" /> Change Photo
              </button>
              <button
                v-if="form.profile_image && editing"
                class="account-remove-photo"
                type="button"
                @click="removeImage"
              >
                <Trash2 :size="14" aria-hidden="true" /> Remove
              </button>
              <small>JPG, PNG, or WebP up to 2 MB</small>
            </div>

            <div class="account-form-grid">
              <label class="account-field account-field-wide">
                <span>Full Name</span>
                <div class="account-input-wrap">
                  <UserRound :size="15" aria-hidden="true" />
                  <input
                    v-model="form.name"
                    autocomplete="name"
                    minlength="2"
                    maxlength="120"
                    :disabled="!editing"
                    required
                  />
                </div>
              </label>
              <label class="account-field account-field-wide">
                <span>Email Address</span>
                <div class="account-input-wrap">
                  <Mail :size="15" aria-hidden="true" />
                  <input
                    v-model="form.email"
                    type="email"
                    autocomplete="email"
                    maxlength="254"
                    :disabled="!editing"
                    required
                  />
                </div>
              </label>
              <label class="account-field account-field-wide">
                <span>Mobile Number</span>
                <div class="account-input-wrap">
                  <Phone :size="15" aria-hidden="true" />
                  <input
                    v-model="form.phone"
                    type="tel"
                    autocomplete="tel"
                    maxlength="24"
                    :disabled="!editing"
                  />
                </div>
              </label>
              <label class="account-field">
                <span>Role</span>
                <div class="account-input-wrap readonly">
                  <ShieldCheck :size="15" aria-hidden="true" />
                  <input :value="accountCopy.roleValue" disabled />
                </div>
              </label>
              <label class="account-field">
                <span>{{ accountCopy.secondaryField }}</span>
                <div class="account-input-wrap readonly">
                  <KeyRound :size="15" aria-hidden="true" />
                  <input :value="accountCopy.secondaryValue" disabled />
                </div>
              </label>
            </div>
          </div>
        </section>
        <footer v-if="editing" class="account-save-bar">
          <button type="button" class="account-cancel-button" @click="cancelEditing">Cancel</button>
          <button class="account-save-button" type="submit" :disabled="busy">
            <Save :size="17" aria-hidden="true" />
            {{ busy ? "Saving..." : "Save Changes" }}
          </button>
        </footer>
      </form>

      <div v-else-if="activeTab === 'security'" class="account-settings-view">
        <form class="account-panel account-security-card" @submit.prevent="changePassword">
          <header class="account-panel-heading">
            <div class="account-heading-icon blue">
              <LockKeyhole :size="19" aria-hidden="true" />
            </div>
            <div>
              <h2>Change Password</h2>
              <p>Update your password to keep your account secure.</p>
            </div>
          </header>
          <div class="account-security-fields">
            <div class="account-field">
              <label for="account-current-password">Current Password</label>
              <div class="account-input-wrap account-password-wrap">
                <LockKeyhole :size="16" aria-hidden="true" />
                <input
                  id="account-current-password"
                  v-model="passwordForm.current_password"
                  :type="passwordVisible.current ? 'text' : 'password'"
                  autocomplete="current-password"
                  placeholder="Enter current password"
                  required
                />
                <button
                  type="button"
                  :aria-label="
                    passwordVisible.current ? 'Hide current password' : 'Show current password'
                  "
                  @click="passwordVisible.current = !passwordVisible.current"
                >
                  <EyeOff v-if="passwordVisible.current" :size="17" aria-hidden="true" />
                  <Eye v-else :size="17" aria-hidden="true" />
                </button>
              </div>
            </div>
            <div class="account-field">
              <label for="account-new-password">New Password</label>
              <div class="account-input-wrap account-password-wrap">
                <LockKeyhole :size="16" aria-hidden="true" />
                <input
                  id="account-new-password"
                  v-model="passwordForm.new_password"
                  :type="passwordVisible.next ? 'text' : 'password'"
                  autocomplete="new-password"
                  placeholder="Enter new password"
                  minlength="8"
                  required
                />
                <button
                  type="button"
                  :aria-label="passwordVisible.next ? 'Hide new password' : 'Show new password'"
                  @click="passwordVisible.next = !passwordVisible.next"
                >
                  <EyeOff v-if="passwordVisible.next" :size="17" aria-hidden="true" />
                  <Eye v-else :size="17" aria-hidden="true" />
                </button>
              </div>
            </div>
            <div class="account-field">
              <label for="account-confirm-password">Confirm New Password</label>
              <div class="account-input-wrap account-password-wrap">
                <LockKeyhole :size="16" aria-hidden="true" />
                <input
                  id="account-confirm-password"
                  v-model="passwordForm.confirm_password"
                  :type="passwordVisible.confirm ? 'text' : 'password'"
                  autocomplete="new-password"
                  placeholder="Confirm new password"
                  required
                />
                <button
                  type="button"
                  :aria-label="
                    passwordVisible.confirm ? 'Hide confirmed password' : 'Show confirmed password'
                  "
                  @click="passwordVisible.confirm = !passwordVisible.confirm"
                >
                  <EyeOff v-if="passwordVisible.confirm" :size="17" aria-hidden="true" />
                  <Eye v-else :size="17" aria-hidden="true" />
                </button>
              </div>
            </div>
          </div>
          <div class="account-form-actions">
            <div class="account-password-guidance">
              <Info :size="17" aria-hidden="true" />
              <div>
                <strong>Password Requirements:</strong>
                <ul>
                  <li>At least 8 characters long</li>
                  <li>Include uppercase and lowercase letters</li>
                  <li>Include at least one number</li>
                  <li>Include at least one special character (e.g. !@#$%)</li>
                </ul>
              </div>
            </div>
            <button class="account-save-button" type="submit" :disabled="securityBusy">
              <LockKeyhole :size="16" aria-hidden="true" />
              {{ securityBusy ? "Updating..." : "Update Password" }}
            </button>
          </div>
        </form>

        <section
          class="account-panel account-login-activity-card"
          aria-labelledby="login-activity-title"
        >
          <header class="account-panel-heading">
            <div class="account-heading-icon blue"><Monitor :size="19" aria-hidden="true" /></div>
            <div>
              <h2 id="login-activity-title">Login Activity</h2>
              <p>Recent login history for your account.</p>
            </div>
          </header>
          <div v-if="securityData.login_activity.length" class="account-activity-list">
            <div class="account-activity-header" aria-hidden="true">
              <span>Device</span>
              <span>Date &amp; Time</span>
            </div>
            <div
              v-for="entry in securityData.login_activity"
              :key="entry.id"
              class="account-activity-row"
            >
              <Monitor :size="18" aria-hidden="true" />
              <span>
                <strong>{{ entry.device }}</strong>
                <small v-if="entry.is_current">Current Device</small>
              </span>
              <time :datetime="entry.created_at">{{
                formatAccountDateTime(entry.created_at)
              }}</time>
            </div>
          </div>
          <p v-else class="account-empty-state">
            {{
              securityLoaded
                ? "No recent login activity is available."
                : "Loading login activity..."
            }}
          </p>
        </section>
      </div>

      <div v-else class="account-settings-view">
        <section class="account-panel account-settings-panel">
          <header class="account-panel-heading">
            <div class="account-heading-icon blue"><Bell :size="19" aria-hidden="true" /></div>
            <div>
              <h2>Notification Settings</h2>
              <p>
                {{
                  isPatient
                    ? accountCopy.notificationDescription
                    : "Choose which dashboard notifications you want to receive."
                }}
              </p>
            </div>
          </header>
          <form
            v-if="isPatient"
            class="patient-notifications-form"
            @submit.prevent="saveSmsPreference"
          >
            <div class="account-notification-list">
              <article class="account-notification-row">
                <span class="account-notification-icon blue">
                  <CalendarDays :size="19" aria-hidden="true" />
                </span>
                <span class="account-notification-copy">
                  <strong>Appointment activity</strong>
                  <small>Bookings and status changes in your dashboard</small>
                </span>
                <span class="account-readonly-badge">Enabled</span>
              </article>
              <article class="account-notification-row">
                <span class="account-notification-icon purple">
                  <UserRound :size="19" aria-hidden="true" />
                </span>
                <span class="account-notification-copy">
                  <strong>{{ accountCopy.recordAlertTitle }}</strong>
                  <small>{{ accountCopy.recordAlertNote }}</small>
                </span>
                <span class="account-readonly-badge">Enabled</span>
              </article>
              <article class="account-notification-row patient-sms-notification-row">
                <span class="account-notification-icon teal">
                  <MessageSquareText :size="19" aria-hidden="true" />
                </span>
                <span class="account-notification-copy">
                  <strong>SMS reminders</strong>
                  <small>Appointment, follow-up, payment, and clinic messages</small>
                </span>
                <span class="account-readonly-badge neutral">Your choice</span>
              </article>
            </div>
            <fieldset class="patient-sms-options">
              <legend>SMS message preference</legend>
              <label>
                <input
                  v-model="smsChoice"
                  type="radio"
                  name="sms-preference"
                  :value="true"
                  :disabled="!smsPreferenceLoaded || smsPreferenceBusy"
                />
                <span>Yes, send me SMS messages</span>
              </label>
              <label>
                <input
                  v-model="smsChoice"
                  type="radio"
                  name="sms-preference"
                  :value="false"
                  :disabled="!smsPreferenceLoaded || smsPreferenceBusy"
                />
                <span>No, stop SMS messages</span>
              </label>
            </fieldset>
            <div class="account-notification-actions">
              <div class="account-notification-note">
                <Info :size="22" aria-hidden="true" />
                <p>
                  <strong>SMS Preference</strong>
                  <span v-if="!smsPreferenceLoaded">Loading your SMS preference...</span>
                  <span v-else-if="smsPreferenceAt">
                    Choice saved {{ formatAccountDateTime(smsPreferenceAt) }}.
                  </span>
                  <span v-else> Automated SMS is off until you choose to receive it. </span>
                </p>
              </div>
              <button
                class="account-save-button"
                type="submit"
                :disabled="
                  !smsPreferenceLoaded || smsPreferenceBusy || typeof smsChoice !== 'boolean'
                "
              >
                <Save :size="16" aria-hidden="true" />
                {{ smsPreferenceBusy ? "Saving..." : "Save Changes" }}
              </button>
            </div>
          </form>
          <form v-else @submit.prevent="saveNotifications">
            <div class="account-notification-list">
              <article
                v-for="option in notificationOptions"
                :key="option.key"
                class="account-notification-row"
              >
                <span class="account-notification-icon" :class="option.tone">
                  <component :is="option.icon" :size="19" aria-hidden="true" />
                </span>
                <span class="account-notification-copy">
                  <strong>{{ option.title }}</strong>
                  <small>{{ option.description }}</small>
                </span>
                <label class="account-notification-switch">
                  <input
                    v-model="notificationPreferences[option.key]"
                    type="checkbox"
                    :aria-label="option.title"
                    :disabled="!notificationsLoaded || notificationsBusy"
                  />
                  <span aria-hidden="true"></span>
                </label>
              </article>
            </div>
            <div class="account-notification-actions">
              <div class="account-notification-note">
                <Info :size="22" aria-hidden="true" />
                <p>
                  <strong>System Notifications</strong>
                  <span>
                    These notifications will appear in your dashboard and notification bell. SMS
                    sent to patients are managed separately in the SMS settings.
                  </span>
                </p>
              </div>
              <button
                class="account-save-button"
                type="submit"
                :disabled="!notificationsLoaded || notificationsBusy"
              >
                <Save :size="16" aria-hidden="true" />
                {{ notificationsBusy ? "Saving..." : "Save Changes" }}
              </button>
            </div>
          </form>
        </section>
      </div>

      <aside
        class="account-side-column"
        :class="{ 'account-security-side': activeTab === 'security' }"
      >
        <section class="account-panel account-overview-panel" aria-labelledby="overview-title">
          <header class="account-panel-heading">
            <div class="account-heading-icon green">
              <UserRound :size="19" aria-hidden="true" />
            </div>
            <div>
              <h2 id="overview-title">Account Overview</h2>
              <p>Your account status and access information.</p>
            </div>
          </header>
          <dl class="account-overview-list">
            <div>
              <span class="account-overview-icon green"
                ><Check :size="17" aria-hidden="true"
              /></span>
              <dt>Account Status</dt>
              <dd :class="{ active: accountStatusLabel === 'Active' }">{{ accountStatusLabel }}</dd>
              <small v-if="accountStatusLabel === 'Active'"
                >Your account is in good standing.</small
              >
            </div>
            <div>
              <span class="account-overview-icon purple"
                ><ShieldCheck :size="17" aria-hidden="true"
              /></span>
              <dt>Role</dt>
              <dd>{{ accountCopy.accessLevel }}</dd>
              <small v-if="!isPatient">System administrator access.</small>
            </div>
            <div>
              <span class="account-overview-icon blue"
                ><CalendarDays :size="17" aria-hidden="true"
              /></span>
              <dt>Last Login</dt>
              <dd>{{ lastLoginLabel }}</dd>
            </div>
          </dl>
        </section>

        <template v-if="activeTab === 'security'">
          <section class="account-panel account-sessions-panel">
            <header class="account-panel-heading">
              <div class="account-heading-icon blue"><Monitor :size="19" aria-hidden="true" /></div>
              <div>
                <h2>Active Sessions</h2>
                <p>Manage access from your other devices.</p>
              </div>
            </header>
            <div class="account-current-session">
              <span class="account-current-session-icon"
                ><Monitor :size="23" aria-hidden="true"
              /></span>
              <span>
                <strong>{{ currentLogin?.device || "Current browser" }}</strong>
                <small>{{
                  currentLogin ? formatAccountDateTime(currentLogin.created_at) : "This Device"
                }}</small>
              </span>
              <b>This Device</b>
            </div>
            <button
              class="account-logout-devices"
              type="button"
              :disabled="!securityLoaded || !securityData.other_sessions_count || sessionsBusy"
              @click="logOutOtherDevices"
            >
              <LogOut :size="16" aria-hidden="true" />
              {{ sessionsBusy ? "Logging out..." : "Log Out Other Devices" }}
            </button>
            <small class="account-session-help">
              This will end all other active sessions except for your current device.
            </small>
          </section>

          <section class="account-panel account-security-card" aria-labelledby="recovery-title">
            <header class="account-panel-heading">
              <div class="account-heading-icon purple"><Phone :size="19" aria-hidden="true" /></div>
              <div>
                <h2 id="recovery-title">Recovery Contact</h2>
                <p>Alternate contact details saved with your account.</p>
              </div>
              <button
                v-if="!editingRecovery"
                class="account-edit-button"
                type="button"
                @click="editingRecovery = true"
              >
                Edit
              </button>
            </header>
            <form class="account-security-fields" @submit.prevent="saveRecovery">
              <label class="account-field">
                <span>Recovery Email</span>
                <div class="account-input-wrap">
                  <Mail :size="16" aria-hidden="true" />
                  <input
                    v-model="recoveryForm.email"
                    type="email"
                    autocomplete="email"
                    :disabled="!editingRecovery"
                  />
                </div>
              </label>
              <label class="account-field">
                <span>Recovery Mobile Number</span>
                <div class="account-input-wrap">
                  <Phone :size="16" aria-hidden="true" />
                  <input
                    v-model="recoveryForm.mobile_number"
                    type="tel"
                    autocomplete="tel"
                    maxlength="24"
                    :disabled="!editingRecovery"
                  />
                </div>
              </label>
              <div v-if="editingRecovery" class="account-field">
                <label for="account-recovery-password">Current Password</label>
                <div class="account-input-wrap account-password-wrap">
                  <LockKeyhole :size="16" aria-hidden="true" />
                  <input
                    id="account-recovery-password"
                    v-model="recoveryForm.current_password"
                    :type="passwordVisible.recovery ? 'text' : 'password'"
                    autocomplete="current-password"
                    placeholder="Confirm this change with your password"
                    required
                  />
                  <button
                    type="button"
                    :aria-label="
                      passwordVisible.recovery ? 'Hide current password' : 'Show current password'
                    "
                    @click="passwordVisible.recovery = !passwordVisible.recovery"
                  >
                    <EyeOff v-if="passwordVisible.recovery" :size="17" aria-hidden="true" />
                    <Eye v-else :size="17" aria-hidden="true" />
                  </button>
                </div>
              </div>
              <div v-if="editingRecovery" class="account-form-actions">
                <button
                  type="button"
                  class="account-cancel-button"
                  @click="
                    editingRecovery = false;
                    loadSecurity();
                  "
                >
                  Cancel
                </button>
                <button class="account-save-button" type="submit" :disabled="recoveryBusy">
                  <Save :size="16" aria-hidden="true" />
                  {{ recoveryBusy ? "Saving..." : "Save Contact" }}
                </button>
              </div>
            </form>
          </section>
        </template>

        <section v-else class="account-panel account-quick-panel" aria-labelledby="quick-title">
          <header class="account-panel-heading">
            <div class="account-heading-icon amber"><Settings :size="19" aria-hidden="true" /></div>
            <div>
              <h2 id="quick-title">Quick Actions</h2>
              <p>Common account settings.</p>
            </div>
          </header>
          <div class="account-quick-actions">
            <button type="button" class="security" @click="selectTab('security')">
              <span class="account-action-icon"><LockKeyhole :size="20" aria-hidden="true" /></span>
              <span>Change Password</span>
              <ChevronRight :size="19" aria-hidden="true" />
            </button>
            <button type="button" class="notifications" @click="selectTab('notifications')">
              <span class="account-action-icon"><Bell :size="20" aria-hidden="true" /></span>
              <span>Manage Notifications</span>
              <ChevronRight :size="19" aria-hidden="true" />
            </button>
            <button type="button" class="profile" @click="selectTab('profile')">
              <span class="account-action-icon"><UserRound :size="20" aria-hidden="true" /></span>
              <span>View Profile</span>
              <ChevronRight :size="19" aria-hidden="true" />
            </button>
          </div>
        </section>
      </aside>
    </div>
    <ActivityLog v-if="!isPatient && activeTab === 'security'" />
  </section>
</template>
