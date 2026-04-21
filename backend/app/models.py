from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskLevel = Literal["低风险", "中风险", "高风险"]
BackendName = Literal["medgemma", "ollama"]
ReferralDecision = Literal["观察", "尽快复诊", "建议转诊", "立即转诊"]
CBCItemName = Literal["WBC", "RBC", "HGB", "PLT"]
ChemistryItemName = Literal["Cr", "BUN", "eGFR", "K", "Na", "Cl", "GLU", "ALT", "AST", "TBIL", "ALB"]
LabReportType = Literal["cbc", "chemistry_basic"]
LabItemName = Literal[
    "WBC",
    "RBC",
    "HGB",
    "PLT",
    "Cr",
    "BUN",
    "eGFR",
    "K",
    "Na",
    "Cl",
    "GLU",
    "ALT",
    "AST",
    "TBIL",
    "ALB",
]
ItemFlag = Literal["high", "low", "normal", "unknown"]


class RuleAlert(BaseModel):
    title: str
    matched_terms: list[str] = Field(default_factory=list)
    rationale: str
    recommended_action: str
    risk_level: RiskLevel


class CitationItem(BaseModel):
    source: str
    excerpt: str


class LabReportItem(BaseModel):
    name: LabItemName
    alias: str
    value: str = ""
    unit: str = ""
    reference_range: str = ""
    flag: ItemFlag = "unknown"
    confidence: float = 0.0
    confirmed: bool = True
    edited_by_user: bool = False


class StructuredLabReport(BaseModel):
    report_type: LabReportType = "cbc"
    source_image_name: Optional[str] = None
    items: list[LabReportItem] = Field(default_factory=list)


class LabExtractionResponse(BaseModel):
    report_type: LabReportType = "cbc"
    source_image_name: Optional[str] = None
    raw_text: str = ""
    items: list[LabReportItem] = Field(default_factory=list)
    missing_required_items: list[LabItemName] = Field(default_factory=list)
    can_analyze: bool = False
    notice: Optional[str] = None


class LabAnalysisInput(BaseModel):
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    symptoms: Optional[str] = None
    clinical_notes: Optional[str] = None
    current_medications: Optional[str] = None
    source_image_name: Optional[str] = None
    report_type: LabReportType = "cbc"
    items: list[LabReportItem] = Field(default_factory=list)


class MultiReportAnalysisInput(BaseModel):
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    symptoms: Optional[str] = None
    clinical_notes: Optional[str] = None
    current_medications: Optional[str] = None
    reports: list[StructuredLabReport] = Field(default_factory=list)


class ReferralCard(BaseModel):
    decision: ReferralDecision
    reasons: list[str] = Field(default_factory=list)
    suggested_checks: list[str] = Field(default_factory=list)
    handoff_notes: list[str] = Field(default_factory=list)


class InferenceMeta(BaseModel):
    backend: BackendName
    used_fallback: bool = False
    primary_backend: BackendName = "medgemma"
    fallback_reason: Optional[str] = None


class AnalysisResponse(BaseModel):
    risk_level: RiskLevel
    doctor_summary: str
    abnormal_findings: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    urgent_transfer_reasons: list[str] = Field(default_factory=list)
    medication_watchouts: list[str] = Field(default_factory=list)
    citations: list[CitationItem] = Field(default_factory=list)
    applied_rules: list[RuleAlert] = Field(default_factory=list)
    inference: Optional[InferenceMeta] = None
    structured_report: Optional[StructuredLabReport] = None
    structured_reports: list[StructuredLabReport] = Field(default_factory=list)
    referral_card: Optional[ReferralCard] = None
    disclaimer: str = (
        "本工具仅用于基层临床辅助，不提供确定诊断；高风险或病情进展时应立即转诊或人工复核。"
    )


class HealthResponse(BaseModel):
    status: str
    inference_backend: str
    ollama_base_url: str
    ollama_model: str


CBCReportItem = LabReportItem
StructuredCBCReport = StructuredLabReport
CBCExtractionResponse = LabExtractionResponse
CBCAnalysisInput = LabAnalysisInput
