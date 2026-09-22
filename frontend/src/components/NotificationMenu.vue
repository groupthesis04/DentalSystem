<script setup>
import { Bell } from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { apiRequest } from "../services/api";
import { relativeTime } from "../services/format";
import { showToast } from "../services/toast";

const emit = defineEmits(["open-target"]);
const open = ref(false);
const notifications = ref([]);
const root = ref(null);
let pollTimer;

const unreadCount = computed(() => notifications.value.filter((item) => !item.is_read).length);

async function refresh(showErrors = false) {
  try {
    const data = await apiRequest("/api/notifications");
    notifications.value = data.notifications || [];
  } catch (error) {
    if (showErrors) showToast(error.message, "error");
  }
}

async function markRead(item = null) {
  try {
    await apiRequest("/api/notifications", {
      method: "PATCH",
      body: item ? { id: item.id } : { mark_all: true },
    });
    for (const notification of notifications.value) {
      if (!item || notification.id === item.id) notification.is_read = true;
    }
    if (item) {
      open.value = false;
      emit("open-target", item);
    }
  } catch (error) {
    showToast(error.message, "error");
  }
}

function outsideClick(event) {
  if (root.value && !root.value.contains(event.target)) open.value = false;
}

onMounted(() => {
  refresh();
  pollTimer = window.setInterval(() => {
    if (!document.hidden) refresh();
  }, 30000);
  document.addEventListener("click", outsideClick);
});

onBeforeUnmount(() => {
  window.clearInterval(pollTimer);
  document.removeEventListener("click", outsideClick);
});
</script>

<template>
  <div ref="root" class="notification-center">
    <button
      class="notification-button"
      type="button"
      title="Notifications"
      :aria-label="unreadCount ? `Notifications, ${unreadCount} unread` : 'Notifications'"
      aria-haspopup="dialog"
      :aria-expanded="open"
      @click.stop="open = !open"
    >
      <Bell :size="21" aria-hidden="true" />
      <span
        v-if="unreadCount"
        class="notification-badge"
        :aria-label="`${unreadCount} unread notifications`"
      >
        {{ unreadCount > 99 ? "99+" : unreadCount }}
      </span>
    </button>
    <section v-if="open" class="notification-panel" role="dialog" aria-label="Notifications">
      <div class="notification-panel-header">
        <div>
          <span class="section-kicker">Transactions</span>
          <h2>Notifications</h2>
        </div>
        <button
          class="text-link notification-read-all"
          type="button"
          :disabled="!unreadCount"
          @click="markRead()"
        >
          Mark all read
        </button>
      </div>
      <div class="notification-list">
        <button
          v-for="item in notifications"
          :key="item.id"
          class="notification-item"
          :class="{ unread: !item.is_read }"
          type="button"
          @click="markRead(item)"
        >
          <span class="notification-item-indicator" aria-hidden="true"></span>
          <span class="notification-item-content">
            <strong>{{ item.title }}</strong>
            <span>{{ item.message }}</span>
            <time :datetime="item.created_at">{{ relativeTime(item.created_at) }}</time>
          </span>
        </button>
        <p v-if="!notifications.length" class="notification-empty">No notifications yet.</p>
      </div>
    </section>
  </div>
</template>
