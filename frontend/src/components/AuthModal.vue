<script setup>
import { Eye, EyeOff, LockKeyhole, Mail, ShieldCheck, UserRound, X } from "lucide-vue-next";
import { onBeforeUnmount, onMounted, reactive, ref } from "vue";

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
const register = reactive({
  name: "",
  phone: "",
  email: "",
  password: "",
  role: "patient",
  profile_image: "",
  _website: "",
});
const passwordInput = ref(null);
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

onMounted(() => document.body.classList.add("modal-open"));
onBeforeUnmount(() => document.body.classList.remove("modal-open"));

function switchTab(next) {
  tab.value = next;
  errorMessage.value = "";
  showPassword.value = false;
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
    const payload = validatedPayload({ ...register }, { registration: true });
    const data = await apiRequest("/api/register", { method: "POST", body: payload });
    session.user = data.user;
    session.csrfToken = data.csrf_token || session.csrfToken;
    finishAuthentication(data.user, "Account created successfully.");
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="modal-backdrop" role="dialog" aria-modal="true" @mousedown.self="emit('close')">
      <div class="auth-modal">
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

        <form v-else class="auth-form" @submit.prevent="submitRegister">
          <label class="hp-field" aria-hidden="true"
            >Website<input v-model="register._website" tabindex="-1" autocomplete="off"
          /></label>
          <div class="auth-heading compact">
            <img class="auth-brand-logo" src="/assets/logo.png" alt="" />
            <h2>Create your account</h2>
            <p>Start booking dental visits securely.</p>
          </div>
          <div class="form-grid two">
            <label
              >Full name<input
                v-model="register.name"
                autocomplete="name"
                minlength="2"
                maxlength="120"
                required
            /></label>
            <label
              >Phone<input
                v-model="register.phone"
                autocomplete="tel"
                inputmode="tel"
                maxlength="24"
            /></label>
          </div>
          <label
            >Email<input
              v-model="register.email"
              type="email"
              autocomplete="email"
              maxlength="254"
              required
          /></label>
          <label
            >Password<input
              v-model="register.password"
              type="password"
              autocomplete="new-password"
              minlength="10"
              maxlength="128"
              required
          /></label>
          <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
          <button class="primary-button full" type="submit" :disabled="busy">
            {{ busy ? "Creating..." : "Create Account" }}
          </button>
          <p class="auth-switch">
            Already have an account?
            <button class="active" type="button" @click="switchTab('login')">Log In</button>
          </p>
        </form>
      </div>
    </div>
  </Teleport>
</template>
