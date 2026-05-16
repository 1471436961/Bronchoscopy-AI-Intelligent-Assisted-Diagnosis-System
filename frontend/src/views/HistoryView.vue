<template>
  <div>
    <div class="page-title"><h1>历史会话</h1></div>
    <section class="panel">
      <el-table :data="sessions" stripe @row-click="openDetail">
        <el-table-column prop="id" label="会话编号" min-width="280" />
        <el-table-column prop="patient_id" label="患者ID" width="110" />
        <el-table-column prop="doctor_id" label="医生ID" width="110" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="start_time" label="开始时间" />
      </el-table>
      <el-pagination layout="prev, pager, next, total" :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="load" />
    </section>

    <el-drawer v-model="drawerOpen" title="会话详情" size="520px">
      <el-descriptions v-if="detail.summary" :column="1" border>
        <el-descriptions-item label="主要部位">{{ detail.summary.most_frequent_location }}</el-descriptions-item>
        <el-descriptions-item label="总帧数">{{ detail.summary.total_frames }}</el-descriptions-item>
        <el-descriptions-item label="病灶帧">{{ detail.summary.lesion_frames_count }}</el-descriptions-item>
        <el-descriptions-item label="持续时间">{{ detail.summary.duration }} 秒</el-descriptions-item>
      </el-descriptions>
      <el-table :data="detail.frames || []" style="margin-top: 14px">
        <el-table-column prop="frame_index" label="帧" width="80" />
        <el-table-column prop="location.name" label="部位" />
        <el-table-column prop="abnormality.type" label="异常" />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { api } from "../api/client";

const sessions = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 10;
const drawerOpen = ref(false);
const detail = reactive({ summary: null, frames: [] });

onMounted(load);

async function load() {
  const { data } = await api.get("/session", { params: { page: page.value, page_size: pageSize } });
  sessions.value = data.items;
  total.value = data.total;
}

async function openDetail(row) {
  const { data } = await api.get(`/session/${row.id}`);
  detail.summary = data.summary;
  detail.frames = data.frames;
  drawerOpen.value = true;
}
</script>
