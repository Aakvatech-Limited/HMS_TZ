<template>
  <div class="flex items-center gap-4">
    <Switch
      v-model="openByDefault"
      label="Open this page by default"
      :disabled="isSaving"
      @update:model-value="saveOpenByDefault"
    />
    <Button
      icon-left="list"
      label="List View"
      title="Open the Patient Appointment list"
      @click="openListView"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { Switch, call } from "frappe-ui";
import {
  APPOINTMENT_DOCTYPE,
  LIST_VIEW_URL,
  PAGE_TRIED_SETTINGS,
  isOpenByDefault,
  toUserSettings,
} from "@/data/appointmentsPageDefault";
import { serverErrorText, useToast } from "@/composables/useToast";

/** The user's choice to open Patient Appointment on this page, kept in their desk list settings. */
const openByDefault = ref(false);
const isSaving = ref(false);
const { showError } = useToast();

onMounted(async () => {
  call("frappe.model.utils.user_settings.save", {
    doctype: APPOINTMENT_DOCTYPE,
    user_settings: PAGE_TRIED_SETTINGS,
  });
  openByDefault.value = isOpenByDefault(
    await call("frappe.model.utils.user_settings.get", {
      doctype: APPOINTMENT_DOCTYPE,
    })
  );
});

const openListView = () => window.location.assign(LIST_VIEW_URL);

const saveOpenByDefault = async (value) => {
  isSaving.value = true;
  try {
    await call("frappe.model.utils.user_settings.save", {
      doctype: APPOINTMENT_DOCTYPE,
      user_settings: toUserSettings(value),
    });
  } catch (error) {
    openByDefault.value = !value;
    showError(serverErrorText(error));
  } finally {
    isSaving.value = false;
  }
};
</script>
