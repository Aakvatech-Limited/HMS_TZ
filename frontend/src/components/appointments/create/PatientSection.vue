<template>
  <section class="flex flex-col gap-3 border-t border-gray-200 pt-5">
    <div class="flex items-center justify-between gap-3">
      <h3 class="text-[15px] font-semibold text-gray-900">Patient</h3>
      <TabButtons
        :buttons="PATIENT_MODES"
        :model-value="form.patientMode"
        @update:model-value="(mode) => emit('set-patient-mode', mode)"
      />
    </div>

    <div
      v-if="form.patientMode === 'existing'"
      class="grid grid-cols-1 gap-4 sm:grid-cols-4 sm:items-end"
    >
      <div class="sm:col-span-2">
        <FieldLabel
          label="Patient"
          required
          :from-card="form.fromCard.patient"
        />
        <Link
          :value="form.patient"
          doctype="Patient"
          :search-method="SEARCH_PATIENTS_METHOD"
          :page-length="20"
          placeholder="Search by name, ID, mobile or card no"
          @change="(value) => emit('select-patient', value)"
        >
          <template #item-label="{ option }">
            <div class="flex min-w-0 flex-col">
              <span class="truncate font-medium text-gray-900">
                {{ option.patient_name || option.value }}
              </span>
              <span class="truncate text-sm text-gray-600">
                {{ patientOptionDetails(option) }}
              </span>
            </div>
          </template>
        </Link>
      </div>
      <div
        v-if="summary"
        class="rounded-lg border border-gray-200 px-2.5 py-1.5 text-sm text-gray-600 sm:col-span-2"
      >
        {{ summary }}
      </div>
    </div>

    <template v-else>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-4">
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
          <FormControl
            v-else-if="field.name === 'dob'"
            v-model="form.newPatient.dob"
            type="date"
            :max="today"
          />
          <FormControl
            v-else
            v-model="form.newPatient[field.name]"
            type="text"
            :placeholder="field.placeholder || field.label"
          />
        </div>
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
        <div class="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-4">
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
import dayjs from "dayjs";
import { TabButtons } from "frappe-ui";
import Link from "@/components/controls/Link.vue";
import FieldLabel from "./FieldLabel.vue";
import { patientSummary } from "./useBookingForm";
import { SEARCH_PATIENTS_METHOD } from "@/data/insurance";

const patientOptionDetails = (option) =>
  [
    option.value,
    option.sex,
    option.mobile && `Mob: ${option.mobile}`,
    option.card_no && `Card: ${option.card_no}`,
  ]
    .filter(Boolean)
    .join(" · ");

const today = dayjs().format("YYYY-MM-DD");
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
const emit = defineEmits(["select-patient", "set-patient-mode"]);

const summary = computed(() => patientSummary(props.form.patientDetails));
const visibleLinkFields = computed(() =>
  PATIENT_LINK_FIELDS.filter(
    (field) =>
      field.name !== "referred_from" ||
      props.form.newPatient.how_did_you_hear_about_us === "Referred"
  )
);
</script>
