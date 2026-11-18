<template>
  <Popover placement="bottom-end">
    <template #target="{ togglePopover, isOpen }">
      <Button
        icon-left="filter"
        :label="activeCount ? `Filters ${activeCount}` : 'Filters'"
        :variant="activeCount ? 'subtle' : 'outline'"
        :aria-expanded="isOpen"
        @click="togglePopover()"
      />
    </template>
    <template #body-main>
      <div class="flex w-[40rem] max-w-[calc(100vw-2rem)] flex-col gap-4 p-4">
        <div class="grid gap-4 sm:grid-cols-2">
          <section
            class="flex flex-col gap-3 rounded-lg border border-outline-gray-2 p-3"
          >
            <h3 class="text-sm font-semibold text-ink-gray-8">
              Patient &amp; Payment
            </h3>
            <FormControl
              type="text"
              v-model="appointmentStore.filters.patient_name"
              :debounce="TYPING_DELAY"
              label="Patient Name"
              placeholder="Patient name contains"
            />
            <FormControl
              type="select"
              v-model="appointmentStore.filters.payment"
              label="Payment Method"
              :options="PAYMENT_FILTER_OPTIONS"
            />
            <FormControl
              type="text"
              v-model="appointmentStore.filters.coverage_plan_name"
              :debounce="TYPING_DELAY"
              label="Coverage Plan"
              placeholder="Coverage plan contains"
            />
            <FormControl
              type="checkbox"
              v-model="appointmentStore.filters.follow_up"
              label="Follow Up only"
            />
            <FormControl
              type="checkbox"
              v-model="appointmentStore.filters.apply_fasttrack_charge"
              label="Fast Track only"
            />
          </section>
          <section
            class="flex flex-col gap-3 rounded-lg border border-outline-gray-2 p-3"
          >
            <h3 class="text-sm font-semibold text-ink-gray-8">
              Visit &amp; Practitioner
            </h3>
            <FormControl
              type="select"
              v-model="appointmentStore.filters.status"
              label="Status"
              :options="STATUS_OPTIONS"
            />
            <FormControl
              type="text"
              v-model="appointmentStore.filters.appointment_type"
              :debounce="TYPING_DELAY"
              label="Visit Type"
              placeholder="Visit type contains"
            />
            <FormControl
              type="text"
              v-model="appointmentStore.filters.billing_item"
              :debounce="TYPING_DELAY"
              label="Billing Item"
              placeholder="Billing item contains"
            />
            <FormControl
              type="text"
              v-model="practitionerStore.filters.practitioner"
              :debounce="TYPING_DELAY"
              label="Practitioner"
              placeholder="Practitioner contains"
            />
            <FormControl
              type="text"
              v-model="practitionerStore.filters.department"
              :debounce="TYPING_DELAY"
              label="Department"
              placeholder="Department contains"
            />
          </section>
        </div>
        <Button
          class="self-end"
          label="Clear Filters"
          :disabled="!activeCount"
          @click="clearFilters"
        />
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { computed } from "vue";
import { useAppointmentStore } from "@/data/appointment";
import { usePractitionerStore } from "@/data/practitioner";
import { countActiveFilters } from "@/data/appointmentFilters";
import { PAYMENT_OPTIONS } from "@/data/insurance";
import { APPOINTMENT_STATUSES } from "./appointmentStatus";

/** Desk list style filters for the Appointments grid; the values live in the appointment and practitioner stores. */
const ANY = { label: "All", value: "" };
const STATUS_OPTIONS = [
  ANY,
  ...APPOINTMENT_STATUSES.map(({ label, status }) => ({
    label,
    value: status,
  })),
];
const PAYMENT_FILTER_OPTIONS = [ANY, ...PAYMENT_OPTIONS];

// Typing waits this long before the whole grid re-renders, as a desk list filter does.
const TYPING_DELAY = 300;

const appointmentStore = useAppointmentStore();
const practitionerStore = usePractitionerStore();
const activeCount = computed(
  () =>
    countActiveFilters(appointmentStore.filters) +
    countActiveFilters(practitionerStore.filters)
);

const clearFilters = () => {
  appointmentStore.clearFilters();
  practitionerStore.clearFilters();
};
</script>
