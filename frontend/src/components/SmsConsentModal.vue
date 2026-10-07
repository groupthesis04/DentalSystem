<script setup>
import { nextTick, onMounted, ref } from "vue";
import { Check, LockKeyhole, MessageSquareMore, Smartphone } from "lucide-vue-next";

import BaseModal from "./BaseModal.vue";

const emit = defineEmits(["agree", "cancel"]);
const agreed = ref(false);
const checkbox = ref(null);

onMounted(async () => {
  await nextTick();
  checkbox.value?.focus();
});

function agreeAndContinue() {
  if (agreed.value) emit("agree", true);
}
</script>

<template>
  <BaseModal
    title="SMS Notification Consent"
    size-class="sms-consent-dialog"
    @close="emit('cancel')"
  >
    <div class="sms-consent-body">
      <div class="sms-consent-intro">
        <span class="sms-consent-illustration" aria-hidden="true">
          <Smartphone :size="79" :stroke-width="1.65" />
          <span class="sms-consent-message"
            ><MessageSquareMore :size="28" :stroke-width="2.4"
          /></span>
        </span>
        <h2 aria-hidden="true">SMS Notification Consent</h2>
        <p>
          To continue with your appointment booking, please agree to receive SMS messages from BORJA
          Dental Clinic at the mobile number registered to your account.
        </p>
      </div>

      <div class="sms-consent-list">
        <strong>Messages may include:</strong>
        <ul>
          <li>
            <span><Check :size="14" aria-hidden="true" /></span>Appointment confirmation
          </li>
          <li>
            <span><Check :size="14" aria-hidden="true" /></span>Appointment reminders
          </li>
          <li>
            <span><Check :size="14" aria-hidden="true" /></span>Appointment status or schedule
            updates
          </li>
        </ul>
      </div>

      <p class="sms-consent-privacy">
        <span aria-hidden="true"><LockKeyhole :size="19" /></span>
        Your mobile number is used for appointment-related notifications through the clinic's SMS
        provider.
      </p>

      <label class="sms-consent-choice">
        <input ref="checkbox" v-model="agreed" type="checkbox" />
        <span>I agree to receive SMS notifications regarding my appointment.</span>
      </label>

      <div class="sms-consent-actions">
        <button class="secondary-button" type="button" @click="emit('cancel')">Cancel</button>
        <button class="primary-button" type="button" :disabled="!agreed" @click="agreeAndContinue">
          Agree &amp; Continue
        </button>
      </div>
    </div>
  </BaseModal>
</template>

<style>
.crud-dialog.sms-consent-dialog {
  width: min(555px, calc(100% - 24px));
  border: 1px solid #eadcc3;
  border-radius: 16px;
  background: #fff;
}

.sms-consent-dialog .crud-dialog-shell {
  position: relative;
  max-height: calc(100dvh - 24px);
  overflow-y: auto;
}

.sms-consent-dialog .crud-dialog-header {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 3;
  border: 0;
  background: transparent;
  padding: 0;
}

.sms-consent-dialog .crud-dialog-header > div {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.sms-consent-dialog .crud-dialog-header .icon-button {
  width: 36px;
  height: 36px;
  flex-basis: 36px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #5e5b56;
}

.sms-consent-dialog .crud-dialog-header .icon-button:is(:hover, :focus-visible) {
  background: #f7efdf;
  color: #171511;
}

.sms-consent-body {
  display: grid;
  gap: 18px;
  padding: 20px 32px 28px;
  color: #171511;
}

.sms-consent-intro {
  display: grid;
  justify-items: center;
  gap: 11px;
  text-align: center;
}

.sms-consent-illustration {
  position: relative;
  display: grid;
  width: 138px;
  height: 138px;
  place-items: center;
  border: 1px solid #f3e5c8;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 40%, #fff 17%, #f9eed5 100%);
  color: #171511;
}

.sms-consent-message {
  position: absolute;
  top: 47px;
  right: 15px;
  display: grid;
  width: 47px;
  height: 42px;
  place-items: center;
  border-radius: 8px;
  background: linear-gradient(145deg, #c9a251, #a77b29);
  color: #fff;
  box-shadow: 0 4px 10px rgb(102 72 24 / 18%);
}

.sms-consent-intro h2 {
  margin: 0;
  font-family: var(--font-brand);
  font-size: clamp(1.7rem, 4vw, 2.15rem);
  line-height: 1.15;
}

.sms-consent-intro p {
  max-width: 480px;
  margin: 0;
  color: #514b44;
  font-size: 0.98rem;
  font-weight: 400;
  line-height: 1.52;
}

.sms-consent-list {
  display: grid;
  gap: 7px;
  border-radius: 12px;
  background: linear-gradient(120deg, #f8f1e5, #f4ecdc);
  padding: 15px 20px;
  font-size: 0.93rem;
}

.sms-consent-list strong {
  font-weight: 800;
}

.sms-consent-list ul {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.sms-consent-list li {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  line-height: 1.45;
}

.sms-consent-list li > span {
  display: grid;
  width: 19px;
  height: 19px;
  flex: 0 0 19px;
  place-items: center;
  border-radius: 50%;
  background: #b88c39;
  color: #fff;
}

.sms-consent-privacy {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin: 0;
  color: #58524c;
  font-size: 0.86rem;
  line-height: 1.5;
}

.sms-consent-privacy > span {
  display: grid;
  width: 29px;
  height: 29px;
  flex: 0 0 29px;
  place-items: center;
  border-radius: 50%;
  background: #f7edd9;
  color: #946819;
}

.sms-consent-choice {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  color: #171511;
  font-size: 0.96rem;
  font-weight: 800;
  line-height: 1.45;
  cursor: pointer;
}

.sms-consent-choice input {
  width: 23px;
  height: 23px;
  flex: 0 0 23px;
  margin: 1px 0 0;
  padding: 0;
  border: 1px solid #a07735;
  border-radius: 4px;
  accent-color: #a77b29;
  cursor: pointer;
}

.sms-consent-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.22fr);
  gap: 18px;
  margin-top: 2px;
}

.sms-consent-actions button {
  min-height: 53px;
  font-weight: 800;
}

.sms-consent-actions .secondary-button {
  border: 1px solid #987032;
  background: #fff;
  color: #171511;
}

.sms-consent-actions .primary-button {
  border: 1px solid #aa7e2e;
  background: linear-gradient(110deg, #cb9d48, #a77a2b);
  color: #fff;
}

.sms-consent-actions .primary-button:disabled,
.sms-consent-actions .primary-button:disabled:hover {
  border-color: #d5b873;
  background: linear-gradient(110deg, #e4cb96, #d8b973);
  color: #fff;
  opacity: 1;
}

@media (max-width: 480px) {
  .sms-consent-body {
    gap: 14px;
    padding: 18px 20px 22px;
  }

  .sms-consent-illustration {
    width: 104px;
    height: 104px;
  }

  .sms-consent-illustration > svg {
    width: 62px;
    height: 62px;
  }

  .sms-consent-message {
    top: 35px;
    right: 8px;
    width: 37px;
    height: 33px;
  }

  .sms-consent-message svg {
    width: 22px;
    height: 22px;
  }

  .sms-consent-intro p,
  .sms-consent-choice {
    font-size: 0.9rem;
  }

  .sms-consent-list {
    padding: 13px 15px;
  }

  .sms-consent-actions {
    gap: 10px;
  }
}

@media (max-width: 340px) {
  .sms-consent-actions {
    grid-template-columns: 1fr;
  }
}
</style>
