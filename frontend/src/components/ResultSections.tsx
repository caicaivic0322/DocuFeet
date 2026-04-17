import type { AnalysisResponse } from '../types'
import { StatusPill } from './StatusPill'

const riskTone = {
  低风险: '低风险',
  中风险: '中风险',
  高风险: '高风险',
} as const

type ResultSectionsProps = {
  result: AnalysisResponse
}

export function ResultSections({ result }: ResultSectionsProps) {
  return (
    <div className="result-stack">
      <div className="result-lead">
        <StatusPill label={result.risk_level} tone={riskTone[result.risk_level]} />
        {result.inference?.used_fallback ? (
          <span className="fallback-note">本次由备用模型生成，建议人工复核。</span>
        ) : null}
      </div>

      <p className="doctor-summary">{result.doctor_summary}</p>

      <ResultList title="异常点" items={result.abnormal_findings} />
      <ResultList title="可能原因" items={result.possible_causes} />
      <ResultList title="下一步处理" items={result.next_steps} emphasized />
      <ResultList title="立即转诊原因" items={result.urgent_transfer_reasons} />
      <ResultList title="用药注意" items={result.medication_watchouts} />

      <section className="result-section">
        <h3>红旗提示</h3>
        {result.applied_rules.length ? (
          <div className="chip-row">
            {result.applied_rules.map((rule) => (
              <span className="rule-chip" key={rule.title}>
                {rule.title}
              </span>
            ))}
          </div>
        ) : (
          <p className="muted-copy">未触发明确红旗规则，仍需结合查体和病程变化判断。</p>
        )}
      </section>

      <section className="result-section">
        <h3>参考依据</h3>
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
          <p className="muted-copy">暂无引用片段；请以原始报告、病史和院内流程复核。</p>
        )}
      </section>

      <p className="disclaimer">{result.disclaimer}</p>
    </div>
  )
}

type ResultListProps = {
  title: string
  items: string[]
  emphasized?: boolean
}

function ResultList({ title, items, emphasized = false }: ResultListProps) {
  return (
    <section className={emphasized ? 'result-section emphasized' : 'result-section'}>
      <h3>{title}</h3>
      {items.length ? (
        <ul className="result-list">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted-copy">暂无明确条目。</p>
      )}
    </section>
  )
}
