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
    timeSlots: [],
    workingHours: {
      start: "08:00",
      end: "07:50",
    },
    slotDuration: 10, // minutes
    bufferTime: 5, // minutes buffer for future bookings
  }),

  actions: {
    setSelectedDate(date) {
      this.selectedDate = dayjs(date).format("YYYY-MM-DD");
      this.generateTimeSlots();
    },

    goToPreviousDay() {
      const previousDay = dayjs(this.selectedDate).subtract(1, "day");
      this.setSelectedDate(previousDay);
    },

    goToNextDay() {
      const nextDay = dayjs(this.selectedDate).add(1, "day");
      this.setSelectedDate(nextDay);
    },

    generateTimeSlots() {
      const slots = [];
      const startTime = dayjs(
        `${this.selectedDate} ${this.workingHours.start}`
      );
      const endTime = dayjs(
        `${this.selectedDate} ${this.workingHours.end}`
      ).add(1, "day");

      let startTimeSlot = startTime;

      while (startTimeSlot.isBefore(endTime)) {
        const timeString = startTimeSlot.format("HH:mm");

        slots.push({
          time: timeString,
          display: startTimeSlot.format("h:mm A"),
          timestamp: startTimeSlot.valueOf(),
        });

        startTimeSlot = startTimeSlot.add(this.slotDuration, "minute");
      }

      this.timeSlots = slots;
    },
  },
});
