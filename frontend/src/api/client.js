import axios from "axios";
import { ElMessage } from "element-plus";
import { useAuthStore } from "../stores/auth";

export const api = axios.create({
  baseURL: "/api",
  timeout: 10000
});

api.interceptors.request.use((config) => {
  const auth = useAuthStore();
  if (auth.token) config.headers.Authorization = `Bearer ${auth.token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    if (status === 503) ElMessage.error("AI 服务暂不可用，系统将自动重试");
    if (status === 401) useAuthStore().clear();
    return Promise.reject(error);
  }
);
