# Industrial Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the current product-prototype page into a two-page local clinical system: a low-noise doctor workbench and a model management dashboard with MedGemma-first inference and Ollama automatic fallback.

**Architecture:** Add backend inference metadata and runtime state without introducing a database or queue. Split the frontend into small API/type/page/component modules while keeping simple hash/path routing and existing Vite/React infrastructure.

**Tech Stack:** FastAPI, Pydantic, unittest, React 19, TypeScript, Vite, CSS

---

## File Map

- Modify: `backend/app/models.py`
  - Add inference metadata models to `AnalysisResponse`.
- Modify: `backend/app/main.py`
  - Add status lifecycle, startup warmup, MedGemma-first fallback routing, and expanded `/api/inference/status`.
- Modify: `backend/app/medgemma_client.py`
  - Expose loaded state helpers used by runtime status.
- Create: `backend/tests/test_inference_flow.py`
  - Cover fallback selection and inference metadata helpers.
- Create: `frontend/src/types.ts`
  - Shared frontend API types.
- Create: `frontend/src/api.ts`
  - API calls for inference status and report analysis.
- Create: `frontend/src/components/StatusPill.tsx`
  - Small reusable status badge.
- Create: `frontend/src/components/ResultSections.tsx`
  - Result rendering helpers.
- Create: `frontend/src/pages/DoctorWorkbench.tsx`
  - Low-noise doctor-facing workbench.
- Create: `frontend/src/pages/ModelDashboard.tsx`
  - Admin-facing model status dashboard.
- Modify: `frontend/src/App.tsx`
  - Route between `/` and `/models`.
- Modify: `frontend/src/index.css`
  - Replace marketing layout with industrial card/workbench/dashboard styling.

### Task 1: Backend Inference Metadata and Fallback

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/medgemma_client.py`
- Create: `backend/tests/test_inference_flow.py`

- [x] **Step 1: Write failing backend tests**

Create `backend/tests/test_inference_flow.py` with tests for:

```python
import unittest

from app.main import _choose_backend, _fallback_reason
from app.models import InferenceMeta


class InferenceFlowTest(unittest.TestCase):
    def test_uses_medgemma_when_ready(self):
        self.assertEqual(_choose_backend("ready", True), "medgemma")

    def test_falls_back_to_ollama_when_medgemma_not_ready(self):
        self.assertEqual(_choose_backend("loading", True), "ollama")

    def test_reports_no_backend_when_both_are_unavailable(self):
        self.assertIsNone(_choose_backend("failed", False))

    def test_inference_meta_marks_fallback(self):
        meta = InferenceMeta(
            backend="ollama",
            used_fallback=True,
            primary_backend="medgemma",
            fallback_reason=_fallback_reason("loading"),
        )

        self.assertTrue(meta.used_fallback)
        self.assertEqual(meta.backend, "ollama")
        self.assertIn("MedGemma", meta.fallback_reason)
```

- [x] **Step 2: Verify RED**

Run: `source .venv/bin/activate && python -m unittest tests/test_inference_flow.py`
Workdir: `/Users/vic/Desktop/Devs/赤脚医生/backend`
Expected: fail because `_choose_backend`, `_fallback_reason`, and `InferenceMeta` are not defined.

- [x] **Step 3: Add inference metadata models**

Add `InferenceMeta` to `backend/app/models.py` and an optional `inference` field to `AnalysisResponse`.

- [x] **Step 4: Add backend selection helpers and runtime state**

In `backend/app/main.py`, add:

```python
def _choose_backend(medgemma_status: str, ollama_ready: bool) -> str | None:
    if medgemma_status == "ready":
        return "medgemma"
    if ollama_ready:
        return "ollama"
    return None


def _fallback_reason(medgemma_status: str) -> str:
    reasons = {
        "not_loaded": "MedGemma 尚未加载，已自动使用备用模型。",
        "loading": "MedGemma 正在加载，已自动使用备用模型。",
        "failed": "MedGemma 加载失败，已自动使用备用模型。",
    }
    return reasons.get(medgemma_status, "MedGemma 当前不可用，已自动使用备用模型。")
```

- [x] **Step 5: Update `/api/report/analyze`**

Make analysis use MedGemma when ready and automatically fall back to Ollama when not ready. Attach `InferenceMeta` to the response.

- [x] **Step 6: Verify GREEN**

Run: `source .venv/bin/activate && python -m unittest tests/test_inference_flow.py tests/test_medgemma_client.py tests/test_prompting.py`
Expected: all tests pass.

### Task 2: Backend Status and Startup Warmup

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/medgemma_client.py`

- [x] **Step 1: Add MedGemma loaded helper**

Expose a read-only method or property on `MedGemmaRuntime`:

```python
def is_loaded(self) -> bool:
    return self._loaded
```

- [x] **Step 2: Add app startup task**

Use FastAPI startup to create a background task that warms MedGemma without blocking API startup.

- [x] **Step 3: Expand `/api/inference/status`**

Return:

```json
{
  "strategy": {"primary": "medgemma", "fallback": "ollama", "auto_fallback": true},
  "models": [],
  "last_analysis": {}
}
```

Keep compatibility only if needed by frontend during transition; new frontend should use the new shape.

- [x] **Step 4: Verify service starts**

Run: `source .venv/bin/activate && python -m compileall app tests`
Expected: compile succeeds.

### Task 3: Frontend API, Types, and Routing

**Files:**
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`

- [x] **Step 1: Create frontend types**

Move API types out of `App.tsx` into `types.ts`, including `AnalysisResponse`, `InferenceMeta`, `InferenceStatus`, and form state types.

- [x] **Step 2: Create API wrapper**

Add `fetchInferenceStatus()` and `analyzeReport()` in `api.ts`.

- [x] **Step 3: Replace App with simple routing**

Use `window.location.pathname` to choose:

- `/` -> `DoctorWorkbench`
- `/models` -> `ModelDashboard`

- [x] **Step 4: Verify build**

Run: `npm run build`
Workdir: `/Users/vic/Desktop/Devs/赤脚医生/frontend`
Expected: TypeScript and Vite build pass after page files exist.

### Task 4: Doctor Workbench Page

**Files:**
- Create: `frontend/src/pages/DoctorWorkbench.tsx`
- Create: `frontend/src/components/ResultSections.tsx`
- Create: `frontend/src/components/StatusPill.tsx`
- Modify: `frontend/src/index.css`

- [x] **Step 1: Build standard-mode doctor workbench**

Create cards for:

- Patient info: age, sex
- Report upload
- Clinical notes: symptoms, clinical notes, medications
- Result

Do not include model selector, hero marketing, roadmap, safety commitments, or model technical details.

- [x] **Step 2: Use backend default inference**

Submit report analysis without appending `backend`.

- [x] **Step 3: Show fallback hint**

If `result.inference?.used_fallback` is true, show:

`本次由备用模型生成，建议人工复核。`

- [x] **Step 4: Verify UI compiles**

Run: `npm run lint && npm run build`
Expected: pass.

### Task 5: Model Dashboard Page

**Files:**
- Create: `frontend/src/pages/ModelDashboard.tsx`
- Modify: `frontend/src/index.css`

- [x] **Step 1: Build card dashboard**

Create cards for:

- MedGemma primary model
- Ollama fallback model
- Current strategy
- Last analysis

- [x] **Step 2: Poll inference status**

Refresh status every 10-15 seconds.

- [x] **Step 3: Verify route manually**

Open `http://127.0.0.1:5173/models` and confirm dashboard renders.

### Task 6: Final Verification and Publication

**Files:**
- All modified files

- [x] **Step 1: Run backend tests**

Run: `source .venv/bin/activate && python -m unittest tests/test_inference_flow.py tests/test_medgemma_client.py tests/test_prompting.py`
Workdir: `/Users/vic/Desktop/Devs/赤脚医生/backend`
Expected: all tests pass.

- [x] **Step 2: Run frontend verification**

Run: `npm run lint && npm run build`
Workdir: `/Users/vic/Desktop/Devs/赤脚医生/frontend`
Expected: lint and build pass.

- [x] **Step 3: Browser smoke test**

Open:

- `http://127.0.0.1:5173/`
- `http://127.0.0.1:5173/models`

Expected: doctor workbench and model dashboard render.

- [ ] **Step 4: Commit and push**

```bash
git add backend frontend docs/superpowers/plans/2026-04-17-industrial-workbench.md
git commit -m "feat: add industrial doctor workbench"
git push
```

## Self-Review

### Spec Coverage

- Doctor workbench with no marketing copy: Task 4.
- Model dashboard at `/models`: Task 5.
- MedGemma primary and Ollama fallback: Tasks 1 and 2.
- Inference metadata and fallback hint: Tasks 1 and 4.
- Frontend splitting and card UI: Tasks 3, 4, and 5.
- Verification and publication: Task 6.

### Placeholder Scan

- No TBD/TODO placeholders.
- Each task has exact files and verification commands.

### Type Consistency

- Backend metadata uses `InferenceMeta`.
- Frontend response type includes optional `inference`.
- Status endpoint shape is `strategy`, `models`, and `last_analysis`.
