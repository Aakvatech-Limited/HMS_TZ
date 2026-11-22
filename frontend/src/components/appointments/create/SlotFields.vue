<template>
  <div
    class="grid grid-cols-2 gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3 sm:grid-cols-[1.4fr_1.1fr_0.8fr_1.2fr]"
  >
    <div>
      <FieldLabel label="Practitioner" required />
      <Link
        :value="form.practitioner"
        doctype="Healthcare Practitioner"
        search-method="hms_tz.api.practitioner.search_practitioners"
        placeholder="Practitioner"
        @change="(value) => (form.practitioner = value)"
      >
        <template #item-label="{ option }">
          <div class="flex w-72 max-w-[80vw] flex-col">
            <span class="truncate font-medium text-gray-900">
              {{ option.practitioner_name || option.value }}
            </span>
            <span class="truncate text-sm text-gray-600">
              {{ practitionerDetails(option) }}
            </span>
          </div>
        </template>
      </Link>
    </div>
    <div>
      <FieldLabel label="Date" required />
      <FormControl v-model="form.appointment_date" type="date" :min="today" />
    </div>
    <div>
      <FieldLabel label="Time" required />
      <FormControl v-model="form.appointment_time" type="time" />
    </div>
    <div>
      <FieldLabel label="Visit type" required />
      <Link
        :value="form.appointment_type"
        doctype="Appointment Type"
        search-method="hms_tz.api.appointment.search_visit_types"
        placeholder="Visit type"
        @change="(value) => (form.appointment_type = value)"
      />
    </div>
    <div
      v-if="visitTypeDescription"
      class="col-span-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-sm italic text-blue-500"
    >
      {{ visitTypeDescription }}
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { call } from "frappe-ui";
import dayjs from "dayjs";
import Link from "@/components/controls/Link.vue";
import FieldLabel from "./FieldLabel.vue";

const props = defineProps({ form: { type: Object, required: true } });

// The browser greys out past days; the server still refuses a past appointment time.
const today = dayjs().format("YYYY-MM-DD");

const practitionerDetails = (option) =>
  [
    option.department,
    option.nhif_physician_qualification,
    option.tz_mct_code && `MCT: ${option.tz_mct_code}`,
  ]
    .filter(Boolean)
    .join(" · ");

const visitTypeDescription = ref("");

watch(
  () => props.form.appointment_type,
  async (name) => {
    const visitType = name
      ? await call("frappe.client.get_value", {
          doctype: "Appointment Type",
          filters: name,
          fieldname: [
            "description",
            "requires_remarks",
            "requires_referral_no",
          ],
        })
      : null;
    if (name !== props.form.appointment_type) return;
    visitTypeDescription.value = visitType?.description || "";
    props.form.visitType = {
      requires_remarks: visitType?.requires_remarks || 0,
      requires_referral_no: visitType?.requires_referral_no || 0,
    };
  },
  { immediate: true }
);
</script>
