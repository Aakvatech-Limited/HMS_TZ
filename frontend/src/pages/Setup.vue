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
      <LoadingText v-else-if="!formReady" />

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
                    :sections="getVisibleSections(tab, data, company)"
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

          <aside class="h-fit space-y-6">
            <section class="rounded-lg border bg-white p-6">
              <div class="mb-4 flex items-baseline justify-between">
                <h2 class="text-lg font-semibold text-gray-900">Settings</h2>
                <span class="text-sm text-gray-600">
                  {{ completeGroupCount }} of {{ groups.length }} complete
                </span>
              </div>
              <ul class="space-y-3">
                <li v-for="group in groups" :key="group.label">
                  <div class="flex items-center gap-2 text-base text-gray-900">
                    <FeatherIcon
                      :name="
                        group.missing.length ? 'alert-circle' : 'check-circle'
                      "
                      class="h-4 w-4 shrink-0"
                      :class="
                        group.missing.length
                          ? 'text-orange-500'
                          : 'text-green-600'
                      "
                    />
                    {{ group.label }}
                  </div>
                  <p
                    v-if="group.missing.length"
                    class="ml-6 mt-1 text-sm text-gray-600"
                  >
                    Missing: {{ group.missing.join(", ") }}
                  </p>
                </li>
              </ul>
              <p class="mt-4 text-sm text-gray-600">
                Checked against the saved values.
              </p>
            </section>

            <section v-if="setting" class="rounded-lg border bg-white p-6">
              <div class="mb-4 flex items-baseline justify-between">
                <h2 class="text-lg font-semibold text-gray-900">
                  Setup steps
                </h2>
                <span class="text-sm text-gray-600">
                  {{ completedCount }} of {{ steps.length }} done
                </span>
              </div>
              <p
                v-if="!setup.data.settings_complete"
                class="mb-4 flex items-start gap-2 text-sm text-gray-600"
              >
                <FeatherIcon name="lock" class="mt-0.5 h-4 w-4 shrink-0" />
                Later setup stages stay locked until every settings group is
                complete.
              </p>
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
                    :class="
                      step.completed ? 'text-green-600' : 'text-gray-400'
                    "
                  />
                  {{ step.document_type }}
                </li>
              </ul>
            </section>
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
const data = reactive({});
const formReady = ref(false);
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
const groups = computed(() => setup.data?.groups || []);
const completeGroupCount = computed(
  () => groups.value.filter((group) => !group.missing.length).length
);
const completedCount = computed(
  () => steps.value.filter((step) => step.completed).length
);
const tabs = computed(() => getSettingTabs(fields.data || []));

async function loadSetting(result) {
  await fields.promise;
  Object.assign(data, toSettingForm(fields.data, result.values));
  formReady.value = true;
}

function selectCompany(value) {
  company.value = value;
  router.replace({ query: { company: value } });
  formReady.value = false;
  setup.reset();
  setup.fetch();
}

async function save() {
  saving.value = true;
  try {
    await call("hms_tz.api.setup.save_company_setup", {
      company: company.value,
      values: toSettingValues(fields.data, data),
    });
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
