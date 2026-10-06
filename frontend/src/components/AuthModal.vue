<script setup>
import {
  ArrowRight,
  CalendarDays,
  CircleAlert,
  CircleCheck,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  Mail,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { session, apiRequest } from "../services/api";
import { validatedPayload } from "../services/validation";
import {
  createRegistrationEmailValidation,
  normalizeRegistrationEmail,
} from "../services/registrationEmailValidation";
import {
  internationalRegistrationMobile,
  localMobileFromPaste,
  MOBILE_LENGTH_MESSAGE,
  MOBILE_PREFIX_MESSAGE,
  registrationMobileError,
} from "../services/registrationMobile";
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
  _website: "",
});
const confirmPassword = ref("");
const passwordInput = ref(null);
const emailInput = ref(null);
const mobileTouched = ref(false);
const mobileInputError = ref("");
const mobileFeedback = computed(() => {
  if (mobileInputError.value) return mobileInputError.value;
  return mobileTouched.value ? registrationMobileError(register.phone) : "";
});
const {
  checking: emailChecking,
  status: emailStatus,
  suggestedEmail,
  clear: clearEmailValidation,
  handleInput: handleRegisterEmailInput,
  check: checkRegistrationEmail,
  dispose: disposeEmailValidation,
} = createRegistrationEmailValidation({
  getEmail: () => register.email,
  isValidFormat: hasBasicEmailFormat,
  request: (email) => apiRequest("/api/email-validation", { method: "POST", body: { email } }),
});
const emailStatusText = computed(() => {
  switch (emailStatus.value) {
    case "checking":
      return "Checking email address...";
    case "valid":
      return "Email address is valid.";
    case "invalid_format":
      return "Please enter a valid email address.";
    case "disposable":
      return "Temporary or disposable email addresses are not allowed.";
    case "already_registered":
      return "An account already uses this email address.";
    case "unknown":
      return "This email address could not be fully verified. Please check the address or try another email.";
    case "service_unavailable":
      return "Email validation is temporarily unavailable. Please try again.";
    case "rate_limited":
      return "Too many email checks. Please wait a few minutes and try again.";
    case "suggestion":
      return "Please check your email address.";
    default:
      return "This email address could not be verified. Please check the address and try again.";
  }
});
let registerSubmissionPending = false;
const verificationToken = ref("");
const maskedMobile = ref("");
const verificationCode = ref("");
const resendAt = ref(0);
const expiresAt = ref(0);
const resetEmail = ref("");
const resetToken = ref("");
const resetMaskedEmail = ref("");
const resetCode = ref("");
const resetNewPassword = ref("");
const resetConfirmPassword = ref("");
const showResetPassword = ref(false);
const showResetConfirmPassword = ref(false);
const resetNotice = ref("");
const resetResendAt = ref(0);
const resetExpiresAt = ref(0);
const now = ref(Date.now());
const resendRemaining = computed(() => Math.max(0, Math.ceil((resendAt.value - now.value) / 1000)));
const expiresRemaining = computed(() =>
  Math.max(0, Math.ceil((expiresAt.value - now.value) / 1000)),
);
const resetResendRemaining = computed(() =>
  Math.max(0, Math.ceil((resetResendAt.value - now.value) / 1000)),
);
const resetExpiresRemaining = computed(() =>
  Math.max(0, Math.ceil((resetExpiresAt.value - now.value) / 1000)),
);
let countdownTimer;
let resetFlowVersion = 0;
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
  disposeEmailValidation();
  clearResetState();
  document.body.classList.remove("modal-open");
  window.clearInterval(countdownTimer);
});

function normalizedRegistrationEmail(value = register.email) {
  return normalizeRegistrationEmail(value);
}

function hasBasicEmailFormat(email) {
  if (!email) return false;
  try {
    validatedPayload({ email });
    return emailInput.value?.checkValidity() ?? true;
  } catch {
    return false;
  }
}

async function useSuggestedEmail() {
  if (!suggestedEmail.value) return;
  register.email = suggestedEmail.value;
  clearEmailValidation();
  await nextTick();
  void checkRegistrationEmail();
}

function retryEmailValidation() {
  void checkRegistrationEmail({ force: true });
}

function setRegistrationMobile(value, input) {
  const candidate = String(value ?? "");
  if (!/^\d*$/.test(candidate) || candidate.length > 10) {
    mobileInputError.value = MOBILE_LENGTH_MESSAGE;
  } else if (candidate && !candidate.startsWith("9")) {
    mobileInputError.value = MOBILE_PREFIX_MESSAGE;
  } else {
    register.phone = candidate;
    mobileInputError.value = "";
  }
  if (input) input.value = register.phone;
}

function handleRegisterMobileBeforeInput(event) {
  if (!event.inputType?.startsWith("insert") || !event.data) return;
  if (!/^\d+$/.test(event.data)) {
    event.preventDefault();
    return;
  }
  const input = event.target;
  const start = input.selectionStart ?? register.phone.length;
  const end = input.selectionEnd ?? start;
  const candidate = `${register.phone.slice(0, start)}${event.data}${register.phone.slice(end)}`;
  if (candidate && !candidate.startsWith("9")) {
    event.preventDefault();
    mobileInputError.value = MOBILE_PREFIX_MESSAGE;
  }
}

function handleRegisterMobileInput(event) {
  const value = event.target.value;
  setRegistrationMobile(localMobileFromPaste(value) ?? value, event.target);
}

function handleRegisterMobilePaste(event) {
  event.preventDefault();
  const pasted = event.clipboardData?.getData("text") ?? "";
  const fullNumber = localMobileFromPaste(pasted);
  if (fullNumber) {
    setRegistrationMobile(fullNumber, event.target);
    return;
  }
  if (!/^\d{1,10}$/.test(pasted)) {
    mobileInputError.value = MOBILE_LENGTH_MESSAGE;
    return;
  }
  const input = event.target;
  const start = input.selectionStart ?? register.phone.length;
  const end = input.selectionEnd ?? start;
  setRegistrationMobile(
    `${register.phone.slice(0, start)}${pasted}${register.phone.slice(end)}`,
    input,
  );
}

function clearResetState() {
  resetFlowVersion += 1;
  resetEmail.value = "";
  resetToken.value = "";
  resetMaskedEmail.value = "";
  resetCode.value = "";
  resetNewPassword.value = "";
  resetConfirmPassword.value = "";
  showResetPassword.value = false;
  showResetConfirmPassword.value = false;
  resetNotice.value = "";
  resetResendAt.value = 0;
  resetExpiresAt.value = 0;
}

function closeModal() {
  clearResetState();
  emit("close");
}

function switchTab(next) {
  if (busy.value) return;
  if (next === "forgot") {
    const email = resetEmail.value || login.email;
    clearResetState();
    resetEmail.value = email;
  } else if (next !== "reset-otp" && next !== "new-password") {
    clearResetState();
  }
  tab.value = next;
  errorMessage.value = "";
  showPassword.value = false;
  if (next !== "verify") {
    verificationToken.value = "";
    verificationCode.value = "";
  }
}

function showResetChallenge(data) {
  resetToken.value = data.reset_token;
  resetMaskedEmail.value = data.masked_email || "";
  resetCode.value = "";
  resetNotice.value = "";
  now.value = Date.now();
  resetResendAt.value = now.value + (data.resend_after ?? 60) * 1000;
  resetExpiresAt.value = now.value + (data.expires_in ?? 300) * 1000;
  tab.value = "reset-otp";
}

function handleResetCodeInput() {
  resetCode.value = resetCode.value.replace(/\D/g, "").slice(0, 6);
}

async function requestPasswordReset() {
  if (busy.value) return;
  const flowVersion = resetFlowVersion;
  errorMessage.value = "";
  resetNotice.value = "";
  busy.value = true;
  try {
    const { email } = validatedPayload({ email: resetEmail.value });
    if (!email) throw new Error("Enter your registered email address.");
    const data = await apiRequest("/api/password-reset/request", {
      method: "POST",
      body: { email },
    });
    if (flowVersion !== resetFlowVersion) return;
    if (data.reset_token) {
      showResetChallenge(data);
    } else {
      resetNotice.value =
        "If this email is registered and delivery succeeds, a verification code will arrive shortly.";
    }
  } catch (error) {
    if (flowVersion === resetFlowVersion) errorMessage.value = error.message;
  } finally {
    busy.value = false;
  }
}

async function verifyPasswordResetCode() {
  if (busy.value) return;
  const flowVersion = resetFlowVersion;
  errorMessage.value = "";
  if (!/^[0-9]{6}$/.test(resetCode.value)) {
    errorMessage.value = "Enter the 6-digit verification code.";
    return;
  }
  busy.value = true;
  try {
    const data = await apiRequest("/api/password-reset/verify", {
      method: "POST",
      body: { reset_token: resetToken.value, code: resetCode.value },
    });
    if (flowVersion !== resetFlowVersion) return;
    if (!data.verified) throw new Error("Invalid or expired verification code.");
    resetCode.value = "";
    tab.value = "new-password";
  } catch (error) {
    if (flowVersion === resetFlowVersion) errorMessage.value = error.message;
  } finally {
    busy.value = false;
  }
}

async function resendPasswordResetCode() {
  if (busy.value || resetResendRemaining.value > 0) return;
  const flowVersion = resetFlowVersion;
  errorMessage.value = "";
  busy.value = true;
  try {
    const data = await apiRequest("/api/password-reset/resend", {
      method: "POST",
      body: { reset_token: resetToken.value },
    });
    if (flowVersion !== resetFlowVersion) return;
    if (!data.reset_token)
      throw new Error("Your verification session has expired. Request a new code.");
    showResetChallenge(data);
  } catch (error) {
    if (flowVersion === resetFlowVersion) errorMessage.value = error.message;
    if (flowVersion === resetFlowVersion && error.data?.retry_after) {
      resetResendAt.value = Date.now() + error.data.retry_after * 1000;
    }
  } finally {
    busy.value = false;
  }
}

async function confirmPasswordReset() {
  if (busy.value) return;
  const flowVersion = resetFlowVersion;
  errorMessage.value = "";
  try {
    if (resetNewPassword.value !== resetConfirmPassword.value) {
      throw new Error("Passwords do not match.");
    }
    const password = resetNewPassword.value;
    if (
      password.length < 8 ||
      !/\p{Lu}/u.test(password) ||
      !/\p{Ll}/u.test(password) ||
      !/\p{Nd}/u.test(password) ||
      !/[^\p{L}\p{N}\s]/u.test(password)
    ) {
      throw new Error(
        "Password must be at least 8 characters and include uppercase, lowercase, number, and symbol characters.",
      );
    }
    busy.value = true;
    const data = await apiRequest("/api/password-reset/confirm", {
      method: "POST",
      body: {
        reset_token: resetToken.value,
        new_password: resetNewPassword.value,
        confirm_password: resetConfirmPassword.value,
      },
    });
    if (flowVersion !== resetFlowVersion) return;
    if (!data.ok)
      throw new Error("Password recovery is temporarily unavailable. Please try again.");
    login.email = resetEmail.value;
    login.password = "";
    clearResetState();
    tab.value = "reset-success";
  } catch (error) {
    if (flowVersion === resetFlowVersion) errorMessage.value = error.message;
  } finally {
    busy.value = false;
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
  if (registerSubmissionPending || busy.value) return;
  registerSubmissionPending = true;
  errorMessage.value = "";
  try {
    if (!register.birthdate) throw new Error("Please select your birthdate.");
    mobileTouched.value = true;
    if (mobileInputError.value) throw new Error(mobileInputError.value);
    const phone = internationalRegistrationMobile(register.phone);
    if (register.password !== confirmPassword.value) {
      throw new Error("Passwords do not match.");
    }
    const payload = validatedPayload(
      {
        ...register,
        phone,
        name: [register.first_name, register.middle_name, register.last_name]
          .map((part) => part.trim())
          .filter(Boolean)
          .join(" "),
      },
      { registration: true },
    );
    const emailAtSubmit = normalizedRegistrationEmail();
    const mobileAtSubmit = register.phone;
    if (!(await checkRegistrationEmail())) return;
    if (normalizedRegistrationEmail() !== emailAtSubmit || emailStatus.value !== "valid") return;
    if (register.phone !== mobileAtSubmit || mobileInputError.value) return;
    busy.value = true;
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
    registerSubmissionPending = false;
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
  } else if (event.target?.name === "phone") {
    mobileTouched.value = true;
    errorMessage.value = mobileInputError.value || registrationMobileError(register.phone);
  } else if (event.target?.name === "email") {
    emailStatus.value = "invalid_format";
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="modal-backdrop" role="dialog" aria-modal="true" @mousedown.self="closeModal">
      <div class="auth-modal" :class="{ 'auth-modal-register': tab === 'register' }">
        <button class="modal-close" type="button" aria-label="Close" @click="closeModal">
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
            <button class="forgot-link" type="button" @click="switchTab('forgot')">
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
          v-else-if="tab === 'forgot'"
          class="auth-form auth-reset-form"
          @submit.prevent="requestPasswordReset"
        >
          <div class="auth-heading">
            <Mail class="verification-icon" aria-hidden="true" />
            <h2>Forgot Password</h2>
            <p>
              Enter the email address associated with your account to request a verification code.
            </p>
          </div>
          <label class="auth-field">
            <span>Email Address</span>
            <span class="auth-input-wrap">
              <Mail aria-hidden="true" />
              <input
                v-model="resetEmail"
                name="email"
                type="email"
                autocomplete="email"
                maxlength="254"
                placeholder="you@example.com"
                required
              />
            </span>
          </label>
          <p v-if="resetNotice" class="reset-notice" role="status">{{ resetNotice }}</p>
          <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
          <button class="primary-button login-button full" type="submit" :disabled="busy">
            {{ busy ? "Sending Code..." : "Send Verification Code" }}
          </button>
          <button
            class="verification-back"
            type="button"
            :disabled="busy"
            @click="switchTab('login')"
          >
            Back to Login
          </button>
        </form>

        <form
          v-else-if="tab === 'reset-otp'"
          class="auth-form auth-verify-form auth-reset-form"
          @submit.prevent="verifyPasswordResetCode"
        >
          <div class="auth-heading">
            <ShieldCheck class="verification-icon" aria-hidden="true" />
            <h2>Enter Verification Code</h2>
            <p>
              If this email is registered and delivery succeeds, a 6-digit code will arrive shortly.
              Check your inbox and spam folder.
            </p>
          </div>
          <p v-if="resetMaskedEmail" class="verification-intro">
            Address entered: <strong>{{ resetMaskedEmail }}</strong>
          </p>
          <label class="auth-field">
            <span>Verification Code</span>
            <span class="auth-input-wrap">
              <LockKeyhole aria-hidden="true" />
              <input
                v-model="resetCode"
                name="reset_code"
                type="text"
                inputmode="numeric"
                autocomplete="one-time-code"
                pattern="[0-9]{6}"
                maxlength="6"
                placeholder="Enter 6-digit code"
                required
                @input="handleResetCodeInput"
              />
            </span>
          </label>
          <p class="verification-hint">
            Verification session expires in {{ Math.floor(resetExpiresRemaining / 60) }}:{{
              String(resetExpiresRemaining % 60).padStart(2, "0")
            }}.
            <span v-if="!resetExpiresRemaining">Request a new code to continue.</span>
          </p>
          <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
          <button
            class="primary-button login-button full"
            type="submit"
            :disabled="busy || !resetExpiresRemaining"
          >
            {{ busy ? "Verifying..." : "Verify Code" }}
          </button>
          <button
            class="verification-resend"
            type="button"
            :disabled="busy || resetResendRemaining > 0"
            @click="resendPasswordResetCode"
          >
            {{
              resetResendRemaining > 0
                ? `Resend available in ${resetResendRemaining} seconds`
                : "Resend Code"
            }}
          </button>
          <button
            class="verification-back"
            type="button"
            :disabled="busy"
            @click="switchTab('forgot')"
          >
            Back
          </button>
        </form>

        <form
          v-else-if="tab === 'new-password'"
          class="auth-form auth-reset-form"
          @submit.prevent="confirmPasswordReset"
        >
          <div class="auth-heading">
            <LockKeyhole class="verification-icon" aria-hidden="true" />
            <h2>Create New Password</h2>
            <p>Choose a strong password for your BORJA Dental Clinic account.</p>
          </div>
          <label class="auth-field">
            <span>New Password</span>
            <span class="auth-input-wrap">
              <LockKeyhole aria-hidden="true" />
              <input
                v-model="resetNewPassword"
                name="new_password"
                :type="showResetPassword ? 'text' : 'password'"
                autocomplete="new-password"
                minlength="8"
                maxlength="128"
                placeholder="Create a new password"
                required
              />
              <button
                class="password-toggle"
                type="button"
                :aria-label="showResetPassword ? 'Hide new password' : 'Show new password'"
                :aria-pressed="showResetPassword"
                @click="showResetPassword = !showResetPassword"
              >
                <EyeOff v-if="showResetPassword" aria-hidden="true" />
                <Eye v-else aria-hidden="true" />
              </button>
            </span>
          </label>
          <label class="auth-field">
            <span>Confirm New Password</span>
            <span class="auth-input-wrap">
              <LockKeyhole aria-hidden="true" />
              <input
                v-model="resetConfirmPassword"
                name="confirm_password"
                :type="showResetConfirmPassword ? 'text' : 'password'"
                autocomplete="new-password"
                minlength="8"
                maxlength="128"
                placeholder="Confirm your new password"
                required
              />
              <button
                class="password-toggle"
                type="button"
                :aria-label="
                  showResetConfirmPassword
                    ? 'Hide confirmation password'
                    : 'Show confirmation password'
                "
                :aria-pressed="showResetConfirmPassword"
                @click="showResetConfirmPassword = !showResetConfirmPassword"
              >
                <EyeOff v-if="showResetConfirmPassword" aria-hidden="true" />
                <Eye v-else aria-hidden="true" />
              </button>
            </span>
          </label>
          <p class="reset-requirements">
            At least 8 characters with uppercase and lowercase letters, a number, and a symbol.
          </p>
          <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
          <button class="primary-button login-button full" type="submit" :disabled="busy">
            {{ busy ? "Resetting Password..." : "Reset Password" }}
          </button>
          <button
            class="verification-back"
            type="button"
            :disabled="busy"
            @click="switchTab('login')"
          >
            Back to Login
          </button>
        </form>

        <div v-else-if="tab === 'reset-success'" class="auth-form auth-reset-form">
          <div class="auth-heading">
            <CircleCheck class="verification-icon" aria-hidden="true" />
            <h2>Password Reset Successful</h2>
            <p>
              Your password has been changed successfully. You can now sign in using your new
              password.
            </p>
          </div>
          <button
            class="primary-button login-button full"
            type="button"
            @click="switchTab('login')"
          >
            Back to Login
          </button>
        </div>

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
              <span class="register-input-wrap register-mobile-wrap">
                <span class="register-mobile-prefix" aria-hidden="true">+63</span>
                <input
                  :value="register.phone"
                  name="phone"
                  type="tel"
                  autocomplete="tel-national"
                  inputmode="numeric"
                  maxlength="10"
                  placeholder="917 123 4567"
                  aria-label="Mobile number after plus sixty-three"
                  :aria-invalid="mobileFeedback ? 'true' : undefined"
                  :aria-describedby="mobileFeedback ? 'register-mobile-feedback' : undefined"
                  @beforeinput="handleRegisterMobileBeforeInput"
                  @input="handleRegisterMobileInput"
                  @paste="handleRegisterMobilePaste"
                  @blur="mobileTouched = true"
                  required
                />
              </span>
              <span
                v-if="mobileFeedback"
                id="register-mobile-feedback"
                class="register-mobile-feedback"
                role="alert"
                >{{ mobileFeedback }}</span
              >
            </label>
            <div class="register-email-field">
              <label class="register-field">
                <span>Email</span>
                <span class="register-input-wrap">
                  <Mail aria-hidden="true" />
                  <input
                    ref="emailInput"
                    v-model="register.email"
                    name="email"
                    type="email"
                    autocomplete="email"
                    maxlength="254"
                    placeholder="you@example.com"
                    :aria-describedby="emailStatus ? 'register-email-feedback' : undefined"
                    :aria-invalid="
                      emailStatus && !['valid', 'checking'].includes(emailStatus)
                        ? 'true'
                        : undefined
                    "
                    @input="handleRegisterEmailInput"
                    @blur="checkRegistrationEmail()"
                    required
                  />
                </span>
              </label>
              <p
                v-if="emailStatus"
                id="register-email-feedback"
                class="register-email-feedback"
                :class="{
                  'is-valid': emailStatus === 'valid',
                  'is-checking': emailStatus === 'checking',
                  'is-error': !['valid', 'checking'].includes(emailStatus),
                }"
                aria-live="polite"
              >
                <LoaderCircle
                  v-if="emailStatus === 'checking'"
                  class="email-check-spinner"
                  aria-hidden="true"
                />
                <CircleCheck v-else-if="emailStatus === 'valid'" aria-hidden="true" />
                <CircleAlert v-else aria-hidden="true" />
                <span>{{ emailStatusText }}</span>
              </p>
              <button
                v-if="suggestedEmail"
                class="register-email-action"
                type="button"
                @click="useSuggestedEmail"
              >
                Did you mean {{ suggestedEmail }}? Use this address
              </button>
              <button
                v-if="emailStatus === 'service_unavailable'"
                class="register-email-action"
                type="button"
                @click="retryEmailValidation"
              >
                Try again
              </button>
            </div>
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
          <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
          <button
            class="primary-button register-submit full"
            type="submit"
            :disabled="busy || emailChecking"
          >
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
