# 工业化医生工作台与模型管理台设计说明

## 背景

当前前端已经完成了产品展示型改版，并且后端已经可以在本地运行 MedGemma 与 Ollama。但是页面仍然更像对外展示原型，而不是医生日常可使用的工业级工作系统：

- 医生会看到过多产品说明、路线图、安全承诺和模型细节。
- 模型选择暴露在医生工作台里，增加临床现场认知负担。
- 首屏承担了营销叙事，不适合作为长期使用的工作入口。
- 后端虽然支持按请求选择模型，但尚未形成“主模型优先、备用模型自动降级”的部署策略。
- 模型状态展示还偏轻量，没有区分医生视角和管理员视角。

本次设计目标是把系统从“产品原型首页”推进到“可部署的临床工作台雏形”。

## 用户决策

本轮已确认以下方向：

- 页面结构采用“医生工作台 + 模型管理台”。
- 医生工作台使用标准模式，只保留年龄、性别、检查单上传、主诉、补充病情和当前用药。
- MedGemma 是主力模型，后端启动后优先预热。
- Ollama 是备用模型，用于 MedGemma 不可用时自动降级。
- 医生端不暴露模型选择，不需要理解 MedGemma / Ollama 的技术细节。
- 管理台显示两个模型的状态，并且 MedGemma 排在第一位。

## 目标

1. 将医生端改成低干扰、卡片式、工作流优先的临床界面。
2. 将模型状态、预热、错误和部署信息移到独立管理台。
3. 后端启动后优先预热 MedGemma，并检查 Ollama 备用能力。
4. 分析请求默认走 MedGemma；如果 MedGemma 不可用，自动降级到 Ollama。
5. 分析结果返回元信息，标注实际使用的模型和是否发生降级。
6. 保留现有病例输入字段和结构化结果字段，避免一次性扩展临床字段。

## 非目标

- 不增加用户登录、权限系统或审计日志。
- 不实现病例历史列表、数据库存储或多患者管理。
- 不新增 OCR 字段确认流程。
- 不新增生命体征、过敏史、既往史等完整临床表单。
- 不实现真正的模型队列系统或多 worker 编排。
- 不把 MedGemma 和 Ollama 的结果并排展示给医生比较。
- 不追求生产级高可用，只完成本地部署下的工业化界面与基础模型生命周期。

## 信息架构

### 医生工作台 `/`

医生工作台是默认入口。页面要像工作系统，而不是宣传页。

页面保留的信息：

- 系统名
- 简短系统状态
- 进入模型管理台的入口
- 病例信息卡片
- 检查单上传卡片
- 当前用药与补充病情卡片
- 结果卡片

页面移除的信息：

- 产品路线图
- 大段使命叙事
- 面向管理者的产品价值卡片
- 模型选择下拉框
- MedGemma / Ollama 技术解释
- 展示型 hero 视觉装置

医生端状态文案必须克制：

- 系统准备中
- 可以分析
- 正在分析
- 分析完成
- 已自动启用备用模型
- 分析失败，请人工复核或联系管理员

### 模型管理台 `/models`

模型管理台给管理员、部署者或技术人员使用。医生日常不需要进入。

页面包含四类卡片：

1. MedGemma 主模型卡片
2. Ollama 备用模型卡片
3. 当前推理策略卡片
4. 最近一次分析状态卡片

模型卡片字段：

- 模型名称
- 角色：主力或备用
- 状态：未加载、加载中、可用、失败
- 配置来源：模型 ID、设备、服务地址
- 最近错误
- 建议动作

推理策略卡片字段：

- 默认策略：MedGemma 优先
- 降级策略：MedGemma 不可用时自动使用 Ollama
- 医生端是否显示模型选择：否
- 结果是否标注备用模型：是

## 医生工作台设计

医生端采用卡片式布局。

桌面端建议为双栏结构：

- 左栏：病例输入
- 右栏：分析结果

移动端改为单列：

- 顶部状态
- 病例输入
- 上传检查单
- 生成按钮
- 分析结果

输入卡片：

- 年龄
- 性别
- 主诉 / 症状
- 补充病情
- 当前用药

上传卡片：

- 检查单图片
- 上传后预览
- 文件名和大小

操作卡片：

- 主按钮：生成医生版结论
- 状态提示：系统准备中 / 正在分析 / 分析完成 / 备用模型已启用

结果卡片：

- 风险等级
- 医生摘要
- 异常点
- 可能原因
- 下一步行动
- 立即转诊原因
- 用药注意
- 优先提醒
- 参考依据
- 免责声明

如果发生降级，只显示一句轻提示：

> 本次由备用模型生成，建议人工复核。

## 模型管理台设计

管理台采用仪表盘式卡片布局。

顶部：

- 标题：模型管理台
- 副标题：本地推理状态与降级策略
- 返回医生工作台入口

MedGemma 卡片：

- 作为主模型置顶
- 显示加载状态和模型 ID
- 显示是否已配置 HF token
- 显示设备配置
- 显示最近错误

Ollama 卡片：

- 作为备用模型
- 显示服务地址
- 显示模型名
- 显示是否连接成功
- 显示可用模型列表

策略卡片：

- 说明 MedGemma 优先、Ollama 自动降级
- 说明医生端不显示模型选择
- 说明降级会在结果中标注

最近一次分析卡片：

- 实际使用的后端
- 是否降级
- 请求状态
- 最近错误
- 时间戳

## 后端模型生命周期

### 运行时状态

后端需要维护模型运行时状态，至少包括：

- `status`: `not_loaded | loading | ready | failed`
- `role`: `primary | fallback`
- `backend`: `medgemma | ollama`
- `model_id`
- `device` 或 `base_url`
- `last_error`
- `last_checked_at`

### 启动策略

应用启动后：

1. API 先启动，不阻塞服务可访问性。
2. 后台任务优先预热 MedGemma。
3. 同时或随后检查 Ollama 连接和目标模型可用性。
4. 状态通过管理台接口暴露。

### 分析策略

分析接口默认不再由医生选择模型。

请求流程：

1. 评估红旗规则。
2. 如果 MedGemma 状态为 `ready`，使用 MedGemma。
3. 如果 MedGemma 为 `loading`、`failed` 或 `not_loaded`，自动降级到 Ollama。
4. 如果 Ollama 也不可用，返回清晰错误。
5. 规则高风险仍然可以覆盖模型输出。
6. 响应中加入推理元信息。

## API 设计

### `GET /api/inference/status`

返回面向前端的模型状态。

建议结构：

```json
{
  "strategy": {
    "primary": "medgemma",
    "fallback": "ollama",
    "auto_fallback": true
  },
  "models": [
    {
      "backend": "medgemma",
      "role": "primary",
      "status": "ready",
      "model_id": "google/medgemma-1.5-4b-it",
      "device": "auto",
      "last_error": null,
      "last_checked_at": "2026-04-17T18:00:00+08:00"
    },
    {
      "backend": "ollama",
      "role": "fallback",
      "status": "ready",
      "model_id": "gemma3:4b",
      "base_url": "http://127.0.0.1:11434",
      "last_error": null,
      "last_checked_at": "2026-04-17T18:00:00+08:00"
    }
  ],
  "last_analysis": {
    "backend": "medgemma",
    "used_fallback": false,
    "status": "completed",
    "error": null
  }
}
```

### `POST /api/report/analyze`

请求字段保持不变，但前端医生端不再发送 `backend` 字段。

响应结构在现有 `AnalysisResponse` 基础上增加可选元信息：

```json
{
  "inference": {
    "backend": "ollama",
    "used_fallback": true,
    "primary_backend": "medgemma",
    "fallback_reason": "MedGemma 正在加载"
  }
}
```

前端只使用其中一部分：

- `used_fallback`
- `backend`
- `fallback_reason`

## 前端实现方向

当前 `App.tsx` 已经偏大，后续实现应拆分文件。

建议结构：

- `frontend/src/App.tsx`
  - 只负责当前路径判断和页面切换。
- `frontend/src/pages/DoctorWorkbench.tsx`
  - 医生工作台。
- `frontend/src/pages/ModelDashboard.tsx`
  - 模型管理台。
- `frontend/src/types.ts`
  - API 类型。
- `frontend/src/api.ts`
  - 状态查询与分析请求。
- `frontend/src/components/StatusPill.tsx`
  - 状态徽标。
- `frontend/src/components/ResultSections.tsx`
  - 结果区块。

CSS 可以继续放在 `index.css`，但需要按页面区域重新整理。

## 失败与降级体验

医生端：

- MedGemma 正在加载且 Ollama 可用：自动使用 Ollama，并显示备用模型轻提示。
- MedGemma 失败且 Ollama 可用：自动使用 Ollama，并显示备用模型轻提示。
- 两个模型都不可用：显示错误卡片，提示联系管理员。

管理台：

- 显示每个模型的具体状态和错误。
- 提供建议动作，例如“确认 HF token 权限”、“确认 Ollama 服务已启动”、“确认已拉取 gemma3:4b”。

## 验收标准

医生工作台：

- 默认进入 `/` 后不再出现营销型 hero、路线图、安全承诺区块。
- 医生端不显示模型选择下拉框。
- 医生端可以提交现有字段并获得结构化结果。
- 如果自动降级到 Ollama，结果区显示备用模型提示。
- 移动端单列可用。

模型管理台：

- `/models` 可以看到 MedGemma 和 Ollama 两张模型卡片。
- MedGemma 排在第一位，标注为主力模型。
- Ollama 标注为备用模型。
- 能看到当前推理策略和最近一次分析状态。

后端：

- 启动后 API 不被 MedGemma 加载阻塞。
- 后台优先预热 MedGemma。
- `/api/inference/status` 能返回两个模型状态。
- `/api/report/analyze` 默认 MedGemma 优先，MedGemma 不可用时自动降级 Ollama。
- 新增或更新测试覆盖状态结构、降级逻辑和推理元信息。

验证：

- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过。
- 后端单元测试通过。
- 本地浏览器能打开医生工作台和模型管理台。
- 至少一次手动分析请求能返回结果。

## 风险与取舍

- MedGemma 本地推理慢，医生端必须给出明确“正在分析”的状态。
- 后台预热会占用内存，管理台需要如实显示加载状态。
- 这不是完整生产级模型编排，本轮只做本地部署下的基础生命周期管理。
- 自动降级到 Ollama 会提高可用性，但结果必须轻提示人工复核。
- 医生端减少文字后，管理员需要通过 `/models` 承担更多解释和排错职责。
