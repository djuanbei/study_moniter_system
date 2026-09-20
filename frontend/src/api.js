/**
 * Tiny API client with CSRF + cookie-based auth.
 *
 * Cookies (session, CSRF) are HttpOnly where required by the backend and are
 * sent automatically via `credentials: 'include'`.
 */
import { reportApiFailure } from './lib/logger.js'
const CSRF_HEADER = 'X-CSRF-Token'
const REQUEST_ID_HEADER = 'X-Request-ID'

function readCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return m ? decodeURIComponent(m[1]) : ''
}

function uuid() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

async function request(path, options = {}) {
  const opts = {
    credentials: 'include',
    headers: { Accept: 'application/json', ...(options.headers || {}) },
    ...options,
  }
  const method = (opts.method || 'GET').toUpperCase()
  const requestId = uuid()
  opts.headers = { ...opts.headers, [REQUEST_ID_HEADER]: requestId }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    opts.headers = { ...opts.headers, [CSRF_HEADER]: readCookie('sms_csrf') }
  }
  if (opts.body && !(opts.body instanceof FormData) && typeof opts.body !== 'string') {
    opts.body = JSON.stringify(opts.body)
    opts.headers['Content-Type'] = 'application/json'
  }
  const res = await fetch('/api' + path, opts)
  if (!res.ok) {
    let detail = res.statusText
    let body = null
    try {
      body = await res.json()
      detail = body.detail || detail
    } catch {}
    // Auto-report 5xx to the unified logger so the server-side log has
    // matching request_id and the operator can correlate both sides.
    if (res.status >= 500) {
      reportApiFailure({
        status: res.status,
        message: typeof detail === 'string' ? detail : JSON.stringify(detail),
        url: (opts.method || 'GET') + ' /api' + path,
        method: opts.method || 'GET',
        path,
        body,
        request_id: requestId,
      })
    }
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    err.status = res.status
    err.requestId = requestId
    throw err
  }
  if (res.status === 204) return null
  const ct = res.headers.get('content-type') || ''
  return ct.includes('application/json') ? res.json() : res.blob()
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: 'POST', body }),
  put: (p, body) => request(p, { method: 'PUT', body }),
  patch: (p, body) => request(p, { method: 'PATCH', body }),
  del: (p) => request(p, { method: 'DELETE' }),
  upload: (p, formData) => request(p, { method: 'POST', body: formData }),
}

export const endpoints = {
  bootstrap: () => api.get('/auth/bootstrap'),
  login: (username, password) => api.post('/auth/login', { username, password }),
  logout: () => api.post('/auth/logout'),
  changePassword: (current_password, new_password) =>
    api.post('/auth/change-password', { current_password, new_password }),

  dashboard: () => api.get('/dashboard'),
  studentDashboard: () => api.get('/dashboard/student'),
  parentDashboard: (studentId) => api.get(`/dashboard/parent/${studentId}`),

  students: (classId) => api.get('/students' + (classId ? `?class_id=${classId}` : '')),
  student: (id) => api.get(`/students/${id}`),
  createStudent: (data) => api.post('/students', data),
  updateStudent: (id, data) => api.patch(`/students/${id}`, data),
  deleteStudent: (id) => api.del(`/students/${id}`),
  studentAssignments: (id) => api.get(`/students/${id}/assignments`),
  studentScoreTrend: (id) => api.get(`/students/${id}/score-trend`),

  classes: () => api.get('/classes'),
  createClass: (data) => api.post('/classes', data),
  updateClass: (id, data) => api.patch(`/classes/${id}`, data),
  deleteClass: (id) => api.del(`/classes/${id}`),

  chapters: (textbook, grade) => {
    const qs = new URLSearchParams()
    if (textbook) qs.set('textbook', textbook)
    if (grade) qs.set('grade', grade)
    return api.get('/chapters' + (qs.toString() ? `?${qs}` : ''))
  },
  inferChapter: (textbook, grade, semester) => {
    const qs = new URLSearchParams()
    if (textbook) qs.set('textbook', textbook)
    if (grade) qs.set('grade', grade)
    if (semester) qs.set('semester', semester)
    return api.get('/chapters/infer' + (qs.toString() ? `?${qs}` : ''))
  },
  createChapter: (data) => api.post('/chapters', data),

  assignments: (filters = {}) => {
    const qs = new URLSearchParams()
    if (filters.student_id) qs.set('student_id', filters.student_id)
    if (filters.status) qs.set('status', filters.status)
    return api.get('/assignments' + (qs.toString() ? `?${qs}` : ''))
  },
  assignmentDetail: (id) => api.get(`/assignments/${id}/detail`),
  submitAssignment: (id, formData) => api.upload(`/assignments/${id}/submit`, formData),
  createFromMix: (data) => api.post('/assignments/from-mix', data),
  cancelAssignment: (id) => api.post(`/assignments/${id}/cancel`),

  generateQuestions: (data) => api.post('/questions/generate', data),
  persistSets: (data) => api.post('/questions/persist', data),
  listSets: () => api.get('/questions/sets'),
  getSet: (id) => api.get(`/questions/sets/${id}`),
  updateQuestion: (id, data) => api.patch(`/questions/${id}`, data),

  submissions: (filters = {}) => {
    const qs = new URLSearchParams()
    if (filters.assignment_id) qs.set('assignment_id', filters.assignment_id)
    if (filters.student_id) qs.set('student_id', filters.student_id)
    return api.get('/submissions' + (qs.toString() ? `?${qs}` : ''))
  },
  submissionResult: (id) => api.get(`/submissions/${id}/result`),
  uploadSubmission: (formData) => api.upload('/submissions', formData),

  suggestGrading: (submissionId) => api.post(`/grading/suggest?submission_id=${submissionId}`),
  confirmGrading: (data) => api.post('/grading/confirm', data),
  gradingBySubmission: (submissionId) => api.get(`/grading/by-submission/${submissionId}`),

  knowledgePoints: (chapterId) =>
    api.get('/knowledge-points' + (chapterId ? `?chapter_id=${chapterId}` : '')),
  syncKnowledgePoints: () => api.post('/knowledge-points/sync'),
  knowledgeStates: (studentId) => api.get(`/student-knowledge-state?student_id=${studentId}`),
  weakStates: (limit = 8) => api.get(`/student-knowledge-state/weak?limit=${limit}`),
  learningEvidence: (studentId, limit = 50) =>
    api.get(`/learning-evidence?student_id=${studentId}&limit=${limit}`),
  createEvidence: (data) => api.post('/learning-evidence', data),
  learningObjectives: (studentId) => api.get(`/learning-objectives?student_id=${studentId}`),
  createObjective: (data) => api.post('/learning-objectives', data),
  updateObjective: (id, data) => api.patch(`/learning-objectives/${id}`, data),
  diagnosis: (studentId) => api.get(`/diagnosis/${studentId}`),
  learningPlans: (studentId) => api.get(`/learning-plans?student_id=${studentId}`),
  generatePlan: (studentId) => api.post('/learning-plans/generate', { student_id: studentId }),
  approvePlan: (id) => api.post(`/learning-plans/${id}/approve`),
  cancelPlan: (id) => api.post(`/learning-plans/${id}/cancel`),
  assignPlanItem: (planId, itemId) =>
    api.post(`/learning-plans/${planId}/items/${itemId}/assign`),
  modifyPlanItem: (planId, itemId, data) =>
    api.patch(`/learning-plans/${planId}/items/${itemId}`, data),
  skipPlanItem: (planId, itemId) =>
    api.post(`/learning-plans/${planId}/items/${itemId}/skip`),
  adjustPlanItem: (planId, itemId, data) =>
    api.post(`/learning-plans/${planId}/items/${itemId}/adjust`, data),

  // PRD §84 — new top-level endpoints
  textbooks: () => api.get('/textbooks'),
  createTextbook: (data) => api.post('/textbooks', data),
  createTextbookVersion: (data) => api.post('/textbooks/versions', data),
  learningSessions: (studentId) =>
    api.get(`/learning-sessions?student_id=${studentId}`),
  createLearningSession: (data) => api.post('/learning-sessions', data),
  endLearningSession: (id) => api.post(`/learning-sessions/${id}/end`),
  enqueueQuestionGeneration: (payload) =>
    api.post('/question-generation/enqueue', payload),
  similarQuestions: (id, topK = 5, sameKpOnly = false) =>
    api.get(`/similar-questions/${id}?top_k=${topK}&same_kp_only=${sameKpOnly}`),
  studentProgress: (studentId) =>
    api.get(`/student-progress?student_id=${studentId}`),
  progressHistory: (progressId) =>
    api.get(`/student-progress/${progressId}/history`),
  auditLogs: (filters = {}) => {
    const qs = new URLSearchParams()
    if (filters.action) qs.set('action', filters.action)
    if (filters.user_id) qs.set('user_id', String(filters.user_id))
    if (filters.target_type) qs.set('target_type', filters.target_type)
    return api.get('/audit' + (qs.toString() ? `?${qs}` : ''))
  },
  learningReport: (studentId, days = 7) =>
    api.get(`/reports/learning/${studentId}?days=${days}`),
  paperPdfUrl: (setId, variant = 'student') =>
    `/api/exports/question-sets/${setId}/pdf?variant=${variant}`,
  paperDocxUrl: (setId, variant = 'student') =>
    `/api/exports/question-sets/${setId}/docx?variant=${variant}`,

  materials: () => api.get('/materials'),
  uploadMaterial: (formData) => api.upload('/materials', formData),
  analyzeMaterial: (id) => api.post(`/materials/${id}/analyze`),
  publishMaterial: (id) => api.post(`/materials/${id}/publish`),
  materialFileUrl: (id) => `/api/materials/${id}/file`,
  deleteMaterial: (id) => api.del(`/materials/${id}`),

  agentStatus: () => api.get('/material-agent/status'),
  agentRun: () => api.post('/material-agent/run'),
  agentCandidates: (status = 'discovered') =>
    api.get(`/material-agent/candidates?status=${status}`),
  agentApprove: (id) => api.post(`/material-agent/candidates/${id}/approve`),
  agentReject: (id) => api.post(`/material-agent/candidates/${id}/reject`),

  analyzeHistory: (data) => api.post('/historical/analyze', data),
  historyList: (studentId) => api.get(`/historical?student_id=${studentId}`),
  historyDetail: (id) => api.get(`/historical/${id}`),
  confirmHistory: (id, items) => api.post(`/historical/${id}/confirm`, { items }),
  deleteHistory: (id) => api.del(`/historical/${id}`),

  enqueueJob: (job_type, payload = {}) => api.post('/jobs', { job_type, payload }),
  getJob: (id) => api.get(`/jobs/${id}`),

  createExam: (data) => api.post('/exams', data),
  exams: (studentId) => api.get('/exams' + (studentId ? `?student_id=${studentId}` : '')),
  examDetail: (id) => api.get(`/exams/${id}`),
  startExamAttempt: (examId) => api.post(`/exam-attempts/start?exam_id=${examId}`),
  examAttempts: (studentId) => api.get(`/exam-attempts?student_id=${studentId}`),
  examAttempt: (id) => api.get(`/exam-attempts/${id}`),
  examAttemptDetail: (id) => api.get(`/exam-attempts/${id}/detail`),
  saveExamAnswers: (id, answers) => api.put(`/exam-attempts/${id}/save`, { answers }),
  submitExam: (id, reason = 'manual') => api.post(`/exam-attempts/${id}/submit`, { reason }),
  confirmExam: (id, data) => api.post(`/exam-attempts/${id}/confirm`, data),

  bankList: (filters = {}) => {
    const qs = new URLSearchParams()
    if (filters.knowledge_point) qs.set('knowledge_point', filters.knowledge_point)
    if (filters.subject) qs.set('subject', filters.subject)
    if (filters.difficulty) qs.set('difficulty', filters.difficulty)
    if (filters.q) qs.set('q', filters.q)
    return api.get('/question-bank' + (qs.toString() ? `?${qs}` : ''))
  },
  bankPublish: (data) => api.post('/question-bank', data),
  bankItem: (id) => api.get(`/question-bank/${id}`),
  bankVersions: (id) => api.get(`/question-bank/${id}/versions`),
  bankUpdate: (id, data) => api.patch(`/question-bank/${id}`, data),
  bankDeprecate: (id) => api.post(`/question-bank/${id}/deprecate`),
  bankSimilar: (id) => api.get(`/question-bank/${id}/similar`),
  bankFromSet: (data) => api.post('/question-bank/from-set', data),
  bankToAssignment: (data) => api.post('/question-bank/to-assignment', data),
  bankUpdateAnalysis: () => api.get('/question-bank/updates/analysis'),
  bankCandidates: (status = 'pending') =>
    api.get(`/question-bank/updates/candidates?status=${status}`),
  bankApproveCandidate: (id) => api.post(`/question-bank/updates/candidates/${id}/approve`),
  bankRejectCandidate: (id, note) => api.post(`/question-bank/updates/candidates/${id}/reject`, { note }),

  knowledgeUpdateAnalysis: () => api.get('/knowledge-updates/analysis'),
  knowledgeCandidates: (status = 'pending') =>
    api.get(`/knowledge-updates/candidates?status=${status}`),
  knowledgeApprove: (id) => api.post(`/knowledge-updates/candidates/${id}/approve`),
  knowledgeReject: (id, note) => api.post(`/knowledge-updates/candidates/${id}/reject`, { note }),
  learningPolicy: (studentId) => api.get(`/policy/${studentId}`),
  learningPath: (studentId) => api.get(`/learning-path/${studentId}`),
  knowledgeMap: () => api.get('/knowledge-map'),

  exportCsv: (id) => api.get(`/archive/students/${id}/csv`),
  exportPdf: (id) => api.get(`/archive/students/${id}/pdf`),
  exportImagesZip: (id) => api.get(`/archive/students/${id}/images.zip`),

  accounts: () => api.get('/accounts'),
  createAccount: (data) => api.post('/accounts', data),
  updateAccount: (id, data) => api.patch(`/accounts/${id}`, data),
  disableAccount: (id) => api.post(`/accounts/${id}/disable`),
  enableAccount: (id) => api.post(`/accounts/${id}/enable`),
  resetPassword: (id, new_password) => api.post(`/accounts/${id}/reset-password`, { new_password }),

  settings: () => api.get('/settings'),
  updateSettings: (config) => api.put('/settings', { config }),
}

/**
 * Enqueue a heavy job and poll until it finishes (PRD §82-83 pattern).
 * Returns the job row on SUCCEEDED; throws on FAILED/CANCELLED/timeout.
 */
export async function runJob(jobType, payload = {}, { intervalMs = 1500, timeoutMs = 240000 } = {}) {
  const job = await api.enqueueJob(jobType, payload)
  const deadline = Date.now() + timeoutMs
  for (;;) {
    const current = await api.getJob(job.id)
    if (current.status === 'SUCCEEDED') return current
    if (current.status === 'FAILED') throw new Error(current.error || '任务失败')
    if (current.status === 'CANCELLED') throw new Error('任务已取消')
    if (Date.now() > deadline) throw new Error('任务超时，请稍后在任务列表中查看')
    await new Promise((r) => setTimeout(r, intervalMs))
  }
}