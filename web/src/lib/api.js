/**
 * Lớp bọc quanh API backend.
 *
 * Gom mọi lời gọi mạng vào một chỗ để: token chỉ đính vào một nơi, lỗi được xử lý
 * nhất quán, và khi hết hạn đăng nhập thì toàn ứng dụng phản ứng giống nhau thay
 * vì mỗi trang tự xoay xở một kiểu.
 */

const TOKEN_KEY = 'faceid_token'
const USER_KEY = 'faceid_user'

export const auth = {
  get token() {
    return localStorage.getItem(TOKEN_KEY)
  },
  get user() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
    } catch {
      return null
    }
  },
  save(data) {
    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify({ username: data.username, role: data.role }))
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },
  /** Phân quyền theo thứ bậc, khớp với ROLE_LEVEL bên backend. */
  can(minRole) {
    const level = { viewer: 1, operator: 2, admin: 3 }
    return (level[this.user?.role] || 0) >= (level[minRole] || 1)
  },
}

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message)
    this.status = status
    this.body = body
  }
}

async function request(path, { method = 'GET', body, form, raw = false } = {}) {
  const headers = {}
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`
  let payload
  if (form) {
    payload = form // FormData tự đặt Content-Type kèm boundary — đừng đặt tay
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const res = await fetch(`/api${path}`, { method, headers, body: payload })

  if (res.status === 401) {
    // Token hết hạn: dọn sạch rồi đưa về trang đăng nhập một lần duy nhất.
    auth.clear()
    if (!location.pathname.startsWith('/login')) location.href = '/login'
    throw new ApiError('Phiên đăng nhập đã hết hạn', 401)
  }
  if (raw) {
    if (!res.ok) throw new ApiError('Lỗi tải tệp', res.status)
    return res
  }

  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.detail
    throw new ApiError(
      typeof detail === 'string' ? detail : `Lỗi ${res.status}`,
      res.status,
      data
    )
  }
  return data
}

export const api = {
  // --- xác thực ---
  login: (username, password) => request('/auth/login', { method: 'POST', body: { username, password } }),
  me: () => request('/auth/me'),

  // --- người ---
  persons: (q = '') => request(`/persons${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  person: (id) => request(`/persons/${id}`),
  createPerson: (body) => request('/persons', { method: 'POST', body }),
  updatePerson: (id, body) => request(`/persons/${id}`, { method: 'PATCH', body }),
  deletePerson: (id) => request(`/persons/${id}`, { method: 'DELETE' }),
  personImages: (id) => request(`/persons/${id}/images`),
  reembed: (id) => request(`/persons/${id}/reembed`, { method: 'POST' }),
  uploadImages: (id, files, strict = true) => {
    const fd = new FormData()
    for (const f of files) fd.append('files', f)
    return request(`/persons/${id}/images?strict=${strict}`, { method: 'POST', form: fd })
  },

  // --- nhận diện ---
  recognize: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request('/recognize', { method: 'POST', form: fd })
  },
  checkin: (file, deviceId = 'web', sessionId = null) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('device_id', deviceId)
    if (sessionId) fd.append('session_id', String(sessionId))
    return request('/checkin', { method: 'POST', form: fd })
  },

  // --- điểm danh ---
  attendance: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/attendance${qs ? `?${qs}` : ''}`)
  },
  summary: (day) => request(`/attendance/summary${day ? `?day=${day}` : ''}`),
  trend: (days = 14) => request(`/attendance/trend?days=${days}`),
  unknowns: () => request('/attendance/unknowns'),
  // `dang` = 'xlsx' (mặc định, có định dạng) hoặc 'csv' (thô, cho công cụ khác).
  exportUrl: (from, to, dang = 'xlsx') => {
    const qs = new URLSearchParams()
    if (from) qs.set('day_from', from)
    if (to) qs.set('day_to', to)
    const duong = dang === 'csv' ? '/attendance/export' : '/attendance/export.xlsx'
    return request(`${duong}?${qs}`, { raw: true })
  },

  // --- ca ---
  sessions: () => request('/sessions'),
  createSession: (body) => request('/sessions', { method: 'POST', body }),
  deleteSession: (id) => request(`/sessions/${id}`, { method: 'DELETE' }),

  // --- hệ thống ---
  health: () => request('/system/health'),
  info: () => request('/system/info'),
  stats: () => request('/system/stats'),
  models: () => request('/system/models'),
  reindex: () => request('/system/reindex', { method: 'POST' }),
  reembedAll: () => request('/system/reembed-all', { method: 'POST' }),
  audit: () => request('/system/audit'),
}

export const fmt = {
  time: (s) => (s ? new Date(s).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) : '—'),
  datetime: (s) => (s ? new Date(s).toLocaleString('vi-VN') : '—'),
  pct: (v) => `${Math.round((v || 0) * 100)}%`,
  today: () => new Date().toISOString().slice(0, 10),
}
