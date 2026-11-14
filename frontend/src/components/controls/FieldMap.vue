<template>
  <div class="flex flex-col gap-6">
    <div
      v-for="section in sections"
      :key="section.label"
      class="first:border-t-0 first:pt-0"
      :class="section.hideBorder ? '' : 'border-t pt-4'"
    >
      <div
        v-if="!section.hideLabel"
        class="flex h-7 mb-3 text-xl font-bold text-blue-700 font-mono"
      >
        {{ section.label }}
      </div>

      <div
        class="grid gap-6"
        :class="
          section.columns
            ? 'grid-cols-' +
              section.columns +
              ' sm:grid-cols-' +
              section.columns
            : 'grid-cols-3 sm:grid-cols-3'
        "
      >
        <Fields :section="section" :data="data" />
      </div>
    </div>
  </div>
</template>

<script setup>
import Fields from "./Fields.vue";

defineProps({
  sections: Array,
  data: Object,
});
</script>

<style scoped>
:deep(.form-control.prefix select) {
  padding-left: 2rem;
}
</style>
