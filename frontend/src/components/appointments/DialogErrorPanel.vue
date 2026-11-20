<template>
  <section
    ref="panel"
    class="flex flex-col gap-3 rounded-lg border-2 border-red-500 bg-red-50 p-4"
    role="alert"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="flex items-center gap-2 text-red-700">
        <FeatherIcon name="alert-triangle" class="h-5 w-5 shrink-0" />
        <h3 class="text-base font-semibold">{{ error.title }}</h3>
      </div>
      <div class="flex gap-2">
        <Button variant="subtle" @click="copy">
          <template #prefix>
            <FeatherIcon name="copy" class="h-4 w-4" />
          </template>
          {{ copied ? "Copied" : "Copy" }}
        </Button>
        <Button variant="ghost" aria-label="Close" @click="emit('close')">
          <FeatherIcon name="x" class="h-4 w-4" />
        </Button>
      </div>
    </div>

    <div class="flex flex-col gap-1 text-sm text-gray-900">
      <p v-for="(line, index) in lines" :key="index" class="break-words">
        <template v-if="line.label">
          {{ line.label }} <strong>{{ line.value }}</strong>
        </template>
        <template v-else>{{ line.value || " " }}</template>
      </p>
    </div>
  </section>
</template>

<script setup>
import { toPlainText } from "@/composables/useToast";
import { computed, ref, watch } from "vue";

const props = defineProps({
  error: { type: Object, required: true },
});
const emit = defineEmits(["close"]);

const panel = ref(null);
const copied = ref(false);

const text = computed(() => toPlainText(props.error.message));
// The provider's own words follow "NHIF Response:" or "Jubilee Response:", shown bold as on the desk.
const lines = computed(() =>
  text.value.split("\n").map((line) => {
    const match = line.match(/^(.* Response:)\s*(.*)$/);
    return match ? { label: match[1], value: match[2] } : { value: line };
  })
);

const copy = async () => {
  await navigator.clipboard.writeText(`${props.error.title}\n${text.value}`);
  copied.value = true;
};

// A new error replaces the shown one, so the panel scrolls into view each time.
watch(
  () => props.error,
  () => {
    copied.value = false;
    panel.value?.scrollIntoView({ block: "nearest" });
  },
  { immediate: true, flush: "post" }
);
</script>
