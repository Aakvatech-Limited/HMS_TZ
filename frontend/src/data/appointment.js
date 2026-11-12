import { defineStore } from "pinia";
import { call, createResource } from "frappe-ui";
import dayjs from "dayjs";
import { useToast } from "../composables/useToast";
import { getSlotTime, useDateStore } from "./date";
import { fetchLatest } from "./latestRequest";
import { usePractitionerStore } from "./practitioner";

const APPOINTMENT_FIELDS = [
  "name",
  "patient",
  "patient_name",
  "patient_sex",
  "practitioner",
  "appointment_time",
  "appointment_date",
  "status",
  "appointment_type",
  "department",
  "company",
  "insurance_company",
  "mode_of_payment",
  "billing_item",
  "paid_amount",
  "invoiced",
  "ref_sales_invoice",
  "referral_no",
  "remarks",
  "coverage_plan_name",
  "nhif_employer_name",
  "daily_limit",
  "apply_fasttrack_charge",
  "authorization_number",
  "poc_reference_no",
  "require_fingerprint",
  "require_facial_recognation",
  "biometric_method",
  "fpcode",
];

const toAppointment = (appointment) => ({
  id: appointment.name,
  name: appointment.name,
  patient: appointment.patient,
  patient_name: appointment.patient_name,
  patient_sex: appointment.patient_sex,
  practitioner: appointment.practitioner,
  appointment_time: dayjs(`2024-01-01 ${appointment.appointment_time}`).format(
    "HH:mm"
  ), // Normalize to HH:mm format
  appointment_date: appointment.appointment_date,
  status: appointment.status?.toLowerCase() || "scheduled",
  appointment_type: appointment.appointment_type,
  department: appointment.department,
  company: appointment.company,
  insurance_company: appointment.insurance_company || "Cash",
  insurance_subscription: appointment.insurance_subscription,
  billing_item: appointment.billing_item,
  paid_amount: appointment.paid_amount || 0,
  mode_of_payment: appointment.mode_of_payment,
  invoiced: appointment.invoiced,
  ref_sales_invoice: appointment.ref_sales_invoice,
  referral_no: appointment.referral_no,
  remarks: appointment.remarks,
  coverage_plan_name: appointment.coverage_plan_name,
  nhif_employer_name: appointment.nhif_employer_name,
  daily_limit: appointment.daily_limit,
  apply_fasttrack_charge: appointment.apply_fasttrack_charge,
  authorization_number: appointment.authorization_number,
  poc_reference_no: appointment.poc_reference_no,
  require_fingerprint: appointment.require_fingerprint,
  require_facial_recognation: appointment.require_facial_recognation,
  biometric_method: appointment.biometric_method,
  fpcode: appointment.fpcode,
});

export const useAppointmentStore = defineStore("appointments", {
  state: () => ({
    appointments: [],
    isLoading: false,
    error: null,
    isFetching: false,
    loadError: null,
    latestRequest: 0,
    userRoles: [],
    rolesLoading: false,
  }),

  getters: {
    /** Slot time to practitioner to appointments, with each time floored to its slot. */
    appointmentsBySlot: (state) => {
      const { slotDuration } = useDateStore();
      const bySlot = new Map();
      for (const appointment of state.appointments) {
        const slotTime = getSlotTime(
          appointment.appointment_time,
          slotDuration
        );
        if (!bySlot.has(slotTime)) bySlot.set(slotTime, new Map());
        const byPractitioner = bySlot.get(slotTime);
        if (!byPractitioner.has(appointment.practitioner))
          byPractitioner.set(appointment.practitioner, []);
        byPractitioner.get(appointment.practitioner).push(appointment);
      }
      return bySlot;
    },

    canCancelAppointment: (state) => {
      const allowedRoles = [
        "System Manager",
        "Healthcare Administrator",
        "Healthcare Head Receptionist",
      ];
      return state.userRoles.some((role) => allowedRoles.includes(role));
    },
  },

  actions: {
    /** Load practitioners and appointments for one company and date. */
    async loadDay(company, date) {
      await Promise.all([
        usePractitionerStore().fetchPractitioners(company, date),
        this.fetchAppointments(company, date),
      ]);
    },

    fetchAppointments(company, date) {
      return fetchLatest(
        this,
        () =>
          company
            ? call("frappe.client.get_list", {
                doctype: "Patient Appointment",
                fields: APPOINTMENT_FIELDS,
                filters: { appointment_date: date, company },
                order_by: "appointment_time asc",
                limit_page_length: 0,
              })
            : [],
        (rows) => {
          this.appointments = rows.map(toAppointment);
        }
      );
    },

    async fetchUserRoles() {
      this.rolesLoading = true;
      this.error = null;

      try {
        const userRolesResource = createResource({
          url: "hms_tz.api.appointment.get_user_roles",
          auto: false,
        });

        const roles = await userRolesResource.fetch();
        this.userRoles = roles || [];

        return { success: true, roles: this.userRoles };
      } catch (error) {
        this.error = error.message || "Failed to fetch user roles";
        const { notifications } = useToast();
        notifications.error.dataLoadFailed(error.message || "user roles");
        this.userRoles = [];
        return { success: false, error: error.message };
      } finally {
        this.rolesLoading = false;
      }
    },
  },
});
