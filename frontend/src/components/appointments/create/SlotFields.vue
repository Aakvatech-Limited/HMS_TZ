<template>
  <div
    class="grid grid-cols-2 gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3 sm:grid-cols-[1.4fr_1.1fr_0.8fr_1.2fr]"
  >
    <div>
      <FieldLabel label="Practitioner" required />
      <Link
        :value="form.practitioner"
        doctype="Healthcare Practitioner"
        placeholder="Practitioner"
        @change="(value) => (form.practitioner = value)"
      />
    </div>
    <div>
      <FieldLabel label="Date" required />
      <DatePicker v-model="form.appointment_date" placeholder="Date" />
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
import Link from "@/components/controls/Link.vue";
import FieldLabel from "./FieldLabel.vue";

const props = defineProps({ form: { type: Object, required: true } });

const visitTypeDescription = ref("");

watch(
  () => props.form.appointment_type,
  async (name) => {
    visitTypeDescription.value = name
      ? (
          await call("frappe.client.get_value", {
            doctype: "Appointment Type",
            filters: name,
            fieldname: "description",
          })
        )?.description || ""
      : "";
  },
  { immediate: true }
);
</script>
