<script setup>
import { ChevronDown, LogOut } from "lucide-vue-next";
import { ref, watch } from "vue";

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

watch(
  () => props.active,
  (active) => {
    const group = props.items.find((item) => item.children?.some((child) => child.id === active));
    if (group) expandedGroup.value = group.id;
  },
  { immediate: true },
);

function isActive(item) {
  return props.active === item.id || item.children?.some((child) => child.id === props.active);
}

function selectItem(item) {
  if (!item.children?.length) {
    emit("select", item.id);
    return;
  }

  expandedGroup.value = expandedGroup.value === item.id ? "" : item.id;
  if (!item.children.some((child) => child.id === props.active)) {
    emit("select", item.children[0].id);
  }
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
          type="button"
          class="sidebar-nav-button"
          :class="{ active: isActive(item) }"
          :title="item.label"
          :aria-current="props.active === item.id ? 'page' : undefined"
          :aria-expanded="item.children?.length ? expandedGroup === item.id : undefined"
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
        <div v-if="item.children?.length && expandedGroup === item.id" class="side-nav-submenu">
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
</template>
