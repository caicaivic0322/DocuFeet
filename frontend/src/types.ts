export type RiskLevel = '低风险' | '中风险' | '高风险'

export type BackendName = 'medgemma' | 'ollama'

export type RuleAlert = {
  title: string
  matched_terms: string[]
  rationale: string
  recommended_action: string
  risk_level: RiskLevel
}

export type CitationItem = {
  source: string
  excerpt: string
}

export type InferenceMeta = {
  backend: BackendName
  used_fallback: boolean
  primary_backend: BackendName
  fallback_reason: string | null
}

export type AnalysisResponse = {
  risk_level: RiskLevel
  doctor_summary: string
  abnormal_findings: string[]
  possible_causes: string[]
  next_steps: string[]
  urgent_transfer_reasons: string[]
  medication_watchouts: string[]
  citations: CitationItem[]
  applied_rules: RuleAlert[]
  inference: InferenceMeta | null
  disclaimer: string
}

export type ModelRuntimeStatus = 'not_loaded' | 'loading' | 'ready' | 'failed' | 'disabled'

export type ModelRuntime = {
  name: string
  backend: BackendName
  status: ModelRuntimeStatus
  active?: boolean
  model_id: string
  configured?: boolean
  device?: string
  base_url?: string
  available_models?: string[]
  message: string
  updated_at: string | null
}

export type LastAnalysis = {
  backend: BackendName
  used_fallback: boolean
  risk_level: RiskLevel
  created_at: string
}

export type InferenceStatus = {
  strategy: {
    primary: BackendName
    fallback: BackendName
    auto_fallback: boolean
  }
  models: ModelRuntime[]
  last_analysis: LastAnalysis | null
}

export type AnalyzeReportInput = {
  reportImage: File | null
  patientAge: string
  patientSex: string
  symptoms: string
  clinicalNotes: string
  currentMedications: string
}
