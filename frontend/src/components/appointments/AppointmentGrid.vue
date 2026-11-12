<template>
  <div class="appointment-grid-container flex h-screen flex-col bg-gray-100">
    <div class="flex-shrink-0 bg-white border-b border-gray-300 shadow-sm">
      <div class="px-6 py-4">
        <div class="flex items-center justify-between flex-wrap gap-4">
          <div class="flex items-center space-x-6">
            <h1 class="text-2xl font-semibold text-black">Appointments</h1>

            <div class="flex items-center">
              <Link
                class="form-control min-w-[240px]"
                :value="selectedCompany || ''"
                doctype="Company"
                placeholder="Select Company"
                @change="handleCompanyChange"
                variant="outline"
              />
            </div>

            <div class="flex items-center space-x-2">
              <Button variant="ghost" @click="goToPreviousDay">
                <FeatherIcon name="chevron-left" class="h-4 w-4 text-black" />
              </Button>

              <DatePicker
                v-model="selectedDateForPicker"
                variant="outline"
                placeholder="Select Date"
                @change="handleDateChange"
                class="min-w-[200px]"
              />

              <Button variant="ghost" @click="goToNextDay">
                <FeatherIcon name="chevron-right" class="h-4 w-4 text-black" />
              </Button>
            </div>
          </div>

          <div class="flex items-center space-x-3">
            <TextInput
              placeholder="Search practitioners..."
              class="w-64 text-black"
              v-model="searchQuery"
            >
              <template #prefix>
                <FeatherIcon name="search" class="h-4 w-4 text-gray-600" />
              </template>
            </TextInput>
            <Button
              icon-left="refresh-cw"
              label="Refresh"
              :loading="isRefreshing"
              @click="refreshData"
            />
            <div
              v-if="canScrollLeft || canScrollRight"
              class="flex items-center space-x-1"
            >
              <Button
                icon="arrow-left"
                label="Scroll practitioners left"
                :disabled="!canScrollLeft"
                @click="scrollPractitioners(-1)"
              />
              <Button
                icon="arrow-right"
                label="Scroll practitioners right"
                :disabled="!canScrollRight"
                @click="scrollPractitioners(1)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div ref="scroller" class="grid-scroller">
      <div
        ref="grid"
        role="grid"
        aria-label="Appointments by time slot and practitioner"
        class="appointment-grid"
        :style="{
          '--columns': Math.max(
            practitionerStore.filteredPractitioners.length,
            1
          ),
        }"
        @keydown="onGridKeydown"
        @focusin="onCellFocus"
      >
        <div role="row" class="contents">
          <div role="columnheader" class="corner-cell">
            <span class="text-sm font-semibold text-gray-600">Time Slots</span>
          </div>
          <div
            v-if="practitionerStore.filteredPractitioners.length === 0"
            class="header-cell empty-header"
          >
            <span class="text-gray-500 text-sm">No practitioners found</span>
          </div>
          <div
            v-for="practitioner in practitionerStore.filteredPractitioners"
            :key="practitioner.name"
            role="columnheader"
            class="header-cell"
          >
            <PractitionerCard :practitioner="practitioner" />
          </div>
        </div>

        <div
          v-for="(slot, row) in dateStore.timeSlots"
          :key="slot.time"
          role="row"
          class="contents"
        >
          <div
            role="rowheader"
            class="time-cell"
            :class="{ 'current-time': row === currentSlotIndex }"
            :data-time-row="row"
          >
            <span class="text-sm font-bold text-gray-900">{{
              slot.display
            }}</span>
          </div>
          <SlotCell
            v-for="(
              practitioner, column
            ) in practitionerStore.filteredPractitioners"
            :key="`${slot.time}-${practitioner.name}`"
            :time-slot="slot"
            :practitioner="practitioner"
            :appointment="getAppointment(slot.time, practitioner.name)"
            :is-current="row === currentSlotIndex"
            :tabindex="
              activeCell.row === row && activeCell.column === column ? 0 : -1
            "
            :data-row="row"
            :data-column="column"
            @view="viewAppointment"
            @create="createAppointment"
          />
        </div>
      </div>
    </div>

    <AppointmentDialog
      v-model:show-dialog="showAppointmentDialog"
      :time-slot="selectedTimeSlot"
      :practitioner-data="selectedPractitioner"
      :mode="dialogMode"
      :app-data="selectedAppointmentData"
      :company="selectedCompany"
      @appointment-created="handleAppointmentCreated"
      @close-dialog="closeAppointmentDialog"
      @edit-appointment="handleEditAppointment"
      @mode-changed="handleModeChanged"
    />
  </div>
</template>

<script setup>
import { onMounted, computed, ref, nextTick, watch } from "vue";
// All Frappe UI components are now globally available from main.js
import { useAppointmentStore } from "@/data/appointment";
import { usePractitionerStore } from "@/data/practitioner";
import { useDateStore } from "@/data/date";
import { clamp, useResizeObserver, useScroll } from "@vueuse/core";
import PractitionerCard from "./PractitionerCard.vue";
import SlotCell from "./SlotCell.vue";
import AppointmentDialog from "./AppointmentDialog.vue";
import Link from "../controls/Link.vue";
import { useToast } from "@/composables/useToast";
import dayjs from "dayjs";

const appointmentStore = useAppointmentStore();
const practitionerStore = usePractitionerStore();
const dateStore = useDateStore();
const { notifications } = useToast();

const scroller = ref(null);
const grid = ref(null);

// State
const isRefreshing = ref(false);
const searchQuery = ref("");
const selectedCompany = ref("");
const selectedDateForPicker = ref("");
const userCompanies = ref([]);

// Simple appointment dialog state
const showAppointmentDialog = ref(false);
const selectedTimeSlot = ref("");
const selectedPractitioner = ref(null);
const dialogMode = ref("create");
const selectedAppointmentData = ref({});

const { arrivedState, measure } = useScroll(scroller);
useResizeObserver([scroller, grid], () => measure());
const canScrollLeft = computed(() => !arrivedState.left);
const canScrollRight = computed(() => !arrivedState.right);
const activeCell = ref({ row: 0, column: 0 });

// Initialize selectedDateForPicker with current date
onMounted(() => {
  selectedDateForPicker.value = dateStore.selectedDate;
  // Ensure selectedCompany has a default value
  if (!selectedCompany.value) {
    selectedCompany.value = "";
  }
});

// Initialize data
onMounted(async () => {
  try {
    console.log("🔄 Initializing appointment grid...");

    // Fetch user companies first
    await fetchUserCompanies();

    // Sync dates between stores initially
    appointmentStore.setSelectedDate(dateStore.selectedDate);
    selectedDateForPicker.value = dateStore.selectedDate;

    // Set initial company in appointment store if one is selected
    if (selectedCompany.value) {
      appointmentStore.setSelectedCompany(selectedCompany.value);
    }

    await Promise.all([
      dateStore.generateTimeSlots(),
      selectedCompany.value
        ? practitionerStore.fetchPractitioners(
            selectedCompany.value,
            dateStore.selectedDate
          )
        : Promise.resolve(),
    ]);

    scrollToCurrentSlot();
  } catch (error) {
    console.error("❌ Error initializing appointment grid:", error);
    notifications.error.dataLoadFailed(error.message);
  }
});

// Watch for date changes
watch(
  () => dateStore.selectedDate,
  async (newDate) => {
    console.log("🔍 DateStore date changed to:", newDate);
    selectedDateForPicker.value = newDate;
    appointmentStore.setSelectedDate(newDate); // Update appointment store date
    scrollToCurrentSlot();
    if (selectedCompany.value && selectedCompany.value.trim()) {
      practitionerStore.fetchPractitioners(
        selectedCompany.value,
        dateStore.selectedDate
      );
    }
  }
);

// Watch for company changes
watch(selectedCompany, async (newCompany) => {
  if (newCompany && newCompany.trim()) {
    appointmentStore.setSelectedCompany(newCompany);
    await Promise.all([
      practitionerStore.fetchPractitioners(newCompany, dateStore.selectedDate),
      appointmentStore.fetchAppointments(),
    ]);
  }
});

// Watch for search query changes
watch(searchQuery, (newQuery) => {
  practitionerStore.setSearchQuery(newQuery);
});

// Keep one cell reachable by Tab when the practitioner list shrinks.
watch(
  () => practitionerStore.filteredPractitioners,
  () => {
    activeCell.value = clampCell(
      activeCell.value.row,
      activeCell.value.column
    );
  }
);

const scrollPractitioners = (direction) => {
  const column = scroller.value?.querySelector(".header-cell");
  scroller.value?.scrollBy({ left: direction * 2 * column.offsetWidth });
};

const currentSlotIndex = computed(() =>
  dateStore.timeSlots.findIndex(isCurrentTimeSlot)
);

const scrollToCurrentSlot = () => {
  nextTick(() => {
    const row = currentSlotIndex.value;
    if (row < 0) return;
    activeCell.value = { row, column: activeCell.value.column };
    grid.value
      ?.querySelector(`[data-time-row="${row}"]`)
      ?.scrollIntoView({ block: "start" });
  });
};

const slotsPerHour = computed(() => Math.round(60 / dateStore.slotDuration));

function jumpToNow({ column }) {
  return currentSlotIndex.value < 0 ? null : [currentSlotIndex.value, column];
}

const keyTargets = {
  ArrowUp: ({ row, column }) => [row - 1, column],
  ArrowDown: ({ row, column }) => [row + 1, column],
  ArrowLeft: ({ row, column }) => [row, column - 1],
  ArrowRight: ({ row, column }) => [row, column + 1],
  PageUp: ({ row, column }) => [row - slotsPerHour.value, column],
  PageDown: ({ row, column }) => [row + slotsPerHour.value, column],
  Home: ({ row }) => [row, 0],
  End: ({ row }) => [row, practitionerStore.filteredPractitioners.length - 1],
  t: jumpToNow,
  T: jumpToNow,
};

const onGridKeydown = (event) => {
  const target = keyTargets[event.key];
  if (!target || event.ctrlKey || event.metaKey || event.altKey) return;
  const position = target(activeCell.value);
  if (!position) return;
  event.preventDefault();
  focusCell(...position);
};

const clampCell = (row, column) => {
  const lastRow = dateStore.timeSlots.length - 1;
  const lastColumn = practitionerStore.filteredPractitioners.length - 1;
  return {
    row: clamp(row, 0, Math.max(lastRow, 0)),
    column: clamp(column, 0, Math.max(lastColumn, 0)),
  };
};

const onCellFocus = (event) => {
  const { row, column } = event.target.dataset;
  if (row === undefined) return;
  if (activeCell.value.row === +row && activeCell.value.column === +column)
    return;
  activeCell.value = { row: +row, column: +column };
};

const focusCell = (row, column) => {
  activeCell.value = clampCell(row, column);
  nextTick(() => {
    const { row, column } = activeCell.value;
    const cell = grid.value?.querySelector(
      `[data-row="${row}"][data-column="${column}"]`
    );
    cell?.focus({ preventScroll: true });
    cell?.scrollIntoView({ block: "nearest", inline: "nearest" });
  });
};

// Helper functions
const getAppointment = (timeSlot, practitionerId) => {
  const key = `${timeSlot}-${practitionerId}`;
  const appointment = appointmentStore.appointmentsByTimeSlot[key];

  return appointment;
};

const isCurrentTimeSlot = (slot) => {
  if (!dateStore.isToday) return false;

  const now = dayjs();
  const slotTime = dayjs(`${dateStore.selectedDate} ${slot.time}`);
  const nextSlotTime = slotTime.add(dateStore.slotDuration, "minute");

  return now.isAfter(slotTime) && now.isBefore(nextSlotTime);
};

// Date navigation functions
const goToPreviousDay = () => {
  dateStore.goToPreviousDay();
};

const goToNextDay = () => {
  dateStore.goToNextDay();
};

// Handle date change from DatePicker
const handleDateChange = async (selectedDate) => {
  if (selectedDate) {
    console.log("🔍 Date picker changed to:", selectedDate);
    dateStore.setSelectedDate(selectedDate);

    await Promise.all([
      practitionerStore.fetchPractitioners(
        selectedCompany.value,
        selectedDate
      ),
      appointmentStore.fetchAppointments(),
    ]);

    selectedDateForPicker.value = selectedDate;
  }
};

// Handle company change from Link component
const handleCompanyChange = async (selectedCompanyValue) => {
  if (selectedCompanyValue && typeof selectedCompanyValue === "string") {
    selectedCompany.value = selectedCompanyValue;

    await Promise.all([
      practitionerStore.fetchPractitioners(
        selectedCompanyValue,
        dateStore.selectedDate
      ),
      appointmentStore.setSelectedCompany(selectedCompanyValue),
    ]);

    console.log("Company changed to:", selectedCompanyValue);
  } else if (selectedCompanyValue && selectedCompanyValue.name) {
    // Handle if Link component returns an object
    selectedCompany.value = selectedCompanyValue.name;

    await Promise.all([
      practitionerStore.fetchPractitioners(
        selectedCompanyValue.name,
        dateStore.selectedDate
      ),
      appointmentStore.setSelectedCompany(selectedCompanyValue.name),
    ]);

    console.log("Company changed to:", selectedCompanyValue.name);
  }
};

// Fetch user companies function
const fetchUserCompanies = async () => {
  try {
    // Mock data for now - replace with actual API call
    userCompanies.value = [
      { name: "Nephro One Dialysis Clinic" },
      // { name: 'Shree Hindu Mandal Hospital - Mwanza' },
    ];

    // Set default company if none selected
    if (userCompanies.value.length > 0 && !selectedCompany.value) {
      selectedCompany.value = userCompanies.value[0].name;
    }
  } catch (error) {
    console.error("Error fetching user companies:", error);
    userCompanies.value = [{ name: "Default Company" }];
    selectedCompany.value = "Default Company";
  }
};

// Event handlers
const createAppointment = (timeSlot, practitioner) => {
  // Immediate state update for fast dialog opening
  selectedTimeSlot.value = timeSlot;
  selectedPractitioner.value = practitioner;
  dialogMode.value = "create";
  selectedAppointmentData.value = {};

  // Use nextTick for immediate UI update
  nextTick(() => {
    showAppointmentDialog.value = true;
  });
};

const viewAppointment = (appointment) => {
  selectedAppointmentData.value = appointment;
  dialogMode.value = "view";
  showAppointmentDialog.value = true;
};

const closeAppointmentDialog = () => {
  showAppointmentDialog.value = false;
  selectedTimeSlot.value = "";
  selectedPractitioner.value = null;
  selectedAppointmentData.value = {};
  dialogMode.value = "create";
};

const refreshData = async () => {
  if (isRefreshing.value) return;

  isRefreshing.value = true;
  try {
    await Promise.all([
      dateStore.generateTimeSlots(),
      selectedCompany.value && selectedCompany.value.trim()
        ? practitionerStore.fetchPractitioners(
            selectedCompany.value,
            dateStore.selectedDate
          )
        : Promise.resolve(),
      selectedCompany.value && selectedCompany.value.trim()
        ? appointmentStore.fetchAppointments()
        : Promise.resolve(),
    ]);
    notifications.success.dataRefreshed();
  } catch (error) {
    notifications.error.dataLoadFailed(error.message);
    console.error(error);
  } finally {
    isRefreshing.value = false;
  }
};

const handleAppointmentCreated = async (data) => {
  // Refresh appointments after creating new one
  if (selectedCompany.value && selectedCompany.value.trim()) {
    await appointmentStore.fetchAppointments();
  }
};

const handleModeChanged = (newMode, appointmentData) => {
  // Update dialog mode and appointment data
  dialogMode.value = newMode;
  if (appointmentData) {
    selectedAppointmentData.value = appointmentData;
  }
};

const handleEditAppointment = () => {
  // Switch from view mode to edit mode
  dialogMode.value = "edit";
};
</script>

<style scoped>
.grid-scroller {
  --time-column-width: 96px;
  --column-width: 144px;
  --column-gap: 8px;
  --row-height: 80px;
  --header-height: 96px;
  flex: 1;
  min-height: 0;
  overflow: auto;
  background-color: white;
  border-top: 1px solid #d1d5db;
  scroll-padding-top: var(--header-height);
  scroll-padding-left: calc(var(--time-column-width) + var(--column-gap));
}

/* Each track holds its own gutter so sticky cells cover it when cards scroll under. */
.appointment-grid {
  display: grid;
  grid-template-columns:
    calc(var(--time-column-width) + var(--column-gap))
    repeat(var(--columns), calc(var(--column-width) + var(--column-gap)));
  grid-template-rows: var(--header-height);
  grid-auto-rows: var(--row-height);
  width: max-content;
  min-width: 100%;
}

.corner-cell,
.header-cell,
.time-cell {
  position: sticky;
  background-color: var(--sticky-background);
}

.corner-cell,
.header-cell {
  --sticky-background: white;
  top: 0;
  z-index: 2;
  border-bottom: 2px solid #e5e7eb;
}

.corner-cell,
.time-cell {
  --sticky-background: #f9fafb;
  left: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-right: 1px solid #d1d5db;
}

.corner-cell {
  z-index: 3;
}

.header-cell {
  display: flex;
  padding-right: var(--column-gap);
}

.empty-header {
  justify-content: center;
  text-align: center;
}

.time-cell {
  grid-column: 1;
  z-index: 1;
  border-bottom: 1px solid #e5e7eb;
  text-align: center;
}

.time-cell.current-time {
  --sticky-background: #fecaca;
  color: #b91c1c;
  box-shadow: inset 3px 0 0 #ef4444;
}

@media (max-width: 768px) {
  .appointment-grid-container {
    font-size: 0.875rem;
    line-height: 1.25rem;
  }

  .grid-scroller {
    --time-column-width: 80px;
    --column-width: 128px;
  }
}

@media (max-width: 640px) {
  .appointment-grid-container .px-6 {
    padding-left: 1rem;
    padding-right: 1rem;
  }

  .appointment-grid-container .py-4 {
    padding-top: 0.75rem;
    padding-bottom: 0.75rem;
  }
}

@media (prefers-contrast: high) {
  .time-cell {
    border-color: #9ca3af;
  }
}
</style>
