<template>
  <div>
    <div class="page-title">
      <h1>实时分析</h1>
      <el-tag :type="statusTag">{{ statusText }}</el-tag>
    </div>

    <div class="work-grid">
      <section class="panel">
        <div class="toolbar">
          <el-select v-model="selectedPatient" filterable placeholder="选择患者" style="width: 220px">
            <el-option v-for="patient in patients" :key="patient.id" :label="`${patient.name} · ${patient.medical_no}`" :value="patient.id" />
          </el-select>
          <el-segmented v-model="sourceType" :options="sourceOptions" />
          <el-input v-if="sourceType === 'url'" v-model="streamUrl" placeholder="MJPEG/RTSP 地址" style="width: 260px" />
          <el-upload v-if="sourceType === 'file'" :auto-upload="false" :show-file-list="false" accept="video/*" :on-change="selectVideoFile">
            <el-button><Upload :size="16" />选择视频</el-button>
          </el-upload>
        </div>

        <div class="toolbar">
          <el-button type="primary" :disabled="!selectedPatient || !hasVideo || status === 'running'" @click="start">
            <Play :size="16" />开始
          </el-button>
          <el-button :disabled="status !== 'running'" @click="pause"><Pause :size="16" />暂停</el-button>
          <el-button :disabled="status !== 'paused'" @click="resume"><RotateCcw :size="16" />恢复</el-button>
          <el-button type="danger" plain :disabled="status === 'stopped'" @click="stop"><Square :size="16" />停止</el-button>
          <el-button :disabled="!hasVideo" @click="captureStill"><Camera :size="16" />截图</el-button>
          <el-button type="success" :disabled="!sessionId || status !== 'stopped'" @click="reportOpen = true"><FileText :size="16" />生成报告</el-button>
        </div>

        <div class="video-stage">
          <video ref="video" muted playsinline controls @play="scheduleFrames" />
          <canvas ref="overlay" />
        </div>
      </section>

      <aside class="panel">
        <h2>当前帧结果</h2>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="部位">{{ latest.location?.name || "-" }}</el-descriptions-item>
          <el-descriptions-item label="部位置信度">{{ percent(latest.location?.confidence) }}</el-descriptions-item>
          <el-descriptions-item label="异常">{{ latest.abnormality?.type || "-" }}</el-descriptions-item>
          <el-descriptions-item label="异常置信度">{{ percent(latest.abnormality?.confidence) }}</el-descriptions-item>
          <el-descriptions-item label="延迟">{{ latest.delay_ms ?? "-" }} ms</el-descriptions-item>
        </el-descriptions>
        <div class="stat-grid" style="margin-top: 14px">
          <MetricBlock label="总帧数" :value="stats.total" />
          <MetricBlock label="异常帧" :value="stats.abnormal" />
          <MetricBlock label="病灶帧" :value="stats.lesion" />
        </div>
      </aside>
    </div>

    <el-dialog v-model="reportOpen" title="生成报告" width="720px">
      <el-input v-model="doctorConclusion" type="textarea" :rows="5" placeholder="请输入医生诊断结论" />
      <div class="signature-upload">
        <el-upload :auto-upload="false" :show-file-list="false" accept="image/png,image/jpeg" :on-change="selectSignature">
          <el-button><Upload :size="16" />上传签名图片</el-button>
        </el-upload>
        <img v-if="signatureImage" :src="signatureImage" alt="签名预览" />
      </div>
      <template #footer>
        <el-button @click="reportOpen = false">取消</el-button>
        <el-button type="primary" :loading="reporting" @click="generateReport">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { Camera, FileText, Pause, Play, RotateCcw, Square, Upload } from "lucide-vue-next";
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { io } from "socket.io-client";
import { ElMessage } from "element-plus";
import { api } from "../api/client";
import MetricBlock from "../components/MetricBlock.vue";

const patients = ref([]);
const selectedPatient = ref("");
const sourceType = ref("file");
const sourceOptions = [
  { label: "本地视频", value: "file" },
  { label: "USB 摄像头", value: "usb" },
  { label: "网络流", value: "url" }
];
const streamUrl = ref("");
const status = ref("stopped");
const sessionId = ref("");
const frameIndex = ref(0);
const latest = ref({});
const stats = reactive({ total: 0, abnormal: 0, lesion: 0 });
const video = ref(null);
const overlay = ref(null);
const hasVideo = ref(false);
const socket = ref(null);
const timer = ref(null);
const reportOpen = ref(false);
const reporting = ref(false);
const doctorConclusion = ref("");
const signatureImage = ref("");

const statusText = computed(() => ({ running: "运行中", paused: "已暂停", stopped: "已停止" }[status.value]));
const statusTag = computed(() => ({ running: "success", paused: "warning", stopped: "info" }[status.value]));

onMounted(loadPatients);
onUnmounted(() => {
  clearInterval(timer.value);
  socket.value?.disconnect();
});

async function loadPatients() {
  const { data } = await api.get("/patients", { params: { page_size: 100 } });
  patients.value = data.items;
  if (!selectedPatient.value && patients.value.length) selectedPatient.value = patients.value[0].id;
}

async function start() {
  const { data } = await api.post("/session/start", { patient_id: selectedPatient.value });
  sessionId.value = data.id;
  status.value = "running";
  stats.total = 0;
  stats.abnormal = 0;
  stats.lesion = 0;
  connectSocket();
  await openVideoSource();
  scheduleFrames();
}

async function pause() {
  await api.post("/session/pause", { session_id: sessionId.value });
  status.value = "paused";
  socket.value?.emit("control", { session_id: sessionId.value, type: "pause" });
}

async function resume() {
  await api.post("/session/resume", { session_id: sessionId.value });
  status.value = "running";
  socket.value?.emit("control", { session_id: sessionId.value, type: "resume" });
}

async function stop() {
  await api.post("/session/stop", { session_id: sessionId.value });
  status.value = "stopped";
  clearInterval(timer.value);
}

function connectSocket() {
  socket.value?.disconnect();
  socket.value = io("/ws/analysis", { query: { session_id: sessionId.value } });
  socket.value.on("frame_result", (payload) => {
    latest.value = payload;
    drawOverlay(payload);
  });
}

async function openVideoSource() {
  if (sourceType.value === "usb") {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    video.value.srcObject = stream;
    hasVideo.value = true;
  } else if (sourceType.value === "url") {
    video.value.src = streamUrl.value;
    hasVideo.value = Boolean(streamUrl.value);
  }
  await video.value.play().catch(() => {});
}

function selectVideoFile(file) {
  video.value.src = URL.createObjectURL(file.raw);
  hasVideo.value = true;
  video.value.play();
}

function scheduleFrames() {
  clearInterval(timer.value);
  timer.value = setInterval(sendFrame, 500);
}

async function sendFrame() {
  if (status.value !== "running" || !video.value?.videoWidth) return;
  const capture = document.createElement("canvas");
  capture.width = 512;
  capture.height = 512;
  const ctx = capture.getContext("2d");
  ctx.drawImage(video.value, 0, 0, capture.width, capture.height);
  const image = capture.toDataURL("image/jpeg", 0.82);
  try {
    await api.post("/analysis/frame", {
      session_id: sessionId.value,
      timestamp_ms: Math.floor(video.value.currentTime * 1000),
      frame_index: frameIndex.value++,
      image_jpeg: image,
      sample_every: 5
    });
  } catch (error) {
    if (error.response?.status === 503) setTimeout(sendFrame, 1200);
  }
}

function drawOverlay(payload) {
  const canvas = overlay.value;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width;
  canvas.height = rect.height;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  stats.total += 1;
  if (payload.abnormality?.type_id !== 4 && !payload.abnormality?.is_outside) stats.abnormal += 1;
  if (payload.segmentation?.has_lesion) stats.lesion += 1;

  drawLabel(ctx, 16, 16, payload.location?.name || "-", "#fff", "#172033");
  drawLabel(ctx, 16, 56, payload.abnormality?.type || "-", abnormalColor(payload.abnormality?.type_id), "#fff");
  drawConfidence(ctx, canvas.width - 28, 18, payload.location?.confidence || 0, "#27b0a8");
  drawConfidence(ctx, canvas.width - 14, 18, payload.abnormality?.confidence || 0, "#d44b4b");
  if (payload.segmentation?.has_lesion) paintMask(canvas, payload.segmentation.mask_png);
  if (payload.abnormality?.is_outside) {
    ctx.fillStyle = "rgba(40, 48, 60, .76)";
    ctx.fillRect(0, canvas.height / 2 - 38, canvas.width, 76);
    ctx.fillStyle = "#e5e7eb";
    ctx.font = "700 28px Microsoft YaHei";
    ctx.textAlign = "center";
    ctx.fillText("镜头在体外，请调整位置", canvas.width / 2, canvas.height / 2 + 10);
  }
}

function drawLabel(ctx, x, y, text, bg, fg) {
  ctx.font = "600 16px Microsoft YaHei";
  const width = ctx.measureText(text).width + 22;
  ctx.fillStyle = bg;
  ctx.fillRect(x, y, width, 30);
  ctx.fillStyle = fg;
  ctx.fillText(text, x + 11, y + 21);
}

function drawConfidence(ctx, x, y, value, color) {
  ctx.fillStyle = "rgba(255,255,255,.75)";
  ctx.fillRect(x, y, 8, 130);
  ctx.fillStyle = color;
  ctx.fillRect(x, y + 130 * (1 - value), 8, 130 * value);
}

function paintMask(canvas, maskPng) {
  const img = new Image();
  img.onload = () => {
    const temp = document.createElement("canvas");
    temp.width = canvas.width;
    temp.height = canvas.height;
    const tctx = temp.getContext("2d");
    tctx.drawImage(img, 0, 0, temp.width, temp.height);
    const data = tctx.getImageData(0, 0, temp.width, temp.height);
    for (let i = 0; i < data.data.length; i += 4) {
      const active = data.data[i] > 0;
      data.data[i] = 224;
      data.data[i + 1] = 38;
      data.data[i + 2] = 38;
      data.data[i + 3] = active ? 90 : 0;
    }
    tctx.putImageData(data, 0, 0);
    overlay.value.getContext("2d").drawImage(temp, 0, 0);
  };
  img.src = `data:image/png;base64,${maskPng}`;
}

function abnormalColor(typeId) {
  return ["#d44b4b", "#8f1d2c", "#d8a21d", "#e67e22", "#1f9d55", "#667085"][typeId ?? 4];
}

function percent(value) {
  return value == null ? "-" : `${Math.round(value * 100)}%`;
}

function captureStill() {
  const canvas = document.createElement("canvas");
  const rect = overlay.value.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(rect.width));
  canvas.height = Math.max(1, Math.floor(rect.height));
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#0b111b";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (video.value?.videoWidth) ctx.drawImage(video.value, 0, 0, canvas.width, canvas.height);
  ctx.drawImage(overlay.value, 0, 0, canvas.width, canvas.height);
  const link = document.createElement("a");
  link.download = `screenshot_${Date.now()}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
}

function selectSignature(file) {
  const reader = new FileReader();
  reader.onload = () => (signatureImage.value = reader.result);
  reader.readAsDataURL(file.raw);
}

async function generateReport() {
  if (!doctorConclusion.value.trim() || !signatureImage.value) {
    ElMessage.warning("请填写诊断结论并上传签名图片");
    return;
  }
  reporting.value = true;
  try {
    const { data } = await api.post("/report/generate", {
      session_id: sessionId.value,
      doctor_conclusion: doctorConclusion.value,
      signature_image: signatureImage.value
    });
    ElMessage.success("报告已生成");
    window.open(`/api/report/${data.id}`, "_blank");
    reportOpen.value = false;
  } finally {
    reporting.value = false;
  }
}
</script>

<style scoped>
.signature-upload {
  align-items: center;
  display: flex;
  gap: 14px;
  margin-top: 14px;
}

.signature-upload img {
  border: 1px solid #d8e2ee;
  border-radius: 8px;
  max-height: 70px;
  max-width: 220px;
}
</style>
