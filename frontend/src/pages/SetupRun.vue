<template>
  <SetupLayout :company="company" @select-company="selectCompany">
    <header class="border-b bg-white px-6 py-4">
      <h1 class="text-xl font-semibold text-gray-900">Run setup</h1>
    </header>

    <main class="mx-auto max-w-5xl space-y-6 p-6">
      <p v-if="!company" class="text-base text-gray-600">
        Select a company to run its setup.
      </p>
      <ErrorMessage v-else-if="run.error" :message="run.error" />
      <LoadingText v-else-if="!run.data" />

      <template v-else>
        <section
          class="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border bg-white px-6 py-4 text-base text-gray-900"
        >
          <span
            v-for="item in banner"
            :key="item.label"
            class="flex items-center gap-2"
          >
            <FeatherIcon
              :name="item.ok ? 'check-circle' : 'alert-circle'"
              class="h-4 w-4 shrink-0"
              :class="item.ok ? 'text-green-600' : 'text-orange-500'"
            />
            {{ item.label }}
          </span>
        </section>

        <Alert v-if="lockReason" title="Setup is locked">
          {{ lockReason }}
        </Alert>

        <section class="rounded-lg border bg-white">
          <div
            class="flex flex-wrap items-center justify-between gap-4 border-b px-6 py-4"
          >
            <div>
              <h2 class="text-lg font-semibold text-gray-900">
                Setting up {{ company }}
              </h2>
              <p class="text-sm text-gray-600">
                {{ doneCount }} of {{ steps.length }} steps done
              </p>
            </div>
            <Button
              variant="solid"
              label="Start setup"
              icon-left="play"
              :loading="starting || run.data.is_running"
              :disabled="Boolean(lockReason) || !steps.length"
              @click="start()"
            />
          </div>

          <div v-if="steps.length" class="px-6 pt-4">
            <Progress :value="progress" size="md" />
          </div>
          <p v-else class="px-6 py-8 text-base text-gray-600">
            No setup steps are installed yet.
          </p>

          <ul class="divide-y px-6">
            <li v-for="step in steps" :key="step.step" class="py-4">
              <div class="flex items-center justify-between gap-4">
                <div class="flex items-center gap-3 text-base text-gray-900">
                  <FeatherIcon
                    :name="STATUS_ICONS[step.status]"
                    class="h-4 w-4 shrink-0"
                    :class="[
                      STATUS_COLOURS[step.status],
                      { 'animate-spin': step.status === 'Running' },
                    ]"
                  />
                  {{ step.label }}
                  <Badge
                    v-if="getStepOwner(step)"
                    :label="getStepOwner(step)"
                    theme="blue"
                    variant="subtle"
                  />
                </div>
                <span class="text-sm text-gray-600">{{
                  getStepState(step)
                }}</span>
              </div>
              <div
                v-if="step.status === 'Running' || step.status === 'Done'"
                class="mt-2 pl-7"
              >
                <Progress size="sm" :value="getStepPercent(step)" />
              </div>
              <div
                v-if="step.status === 'Failed'"
                class="ml-7 mt-2 flex flex-wrap items-center justify-between gap-3"
              >
                <p class="text-sm text-red-600">{{ step.error }}</p>
                <Button
                  label="Try again"
                  icon-left="refresh-cw"
                  :disabled="run.data.is_running"
                  @click="start(step.step)"
                />
              </div>
            </li>
          </ul>

          <div
            v-if="runReport"
            class="space-y-1 border-t px-6 py-4 text-base text-gray-900"
          >
            <p>{{ runReport }}</p>
            <p>
              Next: download insurer prices and coverage from the Insurance
              page.
            </p>
          </div>
        </section>
      </template>
    </main>
  </SetupLayout>
</template>

<script setup>
import SetupLayout from "@/components/setup/SetupLayout.vue";
import { serverErrorText, useToast } from "@/composables/useToast";
import {
  applyStepProgress,
  getLockReason,
  getRunReport,
  getStepOwner,
  getStepPercent,
  getStepState,
} from "@/data/setupRun";
import { useSocket } from "@/socket";
import { Progress, call, createResource, usePageMeta } from "frappe-ui";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

usePageMeta(() => ({ title: "Run setup - HMS TZ" }));

const STATUS_ICONS = {
  Waiting: "circle",
  Running: "loader",
  Done: "check-circle",
  Failed: "x-circle",
};
const STATUS_COLOURS = {
  Waiting: "text-gray-400",
  Running: "text-gray-600",
  Done: "text-green-600",
  Failed: "text-red-600",
};
const POLL_MS = 2000;

const route = useRoute();
const router = useRouter();
const { showError } = useToast();

const company = ref(route.query.company || "");
const starting = ref(false);
let pollTimer = null;

const run = createResource({
  url: "hms_tz.api.setup_run.get_setup_run",
  makeParams: () => ({ company: company.value }),
  auto: Boolean(company.value),
});

const steps = computed(() => run.data?.steps || []);
const doneCount = computed(
  () => steps.value.filter((step) => step.status === "Done").length
);
const progress = computed(() =>
  steps.value.length
    ? Math.round((doneCount.value / steps.value.length) * 100)
    : 0
);
const runReport = computed(() => getRunReport(steps.value));

const lockReason = computed(() => getLockReason(run.data));

const banner = computed(() => {
  const records = run.data.standard_records;
  return [
    {
      ok: run.data.settings_complete,
      label: run.data.settings_complete
        ? "Settings complete"
        : "Settings incomplete",
    },
    {
      ok: run.data.rooms > 0,
      label: `${run.data.rooms} ${
        run.data.rooms === 1 ? "room" : "rooms"
      } added`,
    },
    {
      ok: true,
      label:
        `Standard records from HMS TZ: ${records.insurers} insurers, ${records.plans} plans, ` +
        `${records.schedules} schedules, ${records.room_types} room types`,
    },
  ];
});

watch(
  () => run.data?.is_running,
  (isRunning) => {
    clearInterval(pollTimer);
    if (isRunning) pollTimer = setInterval(() => run.reload(), POLL_MS);
  }
);
// Live step progress from the setup job; polling above is the fallback without a socket.
const socket = useSocket();
const onProgress = (message) => applyStepProgress(run.data, message);
onMounted(() => socket?.on("hms_tz_setup_progress", onProgress));
onBeforeUnmount(() => {
  clearInterval(pollTimer);
  socket?.off("hms_tz_setup_progress", onProgress);
});

function selectCompany(value) {
  company.value = value;
  router.replace({ query: { company: value } });
  run.reset();
  run.fetch();
}

async function start(fromStep = null) {
  starting.value = true;
  try {
    await call("hms_tz.api.setup_run.start_company_setup", {
      company: company.value,
      from_step: fromStep,
    });
    await run.reload();
  } catch (error) {
    showError(serverErrorText(error));
  } finally {
    starting.value = false;
  }
}
</script>
