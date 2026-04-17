# Frontend Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the current single-page frontend so it feels like a polished, narrative-driven product launch page for grassroots doctors and hospital managers without changing the app's core structure or API behavior.

**Architecture:** Keep the existing React single-page layout and all current functional flows, then improve the product perception through two tightly scoped areas: copy/content updates in `App.tsx` and visual system cleanup in `index.css`. Do not add routes, new data dependencies, or new interactive state beyond what already exists.

**Tech Stack:** React 19, TypeScript, Vite, CSS

---

## File Map

- Modify: `frontend/src/App.tsx`
  - Responsibility: Homepage narrative, CTA copy, section titles, helper text, empty states, and roadmap wording.
- Modify: `frontend/src/index.css`
  - Responsibility: Global design tokens, hero atmosphere, card styling, form/result hierarchy, and responsive polish.
- Keep unchanged: `frontend/src/App.css`
  - Responsibility: Legacy template styles that are no longer part of the active UI.
- Verify: `frontend/package.json`
  - Responsibility: Existing frontend scripts for `build` and `lint`.

### Task 1: Rewrite the page narrative in `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`
- Verify: `frontend/src/App.tsx`

- [ ] **Step 1: Inspect the current copy blocks that shape the page narrative**

Run: `sed -n '1,260p' /Users/vic/Desktop/Devs/赤脚医生/frontend/src/App.tsx`
Expected: See the hero, status ribbon, facts cards, workspace intro, principles, and roadmap copy that will be rewritten.

- [ ] **Step 2: Rewrite the hero and supporting blocks toward a narrative product tone**

Update the JSX copy so the page leads with grassroots clinical context and product value instead of engineering-first wording.

```tsx
<p className="eyebrow">面向乡镇医院与县级医院的本地辅助系统</p>
<h1>先帮医生看清风险，再谈模型能做什么。</h1>
<p className="hero-description">
  赤脚医生不是替代判断的 AI 医生，而是一名始终站在基层接诊现场旁边的副手。
  它先整理检查单、症状与用药信息，再给出风险分级、下一步动作和转诊优先级，帮助医生更快进入判断。
</p>
```

- [ ] **Step 3: Rewrite value cards, workspace copy, empty states, and roadmap text**

Keep the same sections but rename and rewrite them to highlight real usage moments rather than MVP implementation phases.

```tsx
<article className="stat-card glass-card">
  <span>进入方式</span>
  <strong>从一张检查单开始</strong>
  <p>支持直接拍照上传，把基层最常见的纸质单据先带进判断流程，再逐步补齐结构化能力。</p>
</article>

<p className="empty-title">这里会生成医生版结论</p>
<p>上传检查单并补充最少必要病情后，系统会按风险、异常点和下一步动作给出结构化参考。</p>

<article className="roadmap-card">
  <span>Phase 2</span>
  <h3>让图片先变成可确认的数据</h3>
  <p>补上 OCR 和人工确认后，系统才更适合真正进入基层连续使用场景。</p>
</article>
```

- [ ] **Step 4: Run the frontend build to catch JSX or type regressions**

Run: `npm run build`
Workdir: `/Users/vic/Desktop/Devs/赤脚医生/frontend`
Expected: Vite build completes successfully and outputs the production bundle.

- [ ] **Step 5: Commit the content refresh**

```bash
git add /Users/vic/Desktop/Devs/赤脚医生/frontend/src/App.tsx
git commit -m "feat: refresh homepage narrative copy"
```

### Task 2: Replace the visual tokens and page atmosphere in `index.css`

**Files:**
- Modify: `frontend/src/index.css`
- Verify: `frontend/src/index.css`

- [ ] **Step 1: Inspect the active CSS token and layout definitions**

Run: `sed -n '1,260p' /Users/vic/Desktop/Devs/赤脚医生/frontend/src/index.css`
Expected: See the current root variables, global styles, hero panel styling, card styling, and responsive rules.

- [ ] **Step 2: Introduce a more distinctive visual system without changing layout structure**

Update the root tokens, background treatment, card borders, and button styling so the page reads like a polished medical product launch rather than a generic demo page.

```css
:root {
  font-family:
    "Source Han Sans SC", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #172126;
  background:
    radial-gradient(circle at top left, rgba(182, 223, 216, 0.42), transparent 28%),
    radial-gradient(circle at top right, rgba(230, 214, 188, 0.26), transparent 24%),
    linear-gradient(180deg, #f4efe6 0%, #f8f6f1 18%, #f5f7f4 100%);
  --accent-strong: #235c55;
  --accent-warm: #c48a4a;
  --surface: rgba(255, 252, 246, 0.72);
  --shadow-card: 0 24px 60px rgba(35, 54, 48, 0.10);
}

.primary-button {
  background: linear-gradient(135deg, #173a36, #235c55);
  color: #fdfbf7;
}
```

- [ ] **Step 3: Tighten hierarchy in the hero, workspace, and result areas**

Refine spacing, typography, badge treatments, and card backgrounds so the hero feels intentional and the workspace feels like a production-ready console.

```css
.hero-copy h1 {
  font-size: clamp(3.2rem, 5vw, 5.4rem);
  line-height: 0.94;
  max-width: 9ch;
}

.workspace-card {
  padding: 28px;
  border: 1px solid rgba(23, 33, 38, 0.08);
  background: rgba(255, 250, 244, 0.82);
}

.risk-badge {
  letter-spacing: 0.04em;
  box-shadow: inset 0 0 0 1px rgba(23, 33, 38, 0.06);
}
```

- [ ] **Step 4: Run lint and build to validate the CSS-driven refresh**

Run: `npm run lint && npm run build`
Workdir: `/Users/vic/Desktop/Devs/赤脚医生/frontend`
Expected: ESLint passes and the Vite production build succeeds.

- [ ] **Step 5: Commit the visual refresh**

```bash
git add /Users/vic/Desktop/Devs/赤脚医生/frontend/src/index.css
git commit -m "feat: polish frontend visual language"
```

### Task 3: Connect the local project to the provided GitHub repository and publish

**Files:**
- Modify: `.git` metadata in project root
- Verify: remote GitHub repository state

- [ ] **Step 1: Initialize the current project as a git repository if needed**

Run: `git rev-parse --show-toplevel`
Workdir: `/Users/vic/Desktop/Devs/赤脚医生`
Expected: Either print the repo root or fail, confirming whether initialization is required.

- [ ] **Step 2: Attach the provided GitHub repository as `origin`**

Use the provided remote URL and avoid deleting any local files.

```bash
git init
git remote add origin https://github.com/caicaivic0322/DocuFeet.git
git remote -v
```

- [ ] **Step 3: Stage the full project state after the frontend refresh**

```bash
git add /Users/vic/Desktop/Devs/赤脚医生
git status --short
```

Expected: The refreshed frontend files, spec, and plan appear as staged additions or modifications.

- [ ] **Step 4: Create the first project commit**

```bash
git commit -m "feat: refresh frontend presentation and copy"
```

- [ ] **Step 5: Push the branch to GitHub**

```bash
git branch -M main
git push -u origin main
```

Expected: The local project is published to the provided GitHub repository.

## Self-Review

### Spec coverage

- Hero narrative refresh: covered in Task 1.
- Card, workspace, principle, and roadmap copy refresh: covered in Task 1.
- Visual token and atmosphere cleanup: covered in Task 2.
- Responsive-safe polish without structural rewrite: covered in Task 2.
- GitHub publication to the provided repository: covered in Task 3.

### Placeholder scan

- No placeholder markers remain.
- Each task names exact files and exact commands.
- Verification commands are concrete.

### Type consistency

- The plan only changes JSX copy and CSS rules in the current file structure.
- No new types, functions, props, or API contracts are introduced, so there are no cross-task signature mismatches.
