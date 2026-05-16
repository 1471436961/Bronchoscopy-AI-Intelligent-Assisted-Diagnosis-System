<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="brand large">
        <div class="brand-mark">BA</div>
        <div>
          <strong>Bronchoscopy-AI</strong>
          <span>智能辅助诊断系统</span>
        </div>
      </div>
      <el-form :model="form" label-position="top" @submit.prevent="login">
        <el-form-item label="用户名">
          <el-input v-model="form.username" autofocus />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-button type="primary" class="full" :loading="loading" @click="login">
          <LogIn :size="16" />登录
        </el-button>
      </el-form>
    </section>
  </main>
</template>

<script setup>
import { LogIn } from "lucide-vue-next";
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();
const loading = ref(false);
const form = reactive({ username: "admin", password: "Admin@123456" });

async function login() {
  loading.value = true;
  try {
    const { data } = await api.post("/auth/login", form);
    auth.setSession(data.token, data.user);
    router.push("/live");
  } catch {
    ElMessage.error("用户名或密码错误");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  align-items: center;
  background: linear-gradient(135deg, #dcebf4, #f8fafc 54%, #eaf5ef);
  display: flex;
  min-height: 100vh;
  justify-content: center;
  padding: 20px;
}

.login-panel {
  background: #fff;
  border: 1px solid #d8e2ee;
  border-radius: 8px;
  box-shadow: 0 18px 60px rgba(23, 32, 51, 0.12);
  max-width: 400px;
  padding: 28px;
  width: 100%;
}

.large {
  color: #172033;
  padding: 0 0 24px;
}

.full {
  width: 100%;
}
</style>
