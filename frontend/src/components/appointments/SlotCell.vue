<template>
  <div
    ref="cell"
    role="gridcell"
    class="slot-cell"
    :class="{
      'bg-gray-50': !practitioner.is_available,
      'current-time': isCurrent,
    }"
    :aria-label="ariaLabel"
    @click="open"
    @keydown.enter.prevent="openFromKeyboard"
    @keydown.space.prevent="openFromKeyboard"
  >
    <template v-if="kind === 'appointment'">
      <AppointmentCard :appointment="appointments[0]" />
      <!-- stop: the chip opens the list, not the first appointment -->
      <div v-if="appointments.length > 1" class="more-chip" @click.stop>
        <Popover v-model:show="isListOpen" placement="bottom-end">
          <template #target>
            <button
              type="button"
              tabindex="-1"
              class="rounded-full bg-gray-900 px-1.5 text-xs font-bold text-white"
              :aria-label="`Show all ${appointments.length} appointments`"
              :aria-expanded="isListOpen"
              @click="isListOpen = !isListOpen"
            >
              +{{ appointments.length - 1 }}
            </button>
          </template>
          <template #body-main>
            <ul
              class="min-w-48 p-1"
              :aria-label="`Appointments at ${timeSlot.display}`"
              @keydown.esc.prevent="closeList"
              @keydown.down.prevent="moveListFocus(1)"
              @keydown.up.prevent="moveListFocus(-1)"
            >
              <li v-for="appointment in appointments" :key="appointment.name">
                <button
                  ref="listItems"
                  type="button"
                  class="flex w-full rounded px-2 py-1 text-left text-sm hover:bg-gray-100 focus:bg-gray-100 focus:outline-none"
                  @click="viewFromList(appointment)"
                >
                  {{ appointment.appointment_time }}
                  {{ appointment.patient_name || "Unknown Patient" }}
                </button>
              </li>
            </ul>
          </template>
        </Popover>
      </div>
    </template>

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
      <span
        aria-hidden="true"
        class="text-base font-bold leading-none text-gray-900 group-hover:text-blue-600"
        >+</span
      >
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
import { Popover } from "frappe-ui";
import { computed, nextTick, ref } from "vue";
import AppointmentCard from "./AppointmentCard.vue";

const props = defineProps({
  timeSlot: { type: Object, required: true },
  practitioner: { type: Object, required: true },
  appointments: { type: Array, required: true },
  isCurrent: { type: Boolean, default: false },
  isPast: { type: Boolean, default: false },
});

const emit = defineEmits(["view", "create"]);
const cell = ref(null);
const listItems = ref([]);
const isListOpen = ref(false);

const kind = computed(() => {
  if (props.appointments.length) return "appointment";
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
    const [{ patient_name, status }, ...others] = props.appointments;
    const more = others.length ? `, and ${others.length} more` : "";
    return `${prefix}, ${patient_name || "Unknown Patient"}, ${status}${more}`;
  }
  if (kind.value === "break")
    return `${prefix}, ${props.timeSlot.breakLabel || "Break"}`;
  if (kind.value === "add") return `${prefix}, free`;
  return `${prefix}, ${unavailableReason.value}`;
});

const openList = async () => {
  isListOpen.value = true;
  await nextTick();
  listItems.value[0]?.focus();
};

const closeList = () => {
  isListOpen.value = false;
  cell.value.focus();
};

const moveListFocus = (step) => {
  const items = listItems.value;
  const index = items.indexOf(document.activeElement);
  items[(index + step + items.length) % items.length]?.focus();
};

const viewFromList = (appointment) => {
  isListOpen.value = false;
  emit("view", appointment);
};

const openFromKeyboard = () => {
  if (props.appointments.length > 1) openList();
  else open();
};

const open = () => {
  if (kind.value === "appointment") emit("view", props.appointments[0]);
  else if (kind.value === "add")
    emit("create", props.timeSlot.time, props.practitioner);
};
</script>

<style scoped>
.slot-cell {
  position: relative;
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

.more-chip {
  position: absolute;
  right: calc(6px + var(--column-gap));
  bottom: 12px;
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
