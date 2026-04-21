import { useState } from 'react'
import type { AnalysisResponse, RuleAlert } from '../types'
import { StatusPill } from './StatusPill'

const riskTone = {
  低风险: '低风险',
  中风险: '中风险',
  高风险: '高风险',
} as const

const reportTypeLabel = {
  cbc: '血常规',
  chemistry_basic: '生化基础项',
} as const

type RuleReviewStatus = '待复核' | '已复核' | '不适用'

type ResultSectionsProps = {
  result: AnalysisResponse
}

export function ResultSections({ result }: ResultSectionsProps) {
  const highRiskRules = result.applied_rules.filter((rule) => rule.risk_level === '高风险')
  const hasCrossReportRules = highRiskRules.some((rule) => rule.title.startsWith('联合风险：'))

  return (
    <div className="result-stack">
      {highRiskRules.length ? (
        <section className="override-alert">
          <div className="override-alert-head">
            <div>
              <p className="eyebrow">Rule Override</p>
              <h3>{hasCrossReportRules ? '联合规则强覆盖：已按高风险优先处理' : '规则强覆盖：已按高风险优先处理'}</h3>
            </div>
            <StatusPill label="高风险覆盖" tone="高风险" />
          </div>
          <p>
            {hasCrossReportRules
              ? '本次结果触发跨报告组合安全规则，系统已优先采用规则风险等级，避免模型忽略多张检验单之间的关联风险。'
              : '本次结果触发结构化安全规则，系统已优先采用规则风险等级，避免模型将高危指标降级为普通建议。'}
          </p>
          <div className="override-rule-grid">
            {highRiskRules.map((rule) => (
              <article className="override-rule" key={rule.title}>
                <div className="override-rule-title">
                  <strong>{rule.title}</strong>
                  {rule.title.startsWith('联合风险：') ? <small>跨报告联合命中</small> : null}
                </div>
                {rule.matched_terms.length ? (
                  <span className="matched-terms">命中：{rule.matched_terms.join('、')}</span>
                ) : null}
                <span>{rule.rationale}</span>
                <small>{rule.recommended_action}</small>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {result.referral_card ? (
        <section className="referral-card">
          <div className="referral-card-head">
            <div>
              <p className="eyebrow">Referral Card</p>
              <h3>{result.referral_card.decision}</h3>
            </div>
            <StatusPill label={result.referral_card.decision} tone={result.risk_level} />
          </div>
          <ResultList title="触发原因" items={result.referral_card.reasons} emphasized />
          <ResultList title="建议补充检查" items={result.referral_card.suggested_checks} />
          <ResultList title="交接提示" items={result.referral_card.handoff_notes} />
        </section>
      ) : null}

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

      <RuleGovernancePanel rules={result.applied_rules} />

      <section className="result-section">
        <h3>本次确认字段</h3>
        {result.structured_reports.length || result.structured_report?.items.length ? (
          <div className="structured-report-stack">
            {(result.structured_reports.length
              ? result.structured_reports
              : result.structured_report
                ? [result.structured_report]
                : []
            ).map((report, reportIndex) => (
              <article className="structured-report-card" key={`${report.report_type}-${report.source_image_name}-${reportIndex}`}>
                <div className="structured-report-head">
                  <strong>{reportTypeLabel[report.report_type]}</strong>
                  <span>{report.source_image_name ?? '未命名报告'}</span>
                </div>
                <div className="structured-grid">
                  {report.items.map((item) => (
                    <article className="structured-item" key={item.name}>
                      <strong>{item.name}</strong>
                      <span>
                        {item.value || '未提供'} {item.unit}
                      </span>
                      <small>参考范围：{item.reference_range || '未提供'}</small>
                    </article>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted-copy">本次分析未附带已确认的检验字段。</p>
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

type RuleGovernancePanelProps = {
  rules: RuleAlert[]
}

function RuleGovernancePanel({ rules }: RuleGovernancePanelProps) {
  const [reviewStatusByRule, setReviewStatusByRule] = useState<Record<string, RuleReviewStatus>>({})
  const crossReportRules = rules.filter((rule) => rule.title.startsWith('联合风险：'))
  const singleRules = rules.filter((rule) => !rule.title.startsWith('联合风险：'))
  const highRiskCount = rules.filter((rule) => rule.risk_level === '高风险').length
  const reviewedCount = rules.filter((rule) => reviewStatusByRule[rule.title] === '已复核').length
  const dismissedCount = rules.filter((rule) => reviewStatusByRule[rule.title] === '不适用').length

  const updateRuleStatus = (rule: RuleAlert, status: RuleReviewStatus) => {
    setReviewStatusByRule((current) => ({
      ...current,
      [rule.title]: status,
    }))
  }

  return (
    <section className="rule-governance-panel">
      <div className="rule-governance-head">
        <div>
          <p className="eyebrow">Rule Governance</p>
          <h3>规则命中与医生复核</h3>
        </div>
        <div className="rule-metrics" aria-label="规则命中统计">
          <span>{rules.length} 条规则</span>
          <span>{highRiskCount} 条高风险</span>
          <span>{reviewedCount} 条已复核</span>
          {dismissedCount ? <span>{dismissedCount} 条不适用</span> : null}
        </div>
      </div>

      {rules.length ? (
        <>
          <RuleGroup
            title="跨报告联合规则"
            description="基于多张报告之间的指标关系触发，优先用于发现单张报告不明显的组合风险。"
            emptyText="未触发跨报告联合规则。"
            rules={crossReportRules}
            reviewStatusByRule={reviewStatusByRule}
            onUpdateRuleStatus={updateRuleStatus}
          />
          <RuleGroup
            title="单项与文本红旗规则"
            description="基于症状文本或单项检验指标触发，用于兜住明确红旗和基础安全线。"
            emptyText="未触发单项或文本红旗规则。"
            rules={singleRules}
            reviewStatusByRule={reviewStatusByRule}
            onUpdateRuleStatus={updateRuleStatus}
          />
        </>
      ) : (
        <p className="muted-copy">未触发明确红旗规则，仍需结合查体和病程变化判断。</p>
      )}
    </section>
  )
}

type RuleGroupProps = {
  title: string
  description: string
  emptyText: string
  rules: RuleAlert[]
  reviewStatusByRule: Record<string, RuleReviewStatus>
  onUpdateRuleStatus: (rule: RuleAlert, status: RuleReviewStatus) => void
}

function RuleGroup({
  title,
  description,
  emptyText,
  rules,
  reviewStatusByRule,
  onUpdateRuleStatus,
}: RuleGroupProps) {
  return (
    <div className="rule-group">
      <div className="rule-group-title">
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
      {rules.length ? (
        <div className="rule-review-list">
          {rules.map((rule) => {
            const reviewStatus = reviewStatusByRule[rule.title] ?? '待复核'
            return (
              <article className="rule-review-card" key={rule.title}>
                <div className="rule-review-main">
                  <div className="rule-review-title">
                    <strong>{rule.title}</strong>
                    <StatusPill label={rule.risk_level} tone={rule.risk_level} />
                  </div>
                  {rule.matched_terms.length ? (
                    <span className="matched-terms">命中：{rule.matched_terms.join('、')}</span>
                  ) : null}
                  <p>{rule.rationale}</p>
                  <small>{rule.recommended_action}</small>
                </div>
                <div className="rule-review-actions" aria-label={`${rule.title} 复核状态`}>
                  {(['待复核', '已复核', '不适用'] as RuleReviewStatus[]).map((status) => (
                    <button
                      className={reviewStatus === status ? 'review-chip active' : 'review-chip'}
                      key={status}
                      type="button"
                      onClick={() => onUpdateRuleStatus(rule, status)}
                    >
                      {status}
                    </button>
                  ))}
                </div>
              </article>
            )
          })}
        </div>
      ) : (
        <p className="muted-copy compact-copy">{emptyText}</p>
      )}
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
