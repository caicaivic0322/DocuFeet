import { type ChangeEvent, type FormEvent, useEffect, useMemo, useRef, useState } from 'react'

type RiskLevel = '低风险' | '中风险' | '高风险'

type RuleAlert = {
  title: string
  matched_terms: string[]
  rationale: string
  recommended_action: string
  risk_level: RiskLevel
}

type CitationItem = {
  source: string
  excerpt: string
}

type AnalysisResponse = {
  risk_level: RiskLevel
  doctor_summary: string
  abnormal_findings: string[]
  possible_causes: string[]
  next_steps: string[]
  urgent_transfer_reasons: string[]
  medication_watchouts: string[]
  citations: CitationItem[]
  applied_rules: RuleAlert[]
  disclaimer: string
}

type OllamaStatus = {
  reachable: boolean
  base_url: string
  model: string
  has_model?: boolean
  available_models?: string[]
  message: string
}

type InferenceStatus = {
  default_backend: 'ollama' | 'medgemma'
  ollama: OllamaStatus
  medgemma: {
    model_id: string
    configured: boolean
    device: string
    message: string
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

const riskTone: Record<RiskLevel, string> = {
  低风险: 'risk-low',
  中风险: 'risk-medium',
  高风险: 'risk-high',
}

const modelDisplayName: Record<string, string> = {
  'google/medgemma-1.5-4b-it': 'MedGemma 1.5 4B IT',
}

function App() {
  const [backend, setBackend] = useState<'ollama' | 'medgemma'>('ollama')
  const backendTouched = useRef(false)
  const [patientAge, setPatientAge] = useState('')
  const [patientSex, setPatientSex] = useState('未提供')
  const [symptoms, setSymptoms] = useState('')
  const [clinicalNotes, setClinicalNotes] = useState('')
  const [currentMedications, setCurrentMedications] = useState('')
  const [reportImage, setReportImage] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [inferenceStatus, setInferenceStatus] = useState<InferenceStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [requestPhase, setRequestPhase] = useState('等待输入')

  useEffect(() => {
    let cancelled = false

    const loadStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/inference/status`)
        const payload = (await response.json()) as InferenceStatus
        if (!cancelled) {
          setInferenceStatus(payload)
          if (!backendTouched.current) {
            setBackend(payload.default_backend)
          }
        }
      } catch {
        if (!cancelled) {
          setInferenceStatus(null)
        }
      } finally {
        if (!cancelled) {
          setStatusLoading(false)
        }
      }
    }

    loadStatus()
    const timer = window.setInterval(loadStatus, 15000)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  const fileLabel = useMemo(() => {
    if (!reportImage) {
      return '上传化验单或医院打印报告照片'
    }
    return `${reportImage.name} · ${(reportImage.size / 1024 / 1024).toFixed(2)} MB`
  }, [reportImage])

  const previewUrl = useMemo(() => {
    if (!reportImage) {
      return ''
    }
    return URL.createObjectURL(reportImage)
  }, [reportImage])

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  const statusTone = useMemo(() => {
    if (statusLoading) {
      return 'status-pending'
    }
    if (!inferenceStatus) {
      return 'status-offline'
    }
    if (inferenceStatus.default_backend === 'medgemma') {
      return inferenceStatus.medgemma.configured ? 'status-ready' : 'status-warning'
    }
    if (inferenceStatus.ollama.reachable && inferenceStatus.ollama.has_model) {
      return 'status-ready'
    }
    return 'status-warning'
  }, [inferenceStatus, statusLoading])

  const statusHeadline = useMemo(() => {
    if (statusLoading) {
      return '检查推理服务中...'
    }
    if (!inferenceStatus) {
      return '无法获取推理服务状态，请检查后端是否已启动。'
    }
    if (inferenceStatus.default_backend === 'medgemma') {
      return inferenceStatus.medgemma.configured ? 'MedGemma 已接入本地后端' : 'MedGemma 尚未完成配置'
    }
    return inferenceStatus.ollama.message
  }, [inferenceStatus, statusLoading])

  const statusDetail = useMemo(() => {
    if (!inferenceStatus) {
      return '默认后端：未知'
    }
    if (inferenceStatus.default_backend === 'medgemma') {
      return `默认后端：MedGemma · ${modelDisplayName[inferenceStatus.medgemma.model_id] ?? inferenceStatus.medgemma.model_id}`
    }
    return `默认后端：Ollama · ${inferenceStatus.ollama.model}`
  }, [inferenceStatus])

  const backendMeta = useMemo(() => {
    if (!inferenceStatus) {
      return '状态未知'
    }
    if (inferenceStatus.default_backend === 'medgemma') {
      return `MedGemma / ${inferenceStatus.medgemma.device}`
    }
    return inferenceStatus.ollama.base_url
  }, [inferenceStatus])

  const statusRibbonDetails = useMemo(() => {
    if (!inferenceStatus) {
      return ['正在检查本地推理服务状态。']
    }
    const details = [inferenceStatus.medgemma.message, inferenceStatus.ollama.message]
    if (inferenceStatus.ollama.available_models?.length) {
      details.push(`Ollama 已发现模型：${inferenceStatus.ollama.available_models.join('、')}`)
    }
    return details
  }, [inferenceStatus])

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null
    setReportImage(nextFile)
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setRequestPhase('上传中...')

    try {
      const formData = new FormData()

      if (reportImage) {
        formData.append('report_image', reportImage)
      }
      if (patientAge.trim()) {
        formData.append('patient_age', patientAge.trim())
      }
      if (patientSex !== '未提供') {
        formData.append('patient_sex', patientSex)
      }
      if (symptoms.trim()) {
        formData.append('symptoms', symptoms.trim())
      }
      if (clinicalNotes.trim()) {
        formData.append('clinical_notes', clinicalNotes.trim())
      }
      if (currentMedications.trim()) {
        formData.append('current_medications', currentMedications.trim())
      }
      formData.append('backend', backend)

      const request = fetch(`${API_BASE_URL}/api/report/analyze`, {
        method: 'POST',
        body: formData,
      })
      setRequestPhase('模型推理中...')
      const response = await request

      const payload = (await response.json()) as AnalysisResponse | { detail?: string }
      if (!response.ok) {
        throw new Error('detail' in payload ? payload.detail : '分析失败，请稍后再试。')
      }

      setResult(payload as AnalysisResponse)
      setRequestPhase('分析完成')
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '请求失败，请检查后端服务。')
      setRequestPhase('分析失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">乡</div>
          <div>
            <p className="eyebrow">基层医疗 AI 助手</p>
            <p className="brand-subtitle">本地 Web · MedGemma / Ollama · 医生优先</p>
          </div>
        </div>
        <nav className="topnav">
          <a href="#workspace">工作台</a>
          <a href="#principles">安全原则</a>
          <a href="#roadmap">路线图</a>
        </nav>
      </header>

      <main>
        <section className="hero-panel">
          <div className="hero-copy">
            <p className="eyebrow">面向乡镇医院与县级医院的本地辅助系统</p>
            <h1>先帮医生看清风险，再谈模型能做什么。</h1>
            <p className="hero-description">
              赤脚医生不是替代判断的 AI 医生，而是始终站在基层接诊现场旁边的副手。
              它先整理检查单、症状与用药信息，再给出风险分级、下一步动作和转诊优先级，帮助医生更快进入判断。
            </p>
            <div className="hero-actions">
              <a className="primary-button" href="#workspace">
                看看它怎么帮忙
              </a>
              <a className="secondary-button" href="#principles">
                查看医生版边界
              </a>
            </div>
            <div className={`service-status ${statusTone}`}>
              <span className="status-dot" />
              <div>
                <strong>{statusHeadline}</strong>
                <p>{statusDetail}</p>
              </div>
            </div>
          </div>

          <div className="hero-visual">
            <div className="orb orb-left" />
            <div className="orb orb-right" />
            <div className="device-shell glass-card">
              <div className="device-topbar">
                <span />
                <span />
                <span />
              </div>
              <div className="device-screen">
                <div className="scan-beam" />
                <div className="device-grid">
                  <article className="stat-card glass-card floating-card">
                    <span>进入方式</span>
                    <strong>从一张检查单开始</strong>
                    <p>支持直接拍照上传，把基层最常见的纸质单据先带进判断流程。</p>
                  </article>
                  <article className="stat-card glass-card floating-card delay-card">
                    <span>使用价值</span>
                    <strong>先提示风险，再给动作</strong>
                    <p>在接诊现场先把高危线索和下一步处理顺序理清，减少来回翻查。</p>
                  </article>
                  <article className="stat-card glass-card accent-card floating-card">
                    <span>部署方式</span>
                    <strong>本地可控运行</strong>
                    <p>医院可在内网环境中使用，适合对数据边界和稳定性要求更高的场景。</p>
                  </article>
                </div>
                <div className="hero-meta-row">
                  <div>
                    <span className="meta-label">联调状态</span>
                    <strong>{requestPhase}</strong>
                  </div>
                  <div>
                    <span className="meta-label">默认后端</span>
                    <strong>{backendMeta}</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="status-ribbon-section">
          <div className="status-ribbon glass-card">
            <div>
              <p className="eyebrow">运行状态</p>
              <h2>本地服务正在守着这条分析链路</h2>
            </div>
            <div className="status-ribbon-copy">
              {statusRibbonDetails.map((detail) => (
                <p key={detail}>{detail}</p>
              ))}
            </div>
          </div>
        </section>

        <section className="hero-facts">
          <article className="stat-card glass-card">
            <span>门诊入口</span>
            <strong>从检查单照片切入</strong>
            <p>医生不用先整理一堆字段，先把最常见的纸质检查单带进系统就能开始看风险。</p>
          </article>
          <article className="stat-card glass-card">
            <span>核心收益</span>
            <strong>先把重点拎出来</strong>
            <p>系统会把异常点、可能原因和下一步动作排好顺序，方便基层医生快速接住病例。</p>
          </article>
          <article className="stat-card glass-card accent-card">
            <span>管理视角</span>
            <strong>适合试点推进</strong>
            <p>本地部署、风险分级和结构化输出都保留，医院管理者更容易评估落地路径。</p>
          </article>
        </section>

        <section className="workspace-section" id="workspace">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Doctor Workspace</p>
              <h2>基层接诊工作台</h2>
            </div>
            <p>
              先把最少必要信息录进去，再由规则和本地模型一起整理风险点、建议动作和转诊优先级。
            </p>
          </div>

          <div className="workspace-grid">
            <form className="workspace-card form-card" onSubmit={onSubmit}>
              <div className="card-header">
                <div>
                  <p className="eyebrow">Input</p>
                  <h3>填写最少必要信息</h3>
                </div>
                <span className="muted-pill">医生模式</span>
              </div>

              <label className="upload-dropzone">
                <input type="file" accept="image/*" onChange={onFileChange} />
                <span className="upload-title">先上传一张检查单</span>
                <span className="upload-subtitle">支持手机拍照或打印单截图，先把基层最常见的材料带进判断流程。</span>
                <span className="upload-file">{fileLabel}</span>
              </label>

              {previewUrl ? (
                <div className="upload-preview-shell">
                  <img className="upload-preview-image" src={previewUrl} alt="检查单预览" />
                </div>
              ) : null}

              <div className="field-row two-columns">
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
              </div>

              <label className="field">
                <span>推理后端</span>
                <select
                  value={backend}
                  onChange={(event) => {
                    backendTouched.current = true
                    setBackend(event.target.value as 'ollama' | 'medgemma')
                  }}
                >
                  <option value="ollama">Ollama</option>
                  <option value="medgemma">MedGemma</option>
                </select>
              </label>

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
                  placeholder="例如：既往高血压、糖尿病；今天测血压 180/100 mmHg；化验单刚出。"
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

              <button className="primary-button full-width" type="submit" disabled={submitting}>
                {submitting ? '正在整理风险...' : '生成医生版结论'}
              </button>

              <div className="helper-note">
                <strong>当前进度：</strong>
                <span>{requestPhase}</span>
              </div>

              {error ? <p className="error-banner">{error}</p> : null}
            </form>

            <section className="workspace-card result-card">
              <div className="card-header">
                <div>
                  <p className="eyebrow">Output</p>
                  <h3>面向门诊判断的结果</h3>
                </div>
                <span className="muted-pill">结构化输出</span>
              </div>

              {result ? (
                <div className="result-stack">
                  <div className={`risk-badge ${riskTone[result.risk_level]}`}>{result.risk_level}</div>
                  <p className="doctor-summary">{result.doctor_summary}</p>
                  <ResultSection title="异常点" items={result.abnormal_findings} />
                  <ResultSection title="可能原因" items={result.possible_causes} />
                  <ResultSection title="下一步行动" items={result.next_steps} />
                  <ResultSection title="立即转诊原因" items={result.urgent_transfer_reasons} />
                  <ResultSection title="用药注意" items={result.medication_watchouts} />

                  <div className="result-section">
                    <h4>优先提醒</h4>
                    {result.applied_rules.length ? (
                      <div className="chip-row">
                        {result.applied_rules.map((rule) => (
                          <span className="rule-chip" key={rule.title}>
                            {rule.title}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="placeholder-copy">当前没有触发明确的红旗提示，但仍建议结合病情继续判断。</p>
                    )}
                  </div>

                  <div className="result-section">
                    <h4>参考依据</h4>
                    {result.citations.length ? (
                      <ul className="citation-list">
                        {result.citations.map((citation) => (
                          <li key={`${citation.source}-${citation.excerpt}`}>
                            <strong>{citation.source}</strong>
                            <span>{citation.excerpt}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="placeholder-copy">
                        当前结果还没有附上引用，后续接入本地指南库后会更适合试点使用。
                      </p>
                    )}
                  </div>

                  <p className="disclaimer">{result.disclaimer}</p>
                </div>
              ) : submitting ? (
                <div className="analysis-pending">
                  <div className="pulse-line wide" />
                  <div className="pulse-line" />
                  <div className="pulse-line short" />
                  <p>正在整理检查单和病情信息，稍候就会给出给医生看的结构化结果。</p>
                </div>
              ) : (
                <div className="empty-state">
                  <p className="empty-title">等待首个门诊病例进入</p>
                  <p>
                    上传检查单照片并补充最少必要病情后，这里会输出风险等级、异常点、下一步检查与转诊提示。
                  </p>
                </div>
              )}
            </section>
          </div>
        </section>

        <section className="principles-section" id="principles">
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">Safety Commitments</p>
              <h2>产品边界与承诺</h2>
            </div>
          </div>

          <div className="principles-grid">
            <article className="principle-card">
              <h3>始终把判断权留给医生</h3>
              <p>系统只提供风险提示、可能原因和建议动作，最终诊断仍由临床医生决定。</p>
            </article>
            <article className="principle-card">
              <h3>始终先看风险等级</h3>
              <p>每次都输出低、中、高风险，让门诊现场先抓住最需要优先处理的病例。</p>
            </article>
            <article className="principle-card">
              <h3>始终给下一步动作</h3>
              <p>不只解释结果，也会告诉基层医生下一步检查、观察或转诊应该怎么做。</p>
            </article>
            <article className="principle-card">
              <h3>结论必须能被复核</h3>
              <p>优先引用异常指标、规则命中和本地指南片段，方便医生和管理者一起核对。</p>
            </article>
          </div>
        </section>

        <section className="roadmap-section" id="roadmap">
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">Roadmap</p>
              <h2>分阶段进入真实试点</h2>
            </div>
          </div>

          <div className="roadmap-grid">
            <article className="roadmap-card">
              <span>Phase 1</span>
              <h3>先把照片读进流程</h3>
              <p>先让医生用检查单照片直接发起分析，验证最基础、最贴近门诊的使用方式。</p>
            </article>
            <article className="roadmap-card">
              <span>Phase 2</span>
              <h3>再把关键字段变得可确认</h3>
              <p>加入 OCR 抽取和人工修正，让异常指标识别更稳定，也更适合连续使用。</p>
            </article>
            <article className="roadmap-card">
              <span>Phase 3</span>
              <h3>最后接入可引用的本地知识</h3>
              <p>接入转诊标准、常见病指南和药品说明书，让结果更像医院内部可长期依赖的工具。</p>
            </article>
          </div>
        </section>
      </main>
    </div>
  )
}

type ResultSectionProps = {
  title: string
  items: string[]
}

function ResultSection({ title, items }: ResultSectionProps) {
  return (
    <div className="result-section">
      <h4>{title}</h4>
      {items.length ? (
        <ul className="result-list">
          {items.map((item) => (
            <li key={`${title}-${item}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="placeholder-copy">当前未返回该项内容。</p>
      )}
    </div>
  )
}

export default App
