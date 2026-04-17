import type { AnalysisResponse, AnalyzeReportInput, BackendName, InferenceStatus } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

async function readJson<T extends object>(response: Response): Promise<T> {
  const text = await response.text()
  const contentType = response.headers.get('content-type') ?? ''
  const isJson = contentType.includes('application/json') || text.trim().startsWith('{')
  const payload = (isJson && text ? JSON.parse(text) : { detail: text }) as T | { detail?: string }

  if (!response.ok) {
    const detail = 'detail' in payload ? payload.detail : ''
    throw new Error(detail || `请求失败：HTTP ${response.status}`)
  }

  return payload as T
}

export async function fetchInferenceStatus(): Promise<InferenceStatus> {
  const response = await fetch(`${API_BASE_URL}/api/inference/status`)
  return readJson<InferenceStatus>(response)
}

export async function controlInferenceModel(
  backend: BackendName,
  action: 'load' | 'stop',
): Promise<InferenceStatus> {
  const response = await fetch(`${API_BASE_URL}/api/inference/models/${backend}/${action}`, {
    method: 'POST',
  })
  return readJson<InferenceStatus>(response)
}

export async function analyzeReport(input: AnalyzeReportInput): Promise<AnalysisResponse> {
  const formData = new FormData()

  if (input.reportImage) {
    formData.append('report_image', input.reportImage)
  }
  if (input.patientAge.trim()) {
    formData.append('patient_age', input.patientAge.trim())
  }
  if (input.patientSex !== '未提供') {
    formData.append('patient_sex', input.patientSex)
  }
  if (input.symptoms.trim()) {
    formData.append('symptoms', input.symptoms.trim())
  }
  if (input.clinicalNotes.trim()) {
    formData.append('clinical_notes', input.clinicalNotes.trim())
  }
  if (input.currentMedications.trim()) {
    formData.append('current_medications', input.currentMedications.trim())
  }

  const response = await fetch(`${API_BASE_URL}/api/report/analyze`, {
    method: 'POST',
    body: formData,
  })
  return readJson<AnalysisResponse>(response)
}
