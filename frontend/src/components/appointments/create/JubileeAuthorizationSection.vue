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
        <FieldLabel label="Referral no" />
        <FormControl
          v-model="form.verification.referral_no"
          type="text"
          placeholder="If referred"
        />
      </div>
      <div>
        <FieldLabel label="Authorization no" />
        <FormControl
          v-model="form.verification.authorization_number"
          type="text"
          placeholder="Authorization no"
        />
      </div>
    </div>
    <div>
      <FieldLabel label="Remarks" />
      <FormControl v-model="form.verification.remarks" type="textarea" />
    </div>

    <div v-if="apiEnabled && canAuthorize" class="flex justify-end">
      <Button
        variant="solid"
        :loading="authorizing"
        :disabled="authorizing"
        @click="emit('authorize')"
      >
        <template #prefix>
          <FeatherIcon name="shield" class="h-4 w-4" />
        </template>
        Authorize
      </Button>
    </div>
  </section>
</template>

<script setup>
import FieldLabel from "./FieldLabel.vue";

defineProps({
  form: { type: Object, required: true },
  apiEnabled: { type: Boolean, default: false },
  authorizing: { type: Boolean, default: false },
  canAuthorize: { type: Boolean, default: false },
});
const emit = defineEmits(["authorize"]);
</script>
