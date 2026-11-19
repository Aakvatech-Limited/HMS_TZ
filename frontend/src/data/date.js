import { defineStore } from "pinia";
import dayjs from "dayjs";

/** Start of the slot that contains an "HH:mm" time, e.g. 08:05 -> 08:00 for 10-minute slots. */
export const getSlotTime = (time, slotDuration) => {
  const [hours, minutes] = time.split(":").map(Number);
  const slotMinutes =
    Math.floor((hours * 60 + minutes) / slotDuration) * slotDuration;
  return dayjs().startOf("day").add(slotMinutes, "minute").format("HH:mm");
};

/** One day of `slotDuration`-minute slots on `date`, listed from `dayStartHour` and wrapping past midnight back to it. */
export const getTimeSlots = (date, slotDuration, dayStartHour) => {
  const day = dayjs(date);
  const dayMinutes = 24 * 60;
  const startMinute = dayStartHour * 60;
  const slots = [];
  for (let offset = 0; offset < dayMinutes; offset += slotDuration) {
    const slotStart = day.add((startMinute + offset) % dayMinutes, "minute");
    slots.push({
      time: slotStart.format("HH:mm"),
      timestamp: slotStart.valueOf(),
    });
  }
  return slots;
};

export const useDateStore = defineStore("date", {
  state: () => ({
    selectedDate: dayjs().format("YYYY-MM-DD"),
    slotDuration: 10, // minutes; the grid sets it per company from HMS TZ Setting
    dayStartHour: 7, // first row of the grid
    bufferTime: 5, // minutes buffer for future bookings
  }),

  getters: {
    timeSlots: (state) =>
      getTimeSlots(state.selectedDate, state.slotDuration, state.dayStartHour),
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
