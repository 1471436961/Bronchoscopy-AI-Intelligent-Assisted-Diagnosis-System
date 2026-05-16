
# Bronchoscopy-AI 智能辅助诊断系统 —— 开发实施规范

## 项目名称：Bronchoscopy-AI 智能辅助诊断系统
## 模型来源：MIT 论文 *“EfficientViT: Multi-Scale Linear Attention for High-Resolution Dense Prediction”*

---

## 1. 系统目标与架构总览

### 1.1 核心任务
- 基于已有的 EfficientViT 多任务模型，开发 Web 端实时支气管镜 AI 辅助分析系统。
- 三大 AI 功能：31 部位识别、病灶分割、6 类异常分类，结果实时叠加于视频流。
- 支持检查控制（开始/暂停/恢复/停止）、报告生成（含电子签名）、患者管理。
- 系统完全在内网离线运行，不得依赖互联网。

### 1.2 技术栈与架构约束

| 层 | 组件 | 要求 |
|----|------|------|
| 前端 | Vue 3 + Element Plus + socket.io-client | WebSocket 订阅帧结果，Canvas 叠加渲染 |
| 后端 API | Flask + Gunicorn | RESTful，JWT 鉴权 |
| WebSocket | Flask-SocketIO | 推送帧级结果事件 `frame_result` |
| 推理服务 | 独立微服务，PyTorch + EfficientViT | 通过 gRPC 与 Flask API 通信 |
| 数据库 | PostgreSQL | 存储患者、会话、报告等 |
| 缓存 | Redis | WebSocket 频道管理、会话状态 |
| 对象存储 | MinIO | 保存截图、报告 PDF |
| 部署 | Docker + Nginx | 纯内网离线部署 |

**架构图**（部署视角）：
```
浏览器 → Nginx → Flask API + Flask-SocketIO
                    ↑ gRPC ↓
              推理微服务 (GPU)
                 ↓
          PostgreSQL + Redis + MinIO
```

---

## 2. AI 模型规格

### 2.1 模型信息
- **架构**：EfficientViT（Multi-Scale Linear Attention），共享骨干网络，三个独立输出头。
- **输入**：RGB 图像 `[3, 512, 512]`，归一化 `mean=[0.485,0.456,0.406]`, `std=[0.229,0.224,0.225]`。
- **输出头1（部位）**：31 维 logits → softmax → 概率向量。
- **输出头2（分割）**：`[1,512,512]` logits → sigmoid → 阈值0.5 → 二值掩码。
- **输出头3（异常）**：6 维 logits → softmax → 概率向量。
- **推荐变体**：efficientvit_b1（8.5M 参数，推理约 25ms）。

### 2.2 31 个部位识别标签（顺序固定）

| ID | 名称 | 说明 |
|----|------|------|
| 0 | 声门 | 检查起点 |
| 1 | 气管 | 颈部中央气道 |
| 2 | 隆突 | 气管分叉处 |
| 3 | 右主支气管 | |
| 4 | 右肺上叶 | |
| 5 | 右肺中间段 | |
| 6 | 右肺中叶 | |
| 7 | 右肺下叶 | |
| 8 | 右肺上叶·尖段 | |
| 9 | 右肺上叶·后段 | |
| 10 | 右肺上叶·前段 | |
| 11 | 右肺中叶·外侧段 | |
| 12 | 右肺中叶·内侧段 | |
| 13 | 右肺下叶·背段 | |
| 14 | 右肺下叶·内基底段 | |
| 15 | 右肺下叶·前基底段 | |
| 16 | 右肺下叶·外基底段 | |
| 17 | 右肺下叶·后基底段 | |
| 18 | 左主支气管 | |
| 19 | 左肺上叶 | |
| 20 | 左肺下叶 | |
| 21 | 左肺上叶·固有支 | |
| 22 | 左肺上叶·舌段 | |
| 23 | 左肺上叶·固有支·尖后段 | |
| 24 | 左肺上叶·固有支·前段 | |
| 25 | 左肺上叶·舌段·上舌段 | |
| 26 | 左肺上叶·舌段·下舌段 | |
| 27 | 左肺下叶·背段 | |
| 28 | 左肺下叶·前基底段 | |
| 29 | 左肺下叶·外基底段 | |
| 30 | 左肺下叶·后基底段 | |

### 2.3 6 类异常标签

| ID | 类别 | 颜色 | 含义 |
|----|------|------|------|
| 0 | 病变 | 红色 | 肿瘤、息肉等 |
| 1 | 出血 | 深红 | 出血点、血斑 |
| 2 | 黏液 | 黄色 | 黏液积聚 |
| 3 | 模糊 | 橙色 | 失焦、镜头污染 |
| 4 | 正常 | 绿色 | 未见明显异常 |
| 5 | 体外 | 灰色 | 镜头无效画面 |

---

## 3. 推理微服务接口规范（gRPC）

推理服务独立部署，由 Flask API 通过 gRPC 调用。请实现以下 proto 接口：

### 3.1 请求与响应结构
```protobuf
service InferenceEngine {
    rpc AnalyzeFrame (FrameRequest) returns (FrameResponse);
}

message FrameRequest {
    bytes image_jpeg = 1;      // 原始视频帧，JPEG 编码
    string session_id = 2;
    int64 timestamp_ms = 3;    // 视频时间戳
}

message FrameResponse {
    Location location = 1;
    Segmentation segmentation = 2;
    Abnormality abnormality = 3;
    float processing_ms = 4;
}

message Location {
    int32 id = 1;              // 0-30
    string name = 2;
    float confidence = 3;
    bool is_uncertain = 4;     // confidence < 0.6
}

message Segmentation {
    bytes mask_png = 1;        // 512x512 二值掩码 PNG 编码
    bool has_lesion = 2;       // 掩码中存在连通域
}

message Abnormality {
    int32 type_id = 1;         // 0-5
    string type = 2;
    float confidence = 3;
    bool is_uncertain = 4;
    bool is_outside = 5;       // type_id == 5
}
```

### 3.2 处理流程
1. 接收 JPEG → 解码至 `[H,W,3] numpy` → 缩放 512x512 → 归一化 → `tensor[1,3,512,512]`。
2. 模型前向传播。
3. 后处理：
   - 部位：`softmax` → `argmax` → 映射名称；若最大概率 < 0.6，标记 `is_uncertain=true`。
   - 分割：`sigmoid` → `> 0.5` → 二值掩码 → `findContours` 判断 `has_lesion`；PNG 编码。
   - 异常：`softmax` → `argmax`；`type_id=5` 时 `is_outside=true`；若最大概率 < 0.6，`is_uncertain=true`。
4. 返回 `FrameResponse`。

### 3.3 性能与优化
- 使用 `torch.compile` 或 TensorRT 加速。
- 默认 FP16 推理。
- 服务启动时加载模型并进行 GPU 预热（随机输入推理几次）。

---

## 4. 后端 API 接口实现要求

### 4.1 RESTful 端点清单

| 方法 | 路径 | 功能 | 关键实现点 |
|------|------|------|------------|
| POST | /api/auth/login | 登录 | 返回 JWT token，有效期 24h |
| POST | /api/auth/logout | 登出 | 黑名单 token（Redis） |
| GET | /api/patients | 患者列表 | 分页、模糊搜索 |
| POST | /api/patients | 新增患者 | AES-256 加密姓名、身份证号 |
| PUT | /api/patients/{id} | 修改患者 | |
| POST | /api/session/start | 开始会话 | 创建 session，关联 patient_id，通知推理服务准备 |
| POST | /api/session/pause | 暂停 | 更新 session 状态，前端停止推流 |
| POST | /api/session/resume | 恢复 | 更新状态，前端恢复推流 |
| POST | /api/session/stop | 结束 | 汇总帧级结果，生成摘要 |
| GET | /api/session/{id} | 会话详情 | 返回摘要+帧列表（分页） |
| POST | /api/report/generate | 生成报告 | 接收诊断结论文本和签名图片，调用 PDF 引擎 |
| GET | /api/report/{id} | 获取报告 | 返回 PDF 文件流 |
| GET | /api/model/versions | 模型版本 | 列表，标记当前激活 |
| POST | /api/model/rollback | 回滚模型 | 切换版本，重启推理微服务 |

### 4.2 WebSocket 实现（Flask-SocketIO）
- 命名空间：`/ws/analysis/<session_id>`
- 前端可发送 `{type:"pause"/"resume"}` 控制。
- 后端每收到推理结果后 emit `frame_result` 事件，负载格式：
```json
{
  "timestamp": 1620,
  "location": {
    "name": "右肺上叶",
    "confidence": 0.942,
    "is_uncertain": false
  },
  "abnormality": {
    "type": "病变",
    "type_id": 0,
    "confidence": 0.913,
    "is_uncertain": false,
    "is_outside": false
  },
  "segmentation": {
    "has_lesion": true,
    "mask_png": "base64..."
  },
  "delay_ms": 35
}
```

### 4.3 会话状态机
```
[START] -> running -> (pause) -> paused -> (resume) -> running -> (stop) -> stopped
```
禁止从 paused/stopped 直接回到 start，前端按钮状态需据此切换。

### 4.4 报告 PDF 生成
- 模板数据源：会话摘要 + 医生提交的诊断结论（文本）+ 签名图片（PNG/JPEG，前端采集）。
- 引擎：WeasyPrint 或 ReportLab，生成固定布局的 PDF。
- 文件命名：`报告_{病历号}_{日期}.pdf`。
- 保存到 MinIO，数据库记录路径。

---

## 5. 前端实现规范

### 5.1 核心页面与路由
- `/login` 登录
- `/live` 实时分析（主页面）
- `/patients` 患者管理
- `/history` 历史会话
- `/reports` 报告管理
- `/settings` 系统设置

### 5.2 实时分析页面功能要点
- **视频源选择**：支持直接传入 RTSP/MJPEG URL、USB 摄像头、或上传本地视频模拟。
- **视频播放**：使用 `jsmpeg` 或原生 `video` 标签播放。
- **Canvas 叠加层**：
  - 双层结构：底层放视频，上层放 Canvas（等大覆盖）。
  - 收到 `frame_result` 后，在 Canvas 上绘制：
    - 部位名称（带白底黑字标签，位于左上）。
    - 异常类型彩色标签条（位于部位下方）。
    - 置信度进度条（可选，位于右侧）。
    - 若 `has_lesion == true`，解码 mask PNG，缩放匹配视频尺寸，使用 `globalCompositeOperation = 'source-atop'` 或 `'multiply'` 绘制红色半透明区域。
    - 若 `is_outside == true`，在画面中央绘制大号灰色文字“镜头在体外，请调整位置”。
- **控制按钮栏**：开始、暂停、恢复、停止、截图、生成报告。
  - 未选择患者时“开始”禁用。
  - 只有在 running 状态时可暂停，paused 时可恢复，非 stopped 时可停止。
- **侧边栏**：实时显示当前部位、异常、置信度；小统计卡片（总帧数、异常帧数、病灶帧数）。

### 5.3 报告编辑器
- 从 `session_summary` 展示 AI 分析结果（部位分布、异常统计、关键帧截图）。
- 提供文本框让医生输入诊断结论（必填）。
- 调用签名板组件（`vue-signature-pad`）或上传 CA 签名图片。
- 提交 `/api/report/generate`，成功后提示下载。

### 5.4 患者管理
- 列表支持分页、按姓名或病历号搜索。
- 新增/编辑表单，身份证号为选填，提交时前端不应展示明文（后端加密存储）。

### 5.5 系统设置
- **用户管理**：管理员可 CRUD 用户，分配角色（医生/主任/管理员）。
- **模型管理**：查看版本列表，激活版本高亮，一键回滚（需确认，调用 API 后重启推理服务）。
- **视频流配置**：预定义几个流配置（URL、帧率、分辨率），实时分析页可下拉选择。

---

## 6. 数据库表结构（参考）

请按以下结构建表，注意加密字段标注。

| 表 | 关键列 | 说明 |
|----|--------|------|
| users | id, username, password_hash, role, created_at | 角色: doctor/director/admin |
| patients | id, name_encrypted, medical_no, gender, age, id_number_encrypted, created_at | 加密字段使用 AES-256 |
| analysis_sessions | id, patient_id, doctor_id, status, start_time, end_time | status 枚举 running/paused/stopped |
| frame_results | id, session_id, frame_index, timestamp, location_id, location_name, location_conf, abnormality_id, abnormality_name, abnormality_conf, has_lesion, is_outside | 可按需采样存储(如每5帧存一次) |
| session_summary | session_id, most_frequent_location, abnormalities_json, lesion_frames_count, total_frames, duration | 在 session.stop 时生成 |
| reports | id, session_id, doctor_conclusion, signature_image_path, pdf_path, created_at | |
| model_versions | id, version, file_path, config_path, is_active, created_at | 同一时间只有一个 active |

---

## 7. 开发实现注意事项

1. **离线运行**：所有第三方库打包至 Docker 镜像，不拉取 CDN；前端静态文件全部本地托管。
2. **加密要求**：AES-256 密钥通过环境变量 `ENCRYPTION_KEY` 注入，不得硬编码。
3. **错误处理**：推理服务宕机时，Flask API 应返回 503，前端显示“AI 服务暂不可用”并自动重试。
4. **帧丢弃策略**：若 WebSocket 推送延迟太大，可在前端丢帧（例如每2帧处理1帧），但需保持视频平滑。
5. **掩码映射**：模型输出 512x512 掩码，需根据视频实际显示尺寸计算偏移和缩放，保证叠加位置准确。
6. **安全审计**：记录所有关键操作（登录、开始/停止会话、修改报告）的日志，包含用户ID和时间戳，但不得记录患者明文信息。
7. **模型版本切换**：回滚操作需先确认推理服务可热重载，或自动重启容器。 API 侧需等待服务就绪后再接受新会话。


---

## 8. 附录：模型文件与配置示例

### 配置文件 `efficientvit_config.yaml`
```yaml
model:
  name: EfficientViT-MultiTask
  variant: efficientvit_b1
  input_size: [512, 512]
  num_location_classes: 31
  num_abnormality_classes: 6

backbone:
  type: EfficientViT
  multi_scale: true
  attention_type: multi_scale_linear

heads:
  location: { type: classification, output_dim: 31 }
  segmentation: { type: multi_scale_segmentation, output_dim: 1 }
  abnormality: { type: classification, output_dim: 6 }

preprocessing:
  mean: [0.485, 0.456, 0.406]
  std: [0.229, 0.224, 0.225]

optimization:
  precision: fp16
  batch_size: 1
  use_compile: true
```

### 模型文件要求
- 提供 `efficientvit_multitask.pth`，包含完整的三个任务头权重。
- 可选提供 ONNX 或 TensorRT 引擎文件，加快部署。
