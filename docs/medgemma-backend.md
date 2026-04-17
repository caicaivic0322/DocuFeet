# MedGemma 后端部署说明

## 目标

把 `google/medgemma-1.5-4b-it` 作为可选推理后端接入当前 FastAPI 服务，而不是替换掉现有 `Ollama` 主流程。

这样做的原因：

- 你当前产品主流程仍适合走轻量本地模型
- MedGemma 更适合复杂医学图文理解的增强路由
- MedGemma 官方说明不建议把它当作多轮对话模型，因此更适合作为单次分析 worker

## 当前后端切换方式

可通过环境变量切换默认推理后端：

```bash
INFERENCE_BACKEND=ollama
```

或：

```bash
INFERENCE_BACKEND=medgemma
```

也可以在请求 `/api/report/analyze` 时，通过表单字段 `backend=medgemma` 指定本次请求走 MedGemma。

## 模型选择

当前项目默认接入：

```text
google/medgemma-1.5-4b-it
```

原因：

- 4B 体量更适合先做原型
- 支持图文输入，契合“检查单/报告单图片 + 病情文本”的场景

## 前提条件

1. 先在 Hugging Face 页面接受 MedGemma 的使用条款
2. 准备 Hugging Face Access Token
3. 在后端环境安装 MedGemma 依赖

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-medgemma.txt
```

## 环境变量

在 `backend/.env` 中配置：

```bash
INFERENCE_BACKEND=medgemma
MEDGEMMA_MODEL_ID=google/medgemma-1.5-4b-it
MEDGEMMA_HF_TOKEN=你的_hf_token
MEDGEMMA_DEVICE=auto
MEDGEMMA_MAX_NEW_TOKENS=700
```

## 启动

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

## 当前实现说明

- 业务 API 不变，仍然是 `/api/report/analyze`
- 后端根据 `INFERENCE_BACKEND` 或请求参数决定走 `Ollama` 还是 `MedGemma`
- MedGemma 走单次分析 prompt，不做多轮会话状态
- 如果未配置 HF token 或未安装依赖，会返回明确错误，不会把整个后端打挂

## 后续建议

1. 把 MedGemma 下沉成单独 worker 进程，而不是与 API 进程共载
2. 增加 `complex_case=true` 路由策略，只在复杂病例时调用 MedGemma
3. 增加 GPU/内存占用监控与超时保护
4. 为 MedGemma 输出再加一道 JSON 校验与结构修复层
