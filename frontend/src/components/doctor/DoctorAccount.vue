<script setup>
import {
  Bell,
  CalendarDays,
  Check,
  CircleUserRound,
  ImagePlus,
  KeyRound,
  LockKeyhole,
  Mail,
  Moon,
  Phone,
  Save,
  Settings,
  ShieldCheck,
  Sun,
  Trash2,
  UserRound,
} from "lucide-vue-next";
import { computed, reactive, ref } from "vue";

import { apiRequest, session } from "../../services/api";
import { formatDateTime } from "../../services/format";
import { dashboardTheme, applyDashboardTheme } from "../../services/theme";
import { showToast } from "../../services/toast";
import { imageToDataUrl, validatedPayload } from "../../services/validation";
import AvatarBadge from "../AvatarBadge.vue";

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
  { id: "preferences", label: "Preferences", icon: Settings },
];

const activeTab = ref("profile");
const busy = ref(false);
const editing = ref(false);
const fileInput = ref(null);
const selectedFileName = ref("");
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
        contactDescription: "Patient contact information",
        roleValue: "Patient",
        secondaryField: "Portal Access",
        secondaryValue: "Appointments & Records",
        accessLevel: "Patient",
        securityDescription: "Patient account protection",
        accountProtectionTitle: "Patient account",
        accountProtectionNote: "Personal portal access",
        notificationDescription: "Appointment and dental record alerts",
        recordAlertTitle: "Dental records",
        recordAlertNote: "Treatment record updates",
      }
    : {
        fallbackName: "Clinic administrator",
        role: "Administrator",
        contactDescription: "Administrator contact information",
        roleValue: "Dentist / Administrator",
        secondaryField: "Department",
        secondaryValue: "General Dentistry",
        accessLevel: "Administrator",
        securityDescription: "Administrator account protection",
        accountProtectionTitle: "Administrator account",
        accountProtectionNote: "New doctor accounts are disabled",
        notificationDescription: "Clinic transaction alerts",
        recordAlertTitle: "Patient records",
        recordAlertNote: "New treatment transactions",
      },
);
const displayName = computed(() => form.name.trim() || accountCopy.value.fallbackName);

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
</script>

<template>
  <section
    class="workspace-panel doctor-account-page"
    :class="{ 'patient-account-page': isPatient }"
    aria-labelledby="account-title"
  >
    <header class="account-page-heading">
      <div>
        <h1 id="account-title">Account</h1>
        <p>Manage your profile, security settings, and preferences.</p>
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

    <form v-if="activeTab === 'profile'" class="account-profile-form" @submit.prevent="save">
      <label class="hp-field" aria-hidden="true">
        Website<input v-model="form._website" tabindex="-1" />
      </label>

      <div class="account-content-grid">
        <section class="account-panel account-personal-panel" aria-labelledby="personal-title">
          <header class="account-panel-heading">
            <div class="account-heading-icon blue">
              <CircleUserRound :size="19" aria-hidden="true" />
            </div>
            <div>
              <h2 id="personal-title">Personal Information</h2>
              <p>{{ accountCopy.contactDescription }}</p>
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
                <span class="account-photo-mark"><ImagePlus :size="15" aria-hidden="true" /></span>
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
                class="account-change-photo"
                type="button"
                :disabled="!editing"
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
              <small>{{ selectedFileName || "JPG, PNG, or WebP up to 2 MB" }}</small>
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
              <label class="account-field">
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
              <label class="account-field">
                <span>Phone Number</span>
                <div class="account-input-wrap">
                  <Phone :size="15" aria-hidden="true" />
                  <input
                    v-model="form.phone"
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

        <aside class="account-side-column">
          <section class="account-panel account-overview-panel" aria-labelledby="overview-title">
            <header class="account-panel-heading">
              <div class="account-heading-icon green">
                <UserRound :size="19" aria-hidden="true" />
              </div>
              <div>
                <h2 id="overview-title">Account Overview</h2>
                <p>Account status and access</p>
              </div>
            </header>
            <dl class="account-overview-list">
              <div>
                <span class="account-overview-icon green">
                  <Check :size="17" aria-hidden="true" />
                </span>
                <dt>Account Status</dt>
                <dd class="active">Active</dd>
              </div>
              <div>
                <span class="account-overview-icon blue">
                  <CalendarDays :size="17" aria-hidden="true" />
                </span>
                <dt>Member Since</dt>
                <dd>{{ formatDateTime(session.user?.created_at) }}</dd>
              </div>
              <div>
                <span class="account-overview-icon purple">
                  <ShieldCheck :size="17" aria-hidden="true" />
                </span>
                <dt>Access Level</dt>
                <dd>{{ accountCopy.accessLevel }}</dd>
              </div>
            </dl>
          </section>

          <section class="account-panel account-quick-panel" aria-labelledby="quick-title">
            <header class="account-panel-heading">
              <div class="account-heading-icon amber">
                <Settings :size="19" aria-hidden="true" />
              </div>
              <div>
                <h2 id="quick-title">Quick Actions</h2>
                <p>Common account settings</p>
              </div>
            </header>
            <div class="account-quick-actions">
              <button type="button" class="security" @click="selectTab('security')">
                <LockKeyhole :size="17" aria-hidden="true" /> Security Overview
              </button>
              <button type="button" class="notifications" @click="selectTab('notifications')">
                <Bell :size="17" aria-hidden="true" /> Notification Settings
              </button>
            </div>
          </section>
        </aside>
      </div>

      <footer class="account-save-bar">
        <button
          type="button"
          class="account-cancel-button"
          :disabled="!editing"
          @click="cancelEditing"
        >
          Cancel
        </button>
        <button class="account-save-button" type="submit" :disabled="busy || !editing">
          <Save :size="17" aria-hidden="true" />
          {{ busy ? "Saving..." : "Save Changes" }}
        </button>
      </footer>
    </form>

    <div v-else-if="activeTab === 'security'" class="account-settings-view">
      <section class="account-panel account-settings-panel">
        <header class="account-panel-heading">
          <div class="account-heading-icon blue"><LockKeyhole :size="19" /></div>
          <div>
            <h2>Security</h2>
            <p>{{ accountCopy.securityDescription }}</p>
          </div>
        </header>
        <div class="account-setting-rows">
          <article>
            <KeyRound :size="19" aria-hidden="true" />
            <span
              ><strong>Password authentication</strong><small>Required at every login</small></span
            >
            <b>Enabled</b>
          </article>
          <article>
            <ShieldCheck :size="19" aria-hidden="true" />
            <span><strong>Protected requests</strong><small>Security token validation</small></span>
            <b>Enabled</b>
          </article>
          <article>
            <LockKeyhole :size="19" aria-hidden="true" />
            <span
              ><strong>{{ accountCopy.accountProtectionTitle }}</strong
              ><small>{{ accountCopy.accountProtectionNote }}</small></span
            >
            <b>Protected</b>
          </article>
        </div>
      </section>
    </div>

    <div v-else-if="activeTab === 'notifications'" class="account-settings-view">
      <section class="account-panel account-settings-panel">
        <header class="account-panel-heading">
          <div class="account-heading-icon purple"><Bell :size="19" /></div>
          <div>
            <h2>Notifications</h2>
            <p>{{ accountCopy.notificationDescription }}</p>
          </div>
        </header>
        <div class="account-setting-rows">
          <article>
            <CalendarDays :size="19" aria-hidden="true" />
            <span
              ><strong>Appointment activity</strong><small>Bookings and status changes</small></span
            >
            <b>Enabled</b>
          </article>
          <article>
            <UserRound :size="19" aria-hidden="true" />
            <span
              ><strong>{{ accountCopy.recordAlertTitle }}</strong
              ><small>{{ accountCopy.recordAlertNote }}</small></span
            >
            <b>Enabled</b>
          </article>
        </div>
      </section>
    </div>

    <div v-else class="account-settings-view">
      <section class="account-panel account-settings-panel">
        <header class="account-panel-heading">
          <div class="account-heading-icon amber"><Settings :size="19" /></div>
          <div>
            <h2>Preferences</h2>
            <p>Dashboard appearance</p>
          </div>
        </header>
        <div class="account-theme-choice" role="group" aria-label="Dashboard theme">
          <button
            type="button"
            :class="{ active: dashboardTheme === 'light' }"
            @click="applyDashboardTheme('light')"
          >
            <Sun :size="20" aria-hidden="true" />
            <span><strong>Light</strong><small>Bright dashboard appearance</small></span>
            <Check v-if="dashboardTheme === 'light'" :size="18" aria-hidden="true" />
          </button>
          <button
            type="button"
            :class="{ active: dashboardTheme === 'dark' }"
            @click="applyDashboardTheme('dark')"
          >
            <Moon :size="20" aria-hidden="true" />
            <span><strong>Dark</strong><small>Low-light dashboard appearance</small></span>
            <Check v-if="dashboardTheme === 'dark'" :size="18" aria-hidden="true" />
          </button>
        </div>
      </section>
    </div>
  </section>
</template>
