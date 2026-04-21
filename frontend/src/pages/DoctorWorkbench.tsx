import { type ChangeEvent, type FormEvent, useEffect, useMemo, useState } from 'react'
import {
  analyzeLabReports,
  extractCBCReport,
  fetchDemoCBCSample,
  fetchDemoCBCSampleFile,
  fetchInferenceStatus,
} from '../api'
import { ResultSections } from '../components/ResultSections'
import { StatusPill } from '../components/StatusPill'
import type {
  AnalysisResponse,
  InferenceStatus,
  LabExtractionResponse,
  LabReportItem,
  LabReportType,
  ModelRuntime,
  StructuredLabReport,
} from '../types'

const requiredReportItems: Record<LabReportType, LabReportItem['name'][]> = {
  cbc: ['WBC', 'RBC', 'HGB', 'PLT'],
  chemistry_basic: ['Cr', 'K', 'Na', 'GLU'],
}

const reportTypeLabel: Record<LabReportType, string> = {
  cbc: '血常规',
  chemistry_basic: '生化基础项',
}

const isFileApp = window.location.protocol === 'file:'
const homeHref = isFileApp ? './index.html' : '/'
const modelsHref = isFileApp ? './index.html#/models' : '/models'

function getModel(status: InferenceStatus | null, backend: string): ModelRuntime | null {
  return status?.models.find((model) => model.backend === backend) ?? null
}

function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`
}

function reportKey(report: StructuredLabReport): string {
  return `${report.report_type}:${report.source_image_name ?? '未命名'}:${report.items.length}`
}

export function DoctorWorkbench() {
  const [patientAge, setPatientAge] = useState('')
  const [patientSex, setPatientSex] = useState('未提供')
  const [symptoms, setSymptoms] = useState('')
  const [clinicalNotes, setClinicalNotes] = useState('')
  const [currentMedications, setCurrentMedications] = useState('')
  const [reportImage, setReportImage] = useState<File | null>(null)
  const [status, setStatus] = useState<InferenceStatus | null>(null)
  const [extraction, setExtraction] = useState<LabExtractionResponse | null>(null)
  const [confirmedItems, setConfirmedItems] = useState<LabReportItem[]>([])
  const [confirmedReports, setConfirmedReports] = useState<StructuredLabReport[]>([])
  const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [phase, setPhase] = useState('待录入')
  const [error, setError] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [loadingDemo, setLoadingDemo] = useState(false)
  const [isDemoCase, setIsDemoCase] = useState(false)

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

  const activeReportType = extraction?.report_type ?? 'cbc'
  const confirmedRequiredNames = new Set(
    confirmedItems.filter((item) => item.confirmed && item.value.trim()).map((item) => item.name),
  )
  const missingRequiredItems = requiredReportItems[activeReportType].filter(
    (name) => !confirmedRequiredNames.has(name),
  )
  const canAddCurrentReport = Boolean(extraction) && missingRequiredItems.length === 0
  const canAnalyze = confirmedReports.length > 0

  const resetCurrentUpload = () => {
    setReportImage(null)
    setExtraction(null)
    setConfirmedItems([])
  }

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setReportImage(event.target.files?.[0] ?? null)
    setExtraction(null)
    setConfirmedItems([])
    setResult(null)
    setError('')
    setPhase('待识别')
    setIsDemoCase(false)
  }

  const onExtract = async () => {
    if (!reportImage) {
      setError('请先上传检验单图片。')
      return
    }

    setExtracting(true)
    setError('')
    setResult(null)
    setPhase('识别中')

    try {
      const payload = await extractCBCReport(reportImage)
      setExtraction(payload)
      setConfirmedItems(payload.items.map((item) => ({ ...item, confirmed: Boolean(item.value) })))
      setPhase(payload.can_analyze ? '待加入病例' : '需复核')
    } catch (extractError) {
      setError(extractError instanceof Error ? extractError.message : '识别失败，请检查检验单图片。')
      setPhase('需处理')
    } finally {
      setExtracting(false)
    }
  }

  const addCurrentReport = () => {
    if (!extraction || !canAddCurrentReport) {
      setError(`关键字段尚未确认：${missingRequiredItems.join(', ')}。`)
      return
    }

    const report: StructuredLabReport = {
      report_type: extraction.report_type,
      source_image_name: extraction.source_image_name ?? reportImage?.name ?? null,
      items: confirmedItems,
    }
    setConfirmedReports((current) => [...current, report])
    resetCurrentUpload()
    setError('')
    setPhase('已加入病例')
  }

  const removeReport = (index: number) => {
    setConfirmedReports((current) => current.filter((_, currentIndex) => currentIndex !== index))
    setResult(null)
  }

  const loadDemoReport = async (kind: 'cbc' | 'chemistry') => {
    const demo = await fetchDemoCBCSample(kind)
    const demoFile = await fetchDemoCBCSampleFile(demo.image_url, demo.image_name)
    const payload = await extractCBCReport(demoFile)
    const nextItems = payload.items.map((item) => ({ ...item, confirmed: Boolean(item.value) }))
    const report: StructuredLabReport = {
      report_type: payload.report_type,
      source_image_name: payload.source_image_name ?? demo.image_name,
      items: nextItems,
    }

    return { demo, demoFile, payload, report }
  }

  const onLoadDemo = async (kind: 'cbc' | 'chemistry') => {
    setLoadingDemo(true)
    setError('')
    setResult(null)
    setPhase('加载演示病例')

    try {
      const { demo, demoFile, payload, report } = await loadDemoReport(kind)
      setIsDemoCase(true)
      setReportImage(demoFile)
      setPatientAge(String(demo.patient_age))
      setPatientSex(demo.patient_sex)
      setSymptoms(demo.symptoms)
      setClinicalNotes(demo.clinical_notes)
      setCurrentMedications(demo.current_medications)
      setExtraction(payload)
      setConfirmedItems(report.items)

      if (!payload.can_analyze) {
        setPhase('需复核')
        return
      }

      setConfirmedReports([report])
      setPhase('分析中')
      const analysis = await analyzeLabReports({
        patientAge: String(demo.patient_age),
        patientSex: demo.patient_sex,
        symptoms: demo.symptoms,
        clinicalNotes: demo.clinical_notes,
        currentMedications: demo.current_medications,
        reports: [report],
      })
      setResult(analysis)
      setPhase('已完成')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载演示病例失败。')
      setPhase('需处理')
    } finally {
      setLoadingDemo(false)
    }
  }

  const onLoadCombinedDemo = async () => {
    setLoadingDemo(true)
    setError('')
    setResult(null)
    setPhase('加载综合演示')

    try {
      const cbc = await loadDemoReport('cbc')
      const chemistry = await loadDemoReport('chemistry')
      const reports = [cbc.report, chemistry.report]
      setIsDemoCase(true)
      setPatientAge(String(chemistry.demo.patient_age))
      setPatientSex(chemistry.demo.patient_sex)
      setSymptoms('乏力、头晕、口渴 3 天。')
      setClinicalNotes('综合演示包含血常规和生化基础项，重点观察贫血、电解质、肾功能和血糖风险。')
      setCurrentMedications('二甲双胍')
      setReportImage(chemistry.demoFile)
      setExtraction(chemistry.payload)
      setConfirmedItems(chemistry.report.items)
      setConfirmedReports(reports)

      setPhase('分析中')
      const analysis = await analyzeLabReports({
        patientAge: String(chemistry.demo.patient_age),
        patientSex: chemistry.demo.patient_sex,
        symptoms: '乏力、头晕、口渴 3 天。',
        clinicalNotes: '综合演示包含血常规和生化基础项，重点观察贫血、电解质、肾功能和血糖风险。',
        currentMedications: '二甲双胍',
        reports,
      })
      setResult(analysis)
      setPhase('已完成')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载综合演示失败。')
      setPhase('需处理')
    } finally {
      setLoadingDemo(false)
    }
  }

  const updateItem = (
    name: LabReportItem['name'],
    field: keyof Pick<LabReportItem, 'value' | 'unit' | 'reference_range' | 'flag' | 'confirmed'>,
    nextValue: string | boolean,
  ) => {
    setConfirmedItems((current) =>
      current.map((item) =>
        item.name === name ? { ...item, [field]: nextValue, edited_by_user: true } : item,
      ),
    )
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canAnalyze) {
      setError('请先识别并加入至少一份检验报告。')
      return
    }

    setSubmitting(true)
    setError('')
    setPhase('综合分析中')

    try {
      const payload = await analyzeLabReports({
        patientAge,
        patientSex,
        symptoms,
        clinicalNotes,
        currentMedications,
        reports: confirmedReports,
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
        <a className="brand-lockup" href={homeHref}>
          <span className="brand-mark">赤</span>
          <span>
            <strong>赤脚医生</strong>
            <small>医生工作台</small>
          </span>
        </a>
        <nav className="topnav" aria-label="主导航">
          <a aria-current="page" href={homeHref}>
            工作台
          </a>
          <a href={modelsHref}>模型管理</a>
        </nav>
      </header>

      <main className="clinical-layout">
        <section className="patient-panel">
          <div className="section-title">
            <div>
              <p className="eyebrow">Multi-Report Workflow</p>
              <h1>病例综合分析</h1>
            </div>
            <div className="status-cluster">
              <StatusPill label={activeLabel} tone={primaryModel?.status ?? 'neutral'} />
              <span>{phase}</span>
            </div>
          </div>

          {isDemoCase ? (
            <p className="demo-banner">
              当前为演示病例流程，结果仅用于样例联调与界面展示，不代表真实患者结论。
            </p>
          ) : null}

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
              <div className="section-copy">
                <strong>第一步：上传并追加检验单</strong>
                <p>支持固定版式血常规与生化基础项。每次上传一张，确认后加入当前病例。</p>
              </div>
              <div className="inline-actions">
                <button className="control-button" type="button" disabled={loadingDemo || extracting || submitting} onClick={() => onLoadDemo('cbc')}>
                  {loadingDemo ? '正在演示' : '一键演示血常规'}
                </button>
                <button className="control-button" type="button" disabled={loadingDemo || extracting || submitting} onClick={() => onLoadDemo('chemistry')}>
                  {loadingDemo ? '正在演示' : '一键演示生化'}
                </button>
                <button className="control-button control-button-primary" type="button" disabled={loadingDemo || extracting || submitting} onClick={onLoadCombinedDemo}>
                  {loadingDemo ? '正在综合演示' : '一键综合演示'}
                </button>
              </div>
              <label className="upload-dropzone">
                <input type="file" accept="image/*" onChange={onFileChange} />
                <span className="upload-title">检验报告单</span>
                <span className="upload-copy">支持血常规 / 生化基础项固定版式</span>
                <span className="upload-copy">
                  {reportImage
                    ? `${reportImage.name} · ${(reportImage.size / 1024 / 1024).toFixed(2)} MB`
                    : '拖入或选择一张检验单图片'}
                </span>
              </label>
              {previewUrl ? (
                <figure className="upload-preview">
                  <img src={previewUrl} alt="报告预览" />
                </figure>
              ) : null}
              <button className="control-button control-button-primary" type="button" disabled={!reportImage || extracting} onClick={onExtract}>
                {extracting ? '正在识别检验单' : '识别检验字段'}
              </button>
            </section>

            <section className="form-section">
              <label className="field">
                <span>主诉 / 症状</span>
                <textarea rows={3} placeholder="例如：头晕、心慌、乏力 3 天" value={symptoms} onChange={(event) => setSymptoms(event.target.value)} />
              </label>
              <label className="field">
                <span>补充病情</span>
                <textarea rows={4} placeholder="既往史、生命体征、医生观察到的重点" value={clinicalNotes} onChange={(event) => setClinicalNotes(event.target.value)} />
              </label>
              <label className="field">
                <span>当前用药</span>
                <textarea rows={3} placeholder="例如：阿司匹林、氯沙坦、二甲双胍" value={currentMedications} onChange={(event) => setCurrentMedications(event.target.value)} />
              </label>
            </section>

            <section className="form-section">
              <div className="section-copy">
                <strong>第二步：确认识别字段</strong>
                <p>{extraction?.notice ?? '识别后会在这里展示候选字段，请逐项核对后加入病例。'}</p>
              </div>
              {extraction ? (
                <div className="inline-metadata">
                  <StatusPill label={reportTypeLabel[extraction.report_type]} tone="neutral" />
                </div>
              ) : null}

              {confirmedItems.length ? (
                <div className="cbc-table-wrap">
                  <table className="cbc-table">
                    <thead>
                      <tr>
                        <th>项目</th>
                        <th>数值</th>
                        <th>单位</th>
                        <th>参考范围</th>
                        <th>异常</th>
                        <th>置信度</th>
                        <th>确认</th>
                      </tr>
                    </thead>
                    <tbody>
                      {confirmedItems.map((item) => (
                        <tr key={item.name}>
                          <td>
                            <strong>{item.name}</strong>
                            <small>{item.alias}</small>
                          </td>
                          <td>
                            <input value={item.value} onChange={(event) => updateItem(item.name, 'value', event.target.value)} />
                          </td>
                          <td>
                            <input value={item.unit} onChange={(event) => updateItem(item.name, 'unit', event.target.value)} />
                          </td>
                          <td>
                            <input value={item.reference_range} onChange={(event) => updateItem(item.name, 'reference_range', event.target.value)} />
                          </td>
                          <td>
                            <select value={item.flag} onChange={(event) => updateItem(item.name, 'flag', event.target.value)}>
                              <option value="unknown">待定</option>
                              <option value="normal">正常</option>
                              <option value="high">偏高</option>
                              <option value="low">偏低</option>
                            </select>
                          </td>
                          <td>{formatConfidence(item.confidence)}</td>
                          <td>
                            <label className="confirm-toggle">
                              <input type="checkbox" checked={item.confirmed} onChange={(event) => updateItem(item.name, 'confirmed', event.target.checked)} />
                              <span>已确认</span>
                            </label>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state compact-empty">
                  <strong>等待识别结果</strong>
                  <p>上传并识别检验单图片后，这里会生成可确认的候选字段表。</p>
                </div>
              )}

              {missingRequiredItems.length && extraction ? (
                <p className="warning-banner">关键字段待确认：{missingRequiredItems.join('、')}</p>
              ) : null}
              <button className="control-button control-button-primary" type="button" disabled={!canAddCurrentReport} onClick={addCurrentReport}>
                加入当前病例
              </button>
            </section>

            <section className="form-section">
              <div className="section-copy">
                <strong>第三步：病例内报告</strong>
                <p>已加入 {confirmedReports.length} 份报告。可以继续追加报告，也可以直接综合分析。</p>
              </div>
              {confirmedReports.length ? (
                <div className="report-stack">
                  {confirmedReports.map((report, index) => (
                    <article className="report-card" key={`${reportKey(report)}:${index}`}>
                      <div>
                        <strong>{reportTypeLabel[report.report_type]}</strong>
                        <span>{report.source_image_name ?? '未命名报告'} · {report.items.length} 项</span>
                      </div>
                      <button className="control-button" type="button" onClick={() => removeReport(index)}>
                        移除
                      </button>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="muted-copy">还没有加入病例的报告。</p>
              )}
            </section>

            <button className="primary-button" type="submit" disabled={submitting || !canAnalyze}>
              {submitting ? '正在综合分析' : '生成综合临床建议'}
            </button>

            {error ? <p className="error-banner">{error}</p> : null}
          </form>
        </section>

        <aside className="result-panel">
          <div className="section-title">
            <div>
              <p className="eyebrow">Clinical Output</p>
              <h2>综合转诊卡与结构化结论</h2>
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
              <p>正在综合检验字段、病情和红旗规则。</p>
            </div>
          ) : (
            <div className="empty-state">
              <strong>等待病例输入</strong>
              <p>先识别并加入一份或多份检验报告，再生成综合风险分级、转诊卡和下一步处理建议。</p>
            </div>
          )}
        </aside>
      </main>
    </div>
  )
}
