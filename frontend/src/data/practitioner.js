import { defineStore } from "pinia";
import { call } from "frappe-ui";
import { fetchLatest } from "./latestRequest";

export const usePractitionerStore = defineStore("practitioners", {
  state: () => ({
    practitioners: [],
    isFetching: false,
    loadError: null,
    searchQuery: "",
    latestRequest: 0,
  }),

  getters: {
    filteredPractitioners: (state) => {
      let filtered = state.practitioners;

      // Apply search query
      if (state.searchQuery) {
        filtered = filtered.filter(
          (practitioner) =>
            practitioner.name
              .toLowerCase()
              .includes(state.searchQuery.toLowerCase()) ||
            practitioner.department
              .toLowerCase()
              .includes(state.searchQuery.toLowerCase())
        );
      }

      return filtered;
    },
  },

  actions: {
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
