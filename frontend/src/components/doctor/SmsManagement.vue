<script setup>
import {
  Activity,
  ArrowRight,
  CalendarDays,
  CalendarPlus,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Database,
  FileText,
  Info,
  MessageCircleMore,
  Pencil,
  Power,
  RefreshCw,
  Send,
  Settings2,
  UserRoundPlus,
  Wallet,
  XCircle,
} from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import BaseModal from "../BaseModal.vue";
import SmsTemplates from "./SmsTemplates.vue";
import SmsMessageLogs from "./SmsMessageLogs.vue";
import { apiRequest } from "../../services/api";
import { showToast } from "../../services/toast";

const props = defineProps({ section: { type: String, default: "doctorSmsCenter" } });
const emit = defineEmits(["select-panel"]);
const data = ref(null);
const loading = ref(true);
const error = ref("");
const busy = ref(false);
const selected = ref("booking");
const messages = ref([]);
const total = ref(0);
const page = ref(1);
const status = ref("");
const logRule = ref("");
const showTest = ref(false);
const testPhone = ref("");
const testError = ref("");
const details = ref(null);
let timer;
let refreshing = false;
const icons = {
  booking: CalendarDays,
  approval: CheckCircle2,
  walk_in: UserRoundPlus,
  next_visit: CalendarPlus,
  balance: Wallet,
  cancellation: XCircle,
};
const rule = computed(() => data.value?.rules.find((item) => item.key === selected.value));
const draft = computed(() => rule.value?.template || "");
const sample = computed(() => ({
  PatientName: "Sample Patient",
  AppointmentDate: new Date().toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }),
  Time: "09:00 AM",
  Balance: "500.00",
  ClinicName: data.value?.clinic_name || "BORJA Dental Clinic",
}));
const preview = computed(() =>
  draft.value.replace(/\{(\w+)\}/g, (match, key) => sample.value[key] ?? match),
);
const allOff = computed(() => data.value?.rules.every((item) => !item.enabled));
const creditBalance = computed(() => {
  const value = data.value?.provider?.credit_balance;
  return value === null || value === undefined
    ? "--"
    : new Intl.NumberFormat("en-PH", { maximumFractionDigits: 2 }).format(value);
});
const creditCaption = computed(() => {
  const provider = data.value?.provider;
  if (!provider?.key_configured) return "Connect Semaphore to view";
  if (provider.credit_balance === null || provider.credit_balance === undefined)
    return "Balance temporarily unavailable";
  if (!provider.credit_checked_at) return "Live Semaphore balance";
  return `Updated ${new Date(provider.credit_checked_at).toLocaleTimeString("en-PH", {
    hour: "numeric",
    minute: "2-digit",
  })}`;
});
const statusLabels = {
  pending: "Pending",
  sent: "Sent",
  delivered: "Delivered",
  failed: "Failed",
  not_sent: "Not Sent",
};
const technicalStatusLabels = {
  queued: "Queued",
  processing: "Sending",
  submitted: "Provider queued",
  pending: "In transit",
  sent: "Sent to network",
  delivered: "Delivery confirmed",
  failed: "Failed",
  refunded: "Refunded",
  unknown: "Needs review",
  suppressed: "Not sent",
  expired: "Expired",
};

function dateLabel(value) {
  return value
    ? new Date(value).toLocaleString("en-PH", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : "Not yet submitted";
}

async function loadLogs() {
  const query = new URLSearchParams({
    page: page.value,
    status: status.value,
    rule: logRule.value,
  });
  const result = await apiRequest("/api/sms/logs?" + query);
  messages.value = result.messages;
  total.value = result.total;
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const result = await apiRequest("/api/sms");
    data.value = result;
    await loadLogs();
    error.value = "";
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
    refreshing = false;
  }
}

function selectRule(key, focus = false) {
  selected.value = key;
  if (focus) {
    emit("select-panel", "doctorSmsTemplates");
  }
}

async function updateRule(payload) {
  busy.value = true;
  try {
    await apiRequest("/api/sms/rules", { method: "PATCH", body: payload });
    await refresh();
    showToast("Automation settings saved.");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    busy.value = false;
  }
}

async function sendTest() {
  busy.value = true;
  testError.value = "";
  try {
    await apiRequest("/api/sms/test", {
      method: "POST",
      body: { key: selected.value, phone: testPhone.value, template: draft.value },
    });
    showTest.value = false;
    showToast("Test SMS queued. Its sending status will appear in Message Logs.");
    await refresh();
  } catch (err) {
    testError.value = err.message;
  } finally {
    busy.value = false;
  }
}

function openTest() {
  testError.value = "";
  showTest.value = true;
}
watch([status, logRule], () => {
  page.value = 1;
  loadLogs().catch((err) => {
    error.value = err.message;
  });
});
watch(page, () =>
  loadLogs().catch((err) => {
    error.value = err.message;
  }),
);
onMounted(() => {
  refresh();
  timer = window.setInterval(refresh, 30000);
});
onBeforeUnmount(() => window.clearInterval(timer));
</script>

<template>
  <SmsTemplates
    v-if="section === 'doctorSmsTemplates'"
    :initial-rule="selected"
    :rules="data?.rules || []"
    @changed="refresh"
    @select-panel="emit('select-panel', $event)"
  />
  <SmsMessageLogs v-else-if="section === 'doctorSmsLogs'" />
  <section v-else class="sms-center" aria-labelledby="sms-title">
    <header class="sms-heading">
      <div class="sms-title">
        <MessageCircleMore :size="39" />
        <div>
          <h1 id="sms-title">SMS Automation Center</h1>
          <p>Patient notifications</p>
        </div>
      </div>
      <div class="sms-actions">
        <button type="button" :disabled="!data?.provider.ready" @click="openTest">
          <Send :size="17" /> Test SMS
        </button>
        <button type="button" :disabled="loading" @click="refresh" title="Refresh SMS status">
          <RefreshCw :size="17" /> Refresh
        </button>
        <button
          v-if="data"
          type="button"
          :class="{ danger: !allOff }"
          :disabled="busy"
          @click="updateRule({ key: 'all', enabled: allOff })"
        >
          <Power :size="17" /> {{ allOff ? "Enable All Automations" : "Disable All Automations" }}
        </button>
      </div>
    </header>
    <p v-if="error" class="sms-alert error" role="alert">{{ error }}</p>
    <p v-if="loading" class="sms-empty">Loading SMS automations...</p>
    <template v-if="data">
      <div
        class="sms-provider"
        :class="{ warning: !data.provider.ready || !data.provider.worker_active }"
        role="status"
      >
        <Info :size="19" />
        <span v-if="!data.provider.ready"
          ><strong>Semaphore is not connected.</strong> Phone delivery is inactive. Add the API key
          and approved sender name to the backend configuration, then enable sending.</span
        >
        <span v-else-if="!data.provider.worker_active"
          ><strong>SMS worker is offline.</strong> Messages remain queued until the background
          worker is running.</span
        >
        <span v-else
          ><strong>Semaphore connected</strong> | Worker online | Sender:
          {{ data.provider.sender_name }}</span
        >
      </div>
      <div class="sms-stats">
        <article>
          <span class="stat-icon green"><Settings2 :size="27" /></span>
          <div>
            <p>Automations Active</p>
            <strong>{{ data.stats.active }} / 6</strong
            ><small>{{ allOff ? "All automations paused" : "Rules enabled" }}</small>
          </div>
        </article>
        <article>
          <span class="stat-icon blue"><Send :size="27" /></span>
          <div>
            <p>Messages Sent Today</p>
            <strong>{{ data.stats.sent_today }}</strong
            ><small>Accepted by the network</small>
          </div>
        </article>
        <article>
          <span class="stat-icon amber"><Clock3 :size="27" /></span>
          <div>
            <p>Pending Queue</p>
            <strong>{{ data.stats.pending }}</strong
            ><small>Waiting or in transit</small>
          </div>
        </article>
        <article
          class="credit-stat"
          :title="data.provider.credit_error || 'Live credit balance from Semaphore'"
        >
          <span class="stat-icon purple"><Database :size="27" /></span>
          <div>
            <p>SMS Credits Remaining</p>
            <strong>{{ creditBalance }}</strong
            ><small>{{ creditCaption }}</small>
          </div>
        </article>
        <article>
          <span class="stat-icon green"><Activity :size="27" /></span>
          <div>
            <p>Network Acceptance</p>
            <strong>{{
              data.stats.success_rate === null ? "--" : data.stats.success_rate + "%"
            }}</strong
            ><small>Final results, last 30 days</small>
          </div>
        </article>
      </div>
      <div class="sms-layout">
        <div class="sms-main-column">
          <section class="sms-rules" aria-labelledby="rules-title">
            <header class="section-heading">
              <Settings2 :size="23" />
              <div>
                <h2 id="rules-title">Automation Rules</h2>
                <p>Patient mobile number is used for each notification.</p>
              </div>
            </header>
            <div class="sms-table-wrap">
              <table class="rules-table">
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Rule Name</th>
                    <th scope="col">Trigger</th>
                    <th scope="col">Frequency</th>
                    <th scope="col">Status</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(item, index) in data.rules"
                    :key="item.key"
                    :class="{ selected: selected === item.key }"
                  >
                    <td>{{ index + 1 }}</td>
                    <td>
                      <div class="rule-name">
                        <span class="rule-icon" :class="item.key"
                          ><component :is="icons[item.key]" :size="21" /></span
                        ><strong>{{ item.name }}</strong>
                      </div>
                    </td>
                    <td><span class="mobile-cell-label">Trigger</span>{{ item.trigger }}</td>
                    <td><span class="mobile-cell-label">Frequency</span>{{ item.frequency }}</td>
                    <td>
                      <span class="mobile-cell-label">Status</span>
                      <label class="sms-toggle"
                        ><input
                          type="checkbox"
                          role="switch"
                          :aria-label="item.name"
                          :checked="item.enabled"
                          :disabled="busy"
                          @change="updateRule({ key: item.key, enabled: $event.target.checked })"
                        /><span class="switch-track"></span
                        ><span>{{ item.enabled ? "ON" : "OFF" }}</span></label
                      >
                    </td>
                    <td>
                      <button
                        class="sms-template-action"
                        type="button"
                        @click="selectRule(item.key, true)"
                      >
                        <Pencil :size="14" /> Edit Message
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <section class="sms-logs" aria-labelledby="logs-title">
            <header class="section-heading sms-log-heading">
              <Clock3 :size="23" />
              <div>
                <h2 id="logs-title">Recent SMS Activity</h2>
                <p>Semaphore reports network acceptance, not delivery to the handset.</p>
              </div>
              <button
                class="text-button"
                type="button"
                @click="emit('select-panel', 'doctorSmsLogs')"
              >
                View All Logs <ArrowRight :size="16" />
              </button>
            </header>
            <div class="log-filters">
              <select v-model="logRule" aria-label="Filter SMS automation">
                <option value="">All automations</option>
                <option v-for="item in data.rules" :key="item.key" :value="item.key">
                  {{ item.name }}
                </option></select
              ><select v-model="status" aria-label="Filter SMS status">
                <option value="">All Statuses</option>
                <option v-for="(label, key) in statusLabels" :key="key" :value="key">
                  {{ label }}
                </option>
              </select>
            </div>
            <div class="sms-table-wrap">
              <table class="logs-table">
                <thead>
                  <tr>
                    <th scope="col">Date &amp; Time</th>
                    <th scope="col">Patient</th>
                    <th scope="col">Message Preview</th>
                    <th scope="col">Type</th>
                    <th scope="col">Status</th>
                    <th scope="col"><span class="visually-hidden">Details</span></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in messages" :key="item.id">
                    <td>
                      <span class="mobile-cell-label">Date &amp; Time</span>
                      {{ dateLabel(item.created_at) }}
                    </td>
                    <td>
                      <span class="mobile-cell-label">Patient</span>
                      <strong>{{ item.patient_name }}</strong
                      ><small>{{ item.phone || "No mobile number" }}</small>
                    </td>
                    <td>
                      <span class="mobile-cell-label">Message Preview</span>
                      <span class="message-preview">{{ item.body }}</span>
                    </td>
                    <td>
                      <span class="mobile-cell-label">Type</span>
                      <span class="type-badge" :class="item.rule">{{
                        item.is_test ? "Test SMS" : item.name
                      }}</span>
                    </td>
                    <td>
                      <span class="mobile-cell-label">Status</span>
                      <span class="sms-status" :class="item.display_status">{{
                        statusLabels[item.display_status]
                      }}</span>
                    </td>
                    <td>
                      <button
                        class="details-button"
                        type="button"
                        :aria-label="'View SMS details for ' + item.patient_name"
                        title="View message details"
                        @click="details = item"
                      >
                        <FileText :size="17" />
                      </button>
                    </td>
                  </tr>
                  <tr v-if="!messages.length" class="sms-empty-row">
                    <td colspan="6" class="sms-empty">
                      No SMS messages {{ status || logRule ? "match these filters" : "yet" }}.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <footer class="log-pagination">
              <span>{{
                total
                  ? (page - 1) * 10 + 1 + "-" + Math.min(page * 10, total) + " of " + total
                  : "0 messages"
              }}</span>
              <div>
                <button
                  type="button"
                  aria-label="Previous messages"
                  :disabled="page === 1"
                  @click="page--"
                >
                  <ChevronLeft :size="18" /></button
                ><span>{{ page }}</span
                ><button
                  type="button"
                  aria-label="Next messages"
                  :disabled="page * 10 >= total"
                  @click="page++"
                >
                  <ChevronRight :size="18" />
                </button>
              </div>
            </footer>
          </section>
        </div>
      </div>
    </template>
    <BaseModal
      v-if="showTest"
      title="Send Test SMS"
      eyebrow="Semaphore"
      @close="!busy && (showTest = false)"
    >
      <form class="sms-modal-form" @submit.prevent="sendTest">
        <label
          >Recipient mobile number<input
            v-model="testPhone"
            type="tel"
            required
            placeholder="09XXXXXXXXX"
            autocomplete="tel"
        /></label>
        <div class="sample-preview">
          <h3>Message to Send</h3>
          <p>{{ preview }}</p>
        </div>
        <p>This sends a real SMS to this number and uses your Semaphore credits.</p>
        <p v-if="testError" class="sms-alert error" role="alert">{{ testError }}</p>
        <footer>
          <button type="button" :disabled="busy" @click="showTest = false">Cancel</button
          ><button type="submit" class="primary" :disabled="busy">
            <Send :size="17" /> {{ busy ? "Queuing..." : "Send Test SMS" }}
          </button>
        </footer>
      </form>
    </BaseModal>
    <BaseModal
      v-if="details"
      title="SMS Message Details"
      :eyebrow="details.name"
      @close="details = null"
      ><div class="sms-modal-form">
        <dl class="message-details">
          <div>
            <dt>Patient</dt>
            <dd>{{ details.patient_name }}</dd>
          </div>
          <div>
            <dt>Mobile Number</dt>
            <dd>{{ details.phone || "Not recorded" }}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{{ statusLabels[details.display_status] }}</dd>
          </div>
          <div>
            <dt>Technical Status</dt>
            <dd>{{ technicalStatusLabels[details.status] || details.status }}</dd>
          </div>
          <div>
            <dt>Semaphore Message ID</dt>
            <dd>{{ details.provider_id || "Not assigned" }}</dd>
          </div>
          <div>
            <dt>Created</dt>
            <dd>{{ dateLabel(details.created_at) }}</dd>
          </div>
          <div>
            <dt>Submitted</dt>
            <dd>{{ dateLabel(details.submitted_at) }}</dd>
          </div>
        </dl>
        <p class="sms-message-body">{{ details.body }}</p>
        <p v-if="details.error" class="sms-alert" role="status">{{ details.error }}</p>
        <footer><button type="button" @click="details = null">Close</button></footer>
      </div></BaseModal
    >
  </section>
</template>

<style scoped>
.sms-center {
  color: var(--dashboard-text, #17345a);
  min-width: 0;
}
.sms-center *,
.sms-modal-form * {
  box-sizing: border-box;
  letter-spacing: 0;
}
.sms-heading,
.sms-title,
.sms-actions,
.section-heading,
.rule-name,
.log-pagination,
.log-pagination > div {
  display: flex;
  align-items: center;
  gap: 12px;
}
.sms-heading {
  justify-content: space-between;
  flex-wrap: wrap;
  margin-bottom: 18px;
}
.sms-title > svg,
.section-heading > svg {
  color: #0876ef;
  flex-shrink: 0;
}
.sms-title h1 {
  font-size: 27px;
  line-height: 1.2;
  margin: 0 0 5px;
}
.sms-title p,
.section-heading p {
  font-size: 12px;
  color: var(--dashboard-muted, #66809f);
  margin: 0;
}
.sms-actions {
  flex-wrap: wrap;
  gap: 8px;
}
.sms-center button,
.sms-modal-form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid #cbdff7;
  background: var(--surface, #fff);
  color: #0868d4;
  border-radius: 6px;
  padding: 10px 13px;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  min-height: 36px;
  box-shadow: none;
}
.sms-center button:hover:not(:disabled),
.sms-modal-form button:hover:not(:disabled) {
  background: #eaf4ff;
}
.sms-center button:disabled,
.sms-modal-form button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
.sms-center button.danger {
  border-color: #efb6bf;
  color: #c6334c;
}
.sms-center button.primary,
.sms-modal-form button.primary {
  color: #fff;
  border-color: #0876ef;
  background: #0876ef;
}
.sms-center button.primary:hover:not(:disabled),
.sms-modal-form button.primary:hover:not(:disabled) {
  background: #0664ca;
}
.sms-provider,
.sms-alert {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: #ebf9f4;
  border: 1px solid #c7ecdf;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  margin: 0 0 16px;
}
.sms-provider > svg {
  flex-shrink: 0;
}
.sms-provider.warning {
  background: #fff8e9;
  border-color: #f1dfb5;
  color: #785622;
}
.sms-alert.error {
  color: #b4233e;
  background: #fff1f3;
  border-color: #f3ccd2;
}
.sms-stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 22px;
}
.sms-stats article {
  display: flex;
  align-items: center;
  gap: 17px;
  padding: 17px;
  background: var(--surface, #fff);
  border: 1px solid var(--dashboard-border, #dde7f3);
  border-radius: 7px;
}
.stat-icon {
  width: 54px;
  height: 58px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  flex-shrink: 0;
}
.green {
  background: #e2f6ed;
  color: #0a9970;
}
.blue {
  background: #e8f2ff;
  color: #0876ef;
}
.amber {
  background: #fff3e6;
  color: #d77812;
}
.purple {
  background: #f2eaff;
  color: #7d43cf;
}
.credit-stat strong {
  font-variant-numeric: tabular-nums;
}
.sms-stats p {
  font-size: 12px;
  margin: 0 0 5px;
}
.sms-stats strong {
  display: block;
  font-size: 26px;
  line-height: 1.2;
}
.sms-stats small {
  color: var(--dashboard-muted, #66809f);
  font-size: 11px;
}
.sms-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.sms-main-column {
  min-width: 0;
}
.sms-rules,
.sms-logs {
  padding: 0 0 18px;
  border-bottom: 1px solid var(--dashboard-border, #dbe6f2);
  scroll-margin-top: 170px;
}
.sms-logs {
  margin-top: 22px;
}
.section-heading {
  max-width: none;
  margin-bottom: 14px;
  align-items: flex-start;
}
.sms-log-heading {
  display: grid;
  grid-template-columns: 23px minmax(0, 1fr) auto;
  align-items: center;
}
.section-heading h2 {
  font-size: 17px;
  margin: 0 0 4px;
  line-height: 1.35;
}
.section-heading p {
  line-height: 1.5;
}
.sms-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--dashboard-border, #dbe6f2);
  border-radius: 6px;
  background: var(--surface, #fff);
}
.sms-center table {
  width: 100%;
  min-width: 0;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 11px;
  line-height: 1.45;
  margin: 0;
}
.sms-center th {
  background: var(--sms-muted-surface, #eef4fb);
  color: var(--dashboard-muted, #4a668b);
  font-size: 10px;
  text-transform: uppercase;
  font-weight: 700;
  padding: 11px 9px;
  text-align: left;
  white-space: normal;
}
.sms-center td {
  padding: 13px 9px;
  border-top: 1px solid var(--dashboard-border, #e3ebf5);
  vertical-align: middle;
  overflow-wrap: anywhere;
}
.mobile-cell-label {
  display: none;
}
.sms-center tr.selected {
  background: #f6faff;
}
.rules-table th:nth-child(1) {
  width: 4%;
}
.rules-table th:nth-child(2) {
  width: 27%;
}
.rules-table th:nth-child(3) {
  width: 23%;
}
.rules-table th:nth-child(4) {
  width: 15%;
}
.rules-table th:nth-child(5) {
  width: 12%;
}
.rules-table th:nth-child(6) {
  width: 19%;
}
.rule-name {
  gap: 9px;
}
.rule-name strong {
  font-weight: 650;
}
.rule-icon {
  display: grid;
  place-items: center;
  width: 31px;
  height: 34px;
  border-radius: 6px;
  color: #0876ef;
  background: #e8f2ff;
  flex-shrink: 0;
}
.approval {
  background: #e3f7ef;
  color: #087e68;
}
.walk_in,
.next_visit {
  background: #f0eaff;
  color: #7555c5;
}
.balance {
  background: #fff0e0;
  color: #98630d;
}
.cancellation {
  background: #fff0f3;
  color: #d33452;
}
.sms-center .sms-template-action {
  font-size: 10px;
  padding: 7px 8px;
  min-height: 30px;
  white-space: nowrap;
  gap: 5px;
  width: 100%;
}
.sms-template-action svg {
  flex-shrink: 0;
}
.sms-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative;
  cursor: pointer;
  font-size: 10px;
  font-weight: 600;
}
.sms-toggle input {
  position: absolute;
  opacity: 0;
  width: 31px;
  height: 20px;
  margin: 0;
}
.switch-track {
  width: 31px;
  height: 18px;
  border-radius: 12px;
  background: #a8b6c8;
  flex-shrink: 0;
  transition: background 0.2s;
}
.switch-track::after {
  content: "";
  display: block;
  width: 14px;
  height: 14px;
  margin: 2px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
}
.sms-toggle input:checked + .switch-track {
  background: #12a775;
}
.sms-toggle input:checked + .switch-track::after {
  transform: translateX(13px);
}
.sms-toggle input:focus-visible + .switch-track {
  outline: 2px solid #0876ef;
  outline-offset: 3px;
}
.sms-toggle input:disabled ~ span {
  opacity: 0.5;
}
.log-filters select,
.sms-modal-form input {
  font: inherit;
  font-size: 12px;
  color: inherit;
  border: 1px solid #cbdcf1;
  border-radius: 6px;
  background: var(--surface, #fff);
  padding: 10px;
  width: 100%;
  min-width: 0;
  box-shadow: none;
}
.sample-preview {
  margin-top: 22px;
}
.sample-preview h3 {
  font-size: 12px;
  margin: 0 0 8px;
}
.sample-preview p {
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--dashboard-text, #17345a);
  background: var(--sms-muted-surface, #f2f6fb);
  border-left: 3px solid #9ecbf5;
  padding: 12px;
  margin: 0 0 8px;
}
.sample-preview small {
  font-size: 10px;
  color: var(--dashboard-muted, #66809f);
}
.sms-center .text-button {
  border: 0;
  background: transparent;
  padding: 0;
  margin-left: auto;
  font-size: 11px;
  white-space: nowrap;
}
.log-filters {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.log-filters select {
  max-width: 260px;
}
.logs-table th:nth-child(1) {
  width: 17%;
}
.logs-table th:nth-child(2) {
  width: 20%;
}
.logs-table th:nth-child(3) {
  width: 26%;
}
.logs-table th:nth-child(4) {
  width: 18%;
}
.logs-table th:nth-child(5) {
  width: 14%;
}
.logs-table th:nth-child(6) {
  width: 5%;
}
.logs-table td {
  font-size: 10px;
}
.logs-table td small {
  display: block;
  color: var(--dashboard-muted, #66809f);
  font-size: 10px;
  margin-top: 3px;
}
.message-preview {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.type-badge {
  padding: 4px 5px;
  border-radius: 4px;
  display: inline-block;
  font-size: 9px;
}
.sms-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
}
.sms-status::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #8a99ac;
  flex-shrink: 0;
}
.sms-status.sent,
.sms-status.delivered {
  color: #07865e;
}
.sms-status.sent::before,
.sms-status.delivered::before {
  background: #13aa79;
}
.sms-status.failed {
  color: #be354f;
}
.sms-status.failed::before {
  background: #dd4260;
}
.sms-status.pending {
  color: #a96f00;
}
.sms-status.pending::before {
  background: #3285ef;
}
.sms-center .details-button {
  border: 0;
  padding: 2px;
  min-height: 28px;
  background: transparent;
}
.sms-center .sms-empty {
  text-align: center;
  padding: 40px 15px;
  color: var(--dashboard-muted, #66809f);
  font-size: 13px;
}
.log-pagination {
  justify-content: space-between;
  font-size: 11px;
  margin-top: 12px;
}
.log-pagination button {
  padding: 5px;
  min-height: 30px;
}
.log-pagination > div {
  gap: 10px;
}
.sms-modal-form {
  padding: 24px;
  color: var(--dashboard-text, #17345a);
}
.sms-modal-form > label {
  display: grid;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}
.sms-modal-form > p {
  font-size: 13px;
  line-height: 1.6;
}
.sms-modal-form footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}
.message-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin: 0;
}
.message-details dt {
  font-size: 11px;
  color: var(--dashboard-muted, #66809f);
}
.message-details dd {
  margin: 4px 0 0;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.sms-message-body {
  white-space: pre-wrap;
  padding: 16px;
  background: var(--sms-muted-surface, #eef4fb);
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}
@media (max-width: 1250px) {
  .sms-stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .sms-stats article {
    gap: 10px;
    padding: 14px;
  }
  .stat-icon {
    width: 43px;
    height: 49px;
  }
  .sms-stats p {
    font-size: 11px;
  }
  .sms-stats strong {
    font-size: 23px;
  }
}
@media (max-width: 750px) {
  .sms-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .sms-title h1 {
    font-size: 23px;
  }
  .sms-center table {
    display: block;
    width: 100%;
    min-width: 0;
  }
  .sms-center table thead {
    display: none;
  }
  .sms-center table tbody {
    display: grid;
    gap: 10px;
    padding: 10px;
  }
  .sms-center table tr {
    display: grid;
    gap: 10px 12px;
    border: 1px solid var(--dashboard-border, #dbe6f2);
    border-radius: 7px;
    background: var(--surface, #fff);
    padding: 12px;
  }
  .sms-center table td {
    display: block;
    min-width: 0;
    padding: 0;
    border: 0;
    font-size: 12px;
  }
  .mobile-cell-label {
    display: block;
    margin-bottom: 3px;
    color: var(--dashboard-muted, #66809f);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .sms-rules .sms-table-wrap {
    overflow: visible;
    border: 0;
    background: transparent;
  }
  .rules-table tr {
    grid-template-columns: 30px minmax(0, 1fr) auto;
    align-items: center;
  }
  .rules-table td:first-child {
    grid-column: 1;
    grid-row: 1;
    align-self: start;
    color: var(--dashboard-muted, #66809f);
    font-weight: 700;
  }
  .rules-table td:first-child::before {
    content: "#";
  }
  .rules-table td:nth-child(2) {
    grid-column: 2 / -1;
    grid-row: 1;
  }
  .rules-table td:nth-child(3),
  .rules-table td:nth-child(4) {
    grid-column: 1 / -1;
  }
  .rules-table td:nth-child(5) {
    grid-column: 1 / 3;
  }
  .rules-table td:nth-child(6) {
    grid-column: 3;
    align-self: end;
  }
  .rules-table .rule-name {
    align-items: flex-start;
  }
  .rules-table .sms-toggle {
    min-height: 36px;
    font-size: 12px;
  }
  .sms-center .rules-table .sms-template-action {
    width: auto;
    min-height: 38px;
    font-size: 11px;
  }
  .logs-table tr:not(.sms-empty-row) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .logs-table td:nth-child(-n + 3) {
    grid-column: 1 / -1;
  }
  .logs-table td:last-child {
    grid-column: 1 / -1;
    justify-self: end;
  }
  .logs-table td,
  .logs-table td small {
    font-size: 12px;
  }
  .logs-table .sms-empty-row {
    display: block;
  }
  .sms-center .logs-table .sms-empty {
    padding: 18px;
  }
  .log-filters {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .log-filters select {
    max-width: none;
  }
  .sms-actions {
    width: 100%;
  }
  .sms-actions button {
    flex: 1;
    font-size: 11px;
  }
  .section-heading {
    flex-wrap: wrap;
  }
  .sms-log-heading {
    grid-template-columns: 23px minmax(0, 1fr);
  }
  .sms-center .text-button {
    grid-column: 2;
    justify-self: end;
    margin-left: 0;
  }
  .sms-provider {
    align-items: flex-start;
  }
  .message-details {
    grid-template-columns: 1fr;
  }
  .sms-modal-form {
    padding: 18px;
  }
}
@media (max-width: 420px) {
  .log-filters {
    grid-template-columns: 1fr;
  }
  .sms-stats article {
    gap: 8px;
    padding: 10px;
  }
  .stat-icon {
    width: 34px;
    height: 43px;
  }
  .stat-icon svg {
    width: 22px;
  }
  .sms-stats small {
    font-size: 9px;
  }
  .sms-actions {
    flex-wrap: wrap;
  }
  .sms-actions button {
    flex: 1 1 40%;
  }
}
:global(html[data-dashboard-theme="dark"]) .sms-center tr.selected {
  background: #243443;
}
:global(html[data-dashboard-theme="dark"]) .sms-center,
:global(html[data-dashboard-theme="dark"]) .sms-modal-form {
  --sms-muted-surface: #202c3b;
}
</style>
