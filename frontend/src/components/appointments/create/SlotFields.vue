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
        placeholder="Visit type"
        @change="(value) => (form.appointment_type = value)"
      />
    </div>
  </div>
</template>

<script setup>
import Link from "@/components/controls/Link.vue";
import FieldLabel from "./FieldLabel.vue";

defineProps({ form: { type: Object, required: true } });
</script>
