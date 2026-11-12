<template>
  <div
    role="gridcell"
    class="slot-cell"
    :class="{
      'bg-gray-50': !practitioner.is_available,
      'current-time': isCurrent,
    }"
    :aria-label="ariaLabel"
    @click="open"
    @keydown.enter.prevent="open"
    @keydown.space.prevent="open"
  >
    <AppointmentCard
      v-if="kind === 'appointment'"
      :appointment="appointment"
    />

    <div
      v-else-if="kind === 'break'"
      class="break-slot"
      :title="timeSlot.breakLabel"
    >
      <span class="text-xs font-bold text-orange-800">{{
        timeSlot.breakLabel || "Break"
      }}</span>
    </div>

    <div
      v-else-if="kind === 'add'"
      class="add-appointment-button group cursor-pointer"
      :title="`Create appointment for ${practitioner.name} at ${timeSlot.display}`"
    >
      <FeatherIcon
        name="plus"
        class="h-4 w-4 text-gray-900 group-hover:text-blue-600"
      />
      <span class="text-xs font-bold text-gray-900 group-hover:text-blue-600"
        >Add</span
      >
    </div>

    <div v-else class="unavailable-slot" :title="unavailableReason">
      <span class="text-xs font-bold text-gray-600">—</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import AppointmentCard from "./AppointmentCard.vue";

const props = defineProps({
  timeSlot: { type: Object, required: true },
  practitioner: { type: Object, required: true },
  appointment: { type: Object, default: null },
  isCurrent: { type: Boolean, default: false },
  isPast: { type: Boolean, default: false },
});

const emit = defineEmits(["view", "create"]);

const kind = computed(() => {
  if (props.appointment) return "appointment";
  if (props.timeSlot.isDuringBreak) return "break";
  if (!props.isPast && props.practitioner.is_available) return "add";
  return "unavailable";
});

const unavailableReason = computed(() =>
  props.isPast ? "Past time slot" : "Practitioner unavailable"
);

const ariaLabel = computed(() => {
  const prefix = `${props.practitioner.name}, ${props.timeSlot.display}`;
  if (kind.value === "appointment") {
    const { patient_name, status } = props.appointment;
    return `${prefix}, ${patient_name || "Unknown Patient"}, ${status}`;
  }
  if (kind.value === "break")
    return `${prefix}, ${props.timeSlot.breakLabel || "Break"}`;
  if (kind.value === "add") return `${prefix}, free`;
  return `${prefix}, ${unavailableReason.value}`;
});

const open = () => {
  if (kind.value === "appointment") emit("view", props.appointment);
  else if (kind.value === "add")
    emit("create", props.timeSlot.time, props.practitioner);
};
</script>

<style scoped>
.slot-cell {
  display: flex;
  padding: 2px calc(2px + var(--column-gap)) 8px 2px;
  outline: none;
  box-shadow: inset 0 1px 0 #e5e7eb;
  transition: background-color 150ms;
}

.slot-cell:hover {
  background-color: #eff6ff;
}

.slot-cell:focus-visible {
  box-shadow: inset 0 0 0 2px #3b82f6;
}

.slot-cell.current-time {
  background-color: #fef2f2;
}

.add-appointment-button,
.unavailable-slot,
.break-slot {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px dotted #9ca3af;
  border-radius: 0.375rem;
}

.add-appointment-button {
  background-color: #f8f9fa;
  transition-property: background-color, border-color;
  transition-duration: 150ms;
}

.add-appointment-button:hover {
  background-color: #bfdbfe;
  border-color: #2563eb;
}

.unavailable-slot {
  color: #4b5563;
  background-color: #e5e7eb;
}

.break-slot {
  background-color: #fed7aa;
  color: #9a3412;
  border-color: #f97316;
}

@media (prefers-reduced-motion: reduce) {
  .slot-cell,
  .add-appointment-button {
    transition: none;
  }
}
</style>
