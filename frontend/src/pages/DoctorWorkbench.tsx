import { type ChangeEvent, type FormEvent, useEffect, useMemo, useState } from 'react'
import { analyzeReport, fetchInferenceStatus } from '../api'
import { ResultSections } from '../components/ResultSections'
import { StatusPill } from '../components/StatusPill'
import type { AnalysisResponse, InferenceStatus, ModelRuntime } from '../types'

function getModel(status: InferenceStatus | null, backend: string): ModelRuntime | null {
  return status?.models.find((model) => model.backend === backend) ?? null
}

export function DoctorWorkbench() {
  const [patientAge, setPatientAge] = useState('')
  const [patientSex, setPatientSex] = useState('未提供')
  const [symptoms, setSymptoms] = useState('')
  const [clinicalNotes, setClinicalNotes] = useState('')
  const [currentMedications, setCurrentMedications] = useState('')
  const [reportImage, setReportImage] = useState<File | null>(null)
  const [status, setStatus] = useState<InferenceStatus | null>(null)
  const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [phase, setPhase] = useState('待录入')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const payload = await fetchInferenceStatus()
        if (!cancelled) {
          setStatus(payload)
        }
      } catch {
        if (!cancelled) {
          setStatus(null)
        }
      }
    }

    load()
    const timer = window.setInterval(load, 15000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  const previewUrl = useMemo(() => (reportImage ? URL.createObjectURL(reportImage) : ''), [reportImage])

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  const primaryModel = getModel(status, 'medgemma')
  const fallbackModel = getModel(status, 'ollama')
  const activeLabel =
    primaryModel?.status === 'ready'
      ? '本地分析就绪'
      : fallbackModel?.status === 'ready'
        ? '备用链路可用'
        : '服务检查中'

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setReportImage(event.target.files?.[0] ?? null)
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setPhase('分析中')

    try {
      const payload = await analyzeReport({
        reportImage,
        patientAge,
        patientSex,
        symptoms,
        clinicalNotes,
        currentMedications,
      })
      setResult(payload)
      setPhase('已完成')
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '请求失败，请检查本地后端。')
      setPhase('需处理')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="app-shell workbench-shell">
      <header className="topbar">
        <a className="brand-lockup" href="/">
          <span className="brand-mark">赤</span>
          <span>
            <strong>赤脚医生</strong>
            <small>医生工作台</small>
          </span>
        </a>
        <nav className="topnav" aria-label="主导航">
          <a aria-current="page" href="/">
            工作台
          </a>
          <a href="/models">模型管理</a>
        </nav>
      </header>

      <main className="clinical-layout">
        <section className="patient-panel">
          <div className="section-title">
            <div>
              <p className="eyebrow">Standard Mode</p>
              <h1>门诊分析</h1>
            </div>
            <div className="status-cluster">
              <StatusPill label={activeLabel} tone={primaryModel?.status ?? 'neutral'} />
              <span>{phase}</span>
            </div>
          </div>

          <form className="clinical-form" onSubmit={onSubmit}>
            <section className="form-section compact-grid">
              <label className="field">
                <span>年龄</span>
                <input
                  type="number"
                  min="0"
                  placeholder="例如 68"
                  value={patientAge}
                  onChange={(event) => setPatientAge(event.target.value)}
                />
              </label>
              <label className="field">
                <span>性别</span>
                <select value={patientSex} onChange={(event) => setPatientSex(event.target.value)}>
                  <option value="未提供">未提供</option>
                  <option value="男">男</option>
                  <option value="女">女</option>
                </select>
              </label>
            </section>

            <section className="form-section">
              <label className="upload-dropzone">
                <input type="file" accept="image/*" onChange={onFileChange} />
                <span className="upload-title">检查单 / 影像报告</span>
                <span className="upload-copy">
                  {reportImage
                    ? `${reportImage.name} · ${(reportImage.size / 1024 / 1024).toFixed(2)} MB`
                    : '拖入或选择一张报告照片'}
                </span>
              </label>
              {previewUrl ? (
                <figure className="upload-preview">
                  <img src={previewUrl} alt="报告预览" />
                </figure>
              ) : null}
            </section>

            <section className="form-section">
              <label className="field">
                <span>主诉 / 症状</span>
                <textarea
                  rows={3}
                  placeholder="例如：胸闷、出汗、头晕 2 小时"
                  value={symptoms}
                  onChange={(event) => setSymptoms(event.target.value)}
                />
              </label>
              <label className="field">
                <span>补充病情</span>
                <textarea
                  rows={4}
                  placeholder="既往史、生命体征、检查背景、医生观察到的重点"
                  value={clinicalNotes}
                  onChange={(event) => setClinicalNotes(event.target.value)}
                />
              </label>
              <label className="field">
                <span>当前用药</span>
                <textarea
                  rows={3}
                  placeholder="例如：阿司匹林、氯沙坦、二甲双胍"
                  value={currentMedications}
                  onChange={(event) => setCurrentMedications(event.target.value)}
                />
              </label>
            </section>

            <button className="primary-button" type="submit" disabled={submitting}>
              {submitting ? '正在生成结论' : '开始分析'}
            </button>

            {error ? <p className="error-banner">{error}</p> : null}
          </form>
        </section>

        <aside className="result-panel">
          <div className="section-title">
            <div>
              <p className="eyebrow">Clinical Output</p>
              <h2>结构化结论</h2>
            </div>
            {result?.inference?.used_fallback ? <StatusPill label="人工复核" tone="loading" /> : null}
          </div>

          {result ? (
            <ResultSections result={result} />
          ) : submitting ? (
            <div className="pending-state">
              <span />
              <span />
              <span />
              <p>正在整理报告、病情和红旗规则。</p>
            </div>
          ) : (
            <div className="empty-state">
              <strong>等待病例输入</strong>
              <p>填写左侧信息后，这里会显示风险分级、异常点、下一步处理和转诊提示。</p>
            </div>
          )}
        </aside>
      </main>
    </div>
  )
}
