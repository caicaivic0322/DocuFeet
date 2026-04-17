import { useEffect, useState } from 'react'
import { fetchInferenceStatus } from '../api'
import { StatusPill } from '../components/StatusPill'
import type { InferenceStatus, ModelRuntime } from '../types'

const statusLabel = {
  ready: '就绪',
  loading: '加载中',
  failed: '不可用',
  not_loaded: '未加载',
}

function pickModel(status: InferenceStatus | null, backend: string): ModelRuntime | null {
  return status?.models.find((model) => model.backend === backend) ?? null
}

export function ModelDashboard() {
  const [status, setStatus] = useState<InferenceStatus | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const payload = await fetchInferenceStatus()
        if (!cancelled) {
          setStatus(payload)
          setError('')
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '无法读取模型状态。')
        }
      }
    }

    load()
    const timer = window.setInterval(load, 10000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  const medgemma = pickModel(status, 'medgemma')
  const ollama = pickModel(status, 'ollama')

  return (
    <div className="app-shell models-shell">
      <header className="topbar">
        <a className="brand-lockup" href="/">
          <span className="brand-mark">赤</span>
          <span>
            <strong>赤脚医生</strong>
            <small>模型管理台</small>
          </span>
        </a>
        <nav className="topnav" aria-label="主导航">
          <a href="/">工作台</a>
          <a aria-current="page" href="/models">
            模型管理
          </a>
        </nav>
      </header>

      <main className="models-layout">
        <section className="dashboard-head">
          <div>
            <p className="eyebrow">Inference Control</p>
            <h1>本地模型状态</h1>
            <p>MedGemma 优先加载；不可用时自动切换到 Ollama，医生端不暴露模型选择。</p>
          </div>
          {error ? <p className="error-banner compact">{error}</p> : null}
        </section>

        <section className="model-card-grid">
          <ModelCard model={medgemma} role="Primary" />
          <ModelCard model={ollama} role="Fallback" />
        </section>

        <section className="ops-grid">
          <article className="ops-panel">
            <p className="eyebrow">Strategy</p>
            <h2>推理策略</h2>
            <dl className="metric-list">
              <div>
                <dt>主模型</dt>
                <dd>{status?.strategy.primary ?? 'medgemma'}</dd>
              </div>
              <div>
                <dt>备用模型</dt>
                <dd>{status?.strategy.fallback ?? 'ollama'}</dd>
              </div>
              <div>
                <dt>自动兜底</dt>
                <dd>{status?.strategy.auto_fallback ? '开启' : '关闭'}</dd>
              </div>
            </dl>
          </article>

          <article className="ops-panel">
            <p className="eyebrow">Last Analysis</p>
            <h2>最近一次分析</h2>
            {status?.last_analysis ? (
              <dl className="metric-list">
                <div>
                  <dt>使用模型</dt>
                  <dd>{status.last_analysis.backend}</dd>
                </div>
                <div>
                  <dt>风险等级</dt>
                  <dd>{status.last_analysis.risk_level}</dd>
                </div>
                <div>
                  <dt>是否兜底</dt>
                  <dd>{status.last_analysis.used_fallback ? '是' : '否'}</dd>
                </div>
              </dl>
            ) : (
              <p className="muted-copy">暂无分析记录。</p>
            )}
          </article>
        </section>
      </main>
    </div>
  )
}

type ModelCardProps = {
  model: ModelRuntime | null
  role: string
}

function ModelCard({ model, role }: ModelCardProps) {
  const currentStatus = model?.status ?? 'not_loaded'

  return (
    <article className="model-card">
      <div className="model-card-head">
        <div>
          <p className="eyebrow">{role}</p>
          <h2>{model?.name ?? '等待状态'}</h2>
        </div>
        <StatusPill label={statusLabel[currentStatus]} tone={currentStatus} />
      </div>

      <p className="model-message">{model?.message ?? '正在读取后端状态。'}</p>

      <dl className="model-meta">
        <div>
          <dt>模型</dt>
          <dd>{model?.model_id ?? '-'}</dd>
        </div>
        {model?.device ? (
          <div>
            <dt>设备</dt>
            <dd>{model.device}</dd>
          </div>
        ) : null}
        {model?.base_url ? (
          <div>
            <dt>地址</dt>
            <dd>{model.base_url}</dd>
          </div>
        ) : null}
        <div>
          <dt>更新时间</dt>
          <dd>{model?.updated_at ? new Date(model.updated_at).toLocaleString() : '-'}</dd>
        </div>
      </dl>
    </article>
  )
}
