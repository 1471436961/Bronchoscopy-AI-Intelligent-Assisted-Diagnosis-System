<template>
  <div>
    <div class="page-title"><h1>报告管理</h1></div>
    <section class="panel">
      <el-table :data="reports" stripe>
        <el-table-column prop="id" label="报告ID" width="100" />
        <el-table-column prop="session_id" label="会话编号" min-width="280" />
        <el-table-column prop="created_at" label="生成时间" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="open(row)">查看 PDF</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination layout="prev, pager, next, total" :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="load" />
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { api } from "../api/client";

const reports = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 10;

onMounted(load);

async function load() {
  const { data } = await api.get("/report", { params: { page: page.value, page_size: pageSize } });
  reports.value = data.items;
  total.value = data.total;
}

function open(row) {
  window.open(`/api/report/${row.id}`, "_blank");
}
</script>
