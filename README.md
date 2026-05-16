# Bronchoscopy-AI 智能辅助诊断系统

这是依据 `Development-and-Implementation-Standards.md` 从零实现的离线内网部署项目，包含 Vue 3 前端、Flask REST API、Flask-SocketIO 实时推送、独立 PyTorch gRPC 推理服务、PostgreSQL、Redis、MinIO、Nginx 与 Docker Compose。

## 功能范围

- 登录/登出，JWT 24 小时有效期，Redis token 黑名单。
- 患者管理，姓名和身份证号使用 AES-256 加密存储。
- 检查会话开始、暂停、恢复、停止，停止时生成帧级摘要。
- 视频帧分析入口 `/api/analysis/frame`，调用 gRPC 推理服务并向前端推送 `frame_result`。
- 推理服务实现规范中的 `InferenceEngine.AnalyzeFrame` proto，包含预处理、softmax/sigmoid 后处理、PNG 掩码编码。
- 实时分析工作台支持本地视频、USB 摄像头和网络流输入，Canvas 叠加部位、异常、置信度和分割掩码。
- PDF 报告生成，包含 AI 摘要、医生结论和签名图片，支持本地存储或 MinIO。
- 管理端包含用户、模型版本、视频流配置。

## 快速启动

```bash
docker compose up --build
```

打开 `http://127.0.0.1:5173`，默认账号：

```text
用户名：admin
密码：Admin@123456
```

## 模型权重

将真实权重放在：

```text
models/efficientvit_multitask.pth
```

如果该文件不存在，推理服务会使用一个轻量 fallback 网络保持接口可用，便于离线联调。上线验收准确率必须替换为真实 EfficientViT 多任务权重。

## 本地开发

后端：

```bash
cd backend
pip install -r requirements.txt
mkdir -p generated
touch generated/__init__.py
python -m grpc_tools.protoc -I../inference/proto --python_out=generated --grpc_python_out=generated ../inference/proto/inference.proto
export PYTHONPATH="$PWD:$PWD/generated"
python wsgi.py
```

推理服务：

```bash
cd inference
pip install -r requirements.txt
mkdir -p generated
touch generated/__init__.py
python -m grpc_tools.protoc -Iproto --python_out=generated --grpc_python_out=generated proto/inference.proto
export PYTHONPATH="$PWD:$PWD/generated"
python -m app.server
```

前端：

```bash
cd frontend
npm install
npm run dev
```

## 生产配置提醒

- 必须替换 `SECRET_KEY`、`JWT_SECRET_KEY`、`ENCRYPTION_KEY`。
- 内网离线环境应预先构建并保存 Docker 镜像，第三方依赖通过私有镜像仓库或离线包缓存安装。
- ReportLab 使用中文 CID 字体生成 PDF；如医院模板有固定版式，可在 `backend/app/pdf.py` 内替换布局。
- 当前 Socket.IO 使用命名空间 `/ws/analysis` 并通过 `session_id` query 加入房间，推送事件名为 `frame_result`。
