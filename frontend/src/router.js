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
    path: "/setup/coverages",
    name: "Coverages",
    component: () => import("@/pages/SetupRecords.vue"),
    props: { screen: "coverages" },
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
