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
  learningReport: (studentId, days = 7) =>
    api.get(`/reports/learning/${studentId}?days=${days}`),
  paperPdfUrl: (setId, variant = 'student') =>
    `/api/exports/question-sets/${setId}/pdf?variant=${variant}`,

  materials: () => api.get('/materials'),
  uploadMaterial: (formData) => api.upload('/materials', formData),
  analyzeMaterial: (id) => api.post(`/materials/${id}/analyze`),
  publishMaterial: (id) => api.post(`/materials/${id}/publish`),
  materialFileUrl: (id) => `/api/materials/${id}/file`,
  deleteMaterial: (id) => api.del(`/materials/${id}`),

  analyzeHistory: (data) => api.post('/historical/analyze', data),
  historyList: (studentId) => api.get(`/historical?student_id=${studentId}`),
  historyDetail: (id) => api.get(`/historical/${id}`),
  confirmHistory: (id, items) => api.post(`/historical/${id}/confirm`, { items }),
  deleteHistory: (id) => api.del(`/historical/${id}`),

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