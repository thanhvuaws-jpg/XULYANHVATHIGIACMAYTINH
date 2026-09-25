import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Icon } from '../components/ui.jsx'
import { api, auth } from '../lib/api.js'

export default function Login() {
  const nav = useNavigate()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      auth.save(await api.login(username, password))
      nav('/')
    } catch (e2) {
      setErr(e2.message || 'Đăng nhập thất bại')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 text-white text-xl font-extrabold">
            <span className="w-3 h-3 rounded-full bg-brand-400" />
            FaceID Attendance
          </div>
          <p className="text-sm text-slate-400 mt-2">Hệ thống điểm danh bằng khuôn mặt</p>
        </div>

        <form onSubmit={submit} className="card p-6 space-y-4">
          <Alert onClose={() => setErr('')}>{err}</Alert>
          <div>
            <label className="label">Tài khoản</label>
            <input className="input" value={username} autoFocus
                   onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <label className="label">Mật khẩu</label>
            <input className="input" type="password" value={password}
                   onChange={(e) => setPassword(e.target.value)} />
          </div>
          <button className="btn btn-primary w-full justify-center" disabled={busy || !password}>
            {busy ? 'Đang đăng nhập…' : 'Đăng nhập'}
          </button>
          <p className="text-[11px] text-slate-500 text-center pt-1">
            Lần đầu chạy: <code className="text-slate-400">admin</code> /{' '}
            <code className="text-slate-400">admin123</code> — đổi ngay sau khi đăng nhập
          </p>
        </form>
      </div>
    </div>
  )
}
