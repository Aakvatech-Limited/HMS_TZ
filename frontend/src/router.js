import { userResource } from "@/data/user";
import { createRouter, createWebHistory } from "vue-router";
import { session } from "./data/session";

const routes = [
  {
    path: "/",
    name: "Home",
    component: () => import("@/pages/Home.vue"),
  },
  {
    path: "/appointments",
    name: "Appointments",
    component: () => import("@/pages/Appointments.vue"),
  },
  {
    path: "/nurse-roster",
    name: "NurseRoster",
    component: () => import("@/pages/NurseRoster.vue"),
  },
  {
    path: "/ot-roster",
    name: "OTRoster",
    component: () => import("@/pages/OTRoster.vue"),
  },
  {
    path: "/setup",
    name: "Setup",
    component: () => import("@/pages/Setup.vue"),
  },
  {
    path: "/setup/rooms",
    name: "Rooms",
    component: () => import("@/pages/Rooms.vue"),
  },
  {
    path: "/setup/doctors",
    name: "Doctors",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "doctors" },
  },
  {
    path: "/setup/insurance-companies",
    name: "InsuranceCompanies",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "insurance_companies" },
  },
  {
    path: "/setup/coverage-plans",
    name: "CoveragePlans",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "coverage_plans" },
  },
  {
    path: "/setup/visit-types",
    name: "VisitTypes",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "visit_types" },
  },
  {
    path: "/setup/coverages",
    name: "Coverages",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "coverages" },
  },
  {
    path: "/setup/nhif-schemes",
    name: "NHIFSchemes",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "nhif_schemes" },
  },
  {
    path: "/setup/nhif-updates",
    name: "NHIFUpdates",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "nhif_updates" },
  },
  {
    path: "/setup/jubilee-updates",
    name: "JubileeUpdates",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "jubilee_updates" },
  },
  {
    path: "/setup/nhif-items",
    name: "NHIFItems",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "nhif_items" },
  },
  {
    path: "/setup/lab-templates",
    name: "LabTemplates",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "lab_templates" },
  },
  {
    path: "/setup/radiology-templates",
    name: "RadiologyTemplates",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "radiology_templates" },
  },
  {
    path: "/setup/procedure-templates",
    name: "ProcedureTemplates",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "procedure_templates" },
  },
  {
    path: "/setup/therapy-types",
    name: "TherapyTypes",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "therapy_types" },
  },
  {
    path: "/setup/medications",
    name: "Medications",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "medications" },
  },
  {
    path: "/setup/nhif-templates",
    name: "NHIFTemplates",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "nhif_templates" },
  },
  {
    path: "/setup/run",
    name: "SetupRun",
    component: () => import("@/pages/SetupRun.vue"),
  },
  {
    name: "Login",
    path: "/account/login",
    component: () => import("@/pages/Login.vue"),
  },
];

const router = createRouter({
  history: createWebHistory("/frontend"),
  routes,
});

router.beforeEach(async (to, from, next) => {
  let isLoggedIn = session.isLoggedIn;
  try {
    await userResource.promise;
  } catch (error) {
    isLoggedIn = false;
  }

  if (to.name === "Login" && isLoggedIn) {
    next({ name: "Home" });
  } else if (to.name !== "Login" && !isLoggedIn) {
    next({ name: "Login" });
  } else {
    next();
  }
});

export default router;
