<script setup>
import { ClipboardList, RefreshCw } from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";

import { apiRequest } from "../../services/api";

const eventOptions = [
  { value: "", label: "All activities" },
  { value: "LOGIN_SUCCESS", label: "Login succeeded" },
  { value: "LOGIN_FAILED", label: "Login failed" },
  { value: "LOGOUT", label: "Logged out" },
  { value: "PASSWORD_CHANGED", label: "Password changed" },
  { value: "ACCOUNT_LOCKED", label: "Account locked" },
  { value: "ACCOUNT_DISABLED", label: "Account disabled" },
  { value: "ACCOUNT_ENABLED", label: "Account enabled" },
  { value: "PATIENT_CREATED", label: "Patient record created" },
  { value: "PATIENT_UPDATED", label: "Patient record updated" },
  { value: "PATIENT_DELETED", label: "Patient record deleted" },
  { value: "TREATMENT_CREATED", label: "Treatment record created" },
  { value: "TREATMENT_UPDATED", label: "Treatment record updated" },
  { value: "TREATMENT_DELETED", label: "Treatment record deleted" },
  { value: "APPOINTMENT_CANCELLED", label: "Appointment cancelled" },
  { value: "SMS_SENT", label: "SMS accepted by gateway" },
];

const eventFilter = ref("");
const events = ref([]);
const page = ref(1);
const pageSize = ref(25);
const total = ref(0);
const loading = ref(false);
const loaded = ref(false);
const error = ref("");
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
let latestRequest = 0;

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

async function loadActivity() {
  const requestId = ++latestRequest;
  loading.value = true;
  error.value = "";
  try {
    const params = new URLSearchParams({ page: String(page.value) });
    if (eventFilter.value) params.set("event", eventFilter.value);
    const data = await apiRequest(`/api/account/activity-log?${params}`);
    if (requestId !== latestRequest) return;
    events.value = Array.isArray(data.events) ? data.events : [];
    total.value = Number(data.total || 0);
    pageSize.value = Number(data.page_size || 25);
    loaded.value = true;
  } catch (cause) {
    if (requestId !== latestRequest) return;
    error.value = cause.message || "Could not load activity.";
  } finally {
    if (requestId === latestRequest) loading.value = false;
  }
}

function changePage(nextPage) {
  if (nextPage < 1 || nextPage > pageCount.value || loading.value) return;
  page.value = nextPage;
  loadActivity();
}

watch(eventFilter, () => {
  page.value = 1;
  events.value = [];
  total.value = 0;
  loaded.value = false;
  loadActivity();
});
onMounted(loadActivity);
</script>

<template>
  <section class="account-panel activity-log" aria-labelledby="activity-log-title">
    <header class="account-panel-heading">
      <div class="account-heading-icon blue"><ClipboardList :size="19" aria-hidden="true" /></div>
      <div>
        <h2 id="activity-log-title">Activity Log</h2>
        <p>Recent account, patient, treatment, appointment, and SMS activity.</p>
      </div>
      <button type="button" class="activity-refresh" :disabled="loading" @click="loadActivity">
        <RefreshCw :size="16" aria-hidden="true" /> Refresh
      </button>
    </header>

    <div class="activity-controls">
      <div class="activity-filter">
        <label for="activity-event-filter">Activity type</label>
        <select id="activity-event-filter" v-model="eventFilter" :disabled="loading">
          <option v-for="option in eventOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>
      <span v-if="loaded" class="activity-count"
        >{{ total }} {{ total === 1 ? "event" : "events" }}</span
      >
    </div>

    <p v-if="error" class="activity-message activity-error" role="alert">
      {{ error }} <button type="button" @click="loadActivity">Try again</button>
    </p>
    <p v-else-if="loading && !loaded" class="activity-message" role="status">Loading activity...</p>
    <div v-else-if="events.length" class="activity-table-wrap">
      <table class="activity-table">
        <thead>
          <tr>
            <th scope="col">Date &amp; Time</th>
            <th scope="col">User</th>
            <th scope="col">Activity</th>
            <th scope="col">Record</th>
            <th scope="col">Result</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in events" :key="entry.id">
            <td>
              <time :datetime="entry.created_at">{{ formatDateTime(entry.created_at) }}</time>
            </td>
            <td data-label="User">
              <span class="activity-identity"
                >{{ entry.actor }}
                <small v-if="entry.actor_id">{{ entry.actor_id }}</small>
              </span>
            </td>
            <td>{{ entry.activity }}</td>
            <td data-label="Record">
              <span v-if="entry.target_id" class="activity-identity"
                >{{ entry.target_type }}
                <small>{{ entry.target_id }}</small>
              </span>
              <span v-else>—</span>
            </td>
            <td>
              <span class="activity-result" :class="entry.result">{{
                entry.result === "failed" ? "Failed" : "Success"
              }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="activity-message">No activity has been recorded for this filter.</p>

    <footer v-if="total > pageSize" class="activity-pagination">
      <span>Page {{ page }} of {{ pageCount }}</span>
      <div>
        <button type="button" :disabled="page <= 1 || loading" @click="changePage(page - 1)">
          Previous
        </button>
        <button
          type="button"
          :disabled="page >= pageCount || loading"
          @click="changePage(page + 1)"
        >
          Next
        </button>
      </div>
    </footer>
  </section>
</template>

<style scoped>
.activity-log {
  min-width: 0;
}
.activity-log .account-panel-heading {
  margin-bottom: 0.75rem;
}
.activity-refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  margin-left: auto;
  padding: 0.42rem 0.7rem;
  border: 1px solid var(--dashboard-border);
  border-radius: 0.5rem;
  background: var(--dashboard-surface);
  color: var(--dashboard-text);
  font-size: 0.78rem;
  white-space: nowrap;
  cursor: pointer;
}
.activity-refresh:disabled {
  cursor: wait;
  opacity: 0.6;
}
.activity-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.65rem;
  color: var(--dashboard-muted);
  font-size: 0.78rem;
}
.activity-filter {
  display: flex;
  flex: 0 1 21rem;
  align-items: center;
  gap: 0.55rem;
  min-width: 0;
}
.activity-filter label {
  flex: none;
  white-space: nowrap;
}
.activity-controls select {
  flex: 1 1 11rem;
  width: auto;
  min-width: 0;
  max-width: 14rem;
  min-height: 2.1rem;
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--dashboard-border);
  border-radius: 0.5rem;
  background: var(--dashboard-surface);
  color: var(--dashboard-text);
  font-size: 0.78rem;
}
.activity-count {
  margin-left: auto;
  white-space: nowrap;
}
.activity-table-wrap {
  max-width: 100%;
  overflow-x: auto;
}
.activity-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 35rem;
  text-align: left;
}
.activity-table th,
.activity-table td {
  padding: 0.5rem 0.45rem;
  border-bottom: 1px solid var(--dashboard-border);
  font-size: 0.78rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.activity-table th {
  color: var(--dashboard-muted);
  font-weight: 600;
}
.activity-table td {
  color: var(--dashboard-text);
}
.activity-identity {
  display: flex;
  flex-direction: column;
  gap: 0.05rem;
  text-transform: capitalize;
}
.activity-identity small {
  color: var(--dashboard-muted);
  font-size: 0.72rem;
  overflow-wrap: anywhere;
  text-transform: none;
}
.activity-result {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: #f4e7cd;
  color: #8a6526;
  font-size: 0.8rem;
  font-weight: 600;
}
.activity-result.failed {
  background: #fee2e2;
  color: #991b1b;
}
.activity-message {
  margin: 0;
  padding: 0.45rem 0 0.15rem;
  color: var(--dashboard-muted);
  font-size: 0.78rem;
}
.activity-error {
  color: #b91c1c;
}
.activity-error button {
  border: 0;
  background: none;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}
.activity-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding-top: 0.75rem;
  color: var(--dashboard-muted);
  font-size: 0.875rem;
}
.activity-pagination div {
  display: flex;
  gap: 0.5rem;
}
.activity-pagination button {
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--dashboard-border);
  border-radius: 0.4rem;
  background: var(--dashboard-surface);
  color: var(--dashboard-text);
  cursor: pointer;
}
.activity-pagination button:disabled {
  opacity: 0.5;
  cursor: default;
}
:global(html[data-dashboard-theme="dark"]) .activity-result {
  background: #241e17;
  color: #e3c985;
}
:global(html[data-dashboard-theme="dark"]) .activity-result.failed {
  background: #28241e;
  color: #fca5a5;
}
@media (max-width: 980px) {
  .activity-log .account-panel-heading {
    grid-template-columns: auto minmax(0, 1fr) auto;
  }
  .activity-log .account-panel-heading > .activity-refresh {
    grid-column: auto;
    justify-self: end;
  }
}
@media (max-width: 620px) {
  .activity-count {
    font-size: 0.72rem;
  }
  .activity-table {
    display: block;
    min-width: 0;
  }
  .activity-table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }
  .activity-table tbody {
    display: grid;
    gap: 0.5rem;
  }
  .activity-table tr {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.35rem 0.75rem;
    padding: 0.65rem;
    border: 1px solid var(--dashboard-border);
    border-radius: 0.5rem;
  }
  .activity-table td {
    padding: 0;
    border: 0;
  }
  .activity-table td:first-child {
    grid-column: 1;
    grid-row: 1;
    color: var(--dashboard-muted);
    font-size: 0.72rem;
  }
  .activity-table td:nth-child(2) {
    grid-column: 1;
    grid-row: 3;
  }
  .activity-table td:nth-child(3) {
    grid-column: 1 / -1;
    grid-row: 2;
    font-weight: 600;
  }
  .activity-table td:nth-child(4) {
    grid-column: 2;
    grid-row: 3;
  }
  .activity-table td:last-child {
    grid-column: 2;
    grid-row: 1;
    justify-self: end;
  }
  .activity-table td[data-label]::before {
    display: block;
    margin-bottom: 0.1rem;
    color: var(--dashboard-muted);
    content: attr(data-label);
    font-size: 0.7rem;
  }
  .activity-pagination {
    flex-wrap: wrap;
  }
}
</style>
