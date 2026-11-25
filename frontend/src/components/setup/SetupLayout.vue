<template>
  <div class="flex min-h-screen flex-col bg-gray-50 md:flex-row">
    <aside
      class="flex shrink-0 flex-col border-b bg-gray-100 px-3 py-4 md:sticky md:top-0 md:h-screen md:w-64 md:border-b-0 md:border-r"
    >
      <h1 class="px-2 text-lg font-semibold text-gray-900">HMS TZ Setup</h1>
      <div class="mt-3">
        <Link
          doctype="Company"
          :value="company"
          placeholder="Select company"
          @change="(value) => emit('select-company', value)"
        />
      </div>

      <nav v-if="company" class="mt-1 flex-1 overflow-y-auto">
        <div v-for="group in groups" :key="group.label" class="mt-4">
          <p class="px-2 pb-1 text-xs font-medium uppercase text-gray-500">
            {{ group.label }}
          </p>
          <router-link
            v-for="screen in group.screens"
            :key="screen.route"
            :to="{ name: screen.route, query: { company } }"
            class="flex h-8 items-center gap-2 rounded px-2 text-base"
            :class="
              route.name === screen.route
                ? 'bg-white font-medium text-gray-900 shadow-sm'
                : 'text-gray-700 hover:bg-gray-200'
            "
          >
            <FeatherIcon :name="screen.icon" class="h-4 w-4 shrink-0" />
            <span class="flex-1 truncate">{{ screen.label }}</span>
            <Badge
              v-if="screen.toReview"
              :label="String(screen.toReview)"
              theme="orange"
              variant="subtle"
            />
            <FeatherIcon
              v-else-if="screen.status"
              :name="screen.status === 'done' ? 'check-circle' : 'circle'"
              class="h-3.5 w-3.5 shrink-0"
              :class="
                screen.status === 'done' ? 'text-green-600' : 'text-gray-400'
              "
            />
          </router-link>
        </div>
      </nav>
      <p v-else class="mt-4 flex-1 px-2 text-sm text-gray-600">
        Select a company to see its setup screens.
      </p>

      <Button
        v-if="company"
        class="mt-3 w-full"
        variant="solid"
        icon-left="play"
        :label="getRunLabel(navigation.data)"
        :route="{ name: 'SetupRun', query: { company } }"
      />
    </aside>

    <div class="min-w-0 flex-1">
      <slot />
    </div>
  </div>
</template>

<script setup>
import Link from "@/components/controls/Link.vue";
import { getNavigationGroups, getRunLabel } from "@/data/setupNavigation";
import { createResource } from "frappe-ui";
import { computed, watch } from "vue";
import { useRoute } from "vue-router";

const props = defineProps({ company: { type: String, default: "" } });
const emit = defineEmits(["select-company"]);
const route = useRoute();

const navigation = createResource({
  url: "hms_tz.api.setup.get_setup_navigation",
  makeParams: () => ({ company: props.company }),
});

const groups = computed(() => getNavigationGroups(navigation.data));

/** Fetch the screen statuses again, for example after a screen saved something. */
function reload() {
  if (props.company) navigation.fetch();
}

watch(() => [props.company, route.name], reload, { immediate: true });

defineExpose({ reload });
</script>
