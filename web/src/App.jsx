import React, { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Icon } from './components/ui.jsx'
import { api, auth } from './lib/api.js'
import Attendance from './pages/Attendance.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Enroll from './pages/Enroll.jsx'
import Login from './pages/Login.jsx'
import Persons from './pages/Persons.jsx'
import Sessions from './pages/Sessions.jsx'
import System from './pages/System.jsx'
import Unknowns from './pages/Unknowns.jsx'

const NAV = [
  { to: '/', label: 'Tổng quan', icon: 'dashboard', end: true },
  { to: '/persons', label: 'Danh sách người', icon: 'users' },
  { to: '/enroll', label: 'Đăng ký khuôn mặt', icon: 'userplus' },
  { to: '/attendance', label: 'Điểm danh', icon: 'clock' },
  { to: '/sessions', label: 'Ca / buổi học', icon: 'calendar' },
  { to: '/unknowns', label: 'Cảnh báo người lạ', icon: 'alert' },
  { to: '/system', label: 'Hệ thống', icon: 'settings' },
]

function Shell({ children }) {
  const nav = useNavigate()
  const [health, setHealth] = useState(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  const logout = () => {
    auth.clear()
    nav('/login')
  }

  return (
    <div className="min-h-screen flex">
      <aside className="w-60 shrink-0 bg-ink-800 border-r border-line flex flex-col">
        <div className="px-5 pt-6 pb-4">
          <div className="flex items-center gap-2 text-white font-extrabold">
            <span className="w-2.5 h-2.5 rounded-full bg-brand-400" />
            FaceID Attendance
          </div>
          <div className="text-[9px] tracking-[0.2em] text-brand-400 font-bold mt-1">
            ĐIỂM DANH KHUÔN MẶT
          </div>
        </div>

        <nav className="flex-1 px-2 space-y-0.5">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition ${
                  isActive
                    ? 'bg-gradient-to-r from-brand-500/25 to-rose-400/10 text-white font-semibold border-l-2 border-brand-400'
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`
              }
            >
              <Icon name={n.icon} className="w-[18px] h-[18px]" />
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-line text-[11px] text-slate-500 space-y-1">
          <div className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${health?.status === 'ok' ? 'bg-mint-400' : 'bg-rose-400'}`} />
            {health?.status === 'ok' ? 'Máy chủ hoạt động' : 'Mất kết nối máy chủ'}
          </div>
          <div>Engine: {health?.engine_loaded ? 'đã nạp' : 'chưa nạp'}</div>
          <div className="pt-2 flex items-center justify-between">
            <span className="text-slate-400">
              {auth.user?.username} · {auth.user?.role}
            </span>
            <button onClick={logout} className="text-slate-400 hover:text-rose-400" title="Đăng xuất">
              <Icon name="logout" className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 min-w-0 p-8 overflow-x-hidden">{children}</main>
    </div>
  )
}

function Protected({ children }) {
  const loc = useLocation()
  if (!auth.token) return <Navigate to="/login" state={{ from: loc.pathname }} replace />
  return <Shell>{children}</Shell>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/persons" element={<Protected><Persons /></Protected>} />
      <Route path="/enroll" element={<Protected><Enroll /></Protected>} />
      <Route path="/attendance" element={<Protected><Attendance /></Protected>} />
      <Route path="/sessions" element={<Protected><Sessions /></Protected>} />
      <Route path="/unknowns" element={<Protected><Unknowns /></Protected>} />
      <Route path="/system" element={<Protected><System /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
