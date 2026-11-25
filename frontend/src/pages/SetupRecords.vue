<template>
  <SetupLayout :company="company" @select-company="selectCompany">
    <header class="border-b bg-white px-6 py-4">
      <h1 class="text-xl font-semibold text-gray-900">{{ title }}</h1>
    </header>

    <main class="mx-auto max-w-screen-2xl space-y-6 p-6">
      <ErrorMessage v-if="screen.error" :message="screen.error" />
      <LoadingText v-else-if="!screen.data" />
      <p v-else-if="!company" class="text-base text-gray-600">
        Select a company to see its {{ screen.data.plural_label }}.
      </p>
      <ErrorMessage v-else-if="records.error" :message="records.error" />
      <LoadingText v-else-if="!records.data" />

      <template v-else>
        <Alert
          v-if="!records.data.settings_complete"
          title="Complete the settings first"
        >
          {{ title }} can be added once every settings group of
          {{ company }} is complete on the setup page.
        </Alert>

        <section
          v-if="importResult"
          class="rounded-lg border bg-white px-6 py-4 text-base"
        >
          <div class="flex items-center justify-between">
            <p class="text-gray-900">
              Import: {{ importResult.added }} added,
              {{ importResult.changed }} changed,
              {{ importResult.errors.length }} not imported
            </p>
            <Button
              variant="ghost"
              icon="x"
              label="Close"
              @click="importResult = null"
            />
          </div>
          <ul
            v-if="importResult.errors.length"
            class="mt-3 space-y-1 text-sm text-gray-700"
          >
            <li v-for="error in importResult.errors" :key="error.row">
              Row {{ error.row }}: {{ error.message }}
            </li>
          </ul>
        </section>

        <section class="rounded-lg border bg-white">
          <div class="flex items-center justify-between border-b px-6 py-4">
            <h2 class="text-lg font-semibold text-gray-900">
              {{
                getCountText(
                  records.data.records.length,
                  screen.data,
                  records.data.has_more
                )
              }}
            </h2>
            <div class="flex flex-wrap items-center gap-2">
              <Dropdown
                v-for="group in records.data.action_groups"
                :key="group.label"
                :options="getActionOptions(group, actionRuns, runAction)"
              >
                <Button
                  :label="group.label"
                  icon-left="list"
                  icon-right="chevron-down"
                  :loading="isGroupRunning(group, actionRuns)"
                />
              </Dropdown>
              <template v-if="screen.data.has_add_actions">
                <Dropdown :options="templateOptions">
                  <Button
                    label="Download template"
                    icon-left="download"
                    icon-right="chevron-down"
                  />
                </Dropdown>
                <FileUploader
                  :file-types="['.csv', '.xlsx']"
                  :upload-args="{ private: true }"
                  @success="importFile"
                  @failure="(error) => showError(serverErrorText(error))"
                >
                  <template #default="{ openFileSelector, uploading }">
                    <Button
                      label="Import"
                      icon-left="upload"
                      :loading="uploading || importing"
                      :disabled="!records.data.settings_complete"
                      @click="openFileSelector()"
                    />
                  </template>
                </FileUploader>
                <Button
                  variant="solid"
                  :label="`Add ${screen.data.label}`"
                  icon-left="plus"
                  :disabled="!records.data.settings_complete"
                  @click="openRecord()"
                />
              </template>
            </div>
          </div>
          <div v-if="filterSections.length" class="border-b px-6 py-4">
            <FieldMap :sections="filterSections" :data="filterData" />
          </div>
          <p
            v-if="!records.data.records.length"
            class="px-6 py-8 text-base text-gray-600"
          >
            No {{ screen.data.plural_label }} yet.
          </p>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-left text-base">
              <thead class="border-b text-sm text-gray-600">
                <tr>
                  <th
                    v-for="field in screen.data.fields"
                    :key="field.fieldname"
                    class="whitespace-nowrap px-6 py-3 font-medium"
                  >
                    {{ field.label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="record in records.data.records"
                  :key="record.name"
                  class="cursor-pointer border-b last:border-b-0 hover:bg-gray-50"
                  :class="{
                    'pointer-events-none':
                      !records.data.settings_complete &&
                      !screen.data.is_read_only,
                  }"
                  @click="openRecord(record)"
                >
                  <td
                    v-for="field in screen.data.fields"
                    :key="field.fieldname"
                    class="px-6 py-3 text-gray-900"
                  >
                    <template v-if="field.fieldtype === 'Check'">
                      {{ record[field.fieldname] ? "Yes" : "" }}
                    </template>
                    <template v-else>{{ record[field.fieldname] }}</template>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="runRows.length" class="rounded-lg border bg-white">
          <h2 class="border-b px-6 py-4 text-lg font-semibold text-gray-900">
            Last runs
          </h2>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-base">
              <thead class="border-b text-sm text-gray-600">
                <tr>
                  <th class="px-6 py-3 font-medium">Action</th>
                  <th class="px-6 py-3 font-medium">Status</th>
                  <th class="px-6 py-3 font-medium">Started</th>
                  <th class="px-6 py-3 font-medium">Finished</th>
                  <th class="px-6 py-3 font-medium">Result</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in runRows"
                  :key="row.key"
                  class="border-b last:border-b-0"
                >
                  <td class="px-6 py-3 text-gray-900">{{ row.label }}</td>
                  <td class="px-6 py-3">
                    <Badge
                      :label="row.run?.status || 'Not run yet'"
                      :theme="RUN_THEMES[row.run?.status] || 'gray'"
                      variant="subtle"
                    />
                  </td>
                  <td class="whitespace-nowrap px-6 py-3 text-gray-700">
                    {{ row.run?.started_on || "" }}
                  </td>
                  <td class="whitespace-nowrap px-6 py-3 text-gray-700">
                    {{ row.run?.finished_on || "" }}
                  </td>
                  <td class="px-6 py-3 text-gray-700">
                    <template v-if="row.run?.status === 'Failed'">
                      {{ row.run.error }}
                      <a
                        v-if="row.run.error_log"
                        class="underline"
                        :href="`/desk/error-log/${row.run.error_log}`"
                        target="_blank"
                        >Error Log</a
                      >
                    </template>
                    <template v-else>{{ row.run?.result || "" }}</template>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </main>

    <Dialog
      v-if="screen.data"
      v-model="dialogOpen"
      :options="{
        title: getDialogTitle(screen.data, editing),
        size: screen.data.has_child_rows ? '5xl' : '2xl',
        actions: dialogActions,
      }"
    >
      <template #body-content>
        <FieldMap :sections="dialogSections" :data="data" />
        <section v-if="screen.data.has_child_rows" class="mt-6 space-y-3">
          <p class="text-base font-semibold text-gray-900">
            {{ childRows.rows.length }} of {{ childRows.total }} rows
          </p>
          <div class="max-h-96 overflow-auto rounded border">
            <table class="w-full text-left text-sm">
              <thead class="sticky top-0 border-b bg-gray-50 text-gray-600">
                <tr>
                  <th
                    v-for="field in childRows.fields"
                    :key="field.fieldname"
                    class="whitespace-nowrap px-3 py-2 font-medium"
                  >
                    {{ field.label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, index) in childRows.rows"
                  :key="index"
                  class="border-b last:border-b-0"
                >
                  <td
                    v-for="field in childRows.fields"
                    :key="field.fieldname"
                    class="px-3 py-2 align-top text-gray-900"
                  >
                    {{ row[field.fieldname] }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <Button
            v-if="childRows.rows.length < childRows.total"
            label="Show more"
            :loading="loadingChildRows"
            @click="loadChildRows(childRows.rows.length)"
          />
        </section>
      </template>
    </Dialog>
  </SetupLayout>
</template>

<script setup>
import FieldMap from "@/components/controls/FieldMap.vue";
import SetupLayout from "@/components/setup/SetupLayout.vue";
import { serverErrorText, useToast } from "@/composables/useToast";
import {
  capitalize,
  getActionOptions,
  getRunRows,
  getCountText,
  getDialogFields,
  getDialogTitle,
  isGroupRunning,
  isRunActive,
} from "@/data/setupRecords";
import {
  getSettingTabs,
  getVisibleSections,
  toSettingForm,
  toSettingValues,
} from "@/data/setupSettings";
import {
  Dialog,
  Dropdown,
  FileUploader,
  call,
  createResource,
  usePageMeta,
} from "frappe-ui";
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

/** One setup screen of company records, such as "doctors"; the server holds its DocType and fields. */
const props = defineProps({ screen: { type: String, required: true } });

const API = "hms_tz.api.setup_records";

const route = useRoute();
const router = useRouter();
const { showSuccess, showError } = useToast();

const company = ref(route.query.company || "");
const data = reactive({});
const dialogOpen = ref(false);
const editing = ref(null);
const saving = ref(false);
const importing = ref(false);
const RUN_POLL_MS = 3000;
const RUN_THEMES = {
  Queued: "blue",
  Running: "blue",
  Done: "green",
  Failed: "red",
};
let runPoll = null;
const importResult = ref(null);
const childRows = ref({ fields: [], rows: [], total: 0 });
const loadingChildRows = ref(false);

const filterData = reactive({});

const screen = createResource({
  url: `${API}.get_screen_fields`,
  params: { screen: props.screen },
  auto: true,
  onSuccess: resetFilters,
});

const records = createResource({
  url: `${API}.get_company_records`,
  makeParams: () => ({
    screen: props.screen,
    company: company.value,
    list_filters: filterData[screen.data?.doctype] || {},
  }),
  auto: Boolean(company.value),
});

const filterSections = computed(() => {
  const doctype = screen.data?.doctype;
  const [tab] = getSettingTabs(screen.data?.list_filters || []);
  if (!tab || !filterData[doctype]) return [];
  return getVisibleSections(tab, filterData, company.value).map((section) => ({
    ...section,
    hideLabel: true,
    hideBorder: true,
  }));
});

// A changed filter, such as a picked coverage plan, lists the matching records.
watch(
  () => JSON.stringify(filterData),
  () => company.value && records.reload()
);

function resetFilters() {
  Object.assign(filterData, toSettingForm(screen.data?.list_filters || []));
}

const actionRuns = computed(() => records.data?.action_runs || {});
const runRows = computed(() =>
  getRunRows(records.data?.action_groups || [], actionRuns.value)
);

// Keep the runs current while one is queued or running; the job writes its status as it goes.
watch(
  () => runRows.value.some((row) => isRunActive(row.run)),
  (isActive) => {
    clearInterval(runPoll);
    if (isActive) runPoll = setInterval(() => records.reload(), RUN_POLL_MS);
  }
);
onBeforeUnmount(() => clearInterval(runPoll));

const title = computed(() => capitalize(screen.data?.plural_label) || "Setup");
usePageMeta(() => ({ title: `${title.value} - HMS TZ` }));

const dialogSections = computed(() => {
  const doctype = screen.data?.doctype;
  const fields = getDialogFields(
    screen.data?.fields || [],
    Boolean(editing.value),
    Boolean(screen.data?.is_read_only)
  );
  const [tab] = getSettingTabs(fields);
  if (!tab || !data[doctype]) return [];
  return getVisibleSections(tab, data, company.value).map((section) => ({
    ...section,
    columns: 2,
    hideLabel: true,
  }));
});

const dialogActions = computed(() => [
  {
    label: screen.data?.is_read_only ? "Close" : "Cancel",
    variant: "subtle",
    onClick: () => (dialogOpen.value = false),
  },
  ...(screen.data?.is_read_only ? [] : [saveAction.value]),
]);

const saveAction = computed(() => ({
  label: editing.value ? "Save" : `Add ${screen.data.label}`,
  variant: "solid",
  loading: saving.value,
  onClick: save,
}));

function selectCompany(value) {
  company.value = value;
  router.replace({ query: { company: value } });
  importResult.value = null;
  resetFilters();
  records.reset();
  records.fetch();
}

function openRecord(record) {
  editing.value = record || null;
  const values = record ? { [screen.data.doctype]: record } : {};
  Object.assign(data, toSettingForm(screen.data.fields, values));
  dialogOpen.value = true;
  childRows.value = { fields: [], rows: [], total: 0 };
  if (record && screen.data.has_child_rows) loadChildRows(0);
}

async function loadChildRows(start) {
  loadingChildRows.value = true;
  try {
    const page = await call(`${API}.get_record_child_rows`, {
      screen: props.screen,
      company: company.value,
      name: editing.value.name,
      start,
    });
    childRows.value = {
      ...page,
      rows: [...childRows.value.rows, ...page.rows],
    };
  } catch (error) {
    showError(serverErrorText(error));
  } finally {
    loadingChildRows.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    await call(`${API}.save_company_record`, {
      screen: props.screen,
      company: company.value,
      name: editing.value?.name,
      values: toSettingValues(screen.data.fields, data)[screen.data.doctype],
    });
    const label = capitalize(screen.data.label);
    showSuccess(editing.value ? `${label} saved` : `${label} added`);
    dialogOpen.value = false;
    await records.reload();
  } catch (error) {
    showError(serverErrorText(error));
  } finally {
    saving.value = false;
  }
}

const templateOptions = computed(() =>
  [
    { label: "Headers only", samples: "0" },
    { label: "With 2 samples", samples: "2" },
    { label: "With 5 samples", samples: "5" },
    { label: `With all ${screen.data?.plural_label}`, samples: "all" },
  ].map(({ label, samples }) => ({
    label,
    onClick: () => downloadTemplate(samples),
  }))
);

function downloadTemplate(samples) {
  const query = new URLSearchParams({
    screen: props.screen,
    company: company.value,
    samples,
  });
  window.open(
    `/api/method/${API}.download_records_template?${query}`,
    "_blank"
  );
}

async function runAction(action) {
  try {
    await call(`${API}.run_screen_action`, {
      screen: props.screen,
      company: company.value,
      action: action.key,
    });
    showSuccess(`${action.label}: queued`);
    await records.reload();
  } catch (error) {
    showError(serverErrorText(error));
  }
}

async function importFile(file) {
  importing.value = true;
  try {
    importResult.value = await call(`${API}.import_company_records`, {
      screen: props.screen,
      company: company.value,
      file_url: file.file_url,
    });
    await records.reload();
  } catch (error) {
    showError(serverErrorText(error));
  } finally {
    importing.value = false;
  }
}
</script>
