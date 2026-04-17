from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskLevel = Literal["低风险", "中风险", "高风险"]
BackendName = Literal["medgemma", "ollama"]


class RuleAlert(BaseModel):
    title: str
    matched_terms: list[str] = Field(default_factory=list)
    rationale: str
    recommended_action: str
    risk_level: RiskLevel


class CitationItem(BaseModel):
    source: str
    excerpt: str


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
    disclaimer: str = (
        "本工具仅用于基层临床辅助，不提供确定诊断；高风险或病情进展时应立即转诊或人工复核。"
    )


class HealthResponse(BaseModel):
    status: str
    inference_backend: str
    ollama_base_url: str
    ollama_model: str
