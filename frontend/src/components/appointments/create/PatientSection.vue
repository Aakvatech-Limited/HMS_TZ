<template>
  <section class="flex flex-col gap-3 border-t border-gray-200 pt-5">
    <div class="flex items-center justify-between gap-3">
      <h3 class="text-[15px] font-semibold text-gray-900">Patient</h3>
      <TabButtons :buttons="PATIENT_MODES" v-model="form.patientMode" />
    </div>

    <template v-if="form.patientMode === 'existing'">
      <div>
        <FieldLabel
          label="Patient"
          required
          :from-card="form.fromCard.patient"
        />
        <Link
          :value="form.patient"
          doctype="Patient"
          placeholder="Search patient"
          @change="(value) => emit('select-patient', value)"
        />
      </div>
      <div
        v-if="summary"
        class="rounded-lg border border-gray-200 px-2.5 py-1.5 text-sm text-gray-600"
      >
        {{ summary }}
      </div>
    </template>

    <template v-else>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div v-for="field in PATIENT_FIELDS" :key="field.name">
          <FieldLabel
            :label="field.label"
            :required="field.required"
            :from-card="form.fromCard[field.name]"
          />
          <Select
            v-if="field.name === 'sex'"
            v-model="form.newPatient.sex"
            :options="GENDERS"
            placeholder="Select"
          />
          <DatePicker
            v-else-if="field.name === 'dob'"
            v-model="form.newPatient.dob"
            placeholder="Date of birth"
          />
          <FormControl
            v-else
            v-model="form.newPatient[field.name]"
            type="text"
            :placeholder="field.placeholder || field.label"
          />
        </div>
      </div>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div v-for="field in visibleLinkFields" :key="field.name">
          <FieldLabel :label="field.label" :required="field.required" />
          <Link
            :value="form.newPatient[field.name]"
            :doctype="field.doctype"
            :placeholder="field.label"
            @change="(value) => (form.newPatient[field.name] = value)"
          />
        </div>
      </div>
      <details class="text-sm text-gray-600">
        <summary class="cursor-pointer font-medium">
          Next of kin (optional)
        </summary>
        <div class="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div v-for="field in NEXT_OF_KIN_FIELDS" :key="field.name">
            <FieldLabel :label="field.label" />
            <FormControl v-model="form.newPatient[field.name]" type="text" />
          </div>
        </div>
      </details>
    </template>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { TabButtons } from "frappe-ui";
import Link from "@/components/controls/Link.vue";
import FieldLabel from "./FieldLabel.vue";
import { patientSummary } from "./useBookingForm";

const PATIENT_MODES = [
  { label: "Existing patient", value: "existing" },
  { label: "New patient", value: "new" },
];
const GENDERS = [
  { label: "Male", value: "Male" },
  { label: "Female", value: "Female" },
];
const PATIENT_FIELDS = [
  { name: "first_name", label: "First name", required: true },
  { name: "middle_name", label: "Middle name" },
  { name: "last_name", label: "Last name", required: true },
  { name: "sex", label: "Gender", required: true },
  { name: "dob", label: "Date of birth", required: true },
  {
    name: "mobile",
    label: "Mobile",
    required: true,
    placeholder: "07XX XXX XXX",
  },
];
// hms_tz makes these Patient fields mandatory; Referred From shows only for referrals, as in the desk form.
const PATIENT_LINK_FIELDS = [
  { name: "demography", label: "Area", doctype: "Demography", required: true },
  {
    name: "common_occupation",
    label: "Occupation",
    doctype: "Occupation",
    required: true,
  },
  {
    name: "ethnicity",
    label: "Ethnicity",
    doctype: "Ethnicity",
    required: true,
  },
  {
    name: "how_did_you_hear_about_us",
    label: "How did you hear about us",
    doctype: "Campaign",
    required: true,
  },
  {
    name: "referred_from",
    label: "Referred from",
    doctype: "Healthcare Facility",
  },
];
const NEXT_OF_KIN_FIELDS = [
  { name: "next_to_kin_name", label: "Name" },
  { name: "next_to_kin_mobile_no", label: "Mobile" },
  { name: "next_to_kin_relationship", label: "Relationship" },
];

const props = defineProps({ form: { type: Object, required: true } });
const emit = defineEmits(["select-patient"]);

const summary = computed(() => patientSummary(props.form.patientDetails));
const visibleLinkFields = computed(() =>
  PATIENT_LINK_FIELDS.filter(
    (field) =>
      field.name !== "referred_from" ||
      props.form.newPatient.how_did_you_hear_about_us === "Referred"
  )
);
</script>
