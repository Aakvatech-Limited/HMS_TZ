/** Card colours for the hms_tz Patient Appointment statuses. Keys are lower case. */
export const APPOINTMENT_STATUSES = [
  {
    status: "scheduled",
    label: "Scheduled",
    card: "bg-orange-200 border-orange-500 hover:bg-orange-300",
    text: "text-orange-900",
  },
  {
    status: "open",
    label: "Open",
    card: "bg-yellow-200 border-yellow-500 hover:bg-yellow-300",
    text: "text-yellow-900",
  },
  {
    status: "closed",
    label: "Closed",
    card: "bg-green-200 border-green-500 hover:bg-green-300",
    text: "text-green-900",
  },
  {
    status: "cancelled",
    label: "Cancelled",
    card: "bg-red-200 border-red-500 hover:bg-red-300",
    text: "text-red-900",
  },
];

const UNKNOWN_STATUS = {
  label: "Unknown",
  card: "bg-gray-200 border-gray-400 hover:bg-gray-300",
  text: "text-gray-900",
};

const STYLE_BY_STATUS = Object.fromEntries(
  APPOINTMENT_STATUSES.map((style) => [style.status, style])
);
// The card has always shown "completed" like "closed".
STYLE_BY_STATUS.completed = STYLE_BY_STATUS.closed;

export const getStatusStyle = (status) =>
  STYLE_BY_STATUS[status] || UNKNOWN_STATUS;
