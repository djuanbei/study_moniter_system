/**
 * Client-side error capture.
 *
 * Installs handlers for:
 *   - window.onerror          → JS runtime errors
 *   - unhandledrejection      → unhandled promise rejections
 *   - api.js 5xx responses    → server failures
 *
 * Each report POSTs to /api/errors/client with an X-Request-ID header so
 * the server log entry can be correlated with the client's failure.
 */

const CSRF_COOKIE = 'sms_csrf'

function readCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return m ? decodeURIComponent(m[1]) : ''
}

function uuid() {
  if (crypto?.randomUUID) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

let pendingRequestId = null

export function currentRequestId() {
  return pendingRequestId
}

async function report(payload) {
  const request_id = pendingRequestId || uuid()
  pendingRequestId = null
  try {
    await fetch('/api/errors/client', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': readCookie(CSRF_COOKIE),
        'X-Request-ID': request_id,
      },
      body: JSON.stringify({ ...payload, request_id }),
    })
  } catch {
    /* swallow — we can't do anything useful here */
  }
}

export function reportApiFailure(detail) {
  pendingRequestId = detail?.request_id || uuid()
  return report({
    kind: 'api_failure',
    message: detail?.message || `HTTP ${detail?.status}`,
    url: detail?.url,
    detail: {
      status: detail?.status,
      body: detail?.body,
      method: detail?.method,
      path: detail?.path,
    },
  })
}

export function installClientErrorHandlers() {
  // Global JS error handler.
  window.addEventListener('error', (event) => {
    pendingRequestId = uuid()
    report({
      kind: 'js_error',
      message: event.message || 'Unknown error',
      url: event.filename,
      line: event.lineno,
      column: event.colno,
      stack: event.error?.stack || null,
    })
  })

  // Unhandled promise rejection handler.
  window.addEventListener('unhandledrejection', (event) => {
    pendingRequestId = uuid()
    const reason = event.reason
    report({
      kind: 'unhandledrejection',
      message: reason?.message || String(reason) || 'Unhandled rejection',
      stack: reason?.stack || null,
      url: window.location.href,
    })
  })
}