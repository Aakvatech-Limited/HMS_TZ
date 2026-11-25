<template>
  <SetupLayout :company="company" @select-company="selectCompany">
    <header class="border-b bg-white px-6 py-4">
      <h1 class="text-xl font-semibold text-gray-900">Rooms</h1>
    </header>

    <main class="mx-auto max-w-screen-2xl space-y-6 p-6">
      <p v-if="!company" class="text-base text-gray-600">
        Select a company to see its rooms.
      </p>
      <ErrorMessage
        v-else-if="fields.error || rooms.error"
        :message="fields.error || rooms.error"
      />
      <LoadingText v-else-if="!fields.data || !rooms.data" />

      <template v-else>
        <Alert
          v-if="!rooms.data.settings_complete"
          title="Complete the settings first"
        >
          Rooms can be added once every settings group of {{ company }} is
          complete on the setup page.
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
              {{ rooms.data.rooms.length }}
              {{ rooms.data.rooms.length === 1 ? "room" : "rooms" }}
            </h2>
            <div class="flex items-center gap-2">
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
                    :disabled="!rooms.data.settings_complete"
                    @click="openFileSelector()"
                  />
                </template>
              </FileUploader>
              <Button
                variant="solid"
                label="Add room"
                icon-left="plus"
                :disabled="!rooms.data.settings_complete"
                @click="openRoom()"
              />
            </div>
          </div>
          <p
            v-if="!rooms.data.rooms.length"
            class="px-6 py-8 text-base text-gray-600"
          >
            No rooms yet.
          </p>
          <table v-else class="w-full text-left text-base">
            <thead class="border-b text-sm text-gray-600">
              <tr>
                <th
                  v-for="field in fields.data"
                  :key="field.fieldname"
                  class="px-6 py-3 font-medium"
                >
                  {{ field.label }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="room in rooms.data.rooms"
                :key="room.name"
                class="cursor-pointer border-b last:border-b-0 hover:bg-gray-50"
                :class="{
                  'pointer-events-none': !rooms.data.settings_complete,
                }"
                @click="openRoom(room)"
              >
                <td
                  v-for="field in fields.data"
                  :key="field.fieldname"
                  class="px-6 py-3 text-gray-900"
                >
                  <template v-if="field.fieldtype === 'Check'">
                    {{ room[field.fieldname] ? "Yes" : "" }}
                  </template>
                  <template v-else>{{ room[field.fieldname] }}</template>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </template>
    </main>

    <Dialog
      v-model="dialogOpen"
      :options="{
        title: editing ? `Change ${editing}` : 'Add room',
        size: '2xl',
        actions: dialogActions,
      }"
    >
      <template #body-content>
        <FieldMap :sections="dialogSections" :data="data" />
      </template>
    </Dialog>
  </SetupLayout>
</template>

<script setup>
import FieldMap from "@/components/controls/FieldMap.vue";
import SetupLayout from "@/components/setup/SetupLayout.vue";
import { serverErrorText, useToast } from "@/composables/useToast";
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
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

usePageMeta(() => ({ title: "Rooms - HMS TZ" }));

const ROOM_DOCTYPE = "Healthcare Service Unit";

const route = useRoute();
const router = useRouter();
const { showSuccess, showError } = useToast();

const company = ref(route.query.company || "");
const data = reactive({});
const dialogOpen = ref(false);
const editing = ref(null);
const saving = ref(false);
const importing = ref(false);
const importResult = ref(null);

const fields = createResource({
  url: "hms_tz.api.rooms.get_room_fields",
  auto: true,
});

const rooms = createResource({
  url: "hms_tz.api.rooms.get_company_rooms",
  makeParams: () => ({ company: company.value }),
  auto: Boolean(company.value),
});

const dialogSections = computed(() => {
  const [tab] = getSettingTabs(fields.data || []);
  if (!tab || !data[ROOM_DOCTYPE]) return [];
  return getVisibleSections(tab, data, company.value).map((section) => ({
    ...section,
    columns: 2,
    hideLabel: true,
    fields: section.fields.map((field) => ({
      ...field,
      read_only: editing.value && isTitle(field.name),
    })),
  }));
});

const dialogActions = computed(() => [
  {
    label: "Cancel",
    variant: "subtle",
    onClick: () => (dialogOpen.value = false),
  },
  {
    label: editing.value ? "Save" : "Add room",
    variant: "solid",
    loading: saving.value,
    onClick: save,
  },
]);

function isTitle(fieldname) {
  return fields.data.some(
    (field) => field.fieldname === fieldname && field.is_title
  );
}

function selectCompany(value) {
  company.value = value;
  router.replace({ query: { company: value } });
  importResult.value = null;
  rooms.reset();
  rooms.fetch();
}

function openRoom(room) {
  editing.value = room?.name || null;
  Object.assign(
    data,
    toSettingForm(fields.data, room ? { [ROOM_DOCTYPE]: room } : {})
  );
  dialogOpen.value = true;
}

async function save() {
  saving.value = true;
  try {
    await call("hms_tz.api.rooms.save_room", {
      company: company.value,
      name: editing.value,
      values: toSettingValues(fields.data, data)[ROOM_DOCTYPE],
    });
    showSuccess(editing.value ? "Room saved" : "Room added");
    dialogOpen.value = false;
    await rooms.reload();
  } catch (error) {
    showError(serverErrorText(error));
  } finally {
    saving.value = false;
  }
}

const templateOptions = [
  { label: "Headers only", sampleRooms: "0" },
  { label: "With 2 sample rooms", sampleRooms: "2" },
  { label: "With 5 sample rooms", sampleRooms: "5" },
  { label: "With all rooms", sampleRooms: "all" },
].map(({ label, sampleRooms }) => ({
  label,
  onClick: () => downloadTemplate(sampleRooms),
}));

function downloadTemplate(sampleRooms) {
  const query = new URLSearchParams({
    company: company.value,
    sample_rooms: sampleRooms,
  });
  window.open(
    `/api/method/hms_tz.api.rooms.download_rooms_template?${query}`,
    "_blank"
  );
}

async function importFile(file) {
  importing.value = true;
  try {
    importResult.value = await call("hms_tz.api.rooms.import_rooms", {
      company: company.value,
      file_url: file.file_url,
    });
    await rooms.reload();
  } catch (error) {
    showError(serverErrorText(error));
  } finally {
    importing.value = false;
  }
}
</script>
