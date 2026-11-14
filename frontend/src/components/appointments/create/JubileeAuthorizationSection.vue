<template>
  <section class="flex flex-col gap-3 border-t border-gray-200 pt-5">
    <div class="flex items-center gap-2">
      <h3 class="text-[15px] font-semibold text-gray-900">
        {{
          form.payment === "Jubilee"
            ? "Jubilee authorization"
            : "Insurance details"
        }}
      </h3>
      <Badge v-if="form.payment === 'Jubilee'" theme="orange" variant="subtle">
        Jubilee only
      </Badge>
    </div>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:items-end">
      <div>
        <FieldLabel label="Authorization no" />
        <div
          v-if="apiEnabled"
          class="min-h-[28px] rounded border border-gray-200 bg-white px-2 py-1 text-sm text-gray-500"
        >
          Requested from Jubilee on create
        </div>
        <FormControl
          v-else
          v-model="form.verification.authorization_number"
          type="text"
          placeholder="Authorization no"
        />
      </div>
      <div>
        <FieldLabel label="Referral no" />
        <FormControl
          v-model="form.verification.referral_no"
          type="text"
          placeholder="If referred"
        />
      </div>
    </div>
    <div>
      <FieldLabel label="Remarks" />
      <FormControl v-model="form.verification.remarks" type="textarea" />
    </div>
  </section>
</template>

<script setup>
import FieldLabel from "./FieldLabel.vue";

defineProps({
  form: { type: Object, required: true },
  apiEnabled: { type: Boolean, default: false },
});
</script>
