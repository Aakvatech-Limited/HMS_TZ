import { useToast } from "@/composables/useToast";
import {
  authorizeJubileePatient,
  authorizeNhifPatient,
  checkCard as checkCardApi,
  createAppointment,
  createPatient,
  createSubscription,
  getInsuranceApiSettings,
  getPatient,
  getSubscription,
  NHIF_WAIT_MESSAGE,
  validateNewPatientCashBooking,
} from "@/data/insurance";
import { computed, reactive, ref } from "vue";
import dayjs from "dayjs";

const PATIENT_CARD_FIELDS = [
  "first_name",
  "middle_name",
  "last_name",
  "sex",
  "dob",
  "mobile",
];

const emptyPatient = () => ({
  first_name: "",
  middle_name: "",
  last_name: "",
  sex: "",
  dob: "",
  mobile: "",
  demography: "",
  common_occupation: "",
  ethnicity: "",
  how_did_you_hear_about_us: "",
  referred_from: "",
  next_to_kin_name: "",
  next_to_kin_mobile_no: "",
  next_to_kin_relationship: "",
});

const emptySubscription = () => ({
  insurance_company: "",
  healthcare_insurance_coverage_plan: "",
  coverage_plan_card_number: "",
  national_id: "",
});

const DEFAULT_NHIF_CARD_TYPE = "NHIF Beneficiary Card";

export const patientSummary = (patient) => {
  if (!patient) return "";
  const age = patient.dob ? `Age ${dayjs().diff(patient.dob, "year")}` : "";
  const mobile = patient.mobile ? `Mob ${patient.mobile}` : "";
  return [patient.patient_name, patient.sex, age, mobile]
    .filter(Boolean)
    .join(" · ");
};

/** State and server calls of the New Appointment form. */
export function useBookingForm(initial) {
  const {
    showError,
    showErrorReply,
    showSuccess,
    clearError,
    handleResourceError,
  } = useToast();
  const settings = ref({ enable_nhif_api: false, enable_jubilee_api: false });
  const busy = ref(false);
  const status = ref({ title: "", message: "", percent: 0 });

  const form = reactive({
    company: initial.company,
    practitioner: initial.practitioner,
    appointment_date: initial.appointment_date,
    appointment_time: initial.appointment_time,
    appointment_type: "",
    visitType: { requires_remarks: 0, requires_referral_no: 0 },
    payment: "Cash",
    card_type: "",
    card_no: "",
    card: null,
    cardStatus: null,
    patientMode: "existing",
    patient: "",
    patientDetails: null,
    newPatient: emptyPatient(),
    subscriptionMode: "existing",
    subscription: null,
    newSubscription: emptySubscription(),
    fromCard: {},
    verification: {
      method: "FINGERPRINT",
      referral_no: "",
      remarks: "",
      authorization_number: "",
    },
    authorization: null,
  });

  const isInsurance = computed(() => form.payment !== "Cash");
  const canCheckCard = computed(
    () =>
      (form.payment === "NHIF" && settings.value.enable_nhif_api) ||
      (form.payment === "Jubilee" && settings.value.enable_jubilee_api)
  );
  const isNhif = computed(() => form.payment === "NHIF");
  const creates = computed(() => {
    const docs = [];
    if (form.patientMode === "new") docs.push("Patient");
    if (isInsurance.value && form.subscriptionMode === "new")
      docs.push("Insurance Subscription");
    docs.push("Appointment");
    return `Creates: ${docs.join(" → ")}`;
  });
  const canAuthorize = computed(
    () =>
      Boolean(form.appointment_type) &&
      (form.patientMode !== "existing" || Boolean(form.patient)) &&
      (form.subscriptionMode !== "existing" || Boolean(form.subscription)) &&
      !form.verification.authorization_number
  );
  const jubileeCardNo = () =>
    (form.subscriptionMode === "new"
      ? form.newSubscription.coverage_plan_card_number
      : form.subscription?.coverage_plan_card_number) || form.card_no;
  const canAuthorizeJubilee = computed(
    () => canAuthorize.value && Boolean(jubileeCardNo())
  );
  // Authorization is a separate step; an insurance appointment can be authorized later from Edit.
  const canSubmit = computed(() => !busy.value);

  const loadSettings = async () => {
    settings.value = await getInsuranceApiSettings(form.company);
  };

  const setStatus = (message, percent) => {
    status.value = { ...status.value, message, percent };
  };

  // The title names the action on the progress overlay.
  const run = async (title, work) => {
    // One request at a time: a second click while NHIF is busy would authorize twice.
    if (busy.value) return null;
    status.value = { title, message: "", percent: 0 };
    busy.value = true;
    clearError();
    try {
      return await work();
    } catch (error) {
      handleResourceError(error);
      return null;
    } finally {
      busy.value = false;
      setStatus("", 0);
    }
  };

  // Keeps a number typed in from the NHIF portal; drops one NHIF returned.
  const clearAuthorization = () => {
    if (form.authorization) form.verification.authorization_number = "";
    form.authorization = null;
  };

  const setPayment = (payment) => {
    form.payment = payment;
    form.cardStatus = null;
    clearAuthorization();
    form.subscription = null;
    form.subscriptionMode = "existing";
  };

  const selectPatient = async (name) => {
    form.patient = name;
    form.patientDetails = name ? await getPatient(name) : null;
    if (form.subscription && form.subscription.patient !== name) {
      form.subscription = null;
    }
  };

  const applySubscription = async (subscription) => {
    form.subscription = subscription;
    form.subscriptionMode = "existing";
    clearAuthorization();
    if (!subscription) return;
    form.card_no = subscription.coverage_plan_card_number || form.card_no;
    if (isNhif.value)
      form.card_type = subscription.card_type_name || DEFAULT_NHIF_CARD_TYPE;
    form.patientMode = "existing";
    await selectPatient(subscription.patient);
  };

  const selectSubscription = (name) =>
    run("Loading Subscription", async () =>
      applySubscription(name ? await getSubscription(name) : null)
    );

  const fillNewPatientFromCard = (card) => {
    form.patientMode = "new";
    form.fromCard = {};
    for (const field of PATIENT_CARD_FIELDS) {
      if (!card[field]) continue;
      form.newPatient[field] = card[field];
      form.fromCard[field] = true;
    }
  };

  const fillNewSubscriptionFromCard = (result) => {
    form.subscriptionMode = "new";
    form.newSubscription = {
      insurance_company: result.coverage_plan?.insurance_company || "",
      healthcare_insurance_coverage_plan: result.coverage_plan?.name || "",
      coverage_plan_card_number: result.card.card_no,
      national_id: result.card.national_id,
    };
    if (result.coverage_plan)
      form.fromCard.healthcare_insurance_coverage_plan = true;
  };

  const applyCardResult = async (result) => {
    form.card = result.card;
    clearAuthorization();
    if (result.patient) {
      form.patientMode = "existing";
      form.patient = result.patient.name;
      form.patientDetails = result.patient;
      form.fromCard = { patient: true };
    } else {
      fillNewPatientFromCard(result.card);
    }
    if (result.subscription) {
      form.subscription = result.subscription;
      form.subscriptionMode = "existing";
    } else {
      form.subscription = null;
      fillNewSubscriptionFromCard(result);
    }
    form.cardStatus = cardStatusFor(result);
  };

  const cardStatusFor = (result, inHms = "found in HMS") => {
    const holder = result.card.full_name || form.payment;
    if (result.subscription) {
      return {
        tone: "success",
        title: `Card active — ${holder}`,
        text: `${
          result.subscription.coverage_plan_name ||
          result.subscription.healthcare_insurance_coverage_plan
        } · Patient and subscription ${inHms} and loaded below`,
      };
    }
    if (result.patient) {
      return {
        tone: "info",
        title: `Card found — ${holder} · new card`,
        text: "The patient is in HMS, but no subscription has this card. Create new is selected below.",
      };
    }
    return {
      tone: "info",
      title: `Card found — ${holder} · not yet in HMS`,
      text: "A new patient and a new subscription will be created from the card details. Check them before you continue.",
    };
  };

  const checkCard = () =>
    run(`Checking with ${form.payment}`, async () => {
      if (isNhif.value && !form.card_type) {
        showError("Select the card type");
        return;
      }
      if (!form.card_no) {
        showError("Enter the card no");
        return;
      }
      form.cardStatus = null;
      const result = await checkCardApi(
        form.company,
        form.payment,
        form.card_no,
        isNhif.value ? form.card_type : ""
      );
      await applyCardResult(result);
    });

  // The banner from the card check describes records still to create; this updates it once they are saved.
  const refreshCardStatus = () => {
    if (!form.cardStatus || !form.card) return;
    form.cardStatus = cardStatusFor(
      {
        card: form.card,
        patient: form.patientDetails,
        subscription:
          form.subscriptionMode === "existing" ? form.subscription : null,
      },
      "saved in HMS"
    );
  };

  const ensurePatient = async () => {
    if (form.patientMode !== "new") return;
    setStatus("Creating the patient record...", 25);
    const patient = await createPatient({
      ...form.newPatient,
      card_no: isInsurance.value ? form.card?.card_no || form.card_no : "",
      national_id: isInsurance.value ? form.card?.national_id || "" : "",
      card_type: isNhif.value ? form.card_type : "",
    });
    form.patientMode = "existing";
    await selectPatient(patient.name);
    refreshCardStatus();
  };

  const ensureSubscription = async () => {
    if (!isInsurance.value || form.subscriptionMode !== "new") return;
    setStatus("Creating the insurance subscription...", 50);
    const subscription = await createSubscription({
      patient: form.patient,
      company: form.company,
      hms_tz_scheme_id: form.card?.scheme_id || "",
      hms_tz_scheme_name: form.card?.scheme_name || "",
      ...form.newSubscription,
      card_type: isNhif.value ? form.card_type : "",
    });
    form.subscription = subscription;
    form.subscriptionMode = "existing";
    refreshCardStatus();
  };

  const authorizeNhif = (captureBiometric) =>
    run("Authorizing Patient", async () => {
      const errors = validationErrors({ forAuthorization: true });
      if (errors.length) return showErrors(errors);
      await ensurePatient();
      await ensureSubscription();
      const method = form.verification.method;
      const biometric =
        method === "NONE"
          ? { Data: "", fpCode: "" }
          : await captureBiometric(method);
      if (!biometric) return;
      setStatus(NHIF_WAIT_MESSAGE, 75);
      const data = await authorizeNhifPatient({
        insurance_subscription: form.subscription.name,
        appointment_type: form.appointment_type,
        company: form.company,
        card_no: form.subscription.coverage_plan_card_number || form.card_no,
        national_id: form.subscription.national_id || "",
        fingerprint: biometric.Data,
        fpcode: biometric.fpCode,
        biometric_method: method,
        practitioner: form.practitioner,
        referral_no: form.verification.referral_no,
        remarks: form.verification.remarks,
      });
      form.verification.authorization_number = data.authorizationNo;
      if (data.authorizationStatus !== "ACCEPTED") {
        showErrorReply({
          title: data.authorizationStatus,
          message: data.remarks,
        });
      } else {
        showSuccess(
          `NHIF authorized the patient: authorization no ${data.authorizationNo}`
        );
      }
      form.authorization = {
        coverage_plan_name: data.coveragePlanName,
        nhif_employer_name: data.employerName,
        fpcode: data.fpCode,
        poc_reference_no: data.ReferenceNo,
        years_of_insurance: Number.parseInt(data.serviceYear) || 0,
        biometric_method: method,
        require_fingerprint: method === "FINGERPRINT" ? 1 : 0,
        require_facial_recognation: method === "FACIAL" ? 1 : 0,
      };
    });

  const authorizeJubilee = () =>
    run("Authorizing Patient", async () => {
      const errors = validationErrors({ forAuthorization: true });
      if (errors.length) return showErrors(errors);
      const card_no = jubileeCardNo();
      await ensurePatient();
      await ensureSubscription();
      setStatus("Authorizing with Jubilee...", 75);
      const data = await authorizeJubileePatient({
        company: form.company,
        card_no,
        insurance_subscription: form.subscription.name,
      });
      form.verification.authorization_number = data.authorization_number;
      // Marks the number as returned, so a change of payment, card or subscription drops it.
      form.authorization = {};
      if (!String(data.status || "").includes("OK")) {
        showErrorReply({ title: data.status, message: data.description });
      }
    });

  const appointmentPayload = () => ({
    company: form.company,
    practitioner: form.practitioner,
    appointment_date: form.appointment_date,
    appointment_time: form.appointment_time,
    appointment_type: form.appointment_type,
    patient: form.patient,
    payment_mode: isInsurance.value ? "Insurance" : "Cash",
    insurance_subscription: isInsurance.value ? form.subscription?.name : "",
    referral_no: isInsurance.value ? form.verification.referral_no : "",
    remarks: isInsurance.value ? form.verification.remarks : "",
    authorization_number: isInsurance.value
      ? form.verification.authorization_number
      : "",
    ...(form.authorization || {}),
  });

  const book = () =>
    run("Creating Appointment", async () => {
      const errors = validationErrors({ forAuthorization: false });
      if (errors.length) return showErrors(errors);
      // The server refuses an existing patient's booking itself; a new patient must not be created first.
      if (!isInsurance.value && form.patientMode === "new")
        await validateNewPatientCashBooking({
          practitioner: form.practitioner,
          appointment_type: form.appointment_type,
          company: form.company,
        });
      await ensurePatient();
      await ensureSubscription();
      setStatus("Creating the appointment...", 75);
      return await createAppointment(appointmentPayload());
    });

  const validationErrors = ({ forAuthorization }) => {
    const errors = [];
    if (!form.practitioner) errors.push("Practitioner is required");
    if (!form.appointment_date) errors.push("Date is required");
    if (!form.appointment_time) errors.push("Time is required");
    if (!form.appointment_type) errors.push("Visit type is required");
    if (form.patientMode === "new") {
      for (const [field, label] of [
        ["first_name", "First name"],
        ["last_name", "Last name"],
        ["sex", "Gender"],
        ["dob", "Date of birth"],
        ["mobile", "Mobile"],
        ["demography", "Area"],
        ["common_occupation", "Occupation"],
        ["ethnicity", "Ethnicity"],
        ["how_did_you_hear_about_us", "How did you hear about us"],
      ]) {
        if (!String(form.newPatient[field] || "").trim())
          errors.push(`${label} is required`);
      }
    } else if (!form.patient) {
      errors.push("Patient is required");
    }
    if (isNhif.value && !form.card_type) errors.push("Card type is required");
    if (isInsurance.value) errors.push(...subscriptionErrors());
    if (isNhif.value) errors.push(...nhifVerificationErrors(forAuthorization));
    return errors;
  };

  const nhifVerificationErrors = (forAuthorization) => {
    const { referral_no, remarks, method } = form.verification;
    const errors = [];
    if (form.visitType.requires_referral_no && !referral_no)
      errors.push("Referral no is required for this visit type");
    if (form.visitType.requires_remarks && !remarks)
      errors.push("Remarks are required for this visit type");
    else if (forAuthorization && method === "NONE" && !remarks)
      errors.push(
        "Remarks are required when the patient is not verified by biometrics"
      );
    return errors;
  };

  const subscriptionErrors = () => {
    if (form.subscriptionMode === "existing") {
      return form.subscription ? [] : ["Insurance subscription is required"];
    }
    const errors = [];
    if (!form.newSubscription.insurance_company)
      errors.push("Insurance company is required");
    if (!form.newSubscription.healthcare_insurance_coverage_plan) {
      errors.push("Coverage plan is required");
    }
    if (!form.newSubscription.coverage_plan_card_number)
      errors.push("Card no is required");
    return errors;
  };

  const showErrors = (errors) => {
    showError(
      errors.length === 1
        ? errors[0]
        : `Please fill in all required fields:\n\n${errors
            .map((e) => `• ${e}`)
            .join("\n")}`,
      { timeout: 10000 }
    );
  };

  return {
    form,
    settings,
    busy,
    status,
    isInsurance,
    isNhif,
    canCheckCard,
    creates,
    canAuthorize,
    canAuthorizeJubilee,
    canSubmit,
    loadSettings,
    setPayment,
    selectPatient,
    selectSubscription,
    applySubscription,
    checkCard,
    authorizeNhif,
    authorizeJubilee,
    book,
  };
}
