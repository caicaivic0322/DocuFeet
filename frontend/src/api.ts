import type {
  AnalysisResponse,
  AnalyzeCBCInput,
  AnalyzeLabsInput,
  AnalyzeReportInput,
  BackendName,
  DemoCBCSample,
  InferenceStatus,
  LabExtractionResponse,
} from './types'

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

export async function extractCBCReport(reportImage: File): Promise<LabExtractionResponse> {
  const formData = new FormData()
  formData.append('report_image', reportImage)

  const response = await fetch(`${API_BASE_URL}/api/report/extract-cbc`, {
    method: 'POST',
    body: formData,
  })
  return readJson<LabExtractionResponse>(response)
}

export async function analyzeCBCReport(input: AnalyzeCBCInput): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/api/report/analyze-cbc`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      report_type: input.reportType,
      patient_age: input.patientAge.trim() ? Number(input.patientAge.trim()) : null,
      patient_sex: input.patientSex !== '未提供' ? input.patientSex : null,
      symptoms: input.symptoms.trim() || null,
      clinical_notes: input.clinicalNotes.trim() || null,
      current_medications: input.currentMedications.trim() || null,
      source_image_name: input.sourceImageName,
      items: input.items,
    }),
  })

  return readJson<AnalysisResponse>(response)
}

export async function analyzeLabReports(input: AnalyzeLabsInput): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/api/report/analyze-labs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      patient_age: input.patientAge.trim() ? Number(input.patientAge.trim()) : null,
      patient_sex: input.patientSex !== '未提供' ? input.patientSex : null,
      symptoms: input.symptoms.trim() || null,
      clinical_notes: input.clinicalNotes.trim() || null,
      current_medications: input.currentMedications.trim() || null,
      reports: input.reports.map((report) => ({
        report_type: report.report_type,
        source_image_name: report.source_image_name,
        items: report.items,
      })),
    }),
  })

  return readJson<AnalysisResponse>(response)
}

export async function fetchDemoCBCSample(kind: 'cbc' | 'chemistry' = 'cbc'): Promise<DemoCBCSample> {
  const path = kind === 'cbc' ? '/api/demo/cbc-sample' : '/api/demo/chemistry-sample'
  const response = await fetch(`${API_BASE_URL}${path}`)
  return readJson<DemoCBCSample>(response)
}

export async function fetchDemoCBCSampleFile(imageUrl: string, imageName: string): Promise<File> {
  const response = await fetch(`${API_BASE_URL}${imageUrl}`)
  if (!response.ok) {
    throw new Error(`无法加载演示样例：HTTP ${response.status}`)
  }
  const blob = await response.blob()
  return new File([blob], imageName, { type: blob.type || 'image/png' })
}
