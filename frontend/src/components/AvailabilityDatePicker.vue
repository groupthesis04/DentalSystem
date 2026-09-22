<script setup>
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";

import { localDateIso } from "../services/format";

const props = defineProps({
  modelValue: { type: String, default: "" },
  availableDates: { type: Array, default: () => [] },
  placeholder: { type: String, default: "Select a date" },
  ariaLabel: { type: String, default: "Select an available appointment date" },
  disabled: { type: Boolean, default: false },
  clearable: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue", "open"]);

const root = ref(null);
const trigger = ref(null);
const isOpen = ref(false);
const today = localDateIso();
const calendarId = `availability-calendar-${useId().replaceAll(":", "")}`;
const monthCursor = ref(startOfMonth(parseIsoDate(today)));
const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const normalizedDates = computed(() =>
  [...new Set(props.availableDates.map(String).filter((date) => /^\d{4}-\d{2}-\d{2}$/.test(date)))]
    .filter((date) => date >= today)
    .sort(),
);
const availableSet = computed(() => new Set(normalizedDates.value));
const firstAvailableDate = computed(() => normalizedDates.value[0] || "");
const selectedLabel = computed(() => formatLongDate(props.modelValue) || props.placeholder);
const monthLabel = computed(() =>
  monthCursor.value.toLocaleDateString(undefined, { month: "long", year: "numeric" }),
);
const minMonth = computed(() => startOfMonth(parseIsoDate(today)));
const maxMonth = computed(() => {
  const date = parseIsoDate(today);
  date.setFullYear(date.getFullYear() + 1);
  return startOfMonth(date);
});
const canGoPrevious = computed(() => monthKey(monthCursor.value) > monthKey(minMonth.value));
const canGoNext = computed(() => monthKey(monthCursor.value) < monthKey(maxMonth.value));
const calendarDays = computed(() => {
  const year = monthCursor.value.getFullYear();
  const month = monthCursor.value.getMonth();
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cellCount = Math.ceil((firstWeekday + daysInMonth) / 7) * 7;

  return Array.from({ length: cellCount }, (_, index) => {
    const date = new Date(year, month, 1 - firstWeekday + index);
    const iso = localDateIso(date);
    const inCurrentMonth = date.getMonth() === month;
    const available = inCurrentMonth && availableSet.value.has(iso);
    return {
      iso,
      day: date.getDate(),
      inCurrentMonth,
      available,
      selected: iso === props.modelValue,
      today: iso === today,
      label: `${formatLongDate(iso)}, ${available ? "available" : "not available"}`,
    };
  });
});

function parseIsoDate(value) {
  const [year, month, day] = String(value || "")
    .split("-")
    .map(Number);
  if (!year || !month || !day) return new Date();
  return new Date(year, month - 1, day);
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function monthKey(date) {
  return date.getFullYear() * 12 + date.getMonth();
}

function formatLongDate(value) {
  if (!value) return "";
  const date = parseIsoDate(value);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function setVisibleMonth(value = "") {
  const target = value || firstAvailableDate.value || today;
  monthCursor.value = startOfMonth(parseIsoDate(target));
}

function toggleCalendar() {
  if (props.disabled) return;
  if (isOpen.value) {
    closeCalendar();
    return;
  }
  setVisibleMonth(props.modelValue);
  isOpen.value = true;
  emit("open");
}

function closeCalendar({ restoreFocus = false } = {}) {
  if (!isOpen.value) return;
  isOpen.value = false;
  if (restoreFocus) trigger.value?.focus();
}

function moveMonth(offset) {
  const next = new Date(monthCursor.value.getFullYear(), monthCursor.value.getMonth() + offset, 1);
  if (monthKey(next) < monthKey(minMonth.value) || monthKey(next) > monthKey(maxMonth.value))
    return;
  monthCursor.value = next;
}

function chooseDate(day) {
  if (!day.available) return;
  emit("update:modelValue", day.iso);
  closeCalendar({ restoreFocus: true });
}

function clearDate() {
  emit("update:modelValue", "");
  closeCalendar({ restoreFocus: true });
}

function onDocumentPointerDown(event) {
  if (isOpen.value && root.value && !root.value.contains(event.target)) closeCalendar();
}

function onDocumentKeydown(event) {
  if (event.key === "Escape" && isOpen.value) {
    event.stopPropagation();
    closeCalendar({ restoreFocus: true });
  }
}

watch(
  () => props.modelValue,
  (value) => {
    if (value) setVisibleMonth(value);
  },
);
watch(firstAvailableDate, (value, previousValue) => {
  if (isOpen.value && value && !props.modelValue && value !== previousValue) setVisibleMonth(value);
});

onMounted(() => {
  document.addEventListener("pointerdown", onDocumentPointerDown);
  document.addEventListener("keydown", onDocumentKeydown, true);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown);
  document.removeEventListener("keydown", onDocumentKeydown, true);
});
</script>

<template>
  <div ref="root" class="availability-date-picker" :class="{ open: isOpen }">
    <button
      ref="trigger"
      class="availability-date-trigger"
      type="button"
      :disabled="disabled"
      :aria-label="ariaLabel"
      aria-haspopup="dialog"
      :aria-expanded="isOpen"
      :aria-controls="calendarId"
      @click="toggleCalendar"
    >
      <CalendarDays :size="17" aria-hidden="true" />
      <span :class="{ placeholder: !modelValue }">{{ selectedLabel }}</span>
      <ChevronDown :size="16" aria-hidden="true" />
    </button>

    <Transition name="availability-calendar">
      <section
        v-if="isOpen"
        :id="calendarId"
        class="availability-calendar-popover"
        role="dialog"
        :aria-label="ariaLabel"
      >
        <header class="availability-calendar-header">
          <button
            type="button"
            title="Previous month"
            aria-label="Previous month"
            :disabled="!canGoPrevious"
            @click="moveMonth(-1)"
          >
            <ChevronLeft :size="18" />
          </button>
          <strong aria-live="polite">{{ monthLabel }}</strong>
          <button
            type="button"
            title="Next month"
            aria-label="Next month"
            :disabled="!canGoNext"
            @click="moveMonth(1)"
          >
            <ChevronRight :size="18" />
          </button>
        </header>

        <div class="availability-weekdays" aria-hidden="true">
          <span v-for="weekday in weekdays" :key="weekday">{{ weekday }}</span>
        </div>
        <div class="availability-calendar-grid" role="grid">
          <button
            v-for="day in calendarDays"
            :key="day.iso"
            type="button"
            role="gridcell"
            :disabled="!day.available"
            :aria-label="day.label"
            :aria-selected="day.selected"
            :class="{
              outside: !day.inCurrentMonth,
              available: day.available,
              selected: day.selected,
              today: day.today,
            }"
            @click="chooseDate(day)"
          >
            {{ day.day }}
          </button>
        </div>

        <footer class="availability-calendar-footer">
          <div class="availability-calendar-legend">
            <span><i class="available"></i>Available</span>
            <span><i></i>No schedule</span>
          </div>
          <p v-if="normalizedDates.length">
            {{ normalizedDates.length }} clinic date{{ normalizedDates.length === 1 ? "" : "s" }}
            currently open.
          </p>
          <p v-else>No clinic schedule is currently available.</p>
          <button
            v-if="clearable && modelValue"
            class="availability-clear-date"
            type="button"
            @click="clearDate"
          >
            Clear selected date
          </button>
        </footer>
      </section>
    </Transition>
  </div>
</template>

<style scoped>
.availability-date-picker {
  position: relative;
  width: 100%;
  min-width: 0;
  color: #173252;
  font: inherit;
}

.availability-date-trigger {
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: 44px;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  border: 1px solid #cfdde8;
  border-radius: 7px;
  background: #fff;
  padding: 9px 11px;
  color: #223e5f;
  font: inherit;
  font-weight: inherit;
  line-height: inherit;
  text-align: left;
  cursor: pointer;
}

.availability-date-trigger > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.availability-date-trigger .placeholder {
  color: #7b8da2;
  font-weight: inherit;
}

.availability-date-trigger > svg {
  flex: 0 0 auto;
  color: #0a8198;
}

.availability-date-trigger > svg:last-child {
  color: #5e738d;
  transition: transform 150ms ease;
}

.open .availability-date-trigger,
.availability-date-trigger:focus-visible {
  border-color: #0a8198;
  box-shadow: 0 0 0 3px rgb(10 129 152 / 13%);
  outline: 0;
}

.open .availability-date-trigger > svg:last-child {
  transform: rotate(180deg);
}

.availability-date-trigger:disabled {
  background: #f2f5f7;
  color: #8a98a8;
  cursor: not-allowed;
}

.availability-calendar-popover {
  position: absolute;
  z-index: 45;
  top: calc(100% + 7px);
  left: 0;
  width: min(264px, calc(100vw - 24px));
  overflow: hidden;
  border: 1px solid #cee0e8;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 18px 45px rgb(22 58 77 / 20%);
}

.availability-calendar-header {
  display: grid;
  grid-template-columns: 27px minmax(0, 1fr) 27px;
  align-items: center;
  gap: 5px;
  padding: 6px 9px 4px;
}

.availability-calendar-header strong {
  color: #173252;
  font-size: 0.74rem;
  text-align: center;
}

.availability-calendar-header button {
  display: grid;
  width: 27px;
  height: 27px;
  place-items: center;
  border: 0;
  border-radius: 6px;
  background: transparent;
  padding: 0;
  color: #39546f;
  cursor: pointer;
}

.availability-calendar-header button:hover:not(:disabled),
.availability-calendar-header button:focus-visible {
  background: #eaf7fa;
  color: #08778f;
  outline: 0;
}

.availability-calendar-header button:disabled {
  color: #bdc7d0;
  cursor: not-allowed;
}

.availability-weekdays,
.availability-calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 2px;
  padding-inline: 9px;
}

.availability-weekdays {
  padding-block: 2px 3px;
  color: #6e8093;
  font-size: 0.53rem;
  font-weight: 800;
  text-align: center;
}

.availability-calendar-grid {
  padding-bottom: 6px;
}

.availability-calendar-grid button {
  display: grid;
  width: 100%;
  min-width: 0;
  height: 25px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 5px;
  background: #f2f4f5;
  padding: 0;
  color: #9aa5ae;
  font: inherit;
  font-size: 0.58rem;
  font-weight: 750;
}

.availability-calendar-grid button.outside {
  opacity: 0.3;
}

.availability-calendar-grid button.today:not(.available) {
  border-color: #c9d4dc;
}

.availability-calendar-grid button.available {
  border-color: #c2ecef;
  background: #d8f5f5;
  color: #08758a;
  cursor: pointer;
}

.availability-calendar-grid button.available:hover,
.availability-calendar-grid button.available:focus-visible {
  border-color: #0990a8;
  background: #bcebed;
  outline: 2px solid rgb(9 144 168 / 14%);
}

.availability-calendar-grid button.selected {
  border-color: #087f96;
  background: #087f96;
  color: #fff;
  box-shadow: 0 4px 10px rgb(8 127 150 / 22%);
}

.availability-calendar-grid button:disabled {
  cursor: not-allowed;
}

.availability-calendar-footer {
  display: grid;
  gap: 3px;
  border-top: 1px solid #e2ebef;
  background: #f8fbfc;
  padding: 6px 9px 7px;
}

.availability-calendar-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 5px 9px;
}

.availability-calendar-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #607489;
  font-size: 0.53rem;
  font-weight: 700;
}

.availability-calendar-legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #d9dee2;
}

.availability-calendar-legend i.available {
  background: #a7e6e7;
}

.availability-calendar-footer p {
  margin: 0;
  color: #718397;
  font-size: 0.52rem;
  font-weight: 600;
  line-height: 1.35;
}

.availability-clear-date {
  justify-self: start;
  border: 0;
  background: transparent;
  padding: 0;
  color: #087b92;
  font: inherit;
  font-size: 0.62rem;
  font-weight: 800;
  cursor: pointer;
}

.availability-clear-date:hover,
.availability-clear-date:focus-visible {
  text-decoration: underline;
  outline: 0;
}

.availability-calendar-enter-active,
.availability-calendar-leave-active {
  transition:
    opacity 120ms ease,
    transform 120ms ease;
  transform-origin: top left;
}

.availability-calendar-enter-from,
.availability-calendar-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.985);
}

:global(html[data-dashboard-theme="dark"]) .availability-date-trigger,
:global(html[data-dashboard-theme="dark"]) .availability-calendar-popover {
  border-color: #3a485b;
  background: #111821;
  color: #dce7f4;
}

:global(html[data-dashboard-theme="dark"]) .availability-date-trigger > span,
:global(html[data-dashboard-theme="dark"]) .availability-calendar-header strong {
  color: #dce7f4;
}

:global(html[data-dashboard-theme="dark"]) .availability-date-trigger .placeholder,
:global(html[data-dashboard-theme="dark"]) .availability-weekdays,
:global(html[data-dashboard-theme="dark"]) .availability-calendar-footer p,
:global(html[data-dashboard-theme="dark"]) .availability-calendar-legend span {
  color: #9eacc0;
}

:global(html[data-dashboard-theme="dark"]) .availability-calendar-grid button {
  background: #202b39;
  color: #77869a;
}

:global(html[data-dashboard-theme="dark"]) .availability-calendar-grid button.available {
  border-color: #216d78;
  background: #17434a;
  color: #a7edf0;
}

:global(html[data-dashboard-theme="dark"]) .availability-calendar-grid button.selected {
  border-color: #20a7ba;
  background: #0d8297;
  color: #fff;
}

:global(html[data-dashboard-theme="dark"]) .availability-calendar-footer {
  border-color: #344154;
  background: #17212e;
}

@media (max-width: 420px) {
  .availability-date-trigger {
    gap: 5px;
    padding-inline: 7px;
    font-size: 0.68rem;
  }

  .availability-calendar-popover {
    width: min(264px, calc(100vw - 28px));
  }
}
</style>
