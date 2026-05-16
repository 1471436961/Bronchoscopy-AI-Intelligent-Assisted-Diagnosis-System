<template>
  <div>
    <div class="page-title"><h1>系统设置</h1></div>
    <el-tabs v-model="active">
      <el-tab-pane label="用户管理" name="users">
        <section class="panel">
          <div class="toolbar">
            <el-input v-model="userForm.username" placeholder="用户名" style="width: 180px" />
            <el-input v-model="userForm.password" placeholder="密码" type="password" style="width: 180px" />
            <el-select v-model="userForm.role" style="width: 140px">
              <el-option label="医生" value="doctor" />
              <el-option label="主任" value="director" />
              <el-option label="管理员" value="admin" />
            </el-select>
            <el-button type="primary" @click="createUser">新增</el-button>
          </div>
          <el-table :data="users" stripe>
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="role" label="角色" />
            <el-table-column prop="created_at" label="创建时间" />
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane label="模型管理" name="models">
        <section class="panel">
          <el-table :data="versions" stripe>
            <el-table-column prop="version" label="版本" />
            <el-table-column prop="file_path" label="模型文件" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? "激活" : "备用" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button link type="primary" :disabled="row.is_active" @click="rollback(row)">回滚</el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane label="视频流配置" name="streams">
        <section class="panel">
          <div class="toolbar">
            <el-input v-model="streamForm.name" placeholder="名称" style="width: 160px" />
            <el-input v-model="streamForm.url" placeholder="URL" style="width: 320px" />
            <el-input-number v-model="streamForm.fps" :min="1" :max="60" />
            <el-input v-model="streamForm.resolution" placeholder="分辨率" style="width: 120px" />
            <el-button type="primary" @click="createStream">新增</el-button>
          </div>
          <el-table :data="streams" stripe>
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="url" label="URL" />
            <el-table-column prop="fps" label="帧率" width="100" />
            <el-table-column prop="resolution" label="分辨率" width="120" />
          </el-table>
        </section>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, reactive, ref } from "vue";
import { api } from "../api/client";

const active = ref("users");
const users = ref([]);
const versions = ref([]);
const streams = ref([]);
const userForm = reactive({ username: "", password: "", role: "doctor" });
const streamForm = reactive({ name: "", url: "", fps: 25, resolution: "1280x720" });

onMounted(loadAll);

async function loadAll() {
  await Promise.all([loadUsers(), loadVersions(), loadStreams()]);
}

async function loadUsers() {
  const { data } = await api.get("/settings/users");
  users.value = data.items;
}

async function loadVersions() {
  const { data } = await api.get("/model/versions");
  versions.value = data.items;
}

async function loadStreams() {
  const { data } = await api.get("/settings/streams");
  streams.value = data.items;
}

async function createUser() {
  await api.post("/settings/users", userForm);
  Object.assign(userForm, { username: "", password: "", role: "doctor" });
  ElMessage.success("用户已创建");
  loadUsers();
}

async function rollback(row) {
  await ElMessageBox.confirm(`确认回滚到 ${row.version}？`, "模型回滚", { type: "warning" });
  await api.post("/model/rollback", { version_id: row.id });
  ElMessage.success("模型版本已切换");
  loadVersions();
}

async function createStream() {
  await api.post("/settings/streams", streamForm);
  Object.assign(streamForm, { name: "", url: "", fps: 25, resolution: "1280x720" });
  ElMessage.success("视频流配置已创建");
  loadStreams();
}
</script>
