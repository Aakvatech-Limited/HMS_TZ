/**
 * Setup screens of the sidebar, grouped by area. A screen with a step is done when that setup step is
 * done; the HMS TZ Setting screen is done when every settings group is complete.
 */
export const SETUP_GROUPS = [
  {
    label: "Settings",
    screens: [
      {
        label: "HMS TZ Setting",
        route: "Setup",
        icon: "settings",
        step: "HMS TZ Setting",
      },
    ],
  },
  {
    label: "Clinic",
    screens: [
      {
        label: "Rooms",
        route: "Rooms",
        icon: "grid",
        step: "Healthcare Service Unit",
      },
      {
        label: "Doctors",
        route: "Doctors",
        icon: "users",
        step: "Healthcare Practitioner",
      },
      {
        label: "Visit types",
        route: "VisitTypes",
        icon: "calendar",
        step: "Appointment Type",
      },
    ],
  },
  {
    label: "Insurance",
    screens: [
      {
        label: "Insurers",
        route: "InsuranceCompanies",
        icon: "shield",
        step: "Healthcare Insurance Company",
      },
      {
        label: "Plans",
        route: "CoveragePlans",
        icon: "file-text",
        step: "Healthcare Insurance Coverage Plan",
      },
      {
        label: "Coverages",
        route: "Coverages",
        icon: "check-square",
        step: "Healthcare Service Insurance Coverage",
      },
    ],
  },
  {
    label: "NHIF",
    screens: [
      { label: "NHIF schemes", route: "NHIFSchemes", icon: "layers" },
      { label: "NHIF items", route: "NHIFItems", icon: "package" },
      {
        label: "NHIF templates",
        route: "NHIFTemplates",
        icon: "git-merge",
        reviewCount: "nhif_templates_to_review",
      },
      { label: "NHIF updates", route: "NHIFUpdates", icon: "refresh-cw" },
    ],
  },
  {
    label: "Jubilee",
    screens: [
      { label: "Jubilee updates", route: "JubileeUpdates", icon: "rotate-cw" },
    ],
  },
  {
    label: "Templates",
    screens: [
      {
        label: "Lab templates",
        route: "LabTemplates",
        icon: "droplet",
        step: "Lab Test Template",
      },
      {
        label: "Radiology templates",
        route: "RadiologyTemplates",
        icon: "aperture",
        step: "Radiology Examination Template",
      },
      {
        label: "Procedure templates",
        route: "ProcedureTemplates",
        icon: "scissors",
        step: "Clinical Procedure Template",
      },
      {
        label: "Therapy types",
        route: "TherapyTypes",
        icon: "heart",
        step: "Therapy Type",
      },
      {
        label: "Medications",
        route: "Medications",
        icon: "thermometer",
        step: "Medication",
      },
    ],
  },
];

const SETTINGS_STEP = "HMS TZ Setting";

/** "done" or "todo" for a screen with a setup step, null for a screen without one. */
export const getScreenStatus = (screen, navigation) => {
  if (!screen.step) return null;
  const isDone =
    screen.step === SETTINGS_STEP
      ? navigation.settings_complete
      : navigation.steps.some(
          (step) => step.document_type === screen.step && step.completed
        );
  return isDone ? "done" : "todo";
};

/** The sidebar groups with each screen's status and the count it waits on for review. */
export const getNavigationGroups = (navigation) =>
  SETUP_GROUPS.map((group) => ({
    ...group,
    screens: group.screens.map((screen) => ({
      ...screen,
      status: navigation ? getScreenStatus(screen, navigation) : null,
      toReview: (navigation && navigation[screen.reviewCount]) || 0,
    })),
  }));

/** Label of the Run setup button, for example "Run setup · 14 of 19 done". */
export const getRunLabel = (navigation) => {
  const steps = navigation?.steps || [];
  if (!steps.length) return "Run setup";
  const done = steps.filter((step) => step.completed).length;
  return `Run setup · ${done} of ${steps.length} done`;
};
