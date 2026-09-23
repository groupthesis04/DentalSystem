<script setup>
import { ChevronDown, LogOut, X } from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import AvatarBadge from "./AvatarBadge.vue";

const props = defineProps({
  user: { type: Object, required: true },
  roleLabel: { type: String, required: true },
  items: { type: Array, required: true },
  active: { type: String, required: true },
  profilePanelId: { type: String, required: true },
});
const emit = defineEmits(["select", "logout"]);
const expandedGroup = ref("");
const mobileExpandedGroup = ref("");
const isMobile = ref(false);
const mobileSubmenu = ref(null);
const mobileGroup = computed(() =>
  props.items.find((item) => item.id === mobileExpandedGroup.value && item.children?.length),
);
let mobileBreakpoint;

function syncMobileBreakpoint(event) {
  isMobile.value = event.matches;
  if (!event.matches) mobileExpandedGroup.value = "";
}

function closeMobileSubmenu(restoreFocus = false) {
  const groupId = mobileExpandedGroup.value;
  mobileExpandedGroup.value = "";
  if (restoreFocus && groupId) {
    nextTick(() => document.getElementById(`sidebar-group-${groupId}`)?.focus());
  }
}

function handleEscape(event) {
  if (event.key === "Escape" && mobileExpandedGroup.value) {
    event.preventDefault();
    closeMobileSubmenu(true);
  }
}

onMounted(() => {
  mobileBreakpoint = window.matchMedia("(max-width: 720px)");
  syncMobileBreakpoint(mobileBreakpoint);
  mobileBreakpoint.addEventListener("change", syncMobileBreakpoint);
  window.addEventListener("keydown", handleEscape);
});

onBeforeUnmount(() => {
  mobileBreakpoint?.removeEventListener("change", syncMobileBreakpoint);
  window.removeEventListener("keydown", handleEscape);
});

watch(
  () => props.active,
  (active) => {
    const group = props.items.find((item) => item.children?.some((child) => child.id === active));
    if (group) expandedGroup.value = group.id;
    if (mobileExpandedGroup.value && mobileExpandedGroup.value !== group?.id) {
      mobileExpandedGroup.value = "";
    }
  },
  { immediate: true },
);

function isActive(item) {
  return props.active === item.id || item.children?.some((child) => child.id === props.active);
}

function selectItem(item) {
  if (!item.children?.length) {
    closeMobileSubmenu();
    emit("select", item.id);
    return;
  }

  if (isMobile.value) {
    if (mobileExpandedGroup.value === item.id) {
      closeMobileSubmenu(true);
    } else {
      mobileExpandedGroup.value = item.id;
      if (!item.children.some((child) => child.id === props.active)) {
        emit("select", item.children[0].id);
      }
      nextTick(() => mobileSubmenu.value?.querySelector("button")?.focus());
    }
    return;
  }

  expandedGroup.value = expandedGroup.value === item.id ? "" : item.id;
  if (!item.children.some((child) => child.id === props.active)) {
    emit("select", item.children[0].id);
  }
}

function selectMobileChild(child) {
  emit("select", child.id);
  closeMobileSubmenu(true);
}
</script>

<template>
  <aside class="profile-sidebar overview-navigation" :aria-label="`${roleLabel} navigation`">
    <button
      class="sidebar-brand"
      type="button"
      title="Dashboard"
      aria-label="Open dashboard"
      @click="emit('select', items[0]?.id)"
    >
      <img src="/assets/logo.png" alt="" />
      <span class="sidebar-brand-copy">
        <strong>BORJA</strong>
        <small>DENTAL CLINIC</small>
      </span>
    </button>
    <nav class="side-nav">
      <div v-for="item in items" :key="item.id" class="side-nav-item">
        <button
          :id="item.children?.length ? `sidebar-group-${item.id}` : undefined"
          type="button"
          class="sidebar-nav-button"
          :class="{ active: isActive(item) }"
          :title="item.label"
          :aria-current="props.active === item.id ? 'page' : undefined"
          :aria-expanded="
            item.children?.length
              ? isMobile
                ? mobileExpandedGroup === item.id
                : expandedGroup === item.id
              : undefined
          "
          :aria-controls="
            item.children?.length &&
            (isMobile ? mobileExpandedGroup === item.id : expandedGroup === item.id)
              ? isMobile
                ? `mobile-sidebar-submenu-${item.id}`
                : `sidebar-submenu-${item.id}`
              : undefined
          "
          :aria-haspopup="item.children?.length && isMobile ? 'dialog' : undefined"
          @click="selectItem(item)"
        >
          <span class="sidebar-icon-wrap">
            <component :is="item.icon" class="nav-icon" :size="21" aria-hidden="true" />
          </span>
          <span class="sidebar-nav-label">{{ item.shortLabel || item.label }}</span>
          <ChevronDown
            v-if="item.children?.length"
            class="sidebar-nav-chevron"
            :class="{ open: expandedGroup === item.id }"
            :size="15"
            aria-hidden="true"
          />
        </button>
        <div
          v-if="item.children?.length && expandedGroup === item.id"
          :id="`sidebar-submenu-${item.id}`"
          class="side-nav-submenu"
        >
          <button
            v-for="child in item.children"
            :key="child.id"
            type="button"
            :class="{ active: active === child.id }"
            :aria-current="active === child.id ? 'page' : undefined"
            @click="emit('select', child.id)"
          >
            <component :is="child.icon" :size="15" aria-hidden="true" />
            <span class="sidebar-nav-label">{{ child.label }}</span>
          </button>
        </div>
      </div>
    </nav>
    <button
      class="sidebar-account"
      type="button"
      :class="{ active: active === profilePanelId }"
      :title="`View ${user.name}'s profile`"
      :aria-current="active === profilePanelId ? 'page' : undefined"
      @click="emit('select', profilePanelId)"
    >
      <AvatarBadge :name="user.name" :image="user.profile_image" />
      <span class="sidebar-profile-copy">
        <strong>{{ user.name }}</strong>
        <small>View Profile</small>
      </span>
    </button>
    <button
      class="sidebar-logout"
      type="button"
      title="Log out"
      aria-label="Log out"
      @click="emit('logout')"
    >
      <LogOut :size="20" aria-hidden="true" />
      <span>Logout</span>
    </button>
  </aside>
  <Teleport to="body">
    <template v-if="isMobile && mobileGroup">
      <button
        class="mobile-sidebar-submenu-backdrop"
        type="button"
        :aria-label="`Close ${mobileGroup.label} menu`"
        @click="closeMobileSubmenu(true)"
      ></button>
      <div
        :id="`mobile-sidebar-submenu-${mobileGroup.id}`"
        ref="mobileSubmenu"
        class="mobile-sidebar-submenu"
        role="dialog"
        :aria-label="`${mobileGroup.label} sections`"
      >
        <div class="mobile-sidebar-submenu-heading">
          <strong>{{ mobileGroup.label }} sections</strong>
          <button
            type="button"
            :aria-label="`Close ${mobileGroup.label} menu`"
            @click="closeMobileSubmenu(true)"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </div>
        <nav :aria-label="`${mobileGroup.label} pages`">
          <button
            v-for="child in mobileGroup.children"
            :key="child.id"
            type="button"
            :class="{ active: active === child.id }"
            :aria-current="active === child.id ? 'page' : undefined"
            @click="selectMobileChild(child)"
          >
            <component :is="child.icon" :size="19" aria-hidden="true" />
            <span>{{ child.label }}</span>
          </button>
        </nav>
      </div>
    </template>
  </Teleport>
</template>
