<script setup>
import {
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Eye,
  FileText,
  Info,
  MessageCircleMore,
  RefreshCw,
  Search,
  Send,
  Settings2,
  Smartphone,
  UserRound,
  Workflow,
  X,
  XCircle,
} from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import BaseModal from "../BaseModal.vue";
import { apiRequest } from "../../services/api";
import { showToast } from "../../services/toast";

const root = ref(null);
const detailsPanel = ref(null);
const result = ref(null);
const selectedId = ref("");
const loading = ref(true);
const error = ref("");
const filters = reactive({ q: "", rule: "", status: "", source: "", date_from: "", date_to: "" });
const pageSize = ref(10);
const page = ref(1);
const resendTarget = ref(null);
const resending = ref(false);
const resendError = ref("");
let requestNumber = 0;
let searchTimer;
let refreshTimer;
let disposed = false;

const types = {
  booking: "Booking Confirmation",
  approval: "Appointment Approved",
  walk_in: "Walk-in Added",
  next_visit: "Next Visit Reminder",
  balance: "Payment Reminder",
  cancellation: "Appointment Cancelled",
};
const statuses = {
  pending: "Pending",
  sent: "Sent",
  delivered: "Delivered",
  failed: "Failed",
  not_sent: "Not Sent",
};
const sources = { automated: "Automated", manual: "Manual resend", test: "Test SMS" };
const messages = computed(() => result.value?.messages || []);
const selected = computed(() => messages.value.find((item) => item.id === selectedId.value));
const total = computed(() => result.value?.total || 0);
const pages = computed(() => result.value?.pages || 1);
const firstRow = computed(() => (total.value ? (page.value - 1) * pageSize.value + 1 : 0));
const lastRow = computed(() => Math.min(page.value * pageSize.value, total.value));
const invalidDates = computed(
  () => filters.date_from && filters.date_to && filters.date_from > filters.date_to,
);
const hasFilters = computed(() => Object.values(filters).some(Boolean));
const pageLinks = computed(() => {
  const visible = [...new Set([1, page.value - 1, page.value, page.value + 1, pages.value])]
    .filter((value) => value > 0 && value <= pages.value)
    .sort((a, b) => a - b);
  return visible.flatMap((value, index) =>
    index && value - visible[index - 1] > 1 ? [`gap-${value}`, value] : [value],
  );
});
const metrics = computed(() => {
  const stats = result.value?.stats;
  const percent = (value) =>
    stats?.total
      ? `${((value * 100) / stats.total).toFixed(1)}% of matching messages`
      : "No messages yet";
  return [
    {
      label: "Total Messages",
      value: stats?.total,
      detail: hasFilters.value ? "Matching current filters" : "All recorded SMS activity",
      icon: Send,
      color: "blue",
    },
    {
      label: "Delivered",
      value: stats?.delivered,
      detail: percent(stats?.delivered),
      icon: CheckCircle2,
      color: "green",
    },
    {
      label: "Failed",
      value: stats?.failed,
      detail: percent(stats?.failed),
      icon: XCircle,
      color: "red",
    },
    {
      label: "Scheduled",
      value: stats?.scheduled,
      detail: "Queued for a future send",
      icon: Clock3,
      color: "amber",
    },
    {
      label: "Automation Rules Active",
      value: stats?.active_rules,
      detail: `of ${stats?.total_rules ?? 6} total rules`,
      icon: Settings2,
      color: "violet",
    },
  ];
});
const timeline = computed(() => {
  const item = selected.value;
  if (!item) return [];
  const events = [{ label: "Message recorded", at: item.created_at, state: "done" }];
  if (item.submitted_at) {
    events.push({ label: "Submitted to SMS provider", at: item.submitted_at, state: "done" });
  } else if (item.status === "queued") {
    events.push({ label: "Scheduled send", at: item.scheduled_for, state: "pending" });
  }
  if (item.checked_at) {
    events.push({
      label: "Last provider status check",
      at: item.checked_at,
      state: item.display_status,
    });
  }
  return events;
});
const deliveryNote = computed(() => {
  const item = selected.value;
  if (!item) return "";
  if (item.status === "unknown")
    return "Delivery is uncertain. Check Semaphore before taking further action.";
  if (item.display_status === "sent")
    return "Accepted by the mobile network. Handset delivery is not confirmed by Semaphore.";
  if (item.display_status === "delivered") return "Delivery was confirmed by the provider.";
  if (item.display_status === "pending") return "Delivery has not been confirmed.";
  return (
    item.error ||
    (item.display_status === "failed"
      ? "The message could not be sent."
      : "This message was not sent.")
  );
});

function dateLabel(value, withTime = false, withSeconds = false) {
  if (!value) return "--";
  return new Date(value).toLocaleString("en-PH", {
    timeZone: "Asia/Manila",
    month: "short",
    day: "numeric",
    year: "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}),
    ...(withSeconds ? { second: "2-digit" } : {}),
  });
}
function timeLabel(value) {
  return new Date(value).toLocaleTimeString("en-PH", {
    timeZone: "Asia/Manila",
    hour: "numeric",
    minute: "2-digit",
  });
}
function phoneLabel(value) {
  return value?.startsWith("63") ? `+${value}` : value || "No mobile number";
}
async function loadLogs({ reset = false, background = false } = {}) {
  const number = ++requestNumber;
  if (invalidDates.value) {
    loading.value = false;
    return;
  }
  if (reset) page.value = 1;
  if (!background) loading.value = true;
  try {
    const query = new URLSearchParams({ ...filters, page: page.value, page_size: pageSize.value });
    const data = await apiRequest("/api/sms/logs?" + query);
    if (number !== requestNumber || disposed) return;
    result.value = data;
    page.value = data.page;
    if (!data.messages.some((item) => item.id === selectedId.value)) {
      selectedId.value = data.messages[0]?.id || "";
    }
    error.value = "";
  } catch (err) {
    if (number === requestNumber && !disposed) error.value = err.message;
  } finally {
    if (number === requestNumber && !disposed) loading.value = false;
  }
}
function refresh() {
  window.clearTimeout(searchTimer);
  loadLogs();
}
function clearFilters() {
  Object.assign(filters, { q: "", rule: "", status: "", source: "", date_from: "", date_to: "" });
}
function changePage(value) {
  if (value < 1 || value > pages.value || loading.value) return;
  page.value = value;
  refresh();
}
async function selectMessage(item, focus = false) {
  selectedId.value = item.id;
  if (focus) {
    await nextTick();
    detailsPanel.value?.focus({ preventScroll: true });
    detailsPanel.value?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}
function confirmResend(item) {
  if (!item.can_resend) return;
  resendError.value = "";
  resendTarget.value = item;
}
async function resend() {
  if (resending.value || !resendTarget.value) return;
  resending.value = true;
  resendError.value = "";
  try {
    const response = await apiRequest("/api/sms/resend", {
      method: "POST",
      body: { id: resendTarget.value.id },
    });
    resendTarget.value = null;
    showToast(
      response.already_queued
        ? "A resend attempt already exists for this message."
        : "A new SMS attempt has been queued.",
    );
    await loadLogs();
  } catch (err) {
    resendError.value = err.message;
  } finally {
    resending.value = false;
  }
}
watch(
  () => [
    filters.rule,
    filters.status,
    filters.source,
    filters.date_from,
    filters.date_to,
    pageSize.value,
  ],
  () => {
    window.clearTimeout(searchTimer);
    loadLogs({ reset: true });
  },
);
watch(
  () => filters.q,
  () => {
    ++requestNumber;
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => loadLogs({ reset: true }), 300);
  },
);
onMounted(async () => {
  loadLogs();
  refreshTimer = window.setInterval(() => {
    if (!loading.value && !resendTarget.value && !document.hidden) loadLogs({ background: true });
  }, 30000);
  await nextTick();
  root.value?.scrollIntoView({ block: "start" });
});
onBeforeUnmount(() => {
  disposed = true;
  ++requestNumber;
  window.clearTimeout(searchTimer);
  window.clearInterval(refreshTimer);
});
</script>

<template>
  <section ref="root" class="sms-log-page" aria-labelledby="message-log-title">
    <header class="log-page-heading">
      <MessageCircleMore :size="34" />
      <div>
        <h1 id="message-log-title">Message Log</h1>
        <p>SMS activity, delivery status, and message history</p>
      </div>
    </header>

    <div class="log-metrics">
      <article v-for="metric in metrics" :key="metric.label">
        <span class="log-metric-icon" :class="metric.color"
          ><component :is="metric.icon" :size="25"
        /></span>
        <div>
          <h2>{{ metric.label }}</h2>
          <strong>{{ metric.value ?? "--" }}</strong
          ><small>{{ metric.detail }}</small>
        </div>
      </article>
    </div>

    <form class="log-filters" aria-label="Filter SMS messages" @submit.prevent="refresh">
      <label class="log-search"
        >Recipient or mobile number
        <span class="log-search-input"
          ><Search :size="16" /><input
            v-model="filters.q"
            type="search"
            maxlength="120"
            placeholder="Search recipient or number..."
        /></span>
      </label>
      <label
        >Message Type<select v-model="filters.rule">
          <option value="">All Types</option>
          <option v-for="(label, key) in types" :key="key" :value="key">{{ label }}</option>
        </select></label
      >
      <label
        >Delivery Status<select v-model="filters.status">
          <option value="">All Statuses</option>
          <option v-for="(label, key) in statuses" :key="key" :value="key">{{ label }}</option>
        </select></label
      >
      <label
        >Source<select v-model="filters.source">
          <option value="">All Sources</option>
          <option v-for="(label, key) in sources" :key="key" :value="key">{{ label }}</option>
        </select></label
      >
      <fieldset class="log-date-range">
        <legend>Date Range</legend>
        <div>
          <input
            v-model="filters.date_from"
            type="date"
            aria-label="From date"
            :max="filters.date_to || undefined"
          /><span aria-hidden="true">to</span
          ><input
            v-model="filters.date_to"
            type="date"
            aria-label="To date"
            :min="filters.date_from || undefined"
          />
        </div>
      </fieldset>
      <div class="log-filter-actions">
        <button type="button" :disabled="!hasFilters" @click="clearFilters">
          <X :size="15" />Clear</button
        ><button type="submit" class="primary" :disabled="loading || !!invalidDates">
          <RefreshCw :size="15" :class="{ spinning: loading }" />Refresh
        </button>
      </div>
    </form>
    <p v-if="invalidDates" class="log-error" role="alert">
      The start date must be on or before the end date.
    </p>
    <p v-if="error" class="log-error" role="alert">
      {{ error }} <button type="button" @click="refresh">Try again</button>
    </p>

    <div class="log-workspace">
      <section class="log-table-panel" aria-labelledby="log-table-title" :aria-busy="loading">
        <header class="log-panel-heading">
          <CalendarDays :size="23" />
          <div>
            <h2 id="log-table-title">
              Message Log <span>({{ total }} {{ total === 1 ? "message" : "messages" }})</span>
            </h2>
            <p>{{ hasFilters ? "Filtered SMS activity" : "All clinic SMS messages" }}</p>
          </div>
          <span v-if="loading" class="log-updating" role="status">Loading...</span>
        </header>
        <div class="log-table-scroll" tabindex="0" aria-label="SMS message table">
          <table>
            <colgroup>
              <col class="col-date" />
              <col class="col-recipient" />
              <col class="col-phone" />
              <col class="col-type" />
              <col class="col-preview" />
              <col class="col-source" />
              <col class="col-status" />
              <col class="col-actions" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">Date &amp; Time</th>
                <th scope="col">Recipient</th>
                <th scope="col">Mobile Number</th>
                <th scope="col">Message Type</th>
                <th scope="col">Message Preview</th>
                <th scope="col">Source</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in messages"
                :key="item.id"
                :class="{ selected: selectedId === item.id }"
                @click="selectMessage(item)"
              >
                <td>
                  <time :datetime="item.created_at"
                    >{{ dateLabel(item.created_at)
                    }}<small>{{ timeLabel(item.created_at) }}</small></time
                  >
                </td>
                <td class="recipient-cell">
                  {{ item.patient_name }}<small v-if="item.is_test">Test recipient</small>
                </td>
                <td class="phone-cell">{{ phoneLabel(item.phone) }}</td>
                <td>
                  <span class="log-type" :class="item.rule">{{
                    types[item.rule] || item.name
                  }}</span>
                </td>
                <td>
                  <span class="log-preview" :title="item.body">{{ item.body }}</span>
                </td>
                <td>{{ sources[item.source] }}</td>
                <td>
                  <span class="log-status" :class="item.display_status"
                    ><i></i>{{ statuses[item.display_status] }}</span
                  >
                </td>
                <td>
                  <div class="log-row-actions">
                    <button
                      type="button"
                      :aria-label="`View message for ${item.patient_name}`"
                      title="View message"
                      :aria-pressed="selectedId === item.id"
                      @click.stop="selectMessage(item, true)"
                    >
                      <Eye :size="16" /></button
                    ><span :title="item.can_resend ? 'Resend message' : item.resend_reason"
                      ><button
                        type="button"
                        :disabled="!item.can_resend"
                        :aria-label="`Resend message to ${item.patient_name}`"
                        @click.stop="confirmResend(item)"
                      >
                        <Send :size="15" /></button
                    ></span>
                  </div>
                </td>
              </tr>
              <tr v-if="!messages.length">
                <td colspan="8" class="log-empty">
                  <MessageCircleMore :size="34" /><strong>{{
                    loading
                      ? "Loading messages..."
                      : error
                        ? "Messages unavailable"
                        : "No messages found"
                  }}</strong>
                  <p>
                    {{
                      loading
                        ? ""
                        : error
                          ? "Refresh to try again."
                          : hasFilters
                            ? "No SMS messages match these filters."
                            : "There is no recorded SMS activity yet."
                    }}
                  </p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="log-pagination">
          <p aria-live="polite">Showing {{ firstRow }} to {{ lastRow }} of {{ total }} messages</p>
          <nav aria-label="Message log pages">
            <button
              type="button"
              :disabled="page <= 1 || loading"
              title="Previous page"
              aria-label="Previous page"
              @click="changePage(page - 1)"
            >
              <ChevronLeft :size="17" /></button
            ><template v-for="link in pageLinks" :key="link"
              ><span v-if="typeof link === 'string'" class="page-gap">...</span
              ><button
                v-else
                type="button"
                :class="{ current: link === page }"
                :aria-current="link === page ? 'page' : undefined"
                :aria-label="`Page ${link}`"
                :disabled="loading"
                @click="changePage(link)"
              >
                {{ link }}
              </button></template
            ><button
              type="button"
              :disabled="page >= pages || loading"
              title="Next page"
              aria-label="Next page"
              @click="changePage(page + 1)"
            >
              <ChevronRight :size="17" />
            </button>
          </nav>
          <label
            >Rows per page<select v-model.number="pageSize">
              <option :value="10">10</option>
              <option :value="25">25</option>
              <option :value="50">50</option>
            </select></label
          >
        </footer>
      </section>

      <aside
        ref="detailsPanel"
        class="log-details"
        tabindex="-1"
        aria-labelledby="message-details-title"
      >
        <header class="log-panel-heading">
          <FileText :size="23" />
          <div>
            <h2 id="message-details-title">Selected Message Details</h2>
            <p>Recipient, content, and delivery activity</p>
          </div>
        </header>
        <template v-if="selected">
          <div class="log-detail-body">
            <div class="log-message-meta">
              <span class="log-status" :class="selected.display_status"
                ><i></i>{{ statuses[selected.display_status] }}</span
              ><small>Message ID: {{ selected.id }}</small>
            </div>
            <dl class="log-detail-fields">
              <div>
                <dt><UserRound :size="14" />Recipient</dt>
                <dd>{{ selected.patient_name }}</dd>
              </div>
              <div>
                <dt><Smartphone :size="14" />Mobile Number</dt>
                <dd>{{ phoneLabel(selected.phone) }}</dd>
              </div>
              <div>
                <dt><MessageCircleMore :size="14" />Message Type</dt>
                <dd>
                  <span class="log-type" :class="selected.rule">{{ types[selected.rule] }}</span>
                </dd>
              </div>
              <div>
                <dt><Workflow :size="14" />Trigger Source</dt>
                <dd>
                  {{ sources[selected.source]
                  }}<small>{{
                    selected.is_test
                      ? "Admin test message"
                      : selected.resend_of
                        ? "Retry of " + selected.resend_of
                        : selected.trigger
                  }}</small>
                </dd>
              </div>
              <div>
                <dt><Clock3 :size="14" />Date &amp; Time</dt>
                <dd>{{ dateLabel(selected.created_at, true) }}</dd>
              </div>
            </dl>
            <div class="log-content-heading">
              <h3>Message Content</h3>
              <span>{{ selected.body.length }} characters</span>
            </div>
            <div class="log-message-content">{{ selected.body }}</div>
            <section class="log-timeline" aria-labelledby="delivery-timeline-title">
              <h3 id="delivery-timeline-title"><Clock3 :size="16" />Delivery Timeline</h3>
              <ol>
                <li v-for="(event, index) in timeline" :key="index" :class="event.state">
                  <span>{{ event.label }}</span
                  ><time :datetime="event.at">{{ dateLabel(event.at, true, true) }}</time>
                </li>
              </ol>
              <p class="log-delivery-note"><Info :size="15" />{{ deliveryNote }}</p>
              <p v-if="selected.resend_id" class="log-resend-reference">
                New attempt: {{ selected.resend_id }}
              </p>
            </section>
          </div>
          <footer class="log-detail-footer">
            <button
              type="button"
              :disabled="!selected.can_resend"
              :title="selected.resend_reason || 'Resend message'"
              @click="confirmResend(selected)"
            >
              <Send :size="16" />Resend Message
            </button>
            <p v-if="selected.display_status === 'failed' && selected.resend_reason">
              {{ selected.resend_reason }}
            </p>
          </footer>
        </template>
        <div v-else class="log-details-empty">
          <FileText :size="38" /><strong>No message selected</strong>
          <p>Message details will appear here.</p>
        </div>
      </aside>
    </div>

    <BaseModal
      v-if="resendTarget"
      title="Resend Message"
      eyebrow="SMS MESSAGE"
      @close="!resending && (resendTarget = null)"
    >
      <div class="log-resend-confirm">
        <p>
          Queue a new SMS attempt for <strong>{{ resendTarget.patient_name }}</strong
          >?
        </p>
        <p>
          {{
            resendTarget.is_test
              ? "The original test number and message will be used."
              : "The current mobile number and active template will be used."
          }}
          The original message stays in the log. SMS charges may apply.
        </p>
        <p v-if="resendError" class="log-error" role="alert">{{ resendError }}</p>
        <footer>
          <button type="button" :disabled="resending" @click="resendTarget = null">Cancel</button
          ><button type="button" class="primary" :disabled="resending" @click="resend">
            <Send :size="16" />{{ resending ? "Queuing..." : "Confirm Resend" }}
          </button>
        </footer>
      </div>
    </BaseModal>
  </section>
</template>

<style scoped>
.sms-log-page {
  color: var(--dashboard-text, #132d50);
  scroll-margin-top: 180px;
  letter-spacing: 0;
}
.sms-log-page *,
.log-resend-confirm * {
  box-sizing: border-box;
}
.sms-log-page svg {
  flex-shrink: 0;
}
.log-page-heading {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
}
.log-page-heading > svg,
.log-panel-heading > svg {
  color: #0876ef;
}
.log-page-heading h1 {
  font-size: 25px;
  line-height: 1.25;
  margin: 0;
}
.log-page-heading p {
  font-size: 12px;
  color: var(--dashboard-muted, #627da1);
  margin: 5px 0 0;
}
.log-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.log-metrics article {
  display: flex;
  align-items: center;
  gap: 13px;
  min-width: 0;
  padding: 17px 14px;
  border: 1px solid var(--dashboard-border, #dbe6f2);
  border-radius: 6px;
  background: var(--surface, #fff);
}
.log-metrics article > div {
  min-width: 0;
}
.log-metrics h2 {
  font-size: 11px;
  line-height: 1.4;
  margin: 0;
  font-weight: 600;
}
.log-metrics strong {
  display: block;
  font-size: 26px;
  line-height: 1.15;
  margin: 3px 0;
}
.log-metrics small {
  display: block;
  font-size: 10px;
  color: var(--dashboard-muted, #627da1);
  line-height: 1.5;
}
.log-metric-icon {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 8px;
  flex-shrink: 0;
}
.blue {
  background: #e7f3ff;
  color: #0876ef;
}
.green {
  background: #e6f8ef;
  color: #0baf75;
}
.red {
  background: #fff0f3;
  color: #ec4267;
}
.amber {
  background: #fff3e4;
  color: #e18b13;
}
.violet {
  background: #f1eaff;
  color: #8851e1;
}
.log-filters {
  display: grid;
  grid-template-columns:
    minmax(180px, 1.35fr) repeat(3, minmax(115px, 0.8fr)) minmax(246px, 1.6fr)
    auto;
  gap: 12px;
  align-items: end;
  padding: 15px 0;
  margin-bottom: 16px;
  border-block: 1px solid var(--dashboard-border, #dbe6f2);
}
.log-filters label {
  display: grid;
  gap: 6px;
  min-width: 0;
  color: var(--dashboard-muted, #627da1);
  font-size: 11px;
}
.sms-log-page input,
.sms-log-page select {
  font-family: inherit;
  font-size: 12px;
  font-weight: 400;
  letter-spacing: 0;
  color: var(--dashboard-text, #132d50);
  background: var(--surface, #fff);
  border: 1px solid var(--dashboard-border, #dbe6f2);
  border-radius: 5px;
  height: 37px;
  width: 100%;
  min-width: 0;
  padding: 7px 9px;
  box-shadow: none;
}
.sms-log-page select {
  padding-right: 23px;
}
.sms-log-page button,
.log-resend-confirm button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 37px;
  padding: 7px 12px;
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0;
  line-height: 1.25;
  color: #0876ef;
  border: 1px solid var(--dashboard-border, #dbe6f2);
  border-radius: 5px;
  background: var(--surface, #fff);
  box-shadow: none;
  cursor: pointer;
  white-space: nowrap;
}
.sms-log-page button:hover:not(:disabled),
.log-resend-confirm button:hover:not(:disabled) {
  background: #eff6ff;
  border-color: #93bbff;
}
.sms-log-page button:disabled,
.log-resend-confirm button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.sms-log-page button.primary,
.log-resend-confirm button.primary {
  background: #0876ef;
  border-color: #0876ef;
  color: #fff;
}
.sms-log-page button.primary:hover:not(:disabled),
.log-resend-confirm button.primary:hover:not(:disabled) {
  background: #0862c4;
}
.sms-log-page :is(button, input, select):focus-visible,
.log-details:focus-visible,
.log-table-scroll:focus-visible {
  outline: 2px solid #0876ef;
  outline-offset: 2px;
}
.log-search-input {
  position: relative;
  display: block;
}
.log-search-input svg {
  position: absolute;
  left: 10px;
  top: 11px;
  color: #0876ef;
}
.log-search-input input {
  padding-left: 33px;
}
.log-date-range {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
.log-date-range legend {
  font-size: 11px;
  color: var(--dashboard-muted, #627da1);
  padding: 0;
  margin-bottom: 6px;
}
.log-date-range > div {
  display: flex;
  align-items: center;
  gap: 5px;
}
.log-date-range span {
  font-size: 10px;
  color: var(--dashboard-muted, #627da1);
}
.log-date-range input {
  font-size: 11px;
  padding-inline: 5px;
}
.log-filter-actions {
  display: flex;
  gap: 7px;
}
.log-filter-actions button {
  padding-inline: 10px;
}
.log-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 310px;
  align-items: start;
  gap: 16px;
}
.log-table-panel,
.log-details {
  min-width: 0;
  background: var(--surface, #fff);
  border: 1px solid var(--dashboard-border, #dbe6f2);
  border-radius: 6px;
  overflow: hidden;
}
.log-panel-heading {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 16px;
  min-width: 0;
}
.log-panel-heading h2 {
  font-size: 15px;
  line-height: 1.4;
  margin: 0;
}
.log-panel-heading h2 span {
  font-size: 11px;
  font-weight: 500;
  color: var(--dashboard-muted, #627da1);
}
.log-panel-heading p {
  margin: 3px 0 0;
  font-size: 10px;
  color: var(--dashboard-muted, #627da1);
}
.log-updating {
  margin-left: auto;
  font-size: 11px;
  color: var(--dashboard-muted, #627da1);
}
.log-table-scroll {
  width: 100%;
  overflow: auto;
}
.sms-log-page table {
  table-layout: fixed;
  width: 100%;
  min-width: 850px;
  border-collapse: collapse;
}
.sms-log-page th {
  text-align: left;
  background: #eff5fb;
  color: #557294;
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  line-height: 1.4;
  padding: 10px 8px;
  border-block: 1px solid var(--dashboard-border, #dbe6f2);
}
.sms-log-page td {
  font-size: 11px;
  line-height: 1.45;
  padding: 11px 8px;
  border-bottom: 1px solid var(--dashboard-border, #dbe6f2);
  overflow-wrap: anywhere;
}
.sms-log-page td + td,
.sms-log-page th + th {
  border-left: 1px solid var(--dashboard-border, #dbe6f2);
}
.sms-log-page tbody tr:not(:has(.log-empty)) {
  cursor: pointer;
}
.sms-log-page tbody tr.selected {
  background: #edf6ff;
}
.sms-log-page tbody tr:hover:not(.selected):not(:has(.log-empty)) {
  background: #f7fbff;
}
.col-date {
  width: 12%;
}
.col-recipient {
  width: 13%;
}
.col-phone {
  width: 13%;
}
.col-type {
  width: 15%;
}
.col-preview {
  width: 17%;
}
.col-source {
  width: 10%;
}
.col-status {
  width: 11%;
}
.col-actions {
  width: 9%;
}
.sms-log-page td small {
  display: block;
  font-size: 10px;
  color: var(--dashboard-muted, #627da1);
  margin-top: 2px;
}
.recipient-cell {
  font-weight: 500;
}
.phone-cell {
  font-variant-numeric: tabular-nums;
}
.log-type {
  display: inline-block;
  font-size: 10px;
  font-weight: 500;
  line-height: 1.45;
  padding: 3px 5px;
  border-radius: 4px;
  overflow-wrap: anywhere;
}
.booking {
  color: #0671d7;
  background: #e0f0ff;
}
.approval {
  color: #07865c;
  background: #dff7ee;
}
.walk_in {
  color: #7841c7;
  background: #f1e6ff;
}
.next_visit {
  color: #b06217;
  background: #fff0df;
}
.balance {
  color: #b03777;
  background: #ffe8f2;
}
.cancellation {
  color: #c73b54;
  background: #ffe8ed;
}
.log-preview {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-weight: 400;
}
.log-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  white-space: nowrap;
  line-height: 1.5;
}
.log-status i {
  height: 6px;
  width: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
  background: currentColor;
}
.log-status.delivered {
  color: #009868;
}
.log-status.sent {
  color: #08769d;
}
.log-status.pending {
  color: #086ee6;
}
.log-status.failed {
  color: #d63251;
}
.log-status.not_sent {
  color: #778195;
}
.log-row-actions {
  display: flex;
  justify-content: center;
  gap: 2px;
}
.log-row-actions button {
  min-height: 28px;
  height: 28px;
  width: 28px;
  padding: 0;
  border: 0;
  background: transparent;
}
.log-row-actions > span {
  display: inline-flex;
}
.sms-log-page td.log-empty {
  height: 300px;
  text-align: center;
  padding: 35px;
  color: var(--dashboard-muted, #627da1);
}
.log-empty svg {
  display: block;
  margin: 0 auto 12px;
  color: #9abde3;
}
.log-empty strong {
  font-size: 14px;
}
.log-empty p {
  font-size: 12px;
}
.log-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 15px;
  padding: 16px;
}
.log-pagination p {
  font-size: 10px;
  margin: 0;
  color: var(--dashboard-muted, #627da1);
}
.log-pagination nav {
  display: flex;
  align-items: center;
  gap: 4px;
}
.log-pagination nav button {
  width: 28px;
  min-height: 29px;
  padding: 4px;
  font-size: 11px;
}
.log-pagination nav button.current {
  background: #0876ef;
  border-color: #0876ef;
  color: white;
}
.page-gap {
  font-size: 11px;
  padding: 3px;
}
.log-pagination label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: var(--dashboard-muted, #627da1);
}
.log-pagination select {
  width: 55px;
  height: 30px;
  font-size: 11px;
  padding: 4px 6px;
}
.log-details {
  scroll-margin-top: 175px;
}
.log-details .log-panel-heading {
  padding: 16px 13px 13px;
  gap: 9px;
}
.log-details h2 {
  font-size: 13px;
}
.log-detail-body {
  padding: 0 14px 14px;
}
.log-message-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 0 0 17px;
}
.log-message-meta .log-status {
  background: #f0f7fc;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 10px;
}
.log-message-meta small {
  font-size: 9px;
  color: var(--dashboard-muted, #627da1);
  overflow-wrap: anywhere;
}
.log-detail-fields {
  margin: 0 0 22px;
  display: grid;
  gap: 10px;
}
.log-detail-fields > div {
  display: grid;
  grid-template-columns: 102px minmax(0, 1fr);
  gap: 8px;
}
.log-detail-fields dt {
  display: flex;
  gap: 6px;
  align-items: start;
  font-size: 10px;
  color: var(--dashboard-muted, #627da1);
}
.log-detail-fields dt svg {
  color: #0876ef;
}
.log-detail-fields dd {
  margin: 0;
  font-size: 10px;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.log-detail-fields dd small {
  display: block;
  font-size: 9px;
  line-height: 1.5;
  font-weight: 400;
  margin-top: 3px;
  color: var(--dashboard-muted, #627da1);
}
.log-detail-body h3 {
  font-size: 11px;
  margin: 0;
}
.log-content-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.log-content-heading > span {
  font-size: 9px;
  color: var(--dashboard-muted, #627da1);
}
.log-message-content {
  padding: 12px;
  border: 1px solid var(--dashboard-border, #dbe6f2);
  border-radius: 5px;
  background: #f3f8fe;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 11px;
  line-height: 1.65;
}
.log-timeline {
  margin-top: 19px;
}
.log-timeline h3 {
  display: flex;
  gap: 6px;
  align-items: center;
}
.log-timeline h3 svg {
  color: #0876ef;
}
.log-timeline ol {
  list-style: none;
  padding: 0 0 0 5px;
  margin: 12px 0;
}
.log-timeline li {
  display: grid;
  gap: 3px;
  position: relative;
  padding: 0 0 13px 14px;
  border-left: 1px solid #cee3f6;
  font-size: 10px;
}
.log-timeline li:last-child {
  padding-bottom: 0;
  border-left-color: transparent;
}
.log-timeline li::before {
  content: "";
  position: absolute;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #0fb47e;
  top: 3px;
  left: -4px;
}
.log-timeline li.pending::before {
  background: #0876ef;
}
.log-timeline li.failed::before {
  background: #e24466;
}
.log-timeline time {
  color: var(--dashboard-muted, #627da1);
  font-size: 9px;
}
.log-delivery-note {
  display: flex;
  align-items: start;
  gap: 6px;
  margin: 12px 0 0;
  font-size: 10px;
  line-height: 1.5;
  color: var(--dashboard-muted, #627da1);
}
.log-delivery-note svg {
  margin-top: 1px;
}
.log-resend-reference {
  font-size: 10px;
  overflow-wrap: anywhere;
  color: var(--dashboard-muted, #627da1);
}
.log-detail-footer {
  padding: 12px 14px;
  border-top: 1px solid var(--dashboard-border, #dbe6f2);
}
.log-detail-footer button {
  width: 100%;
}
.log-detail-footer p {
  font-size: 10px;
  line-height: 1.5;
  color: var(--dashboard-muted, #627da1);
  margin: 9px 0 0;
}
.log-details-empty {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 10px;
  min-height: 310px;
  padding: 22px;
  text-align: center;
  color: var(--dashboard-muted, #627da1);
}
.log-details-empty svg {
  color: #9abde3;
}
.log-details-empty strong {
  font-size: 13px;
}
.log-details-empty p {
  font-size: 11px;
  margin: 0;
}
.log-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: #fff0f3;
  color: #b42e48;
  padding: 12px;
  border-radius: 5px;
  font-size: 12px;
  margin: 0 0 15px;
}
.log-resend-confirm {
  padding: 22px;
  color: var(--dashboard-text, #132d50);
  font-size: 14px;
  line-height: 1.6;
}
.log-resend-confirm p {
  overflow-wrap: anywhere;
}
.log-resend-confirm footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid var(--dashboard-border, #dbe6f2);
  padding-top: 16px;
  margin-top: 20px;
}
.spinning {
  animation: log-spin 1s linear infinite;
}
@keyframes log-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (min-width: 1750px) {
  .log-workspace {
    grid-template-columns: minmax(0, 1fr) 360px;
  }
  .sms-log-page td {
    font-size: 12px;
  }
  .sms-log-page th {
    font-size: 10px;
  }
  .log-detail-fields dd,
  .log-detail-fields dt,
  .log-message-content {
    font-size: 12px;
  }
}
@media (max-width: 1500px) {
  .log-filters {
    grid-template-columns: minmax(180px, 1.2fr) repeat(3, minmax(120px, 1fr));
  }
  .log-date-range {
    grid-column: span 2;
  }
  .log-filter-actions {
    grid-column: span 2;
    justify-content: flex-end;
  }
  .log-metrics article {
    gap: 9px;
    padding: 13px 10px;
  }
  .log-metric-icon {
    width: 36px;
    height: 40px;
  }
  .log-metrics strong {
    font-size: 23px;
  }
}
@media (max-width: 1100px) {
  .log-workspace {
    grid-template-columns: minmax(0, 1fr);
  }
  .log-detail-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 24px;
  }
  .log-message-meta {
    grid-column: 1/-1;
  }
  .log-detail-fields {
    grid-column: 1;
    grid-row: 2/5;
  }
  .log-content-heading,
  .log-message-content,
  .log-timeline {
    grid-column: 2;
  }
  .log-details-empty {
    min-height: 170px;
  }
  .log-detail-footer button {
    width: auto;
  }
}
@media (max-width: 750px) {
  .log-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .log-metrics article:last-child {
    grid-column: 1/-1;
  }
  .log-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .log-search {
    grid-column: 1/-1;
  }
  .log-date-range {
    grid-column: 1/-1;
  }
  .log-filter-actions {
    grid-column: 1/-1;
  }
  .log-filters > label:nth-child(4) {
    grid-column: 1/-1;
  }
  .log-filter-actions button {
    flex: 1;
  }
  .log-detail-body {
    display: block;
  }
  .log-page-heading h1 {
    font-size: 22px;
  }
  .log-page-heading p {
    line-height: 1.5;
  }
  .log-pagination {
    gap: 12px;
    padding: 13px;
  }
  .log-pagination > p {
    flex-basis: 100%;
  }
  .log-detail-footer button {
    width: 100%;
  }
  .log-detail-fields > div {
    grid-template-columns: 115px minmax(0, 1fr);
  }
  .log-error {
    align-items: start;
  }
}
@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
html[data-dashboard-theme="dark"] .sms-log-page th,
html[data-dashboard-theme="dark"] .log-message-content {
  background: #202c3c;
  color: #a5c5ec;
}
html[data-dashboard-theme="dark"] .log-message-meta .log-status {
  background: #202c3c;
}
html[data-dashboard-theme="dark"] .log-status.delivered {
  color: #58ddb0;
}
html[data-dashboard-theme="dark"] .log-status.sent {
  color: #74d6ed;
}
html[data-dashboard-theme="dark"] .log-status.pending {
  color: #85b9ff;
}
html[data-dashboard-theme="dark"] .log-status.failed {
  color: #ff9eb0;
}
html[data-dashboard-theme="dark"] .log-status.not_sent {
  color: #b7c5d6;
}
html[data-dashboard-theme="dark"] .sms-log-page tbody tr.selected {
  background: #203953;
}
html[data-dashboard-theme="dark"] .sms-log-page tbody tr:hover:not(.selected):not(:has(.log-empty)),
html[data-dashboard-theme="dark"] .sms-log-page button:hover:not(:disabled):not(.primary) {
  background: #28384b;
}
</style>
