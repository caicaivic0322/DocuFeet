export type RiskLevel = '低风险' | '中风险' | '高风险'

export type BackendName = 'medgemma' | 'ollama'
export type ItemFlag = 'high' | 'low' | 'normal' | 'unknown'
export type ReferralDecision = '观察' | '尽快复诊' | '建议转诊' | '立即转诊'
export type LabReportType = 'cbc' | 'chemistry_basic'

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

export type LabReportItem = {
  name:
    | 'WBC'
    | 'RBC'
    | 'HGB'
    | 'PLT'
    | 'Cr'
    | 'BUN'
    | 'eGFR'
    | 'K'
    | 'Na'
    | 'Cl'
    | 'GLU'
    | 'ALT'
    | 'AST'
    | 'TBIL'
    | 'ALB'
  alias: string
  value: string
  unit: string
  reference_range: string
  flag: ItemFlag
  confidence: number
  confirmed: boolean
  edited_by_user: boolean
}

export type LabExtractionResponse = {
  report_type: LabReportType
  source_image_name: string | null
  raw_text: string
  items: LabReportItem[]
  missing_required_items: LabReportItem['name'][]
  can_analyze: boolean
  notice: string | null
}

export type StructuredLabReport = {
  report_type: LabReportType
  source_image_name: string | null
  items: LabReportItem[]
}

export type ReferralCard = {
  decision: ReferralDecision
  reasons: string[]
  suggested_checks: string[]
  handoff_notes: string[]
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
  structured_report: StructuredLabReport | null
  structured_reports: StructuredLabReport[]
  referral_card: ReferralCard | null
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

export type AnalyzeCBCInput = {
  reportType: LabReportType
  patientAge: string
  patientSex: string
  symptoms: string
  clinicalNotes: string
  currentMedications: string
  sourceImageName: string | null
  items: LabReportItem[]
}

export type AnalyzeLabsInput = {
  patientAge: string
  patientSex: string
  symptoms: string
  clinicalNotes: string
  currentMedications: string
  reports: StructuredLabReport[]
}

export type DemoCBCSample = {
  report_type: LabReportType
  patient_age: number
  patient_sex: string
  symptoms: string
  clinical_notes: string
  current_medications: string
  image_url: string
  image_name: string
}

export type CBCReportItem = LabReportItem
export type CBCExtractionResponse = LabExtractionResponse
