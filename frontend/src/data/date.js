import { defineStore } from "pinia";
import dayjs from "dayjs";

/** Start of the slot that contains an "HH:mm" time, e.g. 08:05 -> 08:00 for 10-minute slots. */
export const getSlotTime = (time, slotDuration) => {
  const [hours, minutes] = time.split(":").map(Number);
  const slotMinutes =
    Math.floor((hours * 60 + minutes) / slotDuration) * slotDuration;
  return dayjs().startOf("day").add(slotMinutes, "minute").format("HH:mm");
};

export const useDateStore = defineStore("date", {
  state: () => ({
    selectedDate: dayjs().format("YYYY-MM-DD"),
    slotDuration: 10, // minutes
    bufferTime: 5, // minutes buffer for future bookings
  }),

  getters: {
    /** Slots of `slotDuration` minutes across the whole selected day. */
    timeSlots: (state) => {
      const day = dayjs(state.selectedDate);
      const slots = [];
      for (let minute = 0; minute < 24 * 60; minute += state.slotDuration) {
        const slotStart = day.add(minute, "minute");
        slots.push({
          time: slotStart.format("HH:mm"),
          display: slotStart.format("h:mm A"),
          timestamp: slotStart.valueOf(),
        });
      }
      return slots;
    },
  },

  actions: {
    setSelectedDate(date) {
      this.selectedDate = dayjs(date).format("YYYY-MM-DD");
    },

    goToPreviousDay() {
      const previousDay = dayjs(this.selectedDate).subtract(1, "day");
      this.setSelectedDate(previousDay);
    },

    goToNextDay() {
      const nextDay = dayjs(this.selectedDate).add(1, "day");
      this.setSelectedDate(nextDay);
    },
  },
});
