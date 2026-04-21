# 乡镇医疗 AI 助手

面向乡镇医院和县级医院的本地部署诊断助理原型。首版目标不是“AI 医生”，而是帮助基层医生快速完成：

- 检查报告解释
- 风险分级
- 下一步检查/转诊建议
- 用药注意事项提示

当前技术栈：

- 前端：React + Vite
- 后端：FastAPI
- 推理后端：Ollama / MedGemma（可切换）
- 推荐模型：`gemma3:4b`（支持图片输入，适合检查单照片 MVP）
- 医学增强模型：`google/medgemma-1.5-4b-it`

## 产品原则

- 不输出确定诊断
- 每次强制输出风险等级
- 每次强制输出下一步行动
- 结论尽量引用规则或本地知识片段
- 高风险由规则优先覆盖模型

## 本地启动

### 1. 启动 Ollama

先安装并启动 Ollama，然后拉取一个支持图像输入的模型：

```bash
ollama serve
ollama pull gemma3:4b
```

如需更换模型，可在 `backend/.env.example` 基础上创建 `.env`，修改 `OLLAMA_MODEL`。

### 2. 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

如需切换到 MedGemma 后端：

```bash
pip install -r requirements-medgemma.txt
cp .env.example .env
# 然后把 INFERENCE_BACKEND 改成 medgemma，并填写 MEDGEMMA_HF_TOKEN
uvicorn app.main:app --reload --port 8001
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。

## 当前能力边界

- 输入：检查单照片 + 症状/补充病情 + 当前用药
- 输出：医生版结构化结论
- 规则：内置少量高危红旗词规则
- RAG：当前只有占位的本地知识片段，下一步需要接入更成熟的公开医学资料
- 自检：前端会调用 `/api/ollama/status` 显示本地模型服务、目标模型和可用状态
- 后端切换：`/api/report/analyze` 已支持按请求或环境变量切换 `ollama / medgemma`

## 下一步建议

1. 加入 OCR 和字段确认，把图片输入转换成结构化检验项目。
2. 接入本地知识库：转诊标准、常见病指南、药品说明书、LOINC 检验项目映射。
3. 增加患者版输出，但与医生版严格区分。
4. 增加审计日志，记录输入、规则命中、知识引用和模型版本。

## 联调辅助

- 可用 `docs/sample-report.png` 作为本地图片上传联调样例
- 可用 `python3 scripts/make_sample_report.py` 重新生成样例图
- 可用 `docs/sample-cbc-report.png` 作为血常规 OCR 联调样例
- 可用 `backend/.venv/bin/python scripts/make_sample_cbc_report.py` 重新生成血常规样例图
- 可用 `docs/sample-chemistry-report.png` 作为生化基础项 OCR 联调样例
- 可用 `backend/.venv/bin/python scripts/make_sample_chemistry_report.py` 重新生成生化样例图

## MedGemma 部署

- 详细说明见 `docs/medgemma-backend.md`
- MedGemma 1.5 4B IT 是更适合你当前报告图片场景的图文模型
- 由于该模型受条款控制，接入前需要先在 Hugging Face 接受使用条件

## 设计说明

前端风格采用折中方案：

- 首页参考 Apple 官网的留白、层级和卡片节奏
- 工作台参考 Apple HIG 的应用型布局与表单可用性

仅参考设计语言，不使用 Apple 专有素材。
