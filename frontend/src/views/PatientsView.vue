<template>
  <div>
    <div class="page-title">
      <h1>患者管理</h1>
      <el-button type="primary" @click="openCreate"><Plus :size="16" />新增患者</el-button>
    </div>
    <section class="panel">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="姓名或病历号" clearable style="width: 260px" @keyup.enter="load" />
        <el-button @click="load"><Search :size="16" />搜索</el-button>
      </div>
      <el-table :data="patients" stripe>
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="medical_no" label="病历号" />
        <el-table-column prop="gender" label="性别" width="100" />
        <el-table-column prop="age" label="年龄" width="100" />
        <el-table-column prop="id_number_masked" label="身份证号" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination layout="prev, pager, next, total" :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="load" />
    </section>

    <el-dialog v-model="dialogOpen" :title="editingId ? '编辑患者' : '新增患者'" width="520px">
      <el-form :model="form" label-position="top">
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="病历号"><el-input v-model="form.medical_no" /></el-form-item>
        <el-form-item label="性别">
          <el-select v-model="form.gender" style="width: 100%">
            <el-option label="男" value="男" />
            <el-option label="女" value="女" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="年龄"><el-input-number v-model="form.age" :min="0" :max="130" /></el-form-item>
        <el-form-item label="身份证号"><el-input v-model="form.id_number" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { Plus, Search } from "lucide-vue-next";
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../api/client";

const patients = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 10;
const keyword = ref("");
const dialogOpen = ref(false);
const editingId = ref("");
const form = reactive({ name: "", medical_no: "", gender: "男", age: 50, id_number: "" });

onMounted(load);

async function load() {
  const { data } = await api.get("/patients", { params: { page: page.value, page_size: pageSize, q: keyword.value } });
  patients.value = data.items;
  total.value = data.total;
}

function openCreate() {
  editingId.value = "";
  Object.assign(form, { name: "", medical_no: "", gender: "男", age: 50, id_number: "" });
  dialogOpen.value = true;
}

function openEdit(row) {
  editingId.value = row.id;
  Object.assign(form, { ...row, id_number: "" });
  dialogOpen.value = true;
}

async function save() {
  if (editingId.value) await api.put(`/patients/${editingId.value}`, form);
  else await api.post("/patients", form);
  ElMessage.success("已保存");
  dialogOpen.value = false;
  load();
}
</script>
