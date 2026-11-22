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

const PAID = {
  label: "Paid",
  icon: "check-circle",
  badge: "bg-white/70 text-[9px]",
};
// Solid badges in colours no status uses, so they stand out on every card.
const UNPAID = { label: "Unpaid", badge: "bg-pink-600 text-white text-[8px]" };
const NOT_AUTHORIZED = {
  label: "Not authorized",
  badge: "bg-violet-600 text-white text-[8px]",
};

/** Cash shows Paid or Unpaid; insurance shows Not authorized until it has an authorization number. */
export const getPaymentMarker = (appointment) => {
  if (appointment.status === "cancelled") return null;
  if (appointment.payment === "Cash") {
    if (appointment.ref_sales_invoice) return PAID;
    // invoice_appointment never invoices a follow-up, so nothing is due.
    return appointment.follow_up ? null : UNPAID;
  }
  return appointment.authorization_number ? null : NOT_AUTHORIZED;
};
