<script setup>
import {
  ArrowRight,
  CalendarDays,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  Phone,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { session, apiRequest } from "../services/api";
import { validatedPayload } from "../services/validation";
import { dashboardPath, navigate } from "../router";
import { claimPendingAppointment } from "../services/pendingAppointment";
import { showToast } from "../services/toast";

const props = defineProps({ initialTab: { type: String, default: "login" } });
const emit = defineEmits(["close", "authenticated"]);

const tab = ref(props.initialTab);
const busy = ref(false);
const showPassword = ref(false);
const errorMessage = ref("");
const login = reactive({ email: "", password: "", remember: false, _website: "" });
const privacyNoticeVersion = "registration-2026-10-01";
const register = reactive({
  first_name: "",
  middle_name: "",
  last_name: "",
  birthdate: "",
  phone: "",
  email: "",
  password: "",
  role: "patient",
  profile_image: "",
  privacy_consent_given: false,
  privacy_version: privacyNoticeVersion,
  sms_consent: false,
  _website: "",
});
const confirmPassword = ref("");
const passwordInput = ref(null);
const verificationToken = ref("");
const maskedMobile = ref("");
const verificationCode = ref("");
const resendAt = ref(0);
const expiresAt = ref(0);
const now = ref(Date.now());
const resendRemaining = computed(() => Math.max(0, Math.ceil((resendAt.value - now.value) / 1000)));
const expiresRemaining = computed(() =>
  Math.max(0, Math.ceil((expiresAt.value - now.value) / 1000)),
);
let countdownTimer;
// Optional local credentials are read only in development and stay out of source control.
const configuredTestAccounts = [
  {
    label: "Admin dashboard",
    email: import.meta.env.VITE_TEST_DOCTOR_EMAIL?.trim(),
    password: import.meta.env.VITE_TEST_DOCTOR_PASSWORD,
    role: "doctor",
  },
  {
    label: "Patient dashboard",
    email: import.meta.env.VITE_TEST_PATIENT_EMAIL?.trim(),
    password: import.meta.env.VITE_TEST_PATIENT_PASSWORD,
    role: "patient",
  },
];
const testAccounts = import.meta.env.DEV
  ? configuredTestAccounts.filter((account) => account.email && account.password)
  : [];

onMounted(() => {
  document.body.classList.add("modal-open");
  countdownTimer = window.setInterval(() => (now.value = Date.now()), 1000);
});
onBeforeUnmount(() => {
  document.body.classList.remove("modal-open");
  window.clearInterval(countdownTimer);
});

function switchTab(next) {
  tab.value = next;
  errorMessage.value = "";
  showPassword.value = false;
  if (next !== "verify") {
    verificationToken.value = "";
    verificationCode.value = "";
  }
}

function showVerification(data) {
  register.password = "";
  confirmPassword.value = "";
  verificationToken.value = data.verification_token;
  maskedMobile.value = data.masked_mobile;
  verificationCode.value = "";
  now.value = Date.now();
  resendAt.value = now.value + (data.resend_after || 60) * 1000;
  expiresAt.value = now.value + (data.expires_in || 300) * 1000;
  tab.value = "verify";
}

function selectTestAccount(account) {
  login.email = account.email;
  login.password = account.password;
  errorMessage.value = "";
  passwordInput.value?.focus();
}

function finishAuthentication(user, defaultMessage) {
  let destination = dashboardPath(user.role);
  let message = defaultMessage;
  let messageType = "success";
  if (user.role === "patient") {
    const pending = claimPendingAppointment(user.id);
    if (pending.status === "claimed") {
      destination = "/appointment-confirmation.html";
      message = "Your appointment details were restored.";
    } else if (pending.status === "conflict") {
      message = "The saved appointment belongs to a different patient account.";
      messageType = "error";
    }
  }
  showToast(message, messageType);
  emit("authenticated", user);
  emit("close");
  navigate(destination);
}

async function submitLogin() {
  errorMessage.value = "";
  busy.value = true;
  try {
    const payload = validatedPayload({ ...login, remember: login.remember ? "1" : "" });
    const data = await apiRequest("/api/login", { method: "POST", body: payload });
    session.user = data.user;
    session.csrfToken = data.csrf_token || session.csrfToken;
    finishAuthentication(data.user, `Welcome back, ${data.user.name}.`);
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    busy.value = false;
  }
}

async function submitRegister() {
  errorMessage.value = "";
  busy.value = true;
  try {
    if (!register.birthdate) throw new Error("Please select your birthdate.");
    if (!register.privacy_consent_given) {
      throw new Error("Please agree to the patient information notice to create an account.");
    }
    if (register.password !== confirmPassword.value) {
      throw new Error("Passwords do not match.");
    }
    const payload = validatedPayload(
      {
        ...register,
        name: [register.first_name, register.middle_name, register.last_name]
          .map((part) => part.trim())
          .filter(Boolean)
          .join(" "),
      },
      { registration: true },
    );
    const data = await apiRequest("/api/register", { method: "POST", body: payload });
    if (data.verification_required) {
      showVerification(data);
      return;
    }
    session.user = data.user;
    session.csrfToken = data.csrf_token || session.csrfToken;
    finishAuthentication(data.user, "Account created successfully.");
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    busy.value = false;
  }
}

async function submitVerification() {
  errorMessage.value = "";
  busy.value = true;
  try {
    const data = await apiRequest("/api/account-verification/verify", {
      method: "POST",
      body: { verification_token: verificationToken.value, code: verificationCode.value.trim() },
    });
    session.user = data.user;
    session.csrfToken = data.csrf_token || session.csrfToken;
    finishAuthentication(data.user, "Account verified and created successfully.");
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    busy.value = false;
  }
}

async function resendVerification() {
  errorMessage.value = "";
  busy.value = true;
  try {
    const data = await apiRequest("/api/account-verification/resend", {
      method: "POST",
      body: { verification_token: verificationToken.value },
    });
    showVerification(data);
  } catch (error) {
    errorMessage.value = error.message;
    if (error.data?.retry_after) {
      resendAt.value = Date.now() + error.data.retry_after * 1000;
    }
  } finally {
    busy.value = false;
  }
}

function handleRegisterInvalid(event) {
  if (event.target?.name === "birthdate") {
    errorMessage.value = "Please select your birthdate.";
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="modal-backdrop" role="dialog" aria-modal="true" @mousedown.self="emit('close')">
      <div class="auth-modal" :class="{ 'auth-modal-register': tab === 'register' }">
        <button class="modal-close" type="button" aria-label="Close" @click="emit('close')">
          <X aria-hidden="true" />
        </button>

        <form v-if="tab === 'login'" class="auth-form" @submit.prevent="submitLogin">
          <label class="hp-field" aria-hidden="true"
            >Website<input v-model="login._website" tabindex="-1" autocomplete="off"
          /></label>
          <div class="auth-heading">
            <img class="auth-brand-logo" src="/assets/logo.png" alt="" />
            <h2>Welcome Back</h2>
            <p>Sign in to continue securely.</p>
          </div>
          <section
            v-if="testAccounts.length"
            class="test-account-picker"
            aria-label="Test accounts"
          >
            <span class="test-account-label">Test accounts</span>
            <button
              v-for="account in testAccounts"
              :key="account.role"
              class="test-account-button"
              type="button"
              :aria-label="`Use ${account.label} test account`"
              @click="selectTestAccount(account)"
            >
              <ShieldCheck v-if="account.role === 'doctor'" aria-hidden="true" />
              <UserRound v-else aria-hidden="true" />
              <span>
                <strong>{{ account.label }}</strong>
                <small>{{ account.email }}</small>
                <small class="test-account-password">Password: {{ account.password }}</small>
              </span>
            </button>
          </section>
          <label class="auth-field">
            <span>Email</span>
            <span class="auth-input-wrap">
              <Mail aria-hidden="true" />
              <input
                v-model="login.email"
                name="email"
                type="email"
                autocomplete="email"
                maxlength="254"
                placeholder="you@example.com"
                required
              />
            </span>
          </label>
          <label class="auth-field">
            <span>Password</span>
            <span class="auth-input-wrap">
              <LockKeyhole aria-hidden="true" />
              <input
                ref="passwordInput"
                v-model="login.password"
                name="password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="current-password"
                maxlength="128"
                placeholder="Enter your password"
                required
              />
              <button
                class="password-toggle"
                type="button"
                :aria-label="showPassword ? 'Hide password' : 'Show password'"
                :aria-pressed="showPassword"
                @click="showPassword = !showPassword"
              >
                <EyeOff v-if="showPassword" aria-hidden="true" />
                <Eye v-else aria-hidden="true" />
              </button>
            </span>
          </label>
          <div class="auth-options">
            <label class="remember-choice"
              ><input v-model="login.remember" type="checkbox" /><span>Remember Me</span></label
            >
            <button
              class="forgot-link"
              type="button"
              @click="showToast('Please contact the clinic administrator to reset your password.')"
            >
              Forgot Password?
            </button>
          </div>
          <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
          <button class="primary-button login-button full" type="submit" :disabled="busy">
            {{ busy ? "Signing In..." : "Log In" }}
          </button>
          <p class="auth-switch">
            New here? <button type="button" @click="switchTab('register')">Sign Up</button>
          </p>
        </form>

        <form
          v-else-if="tab === 'verify'"
          class="auth-form auth-verify-form"
          @submit.prevent="submitVerification"
        >
          <div class="auth-heading">
            <ShieldCheck class="verification-icon" aria-hidden="true" />
            <h2>Verify your identity</h2>
            <p>We found an existing BORJA Dental Clinic patient record.</p>
          </div>
          <p class="verification-intro">
            A 6-digit verification code was sent to the mobile number registered with the clinic:
            <strong>{{ maskedMobile }}</strong>
          </p>
          <label class="auth-field">
            <span>Verification code</span>
            <span class="auth-input-wrap">
              <LockKeyhole aria-hidden="true" />
              <input
                v-model="verificationCode"
                name="verification_code"
                type="text"
                inputmode="numeric"
                autocomplete="one-time-code"
                pattern="[0-9]{6}"
                maxlength="6"
                placeholder="Enter 6-digit code"
                required
              />
            </span>
          </label>
          <p class="verification-hint">
            Code expires in 5 minutes.
            <span v-if="!expiresRemaining">The code has expired. Request a new code.</span>
            <span v-if="expiresRemaining"
              >{{ Math.floor(expiresRemaining / 60) }}:{{
                String(expiresRemaining % 60).padStart(2, "0")
              }}
              remaining.</span
            >
          </p>
          <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
          <button class="primary-button login-button full" type="submit" :disabled="busy">
            {{ busy ? "Verifying..." : "Verify Code" }}
          </button>
          <button
            class="verification-resend"
            type="button"
            :disabled="busy || resendRemaining > 0"
            @click="resendVerification"
          >
            {{
              resendRemaining > 0 ? `Resend available in ${resendRemaining} seconds` : "Resend Code"
            }}
          </button>
          <button class="verification-back" type="button" @click="switchTab('register')">
            Back to registration
          </button>
        </form>

        <form
          v-else
          class="auth-form auth-register-form"
          @submit.prevent="submitRegister"
          @invalid.capture="handleRegisterInvalid"
        >
          <label class="hp-field" aria-hidden="true"
            >Website<input v-model="register._website" tabindex="-1" autocomplete="off"
          /></label>
          <div class="auth-heading compact">
            <img class="auth-brand-logo" src="/assets/logo.png" alt="" />
            <span class="auth-brand-wordmark" aria-hidden="true">
              <strong>BORJA</strong>
              <small>DENTAL CLINIC</small>
            </span>
            <h2>Create your account</h2>
            <p>Start booking dental visits securely.</p>
          </div>
          <div class="register-grid">
            <label class="register-field">
              <span>First name</span>
              <span class="register-input-wrap">
                <UserRound aria-hidden="true" />
                <input
                  v-model="register.first_name"
                  name="first_name"
                  autocomplete="given-name"
                  maxlength="80"
                  placeholder="Enter your first name"
                  required
                />
              </span>
            </label>
            <label class="register-field">
              <span>Middle name (optional)</span>
              <span class="register-input-wrap">
                <UserRound aria-hidden="true" />
                <input
                  v-model="register.middle_name"
                  name="middle_name"
                  autocomplete="additional-name"
                  maxlength="80"
                  placeholder="Enter your middle name"
                />
              </span>
            </label>
            <label class="register-field">
              <span>Last name</span>
              <span class="register-input-wrap">
                <UserRound aria-hidden="true" />
                <input
                  v-model="register.last_name"
                  name="last_name"
                  autocomplete="family-name"
                  maxlength="80"
                  placeholder="Enter your last name"
                  required
                />
              </span>
            </label>
            <label class="register-field">
              <span>Birthdate</span>
              <span class="register-input-wrap">
                <CalendarDays aria-hidden="true" />
                <input
                  v-model="register.birthdate"
                  name="birthdate"
                  type="date"
                  autocomplete="bday"
                  required
                />
              </span>
            </label>
            <label class="register-field">
              <span>Mobile Number</span>
              <span class="register-input-wrap">
                <Phone aria-hidden="true" />
                <input
                  v-model="register.phone"
                  name="phone"
                  type="tel"
                  autocomplete="tel"
                  inputmode="tel"
                  maxlength="24"
                  placeholder="e.g. 0917 123 4567"
                  required
                />
              </span>
            </label>
            <label class="register-field">
              <span>Email</span>
              <span class="register-input-wrap">
                <Mail aria-hidden="true" />
                <input
                  v-model="register.email"
                  name="email"
                  type="email"
                  autocomplete="email"
                  maxlength="254"
                  placeholder="you@example.com"
                  required
                />
              </span>
            </label>
            <label class="register-field">
              <span>Password</span>
              <span class="register-input-wrap">
                <LockKeyhole aria-hidden="true" />
                <input
                  v-model="register.password"
                  name="password"
                  type="password"
                  autocomplete="new-password"
                  minlength="10"
                  maxlength="128"
                  placeholder="Create a password"
                  required
                />
              </span>
            </label>
            <label class="register-field">
              <span>Confirm Password</span>
              <span class="register-input-wrap">
                <LockKeyhole aria-hidden="true" />
                <input
                  v-model="confirmPassword"
                  name="confirm_password"
                  type="password"
                  autocomplete="new-password"
                  minlength="10"
                  maxlength="128"
                  placeholder="Confirm your password"
                  required
                />
              </span>
            </label>
          </div>
          <div class="register-consent" aria-label="Patient information choices">
            <p>
              Borja Dental Clinic uses the information you provide to manage appointments, provide
              dental care, track payments, and maintain your patient record.
            </p>
            <label class="register-consent-choice">
              <input v-model="register.privacy_consent_given" type="checkbox" required />
              <span>I agree to this use of my patient information. <strong>Required</strong></span>
            </label>
            <label class="register-consent-choice">
              <input v-model="register.sms_consent" type="checkbox" />
              <span
                >I agree to receive appointment, next-visit, and payment reminder SMS messages.
                <strong>Optional</strong></span
              >
            </label>
            <small>Clinic record verification may still require a one-time code.</small>
          </div>
          <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
          <button class="primary-button register-submit full" type="submit" :disabled="busy">
            <span>{{ busy ? "Creating..." : "Create Account" }}</span>
            <ArrowRight v-if="!busy" aria-hidden="true" />
          </button>
          <p class="auth-switch register-switch">
            <span
              >Already have an account?
              <button class="active" type="button" @click="switchTab('login')">Log In</button>
            </span>
          </p>
        </form>
      </div>
    </div>
  </Teleport>
</template>
