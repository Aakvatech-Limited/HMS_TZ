import { defineStore } from "pinia";
import dayjs from "dayjs";

/** Start of the slot that contains an "HH:mm" time, e.g. 08:05 -> 08:00 for 10-minute slots. */
export const getSlotTime = (time, slotDuration) => {
  const [hours, minutes] = time.split(":").map(Number);
  const slotMinutes =
    Math.floor((hours * 60 + minutes) / slotDuration) * slotDuration;
  return dayjs().startOf("day").add(slotMinutes, "minute").format("HH:mm");
};

/** One day of `slotDuration`-minute slots on `date`, from 00:00 to the last slot that starts before midnight. */
export const getTimeSlots = (date, slotDuration) => {
  const day = dayjs(date);
  const slots = [];
  for (let minute = 0; minute < 24 * 60; minute += slotDuration) {
    const slotStart = day.add(minute, "minute");
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
    bufferTime: 5, // minutes buffer for future bookings
  }),

  getters: {
    timeSlots: (state) => getTimeSlots(state.selectedDate, state.slotDuration),
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
