const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? 'http://localhost:8000' : '')
).replace(/\/$/, '')

export function buildApiUrl(path) {
  return `${BASE_URL}${path}`
}

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : detail?.detail || `HTTP ${status}`)
    this.status = status
    this.detail = detail
    this.name = 'ApiError'
  }
}

async function request(path, options = {}) {
  const url = buildApiUrl(path)
  const headers = { ...options.headers }

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(url, { ...options, headers })
  const contentType = res.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')

  let body
  if (isJson) {
    body = await res.json().catch(() => ({}))
  } else {
    body = await res.text().catch(() => '')
  }

  if (!res.ok) {
    const detail = isJson
      ? body || res.statusText
      : `Expected JSON API response from ${url}, received ${contentType || 'non-JSON response'}`
    throw new ApiError(res.status, detail)
  }

  if (!isJson) {
    throw new ApiError(
      res.status,
      `Expected JSON API response from ${url}, received ${contentType || 'non-JSON response'}`
    )
  }

  return body
}

export function get(path, options = {}) {
  return request(path, { method: 'GET', ...options })
}

export function post(path, body, options = {}) {
  return request(path, { 
    method: 'POST', 
    body: body instanceof FormData ? body : JSON.stringify(body),
    ...options 
  })
}

export function patch(path, body, options = {}) {
  return request(path, { 
    method: 'PATCH', 
    body: JSON.stringify(body),
    ...options 
  })
}

export default { get, post, patch }
