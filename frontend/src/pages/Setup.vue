<template>
  <div class="min-h-screen bg-gray-50">
    <header
      class="flex flex-wrap items-center justify-between gap-4 border-b bg-white px-6 py-4"
    >
      <h1 class="text-xl font-semibold text-gray-900">HMS TZ Setup</h1>
      <div class="w-72">
        <Link
          doctype="Company"
          :value="company"
          placeholder="Select company"
          @change="selectCompany"
        />
      </div>
    </header>

    <main class="mx-auto max-w-screen-2xl space-y-6 p-6">
      <p v-if="!company" class="text-base text-gray-600">
        Select a company to see its setup.
      </p>
      <ErrorMessage
        v-else-if="fields.error || setup.error"
        :message="fields.error || setup.error"
      />
      <LoadingText v-else-if="!fields.data || !setup.data" />

      <template v-else>
        <Alert v-if="!setting" title="Create the HMS TZ Setting first">
          {{ company }} has no HMS TZ Setting. Fill in the settings below and
          create it before anything else.
        </Alert>

        <div class="grid gap-6 xl:grid-cols-[1fr_300px]">
          <section class="rounded-lg border bg-white">
            <Tabs v-model="tabIndex" :tabs="tabs">
              <template #tab-panel="{ tab }">
                <div class="p-6">
                  <FieldMap
                    :sections="
                      getVisibleSections(tab, data[SETTING_DOCTYPE], company)
                    "
                    :data="data"
                  />
                </div>
              </template>
            </Tabs>
            <div class="flex justify-end border-t px-6 py-4">
              <Button
                variant="solid"
                :loading="saving"
                :label="setting ? 'Save' : 'Create HMS TZ Setting'"
                @click="save"
              />
            </div>
          </section>

          <aside v-if="setting" class="h-fit rounded-lg border bg-white p-6">
            <div class="mb-4 flex items-baseline justify-between">
              <h2 class="text-lg font-semibold text-gray-900">Setup steps</h2>
              <span class="text-sm text-gray-600">
                {{ completedCount }} of {{ steps.length }} done
              </span>
            </div>
            <ul class="space-y-2">
              <li
                v-for="step in steps"
                :key="step.document_type"
                class="flex items-center gap-2 text-base"
                :class="step.completed ? 'text-gray-900' : 'text-gray-500'"
              >
                <FeatherIcon
                  :name="step.completed ? 'check-circle' : 'circle'"
                  class="h-4 w-4 shrink-0"
                  :class="step.completed ? 'text-green-600' : 'text-gray-400'"
                />
                {{ step.document_type }}
              </li>
            </ul>
          </aside>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import FieldMap from "@/components/controls/FieldMap.vue";
import Link from "@/components/controls/Link.vue";
import { serverErrorText, useToast } from "@/composables/useToast";
import {
  SETTING_DOCTYPE,
  getSettingTabs,
  getVisibleSections,
  toSettingForm,
  toSettingValues,
} from "@/data/setupSettings";
import { Tabs, call, createResource, usePageMeta } from "frappe-ui";
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

usePageMeta(() => ({ title: "Setup - HMS TZ" }));

const route = useRoute();
const router = useRouter();
const { showSuccess, showError } = useToast();

const company = ref(route.query.company || "");
const data = reactive({ [SETTING_DOCTYPE]: {} });
const saving = ref(false);
const tabIndex = ref(0);

const fields = createResource({
  url: "hms_tz.api.setup.get_setting_fields",
  auto: true,
});

const setup = createResource({
  url: "hms_tz.api.setup.get_company_setup",
  makeParams: () => ({ company: company.value }),
  auto: Boolean(company.value),
  onSuccess: loadSetting,
});

const setting = computed(() => setup.data?.setting);
const steps = computed(() => setup.data?.steps || []);
const completedCount = computed(
  () => steps.value.filter((step) => step.completed).length
);
const tabs = computed(() => getSettingTabs(fields.data || []));

async function loadSetting(result) {
  const saved = result.setting
    ? await call("frappe.client.get", {
        doctype: SETTING_DOCTYPE,
        name: result.setting,
      })
    : null;
  await fields.promise;
  data[SETTING_DOCTYPE] = toSettingForm(fields.data, saved);
}

function selectCompany(value) {
  company.value = value;
  router.replace({ query: { company: value } });
  setup.reset();
  setup.fetch();
}

async function save() {
  saving.value = true;
  const values = toSettingValues(fields.data, data[SETTING_DOCTYPE]);
  try {
    if (setting.value) {
      await call("frappe.client.set_value", {
        doctype: SETTING_DOCTYPE,
        name: setting.value,
        fieldname: values,
      });
    } else {
      await call("frappe.client.insert", {
        doc: { doctype: SETTING_DOCTYPE, company: company.value, ...values },
      });
    }
    showSuccess(
      setting.value ? "HMS TZ Setting saved" : "HMS TZ Setting created"
    );
    await setup.reload();
  } catch (error) {
    showError(serverErrorText(error));
  } finally {
    saving.value = false;
  }
}
</script>
