import { defineStore } from "pinia";
import { call } from "frappe-ui";
import {
  EMPTY_PRACTITIONER_FILTERS,
  contains,
  matchesPractitioner,
} from "./appointmentFilters";
import { fetchLatest } from "./latestRequest";

export const usePractitionerStore = defineStore("practitioners", {
  state: () => ({
    practitioners: [],
    isFetching: false,
    loadError: null,
    searchQuery: "",
    filters: { ...EMPTY_PRACTITIONER_FILTERS },
    latestRequest: 0,
  }),

  getters: {
    filteredPractitioners: (state) =>
      state.practitioners.filter(
        (practitioner) =>
          (contains(practitioner.name, state.searchQuery) ||
            contains(practitioner.department, state.searchQuery)) &&
          matchesPractitioner(practitioner, state.filters)
      ),
  },

  actions: {
    clearFilters() {
      this.filters = { ...EMPTY_PRACTITIONER_FILTERS };
    },

    setSearchQuery(query) {
      this.searchQuery = query;
    },

    fetchPractitioners(company, date) {
      return fetchLatest(
        this,
        () =>
          company
            ? call("hms_tz.api.practitioner.get_practioner_list", {
                company,
                date,
              })
            : [],
        (data) => {
          this.practitioners = data?.practitioners || data || [];
        }
      );
    },
  },
});
