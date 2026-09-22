<script setup>
import {
  BadgePlus,
  ChevronDown,
  MessageSquareText,
  Plus,
  RotateCcw,
  Save,
  Search,
  Star,
  Tag,
} from "lucide-vue-next";
import { computed, nextTick, reactive, ref } from "vue";

import ActionIconButton from "../ActionIconButton.vue";
import BaseModal from "../BaseModal.vue";
import { apiRequest } from "../../services/api";
import { getServiceModalContent } from "../../services/constants";
import { formatDate, initials } from "../../services/format";
import { showToast } from "../../services/toast";
import { validatedPayload } from "../../services/validation";

const props = defineProps({ state: { type: Object, required: true } });

const emptyServiceForm = () => ({
  id: "",
  name: "",
  description: "",
  detail_tagline: "",
  detail_items: "",
  detail_duration: "",
  detail_audience: "",
  detail_care_note: "",
  _website: "",
});
const serviceForm = reactive(emptyServiceForm());
const promoForm = reactive({ id: "", title: "", description: "", _website: "" });
const feedbackForm = reactive({ id: "", rating: "5", message: "", _website: "" });

const serviceSearch = ref("");
const promoSearch = ref("");
const feedbackSearch = ref("");
const feedbackRating = ref("all");
const showAllServices = ref(false);
const showAllPromos = ref(false);
const showAllFeedback = ref(false);
const feedbackEditorOpen = ref(false);
const serviceNameInput = ref(null);
const promoTitleInput = ref(null);
const busy = ref("");

const averageRating = computed(() => {
  if (!props.state.feedback.length) return "0.0";
  const total = props.state.feedback.reduce((sum, item) => sum + Number(item.rating || 0), 0);
  return (total / props.state.feedback.length).toFixed(1);
});

const filteredServices = computed(() => {
  const query = serviceSearch.value.trim().toLowerCase();
  if (!query) return props.state.services;
  return props.state.services.filter((item) =>
    `${item.name} ${item.description}`.toLowerCase().includes(query),
  );
});

const filteredPromos = computed(() => {
  const query = promoSearch.value.trim().toLowerCase();
  if (!query) return props.state.promos;
  return props.state.promos.filter((item) =>
    `${item.title} ${item.description}`.toLowerCase().includes(query),
  );
});

const filteredFeedback = computed(() => {
  const query = feedbackSearch.value.trim().toLowerCase();
  return props.state.feedback.filter((item) => {
    const matchesSearch = !query || `${item.name} ${item.message}`.toLowerCase().includes(query);
    const matchesRating =
      feedbackRating.value === "all" || Number(item.rating) === Number(feedbackRating.value);
    return matchesSearch && matchesRating;
  });
});

const visibleServices = computed(() =>
  showAllServices.value ? filteredServices.value : filteredServices.value.slice(0, 5),
);
const visiblePromos = computed(() =>
  showAllPromos.value ? filteredPromos.value : filteredPromos.value.slice(0, 5),
);
const visibleFeedback = computed(() =>
  showAllFeedback.value ? filteredFeedback.value : filteredFeedback.value.slice(0, 5),
);

function resetServiceForm(focus = false) {
  Object.assign(serviceForm, emptyServiceForm());
  if (focus) nextTick(() => serviceNameInput.value?.focus());
}

function resetPromoForm(focus = false) {
  Object.assign(promoForm, { id: "", title: "", description: "", _website: "" });
  if (focus) nextTick(() => promoTitleInput.value?.focus());
}

function editService(service) {
  const modalContent = getServiceModalContent(service);
  Object.assign(serviceForm, {
    id: service.id,
    name: service.name,
    description: service.description,
    detail_tagline: modalContent.tagline,
    detail_items: modalContent.includes.join("\n"),
    detail_duration: modalContent.duration,
    detail_audience: modalContent.audience,
    detail_care_note: modalContent.careNote,
    _website: "",
  });
  nextTick(() => serviceNameInput.value?.focus());
}

function editPromo(promo) {
  Object.assign(promoForm, {
    id: promo.id,
    title: promo.title,
    description: promo.description,
    _website: "",
  });
  nextTick(() => promoTitleInput.value?.focus());
}

function editFeedback(item) {
  Object.assign(feedbackForm, {
    id: item.id,
    rating: String(item.rating || 5),
    message: item.message || "",
    _website: "",
  });
  feedbackEditorOpen.value = true;
}

async function saveService() {
  const editing = Boolean(serviceForm.id);
  busy.value = "service";
  try {
    const body = validatedPayload({
      ...(editing ? { id: serviceForm.id } : {}),
      name: serviceForm.name,
      description: serviceForm.description,
      detail_tagline: serviceForm.detail_tagline,
      detail_items: serviceForm.detail_items,
      detail_duration: serviceForm.detail_duration,
      detail_audience: serviceForm.detail_audience,
      detail_care_note: serviceForm.detail_care_note,
      _website: serviceForm._website,
    });
    const data = await apiRequest("/api/services", {
      method: editing ? "PATCH" : "POST",
      body,
    });
    const index = props.state.services.findIndex((item) => item.id === data.service.id);
    if (index >= 0) props.state.services.splice(index, 1, data.service);
    else props.state.services.unshift(data.service);
    resetServiceForm();
    showToast(editing ? "Service updated." : "Service saved.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    busy.value = "";
  }
}

async function savePromo() {
  const editing = Boolean(promoForm.id);
  busy.value = "promo";
  try {
    const body = validatedPayload({
      ...(editing ? { id: promoForm.id } : {}),
      title: promoForm.title,
      description: promoForm.description,
      _website: promoForm._website,
    });
    const data = await apiRequest("/api/promos", {
      method: editing ? "PATCH" : "POST",
      body,
    });
    const index = props.state.promos.findIndex((item) => item.id === data.promo.id);
    if (index >= 0) props.state.promos.splice(index, 1, data.promo);
    else props.state.promos.unshift(data.promo);
    resetPromoForm();
    showToast(editing ? "Promo updated." : "Promo saved.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    busy.value = "";
  }
}

async function remove(path, collection, item, label) {
  if (!window.confirm(`Delete ${label}?`)) return false;
  busy.value = `delete-${item.id}`;
  try {
    await apiRequest(path, { method: "DELETE", body: { id: item.id } });
    const index = props.state[collection].findIndex((entry) => entry.id === item.id);
    if (index >= 0) props.state[collection].splice(index, 1);
    showToast(`${label} deleted.`);
    return true;
  } catch (error) {
    showToast(error.message, "error");
    return false;
  } finally {
    busy.value = "";
  }
}

async function deleteService(service) {
  const deleted = await remove("/api/services", "services", service, service.name);
  if (deleted && serviceForm.id === service.id) resetServiceForm();
}

async function deletePromo(promo) {
  const deleted = await remove("/api/promos", "promos", promo, promo.title);
  if (deleted && promoForm.id === promo.id) resetPromoForm();
}

async function saveFeedback() {
  busy.value = "feedback";
  try {
    const data = await apiRequest("/api/feedback", {
      method: "PATCH",
      body: validatedPayload({ ...feedbackForm }),
    });
    const index = props.state.feedback.findIndex((item) => item.id === data.feedback.id);
    if (index >= 0) props.state.feedback.splice(index, 1, data.feedback);
    feedbackEditorOpen.value = false;
    showToast("Feedback updated.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    busy.value = "";
  }
}

async function deleteFeedback(item) {
  const feedback = props.state.feedback.find((entry) => entry.id === item?.id) || item;
  if (!feedback?.id) return;
  const deleted = await remove(
    "/api/feedback",
    "feedback",
    feedback,
    `feedback from ${feedback.name}`,
  );
  if (deleted && feedbackForm.id === feedback.id) feedbackEditorOpen.value = false;
}
</script>

<template>
  <section class="workspace-panel content-management-page" aria-labelledby="content-title">
    <header class="content-page-heading">
      <div>
        <span class="section-kicker">Clinic content</span>
        <h1 id="content-title">Services &amp; Content</h1>
        <p>Manage clinic services, promotional offers, and patient feedback.</p>
      </div>
    </header>

    <div class="content-summary-grid" aria-label="Content summary">
      <article class="content-summary-card service-summary">
        <span class="content-summary-icon"><BadgePlus :size="23" aria-hidden="true" /></span>
        <div>
          <span>Total Services</span>
          <strong>{{ state.services.length }}</strong>
          <small>Available at the clinic</small>
        </div>
      </article>
      <article class="content-summary-card promo-summary">
        <span class="content-summary-icon"><Tag :size="23" aria-hidden="true" /></span>
        <div>
          <span>Active Promos</span>
          <strong>{{ state.promos.length }}</strong>
          <small>Current patient offers</small>
        </div>
      </article>
      <article class="content-summary-card feedback-summary">
        <span class="content-summary-icon">
          <MessageSquareText :size="23" aria-hidden="true" />
        </span>
        <div>
          <span>Total Feedback</span>
          <strong>{{ state.feedback.length }}</strong>
          <small>Patient responses</small>
        </div>
      </article>
      <article class="content-summary-card rating-summary">
        <span class="content-summary-icon"><Star :size="23" aria-hidden="true" /></span>
        <div>
          <span>Average Rating</span>
          <strong>{{ averageRating }}</strong>
          <small>Out of 5.0</small>
        </div>
      </article>
    </div>

    <div class="content-work-grid">
      <section class="content-work-panel services-work-panel" aria-labelledby="services-title">
        <header class="content-panel-heading">
          <div class="content-panel-title">
            <span class="content-panel-icon"><BadgePlus :size="21" aria-hidden="true" /></span>
            <div>
              <h2 id="services-title">Manage Services</h2>
              <p>Add, edit, or remove dental services</p>
            </div>
          </div>
          <button class="content-add-button" type="button" @click="resetServiceForm(true)">
            <Plus :size="17" aria-hidden="true" /> Add Service
          </button>
        </header>

        <form class="content-editor-form" @submit.prevent="saveService">
          <label class="hp-field" aria-hidden="true">
            Website<input v-model="serviceForm._website" tabindex="-1" autocomplete="off" />
          </label>
          <label>
            <span>Service Name <b aria-hidden="true">*</b></span>
            <input
              ref="serviceNameInput"
              v-model="serviceForm.name"
              type="text"
              placeholder="e.g. Teeth Whitening"
              minlength="3"
              maxlength="120"
              required
            />
          </label>
          <label>
            <span>Description <b aria-hidden="true">*</b></span>
            <textarea
              v-model="serviceForm.description"
              rows="3"
              placeholder="Enter service description..."
              minlength="10"
              maxlength="500"
              required
            ></textarea>
          </label>
          <fieldset class="service-popup-editor">
            <legend>Learn More Popup</legend>
            <label>
              <span>Introduction</span>
              <textarea
                v-model="serviceForm.detail_tagline"
                rows="2"
                maxlength="240"
                placeholder="Short introduction shown below the service title"
              ></textarea>
            </label>
            <label>
              <span>What's Included</span>
              <textarea
                v-model="serviceForm.detail_items"
                rows="4"
                maxlength="1600"
                placeholder="Enter one item per line"
              ></textarea>
            </label>
            <div class="service-popup-facts">
              <label>
                <span>Visit Timing</span>
                <input
                  v-model="serviceForm.detail_duration"
                  type="text"
                  maxlength="80"
                  placeholder="By appointment"
                />
              </label>
              <label>
                <span>Patient Suitability</span>
                <input
                  v-model="serviceForm.detail_audience"
                  type="text"
                  maxlength="80"
                  placeholder="Individual care"
                />
              </label>
              <label>
                <span>Treatment Approach</span>
                <input
                  v-model="serviceForm.detail_care_note"
                  type="text"
                  maxlength="100"
                  placeholder="Clear guidance"
                />
              </label>
            </div>
          </fieldset>
          <div class="content-form-actions">
            <button class="content-clear-button" type="button" @click="resetServiceForm()">
              <RotateCcw :size="16" aria-hidden="true" /> Clear
            </button>
            <button
              class="content-save-button service-save"
              type="submit"
              :disabled="busy === 'service'"
            >
              <Save :size="16" aria-hidden="true" />
              {{
                busy === "service"
                  ? "Saving..."
                  : serviceForm.id
                    ? "Update Service"
                    : "Save Service"
              }}
            </button>
          </div>
        </form>

        <div class="content-list-heading">
          <h3>Existing Services</h3>
          <span>{{ filteredServices.length }} total</span>
        </div>
        <label class="content-search-field">
          <Search :size="16" aria-hidden="true" />
          <span class="sr-only">Search services</span>
          <input v-model="serviceSearch" type="search" placeholder="Search services..." />
        </label>
        <div class="content-table-wrap">
          <table class="content-table content-crud-table">
            <thead>
              <tr>
                <th>Service</th>
                <th class="content-actions-column">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="service in visibleServices" :key="service.id">
                <td>
                  <strong>{{ service.name }}</strong>
                  <span>{{ service.description }}</span>
                </td>
                <td class="content-actions-column">
                  <span class="content-row-actions">
                    <ActionIconButton
                      action="edit"
                      :label="`Edit ${service.name}`"
                      :disabled="busy === `delete-${service.id}`"
                      @click="editService(service)"
                    />
                    <ActionIconButton
                      action="delete"
                      :label="`Delete ${service.name}`"
                      :disabled="busy === `delete-${service.id}`"
                      @click="deleteService(service)"
                    />
                  </span>
                </td>
              </tr>
              <tr v-if="!visibleServices.length">
                <td colspan="2" class="table-empty">No matching services.</td>
              </tr>
            </tbody>
          </table>
        </div>
        <button
          v-if="filteredServices.length > 5"
          class="content-more-button"
          type="button"
          @click="showAllServices = !showAllServices"
        >
          {{ showAllServices ? "Show Less" : "More" }}
          <ChevronDown :class="{ rotated: showAllServices }" :size="16" aria-hidden="true" />
        </button>
      </section>

      <section class="content-work-panel promos-work-panel" aria-labelledby="promos-title">
        <header class="content-panel-heading">
          <div class="content-panel-title">
            <span class="content-panel-icon"><Tag :size="21" aria-hidden="true" /></span>
            <div>
              <h2 id="promos-title">Manage Promos</h2>
              <p>Create and manage special offers</p>
            </div>
          </div>
          <button class="content-add-button" type="button" @click="resetPromoForm(true)">
            <Plus :size="17" aria-hidden="true" /> Add Promo
          </button>
        </header>

        <form class="content-editor-form" @submit.prevent="savePromo">
          <label class="hp-field" aria-hidden="true">
            Website<input v-model="promoForm._website" tabindex="-1" autocomplete="off" />
          </label>
          <label>
            <span>Promo Title <b aria-hidden="true">*</b></span>
            <input
              ref="promoTitleInput"
              v-model="promoForm.title"
              type="text"
              placeholder="e.g. Family Smile Day"
              minlength="3"
              maxlength="120"
              required
            />
          </label>
          <label>
            <span>Description <b aria-hidden="true">*</b></span>
            <textarea
              v-model="promoForm.description"
              rows="3"
              placeholder="Enter promo details..."
              minlength="10"
              maxlength="500"
              required
            ></textarea>
          </label>
          <div class="content-form-actions">
            <button class="content-clear-button" type="button" @click="resetPromoForm()">
              <RotateCcw :size="16" aria-hidden="true" /> Clear
            </button>
            <button
              class="content-save-button promo-save"
              type="submit"
              :disabled="busy === 'promo'"
            >
              <Save :size="16" aria-hidden="true" />
              {{ busy === "promo" ? "Saving..." : promoForm.id ? "Update Promo" : "Save Promo" }}
            </button>
          </div>
        </form>

        <div class="content-list-heading">
          <h3>Existing Promos</h3>
          <span>{{ filteredPromos.length }} total</span>
        </div>
        <label class="content-search-field">
          <Search :size="16" aria-hidden="true" />
          <span class="sr-only">Search promos</span>
          <input v-model="promoSearch" type="search" placeholder="Search promos..." />
        </label>
        <div class="content-table-wrap">
          <table class="content-table content-crud-table">
            <thead>
              <tr>
                <th>Promo</th>
                <th class="content-actions-column">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="promo in visiblePromos" :key="promo.id">
                <td>
                  <strong>{{ promo.title }}</strong>
                  <span>{{ promo.description }}</span>
                </td>
                <td class="content-actions-column">
                  <span class="content-row-actions">
                    <ActionIconButton
                      action="edit"
                      :label="`Edit ${promo.title}`"
                      :disabled="busy === `delete-${promo.id}`"
                      @click="editPromo(promo)"
                    />
                    <ActionIconButton
                      action="delete"
                      :label="`Delete ${promo.title}`"
                      :disabled="busy === `delete-${promo.id}`"
                      @click="deletePromo(promo)"
                    />
                  </span>
                </td>
              </tr>
              <tr v-if="!visiblePromos.length">
                <td colspan="2" class="table-empty">No matching promos.</td>
              </tr>
            </tbody>
          </table>
        </div>
        <button
          v-if="filteredPromos.length > 5"
          class="content-more-button"
          type="button"
          @click="showAllPromos = !showAllPromos"
        >
          {{ showAllPromos ? "Show Less" : "More" }}
          <ChevronDown :class="{ rotated: showAllPromos }" :size="16" aria-hidden="true" />
        </button>
      </section>

      <section class="content-work-panel feedback-work-panel" aria-labelledby="feedback-title">
        <header class="content-panel-heading">
          <div class="content-panel-title">
            <span class="content-panel-icon">
              <MessageSquareText :size="21" aria-hidden="true" />
            </span>
            <div>
              <h2 id="feedback-title">Manage Feedback</h2>
              <p>Review and update patient feedback</p>
            </div>
          </div>
        </header>

        <div class="feedback-overview-tabs">
          <span class="active">
            <MessageSquareText :size="15" aria-hidden="true" />
            All Feedback ({{ state.feedback.length }})
          </span>
          <span><Star :size="15" aria-hidden="true" /> {{ averageRating }} Average</span>
        </div>
        <div class="feedback-filter-row">
          <label class="content-search-field">
            <Search :size="16" aria-hidden="true" />
            <span class="sr-only">Search feedback</span>
            <input v-model="feedbackSearch" type="search" placeholder="Search feedback..." />
          </label>
          <label>
            <span class="sr-only">Filter by rating</span>
            <select v-model="feedbackRating" aria-label="Filter feedback by rating">
              <option value="all">All Ratings</option>
              <option value="5">5 Stars</option>
              <option value="4">4 Stars</option>
              <option value="3">3 Stars</option>
              <option value="2">2 Stars</option>
              <option value="1">1 Star</option>
            </select>
          </label>
        </div>

        <div class="feedback-list">
          <article v-for="item in visibleFeedback" :key="item.id" class="feedback-list-item">
            <span class="feedback-avatar" aria-hidden="true">{{ initials(item.name) }}</span>
            <div class="feedback-item-body">
              <div class="feedback-item-heading">
                <strong>{{ item.name }}</strong>
                <time :datetime="item.created_at">{{ formatDate(item.created_at) }}</time>
              </div>
              <div class="feedback-stars" :aria-label="`${item.rating} out of 5 stars`">
                <Star
                  v-for="number in 5"
                  :key="number"
                  :class="{ filled: number <= Number(item.rating) }"
                  :size="14"
                  aria-hidden="true"
                />
              </div>
              <p>{{ item.message }}</p>
            </div>
            <span class="content-row-actions feedback-actions">
              <ActionIconButton
                action="edit"
                :label="`Edit feedback from ${item.name}`"
                :disabled="busy === `delete-${item.id}`"
                @click="editFeedback(item)"
              />
              <ActionIconButton
                action="delete"
                :label="`Delete feedback from ${item.name}`"
                :disabled="busy === `delete-${item.id}`"
                @click="deleteFeedback(item)"
              />
            </span>
          </article>
          <p v-if="!visibleFeedback.length" class="content-empty-state">No matching feedback.</p>
        </div>
        <button
          v-if="filteredFeedback.length > 5"
          class="content-more-button"
          type="button"
          @click="showAllFeedback = !showAllFeedback"
        >
          {{ showAllFeedback ? "Show Less" : "More" }}
          <ChevronDown :class="{ rotated: showAllFeedback }" :size="16" aria-hidden="true" />
        </button>
      </section>
    </div>

    <BaseModal
      v-if="feedbackEditorOpen"
      title="Edit Feedback"
      eyebrow="Patient feedback"
      size-class="compact-dialog"
      @close="feedbackEditorOpen = false"
    >
      <form class="content-feedback-editor" @submit.prevent="saveFeedback">
        <label class="hp-field" aria-hidden="true">
          Website<input v-model="feedbackForm._website" tabindex="-1" autocomplete="off" />
        </label>
        <label>
          Rating
          <select v-model="feedbackForm.rating" required>
            <option value="5">5 - Excellent</option>
            <option value="4">4 - Very good</option>
            <option value="3">3 - Good</option>
            <option value="2">2 - Fair</option>
            <option value="1">1 - Needs improvement</option>
          </select>
        </label>
        <label>
          Message
          <textarea
            v-model="feedbackForm.message"
            rows="5"
            minlength="10"
            maxlength="500"
            required
          ></textarea>
        </label>
        <div class="content-modal-actions">
          <button
            class="danger-button"
            type="button"
            :disabled="busy === `delete-${feedbackForm.id}`"
            @click="deleteFeedback(feedbackForm)"
          >
            Delete Feedback
          </button>
          <button class="primary-button" type="submit" :disabled="busy === 'feedback'">
            <Save :size="17" aria-hidden="true" />
            {{ busy === "feedback" ? "Saving..." : "Save Feedback" }}
          </button>
        </div>
      </form>
    </BaseModal>
  </section>
</template>
