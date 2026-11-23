<template>
  <div class="desk-search-bar" ref="containerRef">
    <div class="search-input-wrapper">
      <svg
        class="search-icon"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
      <input
        ref="searchInput"
        v-model="query"
        type="text"
        placeholder="Search patients, appointments, pages..."
        class="search-input"
        @input="onInput"
        @focus="isFocused = true"
        @keydown.escape="clearSearch"
        @keydown.enter="onEnter"
        @keydown.down.prevent="moveSelection(1)"
        @keydown.up.prevent="moveSelection(-1)"
      />
      <kbd v-if="!query" class="search-shortcut">Ctrl K</kbd>
      <button v-else class="close-btn" @click="clearSearch">
        <svg
          class="h-3.5 w-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </div>

    <!-- Results dropdown -->
    <div v-if="showResults" class="search-results">
      <div v-if="isSearching" class="search-status">
        <span class="search-spinner"></span>
        Searching...
      </div>

      <template v-else-if="results.length">
        <div
          v-for="section in sections"
          :key="section.type"
          class="results-section"
        >
          <div class="results-section-title">{{ section.title }}</div>
          <button
            v-for="item in section.items"
            :key="item.index"
            class="result-item"
            :class="{ 'result-active': selectedIndex === item.index }"
            @click="navigateTo(item)"
            @mouseenter="selectedIndex = item.index"
          >
            <svg
              class="result-icon"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                :d="section.icon"
              />
            </svg>
            <div class="result-text">
              <span class="result-title">{{ item.label }}</span>
              <span class="result-subtitle">{{ item.description }}</span>
            </div>
          </button>
        </div>
      </template>

      <div v-else-if="searchError" class="search-status">
        Search failed: {{ searchError }}
      </div>
      <div v-else-if="query.length >= 2" class="search-status">
        No results found
      </div>
      <div v-else class="search-status">
        Type at least 2 characters to search
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { call, createResource } from "frappe-ui";
import {
  matchPages,
  toOtherRecordResults,
  toRecordResults,
} from "@/data/search";

const router = useRouter();

const containerRef = ref(null);
const searchInput = ref(null);
const query = ref("");
const isFocused = ref(false);
const isSearching = ref(false);
const selectedIndex = ref(-1);
const results = ref([]);
const searchError = ref("");
let debounceTimer = null;

// Custom frontend routes (not DocTypes — always available)
const CUSTOM_PAGES = [
  {
    label: "Nurse Roster",
    description: "Open Nurse Roster",
    route: "/frontend/nurse-roster",
    type: "page",
  },
  {
    label: "OT Roster",
    description: "Open OT Roster",
    route: "/frontend/ot-roster",
    type: "page",
  },
];

// Module-level cache: loaded once, shared across all component instances
const pages = ref([...CUSTOM_PAGES]);
let pagesLoaded = false;

// Resource to load permitted doctypes (called once on mount)
const permittedDoctypesResource = createResource({
  url: "hms_tz.api.search.get_permitted_doctypes",
  auto: false,
  onSuccess(data) {
    if (data) {
      pages.value = [...data, ...CUSTOM_PAGES];
      pagesLoaded = true;
    }
  },
  onError(e) {
    console.warn("Failed to load permitted doctypes:", e);
  },
});

async function loadPermittedDoctypes() {
  if (pagesLoaded) return;
  permittedDoctypesResource.fetch();
}

// Global search fills this many rows before Patient and Patient Appointment rows are dropped.
const OTHER_RECORD_ROWS = 12;
const DOCUMENT_ICON =
  "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z";
const SECTIONS = [
  { type: "page", title: "Pages", icon: DOCUMENT_ICON },
  {
    type: "patient",
    title: "Patients",
    icon: "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
  },
  {
    type: "appointment",
    title: "Appointments",
    icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
  },
  { type: "record", title: "Other records", icon: DOCUMENT_ICON },
];

// Rows keep their place in results, so the arrow keys walk the sections in order.
const sections = computed(() =>
  SECTIONS.map((section) => ({
    ...section,
    items: results.value
      .map((item, index) => ({ ...item, index }))
      .filter((item) => item.type === section.type),
  })).filter((section) => section.items.length)
);
const showResults = computed(() => isFocused.value && query.value.length > 0);

function clearSearch() {
  query.value = "";
  results.value = [];
  selectedIndex.value = -1;
  searchInput.value?.blur();
  isFocused.value = false;
}

function onInput() {
  clearTimeout(debounceTimer);
  selectedIndex.value = -1;

  if (query.value.length < 2) {
    results.value = [];
    return;
  }

  debounceTimer = setTimeout(() => search(), 300);
}

async function search() {
  const q = query.value.trim();
  if (q.length < 2) return;

  isSearching.value = true;
  searchError.value = "";
  try {
    const [records, otherRecords] = await Promise.all([
      call("hms_tz.api.search.search_patients_and_appointments", { txt: q }),
      call("frappe.utils.global_search.search", {
        text: q,
        start: 0,
        limit: OTHER_RECORD_ROWS,
      }),
    ]);
    if (q !== query.value.trim()) return;
    results.value = [
      ...matchPages(pages.value, q),
      ...toRecordResults(records),
      ...toOtherRecordResults(otherRecords),
    ];
  } catch (error) {
    results.value = [];
    searchError.value = error.messages?.[0] || error.message;
  } finally {
    isSearching.value = false;
  }
}

function moveSelection(delta) {
  const total = results.value.length;
  if (total === 0) return;
  selectedIndex.value = (selectedIndex.value + delta + total) % total;
}

function onEnter() {
  if (selectedIndex.value >= 0 && selectedIndex.value < results.value.length) {
    navigateTo(results.value[selectedIndex.value]);
  }
}

function navigateTo(item) {
  clearSearch();
  if (item.type === "appointment") {
    router.push({ name: "Appointments", query: item.query });
  } else if (item.type === "patient" || item.type === "record") {
    // A new tab keeps the appointments page open.
    window.open(item.route, "_blank");
  } else {
    window.location.href = item.route;
  }
}

// Keyboard shortcut: Ctrl+K to focus search
function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "k") {
    e.preventDefault();
    searchInput.value?.focus();
    isFocused.value = true;
  }
}

// Click outside to close results
function handleClickOutside(e) {
  if (containerRef.value && !containerRef.value.contains(e.target)) {
    isFocused.value = false;
  }
}

onMounted(() => {
  document.addEventListener("keydown", handleKeydown);
  document.addEventListener("click", handleClickOutside);
  loadPermittedDoctypes();
});

onUnmounted(() => {
  document.removeEventListener("keydown", handleKeydown);
  document.removeEventListener("click", handleClickOutside);
  clearTimeout(debounceTimer);
});
</script>

<style scoped>
.desk-search-bar {
  position: relative;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  background: white;
  border: none;
  border-radius: 8px;
  padding: 0 10px;
  height: 36px;
  width: 320px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.search-icon {
  width: 16px;
  height: 16px;
  color: #9ca3af;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 13px;
  color: #1f2937;
  background: transparent;
  min-width: 0;
}

.search-input::placeholder {
  color: #9ca3af;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  flex-shrink: 0;
}

.close-btn:hover {
  background: #f3f4f6;
  color: #6b7280;
}

.search-shortcut {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px 5px;
  font-size: 10px;
  font-family: inherit;
  color: #9ca3af;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
}

.search-results {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  width: 360px;
  max-height: 380px;
  overflow-y: auto;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08), 0 4px 10px rgba(0, 0, 0, 0.04);
  z-index: 50;
}

.search-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  font-size: 13px;
  color: #6b7280;
}

.search-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.results-section {
  padding: 4px 0;
}

.results-section + .results-section {
  border-top: 1px solid #f3f4f6;
}

.results-section-title {
  padding: 6px 16px 4px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #9ca3af;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s ease;
}

.result-item:hover,
.result-active {
  background: #f3f4f6;
}

.result-icon {
  width: 16px;
  height: 16px;
  color: #9ca3af;
  flex-shrink: 0;
}

.result-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.result-title {
  font-size: 13px;
  font-weight: 500;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-subtitle {
  font-size: 11px;
  color: #9ca3af;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
