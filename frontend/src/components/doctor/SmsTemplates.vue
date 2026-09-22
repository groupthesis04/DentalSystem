<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import {
  BatteryFull,
  Braces,
  CalendarDays,
  CalendarPlus,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Copy,
  Eye,
  FileText,
  MessageCircleMore,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Settings2,
  Signal,
  Trash2,
  UserRoundPlus,
  Wallet,
  Wifi,
  XCircle,
} from "lucide-vue-next";
import BaseModal from "../BaseModal.vue";
import { apiRequest } from "../../services/api";
import { showToast } from "../../services/toast";

const props = defineProps({
  initialRule: { type: String, default: "booking" },
  rules: { type: Array, default: () => [] },
});
const emit = defineEmits(["changed", "select-panel"]);
const templates = ref([]);
const placeholders = ref([]);
const clinicName = ref("BORJA Dental Clinic");
const selectedId = ref("");
const filter = ref("all");
const drafts = ref({});
const loading = ref(true);
const busy = ref(false);
const error = ref("");
const editor = ref(null);
const editorError = ref("");
const deleteTarget = ref(null);
const deleteError = ref("");
const editorInput = ref(null);
const previewSection = ref(null);
const pageRoot = ref(null);
const icons = {
  booking: CalendarDays,
  approval: CheckCircle2,
  walk_in: UserRoundPlus,
  next_visit: CalendarPlus,
  balance: Wallet,
  cancellation: XCircle,
};
const delays = [0, 5, 15, 30, 60];
const selected = computed(() => templates.value.find((item) => item.id === selectedId.value));
const working = computed(() => drafts.value[selectedId.value]);
const activeCount = computed(() => templates.value.filter((item) => item.enabled).length);
const activePercent = computed(() =>
  templates.value.length ? Math.round((activeCount.value * 100) / templates.value.length) : 0,
);
const latestUpdate = computed(() =>
  templates.value.reduce(
    (latest, item) => (item.updated_at > latest ? item.updated_at : latest),
    "",
  ),
);
const visibleTemplates = computed(() =>
  templates.value.filter(
    (item) => filter.value === "all" || (filter.value === "active" ? item.enabled : !item.enabled),
  ),
);
const dirty = computed(
  () =>
    selected.value &&
    working.value &&
    ["name", "body", "enabled", "delay_minutes"].some(
      (key) => selected.value[key] !== working.value[key],
    ),
);
const sample = computed(() => ({
  PatientName: "Juan",
  ClinicName: clinicName.value,
  AppointmentDate: new Date().toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }),
  Time: "10:00 AM",
  Balance: "500.00",
}));
const preview = computed(() =>
  (working.value?.body || "").replace(/\{(\w+)\}/g, (match, key) => sample.value[key] ?? match),
);
const characterCount = computed(() => Array.from(preview.value).length);
const capacityPercent = computed(() => Math.min(100, (characterCount.value / 1000) * 100));

function dateLabel(value, time = false) {
  return value
    ? new Date(value).toLocaleString(
        "en-US",
        time
          ? { hour: "numeric", minute: "2-digit" }
          : { month: "short", day: "numeric", year: "numeric" },
      )
    : "--";
}
function variables(body) {
  return [...new Set([...body.matchAll(/\{(\w+)\}/g)].map((match) => match[1]))];
}
function selectTemplate(id, scroll = false) {
  selectedId.value = id;
  if (!drafts.value[id]) drafts.value[id] = { ...templates.value.find((item) => item.id === id) };
  if (scroll)
    nextTick(() => previewSection.value?.scrollIntoView({ behavior: "smooth", block: "nearest" }));
}
async function load(preferredId = selectedId.value) {
  const result = await apiRequest("/api/sms/templates");
  const order = Object.keys(icons);
  templates.value = result.templates.sort((a, b) => order.indexOf(a.rule) - order.indexOf(b.rule));
  placeholders.value = result.placeholders;
  clinicName.value = result.clinic_name;
  const first =
    templates.value.find((item) => item.rule === props.initialRule && item.enabled) ||
    templates.value.find((item) => item.rule === props.initialRule) ||
    templates.value[0];
  selectTemplate(templates.value.some((item) => item.id === preferredId) ? preferredId : first?.id);
}
async function initialize() {
  loading.value = true;
  error.value = "";
  try {
    await load();
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}
function reset() {
  drafts.value[selectedId.value] = { ...selected.value };
  error.value = "";
}
async function persist(payload, create = false) {
  busy.value = true;
  error.value = "";
  editorError.value = "";
  try {
    const result = await apiRequest("/api/sms/templates", {
      method: create ? "POST" : "PATCH",
      body: payload,
    });
    delete drafts.value[result.template.id];
    await load(result.template.id);
    // Activation can deactivate another template for the same automation.
    for (const item of templates.value) {
      if (item.rule === result.template.rule && drafts.value[item.id])
        drafts.value[item.id].enabled = item.enabled;
    }
    emit("changed");
    showToast(create ? "Template created." : "Template saved.");
    return true;
  } catch (err) {
    if (editor.value) editorError.value = err.message;
    else error.value = err.message;
    return false;
  } finally {
    busy.value = false;
  }
}
function saveSettings() {
  const item = working.value;
  return persist({
    id: item.id,
    name: item.name,
    body: item.body,
    enabled: item.enabled,
    delay_minutes: item.delay_minutes,
  });
}
function openEditor(item = null, duplicate = false) {
  editorError.value = "";
  if (item && !duplicate) selectTemplate(item.id);
  const source = item ? drafts.value[item.id] || item : null;
  editor.value = {
    id: duplicate ? null : source?.id || null,
    name: source ? source.name.slice(0, duplicate ? 93 : 100) + (duplicate ? " (copy)" : "") : "",
    rule: source?.rule || selected.value?.rule || props.initialRule,
    body: source?.body || "",
    delay_minutes: source?.delay_minutes || 0,
    enabled: duplicate || !source ? false : source.enabled,
  };
  nextTick(() => editorInput.value?.focus());
}
async function saveEditor() {
  if (await persist({ ...editor.value }, !editor.value.id)) editor.value = null;
}
function openDelete(item) {
  if (!item.can_delete) return;
  deleteError.value = "";
  deleteTarget.value = item;
}
async function deleteTemplate() {
  if (!deleteTarget.value || busy.value) return;
  busy.value = true;
  deleteError.value = "";
  const item = deleteTarget.value;
  try {
    await apiRequest("/api/sms/templates", { method: "DELETE", body: { id: item.id } });
    delete drafts.value[item.id];
    deleteTarget.value = null;
    try {
      await load();
    } catch (err) {
      error.value = err.message;
    }
    emit("changed");
    showToast("Template deleted.");
  } catch (err) {
    deleteError.value = err.message;
  } finally {
    busy.value = false;
  }
}
function insertVariable(key) {
  const input = editorInput.value;
  const start = input?.selectionStart ?? editor.value.body.length;
  const end = input?.selectionEnd ?? start;
  const value = "{" + key + "}";
  editor.value.body = editor.value.body.slice(0, start) + value + editor.value.body.slice(end);
  nextTick(() => {
    input?.focus();
    input?.setSelectionRange(start + value.length, start + value.length);
  });
}
onMounted(async () => {
  await initialize();
  await nextTick();
  pageRoot.value?.scrollIntoView({ block: "start" });
});
</script>

<template>
  <section ref="pageRoot" class="sms-templates-page" aria-labelledby="templates-title">
    <header class="templates-heading">
      <div class="heading-title">
        <span class="page-icon"><MessageCircleMore :size="25" /></span>
        <div>
          <h1 id="templates-title">SMS Templates</h1>
          <p>Automated patient messages</p>
        </div>
      </div>
      <nav aria-label="Breadcrumb" class="template-breadcrumb">
        <button @click="emit('select-panel', 'doctorOverview')">Home</button
        ><ChevronRight :size="13" /><button @click="emit('select-panel', 'doctorSmsCenter')">
          SMS</button
        ><ChevronRight :size="13" /><strong>Templates</strong>
      </nav>
    </header>
    <div v-if="error" class="template-error" role="alert">
      {{ error
      }}<button type="button" :disabled="loading || busy" @click="initialize">
        <RefreshCw :size="15" /> Retry
      </button>
    </div>
    <p v-if="loading" class="template-empty" role="status">Loading templates...</p>
    <template v-else-if="templates.length">
      <div class="template-stats">
        <article>
          <span class="metric-icon blue"><FileText :size="24" /></span>
          <div>
            <strong>{{ templates.length }}</strong
            ><span>Total Templates</span><small>Saved message templates</small>
          </div>
        </article>
        <article>
          <span class="metric-icon green"><CheckCircle2 :size="24" /></span>
          <div>
            <strong>{{ activeCount }}</strong
            ><span>Active Templates</span><small>{{ activePercent }}% of templates active</small>
          </div>
        </article>
        <article>
          <span class="metric-icon violet"><Clock3 :size="24" /></span>
          <div>
            <strong class="date-value">{{ dateLabel(latestUpdate) }}</strong
            ><span>Last Updated</span><small>{{ dateLabel(latestUpdate, true) }}</small>
          </div>
        </article>
        <article>
          <span class="metric-icon orange"><Braces :size="24" /></span>
          <div>
            <strong>{{ placeholders.length }}</strong
            ><span>SMS Variables</span><small>Available for messages</small>
          </div>
        </article>
        <div class="create-template">
          <button type="button" class="primary" :disabled="busy" @click="openEditor()">
            <Plus :size="18" /> Create New Template
          </button>
        </div>
      </div>
      <div class="templates-layout">
        <section class="template-library" aria-labelledby="library-title">
          <header class="library-heading">
            <div class="heading-title">
              <Settings2 :size="23" />
              <div>
                <h2 id="library-title">Message Templates</h2>
                <p>{{ templates.length }} templates for {{ rules.length }} automations</p>
              </div>
            </div>
            <select v-model="filter" aria-label="Filter templates">
              <option value="all">All Templates</option>
              <option value="active">Active Templates</option>
              <option value="inactive">Inactive Templates</option>
            </select>
          </header>
          <div class="template-grid">
            <article
              v-for="item in visibleTemplates"
              :key="item.id"
              class="template-card"
              :class="{ selected: selectedId === item.id }"
              :aria-label="item.name"
            >
              <header>
                <span class="template-icon" :class="item.rule"
                  ><component :is="icons[item.rule]" :size="23"
                /></span>
                <div class="template-card-title">
                  <button
                    type="button"
                    :aria-pressed="selectedId === item.id"
                    @click="selectTemplate(item.id)"
                  >
                    {{ item.name }}</button
                  ><small>Recipient: Patient</small>
                </div>
                <label class="template-toggle"
                  ><input
                    type="checkbox"
                    role="switch"
                    :aria-label="item.name + ' status'"
                    :checked="item.enabled"
                    :disabled="busy"
                    @change="persist({ id: item.id, enabled: $event.target.checked })"
                  /><span class="toggle-track"></span
                  ><small>{{ item.enabled ? "ON" : "OFF" }}</small></label
                >
              </header>
              <p class="template-trigger">{{ item.trigger }}</p>
              <p class="template-body">{{ item.body }}</p>
              <div class="variable-tags">
                <span v-for="key in variables(item.body)" :key="key">{{ "{" + key + "}" }}</span>
              </div>
              <footer>
                <button type="button" @click="selectTemplate(item.id, true)">
                  <Eye :size="13" /> Preview</button
                ><button type="button" :disabled="busy" @click="openEditor(item)">
                  <Pencil :size="13" /> Edit</button
                ><button type="button" :disabled="busy" @click="openEditor(item, true)">
                  <Copy :size="13" /> Duplicate
                </button>
                <span
                  class="delete-action-wrap"
                  :title="
                    item.can_delete
                      ? 'Delete template'
                      : 'Activate another template for this automation before deleting this one.'
                  "
                >
                  <button
                    type="button"
                    class="delete-template-action"
                    :disabled="busy || !item.can_delete"
                    @click="openDelete(item)"
                  >
                    <Trash2 :size="13" /> Delete
                  </button>
                </span>
              </footer>
            </article>
          </div>
          <p v-if="!visibleTemplates.length" class="template-empty">
            No templates match this filter.
          </p>
        </section>
        <aside v-if="selected && working" class="template-preview-column">
          <section ref="previewSection" class="template-preview" aria-labelledby="preview-title">
            <h2 id="preview-title"><Eye :size="20" /> Template Preview</h2>
            <select
              :value="selectedId"
              aria-label="Preview template"
              @change="selectTemplate($event.target.value)"
            >
              <option v-for="item in templates" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select>
            <div class="phone-frame" aria-label="Sample SMS preview">
              <div class="phone-status">
                <strong>9:41</strong><span class="phone-camera"></span>
                <div><Signal :size="11" /><Wifi :size="12" /><BatteryFull :size="16" /></div>
              </div>
              <div class="phone-contact">
                <ChevronLeft :size="17" />
                <div>
                  <img src="/assets/logo.png" alt="" /><strong>{{ clinicName }}</strong>
                </div>
              </div>
              <div class="phone-conversation">
                <span class="sample-label">Sample message</span>
                <p>{{ preview }}</p>
                <small>Text Message</small>
              </div>
              <div class="phone-home"></div>
            </div>
          </section>
          <section class="template-settings" aria-labelledby="settings-title">
            <h2 id="settings-title"><Settings2 :size="20" /> Template Settings</h2>
            <div class="character-label">
              <strong>Preview Characters</strong><span>{{ characterCount }}</span>
            </div>
            <progress
              :value="capacityPercent"
              max="100"
              aria-label="Preview character usage"
            ></progress>
            <small class="character-note">{{ working.body.length }}/1000 template characters</small>
            <label class="field-label" for="template-delay">Send Delay</label
            ><select id="template-delay" v-model.number="working.delay_minutes" :disabled="busy">
              <option v-for="delay in delays" :key="delay" :value="delay">
                {{ delay ? "Send after " + delay + " minutes" : "Send immediately (0 minutes)" }}
              </option>
            </select>
            <div class="status-setting">
              <div>
                <strong>Template Status</strong
                ><small>{{
                  working.enabled ? "Active for this automation" : "Inactive template"
                }}</small>
              </div>
              <label class="template-toggle"
                ><input
                  v-model="working.enabled"
                  type="checkbox"
                  role="switch"
                  aria-label="Selected template status"
                  :disabled="busy" /><span class="toggle-track"></span
              ></label>
            </div>
            <p v-if="dirty" class="unsaved-status" role="status">Unsaved changes</p>
            <footer>
              <button type="button" :disabled="!dirty || busy" @click="reset">Reset</button
              ><button
                type="button"
                class="primary"
                :disabled="!dirty || busy"
                @click="saveSettings"
              >
                <Save :size="16" /> {{ busy ? "Saving..." : "Save Changes" }}
              </button>
            </footer>
          </section>
        </aside>
      </div>
    </template>
    <BaseModal
      v-if="editor"
      :title="editor.id ? 'Edit SMS Template' : 'Create SMS Template'"
      eyebrow="SMS Templates"
      size-class="sms-template-modal"
      @close="!busy && (editor = null)"
    >
      <form class="template-editor-form" @submit.prevent="saveEditor">
        <div class="editor-fields">
          <label
            >Template Name<input
              v-model="editor.name"
              required
              maxlength="100"
              :disabled="busy" /></label
          ><label
            >Automation<select v-model="editor.rule" :disabled="!!editor.id || busy">
              <option v-for="item in rules" :key="item.key" :value="item.key">
                {{ item.name }}
              </option>
            </select></label
          >
        </div>
        <label
          >Message Content<textarea
            ref="editorInput"
            v-model="editor.body"
            required
            maxlength="1000"
            rows="6"
            :disabled="busy"
          ></textarea>
        </label>
        <div class="editor-meta">
          <span>{{ editor.body.length }}/1000 characters</span
          ><span v-if="editor.enabled">Active template</span>
        </div>
        <div class="variable-buttons">
          <button
            v-for="key in placeholders"
            :key="key"
            type="button"
            :disabled="busy"
            :title="'Insert ' + key"
            @click="insertVariable(key)"
          >
            {{ "{" + key + "}" }}
          </button>
        </div>
        <div class="editor-fields">
          <label
            >Send Delay<select v-model.number="editor.delay_minutes" :disabled="busy">
              <option v-for="delay in delays" :key="delay" :value="delay">
                {{ delay ? delay + " minutes" : "Immediately" }}
              </option>
            </select></label
          ><label class="editor-activation"
            ><input v-model="editor.enabled" type="checkbox" :disabled="busy" /> Use for this
            automation</label
          >
        </div>
        <p v-if="editor.enabled" class="activation-notice">
          Activating replaces the current template for this automation.
        </p>
        <p v-if="editorError" class="template-error" role="alert">{{ editorError }}</p>
        <footer>
          <button type="button" :disabled="busy" @click="editor = null">Cancel</button
          ><button
            type="submit"
            class="primary"
            :disabled="busy || !editor.name.trim() || !editor.body.trim()"
          >
            <Save :size="17" /> {{ busy ? "Saving..." : "Save Template" }}
          </button>
        </footer>
      </form>
    </BaseModal>
    <BaseModal
      v-if="deleteTarget"
      title="Delete SMS Template"
      eyebrow="SMS Templates"
      @close="!busy && (deleteTarget = null)"
    >
      <div class="delete-template-confirmation">
        <p>
          Delete <strong>{{ deleteTarget.name }}</strong
          >?
        </p>
        <p>
          This permanently removes the saved template. Existing message logs and queued SMS entries
          will not be changed.
        </p>
        <p v-if="deleteError" class="template-error" role="alert">{{ deleteError }}</p>
        <footer>
          <button type="button" :disabled="busy" @click="deleteTarget = null">Cancel</button>
          <button type="button" class="danger-action" :disabled="busy" @click="deleteTemplate">
            <Trash2 :size="16" /> {{ busy ? "Deleting..." : "Delete Template" }}
          </button>
        </footer>
      </div>
    </BaseModal>
  </section>
</template>

<style scoped>
.sms-templates-page,
.template-editor-form,
.delete-template-confirmation {
  color: var(--dashboard-text, #17345a);
  font-size: 13px;
  min-width: 0;
}
.sms-templates-page {
  scroll-margin-top: 175px;
}
.sms-templates-page *,
.template-editor-form *,
.delete-template-confirmation * {
  box-sizing: border-box;
  letter-spacing: 0;
}
.sms-templates-page button,
.template-editor-form button,
.delete-template-confirmation button {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  border: 1px solid var(--dashboard-border, #dbe6f2);
  border-radius: 5px;
  background: var(--surface, #fff);
  color: #0876ef;
  padding: 7px 11px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  box-shadow: none;
}
.sms-templates-page button:hover:not(:disabled),
.template-editor-form button:hover:not(:disabled),
.delete-template-confirmation button:hover:not(:disabled) {
  background: #eaf4ff;
}
.sms-templates-page button:disabled,
.template-editor-form button:disabled,
.delete-template-confirmation button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.sms-templates-page .primary,
.template-editor-form .primary {
  color: #fff;
  background: #0876ef;
  border-color: #0876ef;
}
.sms-templates-page .primary:hover:not(:disabled),
.template-editor-form .primary:hover:not(:disabled) {
  background: #0864ce;
}
.sms-templates-page select,
.template-editor-form input:not([type="checkbox"]),
.template-editor-form select,
.template-editor-form textarea {
  width: 100%;
  min-width: 0;
  min-height: 36px;
  color: inherit;
  font: inherit;
  background: var(--surface, #fff);
  border: 1px solid var(--dashboard-border, #dbe6f2);
  border-radius: 5px;
  padding: 8px 10px;
  box-shadow: none;
}
.sms-templates-page button:focus-visible,
.sms-templates-page select:focus-visible,
.template-editor-form :is(input, select, textarea, button):focus-visible,
.delete-template-confirmation button:focus-visible {
  outline: 2px solid #0876ef;
  outline-offset: 2px;
}
.templates-heading,
.heading-title,
.template-breadcrumb,
.library-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}
.templates-heading {
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-icon {
  width: 43px;
  height: 43px;
  display: grid;
  place-items: center;
  color: #fff;
  background: #0876ef;
  border-radius: 6px;
  flex-shrink: 0;
}
.templates-heading h1 {
  font-size: 23px;
  line-height: 1.2;
  margin: 0 0 4px;
}
.templates-heading p,
.library-heading p {
  margin: 0;
  font-size: 11px;
  color: var(--dashboard-muted, #68809f);
}
.template-breadcrumb {
  gap: 5px;
  font-size: 11px;
}
.template-breadcrumb button {
  min-height: 28px;
  background: none;
  border: 0;
  padding: 4px;
  color: var(--dashboard-muted, #68809f);
  font-weight: 400;
}
.template-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
  gap: 12px;
  margin-bottom: 22px;
}
.template-stats article {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--surface, #fff);
  border: 1px solid var(--dashboard-border, #dbe6f2);
  border-radius: 6px;
  padding: 14px;
  min-width: 0;
}
.template-stats article > div {
  min-width: 0;
  display: grid;
  gap: 4px;
}
.template-stats strong {
  font-size: 22px;
  line-height: 1.2;
}
.template-stats .date-value {
  font-size: 14px;
}
.template-stats span:not(.metric-icon) {
  font-size: 11px;
  font-weight: 600;
}
.template-stats small {
  font-size: 10px;
  color: var(--dashboard-muted, #68809f);
}
.metric-icon {
  width: 42px;
  height: 46px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}
.blue,
.template-icon {
  background: #e8f3ff;
  color: #0876ef;
}
.green,
.approval {
  background: #e9f9f1;
  color: #10a774;
}
.violet,
.walk_in,
.next_visit {
  background: #f2ebff;
  color: #8051de;
}
.orange,
.balance {
  background: #fff3e5;
  color: #e98712;
}
.cancellation {
  background: #fff0f3;
  color: #e94b64;
}
.create-template {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
.create-template button {
  white-space: nowrap;
  min-height: 40px;
  font-size: 12px;
}
.templates-layout {
  display: grid;
  grid-template-columns: minmax(0, 2.6fr) minmax(280px, 1fr);
  gap: 22px;
  align-items: start;
}
.template-library {
  min-width: 0;
}
.library-heading {
  justify-content: space-between;
  margin-bottom: 14px;
  align-items: start;
}
.heading-title > svg,
.template-preview h2 > svg,
.template-settings h2 > svg {
  color: #0876ef;
  flex-shrink: 0;
}
.library-heading h2,
.template-preview h2,
.template-settings h2 {
  font-size: 15px;
  line-height: 1.3;
  margin: 0 0 4px;
}
.library-heading select {
  width: 145px;
  flex-shrink: 0;
  font-size: 11px;
}
.template-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.template-card {
  min-width: 0;
  border: 1px solid var(--dashboard-border, #dbe6f2);
  background: var(--surface, #fff);
  border-radius: 6px;
  padding: 11px;
  display: flex;
  flex-direction: column;
}
.template-card.selected {
  border-color: #559eff;
  box-shadow: 0 0 0 1px #d6e9ff;
}
.template-card header {
  display: grid;
  grid-template-columns: 35px minmax(0, 1fr) auto;
  align-items: start;
  gap: 9px;
}
.template-icon {
  display: grid;
  place-items: center;
  width: 35px;
  height: 37px;
  border-radius: 5px;
}
.sms-templates-page .template-card-title button {
  border: 0;
  padding: 0;
  min-height: 0;
  text-align: left;
  justify-content: start;
  color: inherit;
  font-size: 12px;
  line-height: 1.4;
  background: none;
  overflow-wrap: anywhere;
}
.template-card-title small {
  display: block;
  font-size: 10px;
  color: var(--dashboard-muted, #68809f);
  margin-top: 3px;
}
.template-trigger {
  font-size: 10px;
  color: var(--dashboard-muted, #68809f);
  margin: 6px 0;
  line-height: 1.4;
}
.template-body {
  background: var(--dashboard-soft, #f1f6fc);
  margin: 0 0 9px;
  padding: 7px;
  border-radius: 4px;
  font-size: 11px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
  min-height: 64px;
}
.variable-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}
.variable-tags span {
  font-size: 9px;
  color: #0876d8;
  background: #eaf4ff;
  padding: 2px 5px;
  border-radius: 3px;
  overflow-wrap: anywhere;
  max-width: 100%;
}
.template-card footer {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: auto;
}
.template-card footer button {
  min-height: 27px;
  font-size: 10px;
  padding: 4px 7px;
}
.delete-action-wrap {
  display: inline-flex;
}
.sms-templates-page .template-card footer .delete-template-action {
  color: #d5304e;
}
.sms-templates-page .template-card footer .delete-template-action:hover:not(:disabled) {
  border-color: #f19aaa;
  background: #fff0f3;
}
.delete-template-confirmation {
  padding: 22px;
  color: var(--dashboard-text, #17345a);
  font-size: 13px;
  line-height: 1.6;
}
.delete-template-confirmation p {
  margin: 0 0 12px;
  overflow-wrap: anywhere;
}
.delete-template-confirmation footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid var(--dashboard-border, #dbe6f2);
  padding-top: 16px;
  margin-top: 20px;
}
.template-editor-form .danger-action,
.delete-template-confirmation .danger-action {
  border-color: #e74460;
  background: #e74460;
  color: #fff;
}
.delete-template-confirmation .danger-action:hover:not(:disabled) {
  border-color: #c92946;
  background: #c92946;
}
.template-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  position: relative;
  flex-shrink: 0;
  cursor: pointer;
  min-height: 22px;
}
.template-toggle input {
  position: absolute;
  opacity: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  cursor: pointer;
}
.toggle-track {
  display: block;
  width: 29px;
  height: 16px;
  background: #9aa9ba;
  border-radius: 12px;
  flex-shrink: 0;
  pointer-events: none;
}
.toggle-track::after {
  content: "";
  display: block;
  width: 12px;
  height: 12px;
  margin: 2px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.15s;
}
.template-toggle input:checked + .toggle-track {
  background: #14ad7b;
}
.template-toggle input:checked + .toggle-track::after {
  transform: translateX(13px);
}
.template-toggle input:focus-visible + .toggle-track {
  outline: 2px solid #0876ef;
  outline-offset: 3px;
}
.template-toggle input:disabled ~ span {
  opacity: 0.5;
}
.template-toggle small {
  font-size: 9px;
  pointer-events: none;
}
.template-preview-column {
  border-left: 1px solid var(--dashboard-border, #dbe6f2);
  padding-left: 20px;
  min-width: 0;
}
.template-preview {
  scroll-margin-top: 175px;
}
.template-preview h2,
.template-settings h2 {
  display: flex;
  gap: 9px;
  align-items: center;
  margin-bottom: 10px;
}
.template-preview select {
  font-size: 11px;
  margin-bottom: 15px;
}
.phone-frame {
  position: relative;
  width: min(100%, 270px);
  height: 292px;
  border: 5px solid #263344;
  border-radius: 30px;
  box-shadow: 0 0 0 2px #c4cbd2;
  background: #fff;
  color: #20354c;
  margin: 0 auto;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.phone-status {
  position: relative;
  flex-shrink: 0;
  height: 24px;
  padding: 7px 15px 0;
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  align-items: center;
}
.phone-status > div {
  display: flex;
  gap: 3px;
  align-items: center;
}
.phone-camera {
  position: absolute;
  width: 55px;
  height: 10px;
  border-radius: 8px;
  background: #263344;
  left: 50%;
  top: 3px;
  transform: translateX(-50%);
}
.phone-contact {
  background: #f4f6fa;
  padding: 8px 9px;
  position: relative;
  flex-shrink: 0;
  border-bottom: 1px solid #e7ebef;
}
.phone-contact > svg {
  position: absolute;
  left: 10px;
  top: 22px;
  color: #0876ef;
}
.phone-contact > div {
  display: grid;
  justify-items: center;
  gap: 4px;
}
.phone-contact img {
  width: 29px;
  height: 29px;
  object-fit: contain;
}
.phone-contact strong {
  font-size: 9px;
  max-width: 75%;
  text-align: center;
  overflow-wrap: anywhere;
}
.phone-conversation {
  padding: 12px 11px 18px;
  overflow-y: auto;
  min-height: 0;
  flex: 1;
}
.sample-label {
  display: block;
  text-align: center;
  font-size: 9px;
  color: #7b8797;
  margin-bottom: 10px;
}
.phone-conversation p {
  font-size: 12px;
  line-height: 1.5;
  background: #edf0f5;
  padding: 10px;
  margin: 0 12px 6px 0;
  border-radius: 8px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.phone-conversation small {
  font-size: 8px;
  color: #7b8797;
}
.phone-home {
  width: 85px;
  height: 4px;
  border-radius: 2px;
  background: #263344;
  margin: 5px auto;
  flex-shrink: 0;
}
.template-settings {
  margin-top: 22px;
  padding-top: 17px;
  border-top: 1px solid var(--dashboard-border, #dbe6f2);
}
.character-label {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 10px;
  margin-top: 15px;
}
.template-settings progress {
  appearance: none;
  width: 100%;
  height: 5px;
  border: 0;
  border-radius: 3px;
  margin-top: 8px;
}
.template-settings progress::-webkit-progress-bar {
  background: #e9eef5;
  border-radius: 3px;
}
.template-settings progress::-webkit-progress-value {
  background: #1cba84;
  border-radius: 3px;
}
.template-settings progress::-moz-progress-bar {
  background: #1cba84;
}
.character-note {
  display: block;
  font-size: 9px;
  color: var(--dashboard-muted, #68809f);
  margin-top: 3px;
}
.field-label {
  display: block;
  font-weight: 600;
  font-size: 11px;
  margin: 16px 0 6px;
}
.template-settings select {
  font-size: 11px;
}
.status-setting {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin: 16px 0;
  align-items: start;
}
.status-setting strong {
  font-size: 11px;
}
.status-setting small {
  display: block;
  font-size: 10px;
  color: var(--dashboard-muted, #68809f);
  margin-top: 5px;
}
.template-settings footer {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 8px;
  border-top: 1px solid var(--dashboard-border, #dbe6f2);
  padding-top: 12px;
}
.template-settings footer button {
  font-size: 11px;
}
.unsaved-status {
  font-size: 11px;
  color: #9b6708;
}
.template-empty {
  padding: 32px 15px;
  text-align: center;
  color: var(--dashboard-muted, #68809f);
}
.template-error {
  background: #fff1f3;
  color: #b52d44;
  padding: 12px;
  margin: 10px 0;
  border-radius: 5px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.template-editor-form {
  padding: 24px;
  display: grid;
  gap: 16px;
}
.template-editor-form label {
  display: grid;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
}
.template-editor-form textarea {
  resize: vertical;
  line-height: 1.6;
}
.editor-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.editor-meta {
  display: flex;
  justify-content: space-between;
  margin-top: -9px;
  font-size: 11px;
  color: var(--dashboard-muted, #68809f);
}
.variable-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.variable-buttons button {
  font-size: 11px;
  min-height: 29px;
  padding: 4px 7px;
}
.template-editor-form .editor-activation {
  display: flex;
  align-items: center;
  align-self: end;
  min-height: 36px;
  gap: 9px;
}
.editor-activation input {
  width: 17px;
  height: 17px;
  accent-color: #0876ef;
}
.activation-notice {
  margin: 0;
  color: var(--dashboard-muted, #68809f);
  font-size: 12px;
}
.template-editor-form footer {
  border-top: 1px solid var(--dashboard-border, #dbe6f2);
  padding-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
@media (max-width: 1350px) {
  .template-stats article {
    gap: 9px;
    padding: 11px;
  }
  .metric-icon {
    width: 34px;
  }
  .template-icon {
    width: 30px;
    height: 33px;
  }
}
@media (max-width: 1180px) {
  .template-stats {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .create-template {
    grid-column: 1/-1;
  }
}
@media (max-width: 1050px) {
  .templates-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .template-preview-column {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 28px;
    border-left: 0;
    border-top: 1px solid var(--dashboard-border, #dbe6f2);
    padding: 22px 0 0;
  }
  .template-settings {
    border-top: 0;
    margin-top: 0;
    padding-top: 0;
  }
}
@media (max-width: 650px) {
  .templates-heading {
    align-items: start;
    flex-direction: column;
  }
  .template-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .create-template button {
    width: 100%;
  }
  .library-heading {
    flex-wrap: wrap;
  }
  .library-heading select {
    width: 100%;
  }
  .template-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .template-preview-column {
    grid-template-columns: minmax(0, 1fr);
  }
  .template-settings {
    border-top: 1px solid var(--dashboard-border, #dbe6f2);
    padding-top: 20px;
  }
  .editor-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .template-editor-form {
    padding: 17px;
  }
  .templates-heading h1 {
    font-size: 21px;
  }
}
:global(html[data-dashboard-theme="dark"]) .template-body {
  background: #202a39;
}
:global(html[data-dashboard-theme="dark"]) .variable-tags span {
  background: #203753;
  color: #91c4ff;
}
:global(html[data-dashboard-theme="dark"]) .sms-templates-page button:not(.primary):hover {
  background: #26374c;
}
</style>
