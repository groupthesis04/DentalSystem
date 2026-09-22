<script setup>
import { ArrowLeft, LogIn, ShieldCheck, UserPlus } from "lucide-vue-next";

import BaseModal from "./BaseModal.vue";

const emit = defineEmits(["login", "register", "back"]);
</script>

<template>
  <BaseModal
    title="Authentication Required"
    eyebrow="Appointment saved"
    size-class="booking-auth-dialog"
    @close="emit('back')"
  >
    <div class="booking-auth-content">
      <span class="booking-auth-icon" aria-hidden="true"><ShieldCheck :size="30" /></span>
      <p>
        Your appointment details are saved. Log in or create an account to continue. You will not
        need to fill out the appointment form again.
      </p>

      <div class="booking-auth-actions">
        <button class="primary-button" type="button" @click="emit('login')">
          <LogIn :size="19" aria-hidden="true" />
          <span><strong>Log In</strong><small>I already have a patient account</small></span>
        </button>
        <button class="secondary-button" type="button" @click="emit('register')">
          <UserPlus :size="19" aria-hidden="true" />
          <span><strong>Create Account</strong><small>I am a new patient</small></span>
        </button>
      </div>

      <button class="booking-auth-back" type="button" @click="emit('back')">
        <ArrowLeft :size="17" aria-hidden="true" />Back to Appointment
      </button>
    </div>
  </BaseModal>
</template>

<style scoped>
:global(.booking-auth-dialog) {
  width: min(590px, calc(100vw - 32px));
}

.booking-auth-content {
  display: grid;
  justify-items: center;
  gap: 22px;
  padding: 8px 30px 30px;
  text-align: center;
}

.booking-auth-icon {
  display: grid;
  width: 58px;
  height: 58px;
  place-items: center;
  color: #087d94;
  background: #e5f8fc;
  border-radius: 50%;
}

.booking-auth-content > p {
  max-width: 480px;
  margin: 0;
  color: #415675;
  font-size: 1rem;
  line-height: 1.65;
}

.booking-auth-actions {
  display: grid;
  width: 100%;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.booking-auth-actions button {
  min-height: 72px;
  justify-content: flex-start;
  gap: 11px;
  padding: 13px 16px;
  text-align: left;
}

.booking-auth-actions button span {
  display: grid;
  gap: 3px;
}

.booking-auth-actions button small {
  font-size: 0.75rem;
  font-weight: 500;
  opacity: 0.78;
}

.booking-auth-back {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px;
  color: #395372;
  background: transparent;
  border: 0;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.booking-auth-back:hover,
.booking-auth-back:focus-visible {
  color: #087d94;
}

@media (max-width: 560px) {
  .booking-auth-content {
    gap: 18px;
    padding: 4px 18px 24px;
  }

  .booking-auth-actions {
    grid-template-columns: 1fr;
  }
}
</style>
