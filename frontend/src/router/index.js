import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const routes = [
  { path: "/", redirect: "/live" },
  { path: "/login", component: () => import("../views/LoginView.vue") },
  { path: "/live", component: () => import("../views/LiveView.vue"), meta: { auth: true } },
  { path: "/patients", component: () => import("../views/PatientsView.vue"), meta: { auth: true } },
  { path: "/history", component: () => import("../views/HistoryView.vue"), meta: { auth: true } },
  { path: "/reports", component: () => import("../views/ReportsView.vue"), meta: { auth: true } },
  { path: "/settings", component: () => import("../views/SettingsView.vue"), meta: { auth: true } }
];

const router = createRouter({ history: createWebHistory(), routes });

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.auth && !auth.token) return "/login";
  if (to.path === "/login" && auth.token) return "/live";
  return true;
});

export default router;
