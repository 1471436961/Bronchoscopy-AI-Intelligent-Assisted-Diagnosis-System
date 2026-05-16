<template>
  <router-view v-if="route.path === '/login'" />
  <el-container v-else class="app-shell">
    <el-aside width="232px" class="side-nav">
      <div class="brand">
        <div class="brand-mark">BA</div>
        <div>
          <strong>Bronchoscopy-AI</strong>
          <span>智能辅助诊断</span>
        </div>
      </div>
      <el-menu router :default-active="route.path" class="menu">
        <el-menu-item index="/live"><MonitorPlay class="menu-icon" />实时分析</el-menu-item>
        <el-menu-item index="/patients"><Users class="menu-icon" />患者管理</el-menu-item>
        <el-menu-item index="/history"><History class="menu-icon" />历史会话</el-menu-item>
        <el-menu-item index="/reports"><FileText class="menu-icon" />报告管理</el-menu-item>
        <el-menu-item index="/settings"><Settings class="menu-icon" />系统设置</el-menu-item>
      </el-menu>
      <el-button class="logout" plain @click="logout"><LogOut :size="16" />退出</el-button>
    </el-aside>
    <el-main class="main-area">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { FileText, History, LogOut, MonitorPlay, Settings, Users } from "lucide-vue-next";
import { useRoute, useRouter } from "vue-router";
import { api } from "./api/client";
import { useAuthStore } from "./stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

async function logout() {
  try {
    await api.post("/auth/logout");
  } finally {
    auth.clear();
    router.push("/login");
  }
}
</script>
