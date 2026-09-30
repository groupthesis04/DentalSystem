<script setup>
import {
  CalendarDays,
  CircleCheck,
  CircleX,
  ClipboardList,
  Clock3,
  Coins,
  CreditCard,
  FileText,
  MessageCircle,
  NotebookText,
  Scale,
  UserRound,
  UserRoundCheck,
} from "lucide-vue-next";
import { computed } from "vue";

import {
  formatDate,
  formatMoney,
  statusLabel,
  treatmentBalance,
  treatmentProcedure,
} from "../services/format";
import BaseModal from "./BaseModal.vue";

const props = defineProps({ record: { type: Object, required: true } });
const emit = defineEmits(["close"]);

const fields = computed(() => {
  const record = props.record;
  const status = String(record.status || "")
    .trim()
    .toLowerCase();
  const treatmentStatus = status && status !== "paid" && status !== "unpaid" ? status : "completed";
  const statusTone =
    treatmentStatus === "completed" ? "green" : treatmentStatus === "cancelled" ? "red" : "amber";
  const statusIcon =
    treatmentStatus === "completed"
      ? CircleCheck
      : treatmentStatus === "cancelled"
        ? CircleX
        : Clock3;

  return [
    { label: "Patient", value: record.patient_name || "Patient", icon: UserRound },
    { label: "Date", value: formatDate(record.treatment_date), icon: CalendarDays },
    { label: "Tooth No./s", value: record.tooth_numbers || "-", icon: "tooth" },
    { label: "Procedure", value: treatmentProcedure(record), icon: ClipboardList },
    { label: "Diagnosis", value: record.diagnosis || "-", icon: FileText },
    { label: "Medical Instruction", value: record.prescription || "-", icon: NotebookText },
    { label: "Charged", value: formatMoney(record.amount_charged), icon: Coins, tone: "green" },
    { label: "Paid", value: formatMoney(record.amount_paid), icon: CreditCard },
    { label: "Balance", value: formatMoney(treatmentBalance(record)), icon: Scale, tone: "amber" },
    {
      label: "Remarks",
      value: record.remarks || record.notes || "-",
      icon: MessageCircle,
      tone: "purple",
    },
    { label: "Dentist", value: record.doctor_name || "-", icon: UserRoundCheck },
    {
      label: "Status",
      value: statusLabel(treatmentStatus),
      icon: statusIcon,
      tone: statusTone,
      status: true,
    },
    { label: "Next Visit", value: formatDate(record.next_visit), icon: CalendarDays, wide: true },
  ];
});
</script>

<template>
  <BaseModal
    title="Treatment Details"
    eyebrow="Patient record"
    size-class="treatment-details-dialog"
    @close="emit('close')"
  >
    <template #header-icon>
      <span class="treatment-details-header-icon" aria-hidden="true">
        <svg
          viewBox="0 0 32 32"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path
            d="M16 6.7c-2.8-1.8-6.2-2.5-8.5-.4-2.4 2.2-2.3 6-.8 9.4l3.4 9.5c.5 1.4 2.4 1.3 2.9-.1l1.8-5.3c.4-1.2 2-1.2 2.4 0l1.8 5.3c.5 1.4 2.4 1.5 2.9.1l3.4-9.5c1.5-3.4 1.6-7.2-.8-9.4-2.3-2.1-5.7-1.4-8.5.4Z"
          />
          <path d="M16 6.7c1.2.8 2.5 1.2 3.9 1.3" />
        </svg>
      </span>
    </template>
    <template #subtitle>
      <p class="treatment-details-subtitle">
        View the complete details of this patient's treatment record.
      </p>
    </template>

    <div class="treatment-detail-grid">
      <article
        v-for="field in fields"
        :key="field.label"
        class="treatment-detail-card"
        :class="{ wide: field.wide }"
      >
        <span
          class="treatment-detail-icon"
          :class="`tone-${field.tone || 'blue'}`"
          aria-hidden="true"
        >
          <svg
            v-if="field.icon === 'tooth'"
            viewBox="0 0 32 32"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path
              d="M16 6.7c-2.8-1.8-6.2-2.5-8.5-.4-2.4 2.2-2.3 6-.8 9.4l3.4 9.5c.5 1.4 2.4 1.3 2.9-.1l1.8-5.3c.4-1.2 2-1.2 2.4 0l1.8 5.3c.5 1.4 2.4 1.5 2.9.1l3.4-9.5c1.5-3.4 1.6-7.2-.8-9.4-2.3-2.1-5.7-1.4-8.5.4Z"
            />
            <path d="M16 6.7c1.2.8 2.5 1.2 3.9 1.3" />
          </svg>
          <component v-else :is="field.icon" :size="25" :stroke-width="2" />
        </span>
        <span class="treatment-detail-copy">
          <span class="treatment-detail-label">{{ field.label }}</span>
          <strong v-if="field.status" class="treatment-status-pill" :class="`tone-${field.tone}`">
            {{ field.value }}
          </strong>
          <strong v-else class="treatment-detail-value">{{ field.value }}</strong>
        </span>
      </article>
    </div>
  </BaseModal>
</template>

<style scoped>
:global(.crud-dialog.treatment-details-dialog) {
  width: min(1000px, calc(100% - 16px));
  border: 1px solid #dbe6f2;
  border-radius: 15px;
  color: #0e224b;
}

:global(.treatment-details-dialog .crud-dialog-header) {
  border-bottom: 0;
  padding: 22px 23px 11px;
}

:global(.treatment-details-dialog .crud-dialog-heading-with-icon) {
  gap: 25px;
}

.treatment-details-header-icon {
  display: grid;
  width: 80px;
  height: 80px;
  flex: 0 0 80px;
  place-items: center;
  border-radius: 50%;
  background: #e7f2ff;
  color: #1675ea;
}

.treatment-details-header-icon svg {
  width: 44px;
  height: 44px;
}

:global(.treatment-details-dialog .section-kicker) {
  color: #81afe5;
  font-size: 0.76rem;
  font-weight: 850;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

:global(.treatment-details-dialog .crud-dialog-header h2) {
  margin: 3px 0 0;
  color: #0d2050;
  font-size: 1.9rem;
  line-height: 1.08;
}

.treatment-details-subtitle {
  margin: 5px 0 0;
  color: #667594;
  font-size: 0.96rem;
  line-height: 1.35;
}

:global(.treatment-details-dialog .icon-button) {
  width: 44px;
  height: 44px;
  flex-basis: 44px;
  border-color: #dce6f1;
  border-radius: 12px;
  background: #f4f7fb;
  color: #293c60;
}

.treatment-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 8px 22px 14px;
}

.treatment-detail-card {
  display: flex;
  min-width: 0;
  min-height: 80px;
  align-items: center;
  gap: 24px;
  border: 1px solid #dde8f3;
  border-radius: 13px;
  background: linear-gradient(115deg, #fbfdff 0%, #ffffff 65%, #f9fbfe 100%);
  padding: 10px 14px;
}

.treatment-detail-card.wide {
  grid-column: 1 / -1;
}

.treatment-detail-icon {
  display: grid;
  width: 56px;
  height: 56px;
  flex: 0 0 56px;
  place-items: center;
  border-radius: 50%;
}

.treatment-detail-icon svg {
  width: 27px;
  height: 27px;
}

.tone-blue {
  background: #e9f3ff;
  color: #1375ec;
}

.tone-green {
  background: #e5f9ef;
  color: #078447;
}

.tone-amber {
  background: #fff1dc;
  color: #c77605;
}

.tone-purple {
  background: #f0ebff;
  color: #5c3bd7;
}

.tone-red {
  background: #ffe9ed;
  color: #ce3650;
}

.treatment-detail-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.treatment-detail-label {
  color: #66738f;
  font-size: 0.71rem;
  font-weight: 850;
  line-height: 1.1;
  text-transform: uppercase;
}

.treatment-detail-value {
  color: #0d2050;
  font-size: 1.05rem;
  font-weight: 850;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.treatment-status-pill {
  min-width: 122px;
  border-radius: 999px;
  padding: 7px 14px;
  font-size: 0.85rem;
  font-weight: 850;
  line-height: 1;
  text-align: center;
}

:global(html[data-dashboard-theme="dark"] .crud-dialog.treatment-details-dialog),
:global(html[data-dashboard-theme="dark"] .treatment-details-dialog .crud-dialog-header) {
  border-color: #33455e;
  background: #192536;
  color: #ecf4ff;
}

:global(html[data-dashboard-theme="dark"] .treatment-details-dialog .crud-dialog-header h2),
:global(html[data-dashboard-theme="dark"] .treatment-detail-value) {
  color: #f1f6ff;
}

:global(html[data-dashboard-theme="dark"] .treatment-details-dialog .icon-button),
:global(html[data-dashboard-theme="dark"] .treatment-detail-card) {
  border-color: #344861;
  background: #202f42;
}

:global(html[data-dashboard-theme="dark"] .treatment-details-subtitle),
:global(html[data-dashboard-theme="dark"] .treatment-detail-label) {
  color: #adbed6;
}

@media (max-width: 640px) {
  :global(.crud-dialog.treatment-details-dialog) {
    width: calc(100% - 8px);
    max-height: calc(100dvh - 16px);
  }

  :global(.treatment-details-dialog .crud-dialog-shell) {
    max-height: calc(100dvh - 16px);
  }

  :global(.treatment-details-dialog .crud-dialog-header) {
    gap: 10px;
    padding: 17px 15px 9px;
  }

  :global(.treatment-details-dialog .crud-dialog-heading-with-icon) {
    gap: 12px;
  }

  .treatment-details-header-icon {
    width: 54px;
    height: 54px;
    flex-basis: 54px;
  }

  .treatment-details-header-icon svg {
    width: 32px;
    height: 32px;
  }

  :global(.treatment-details-dialog .crud-dialog-header h2) {
    font-size: 1.3rem;
  }

  .treatment-details-subtitle {
    font-size: 0.77rem;
  }

  :global(.treatment-details-dialog .icon-button) {
    width: 36px;
    height: 36px;
    flex-basis: 36px;
  }

  .treatment-detail-grid {
    grid-template-columns: 1fr;
    gap: 9px;
    padding: 8px 13px 15px;
  }

  .treatment-detail-card {
    min-height: 69px;
    gap: 13px;
    padding: 9px 11px;
  }

  .treatment-detail-icon {
    width: 46px;
    height: 46px;
    flex-basis: 46px;
  }

  .treatment-detail-icon svg {
    width: 23px;
    height: 23px;
  }

  .treatment-detail-value {
    font-size: 0.94rem;
  }
}
</style>
