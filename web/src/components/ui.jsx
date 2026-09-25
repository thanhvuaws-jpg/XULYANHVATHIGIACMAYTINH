/**
 * Các thành phần giao diện dùng lại.
 *
 * Gom vào một chỗ để mọi trang trông như một hệ thống thống nhất, thay vì mỗi
 * trang tự chế một kiểu bảng, một kiểu nhãn trạng thái.
 */
import React from 'react'

/* ------------------------------------------------------------------ biểu tượng */
const P = ({ d }) => <path d={d} />

export function Icon({ name, className = 'w-5 h-5' }) {
  const paths = {
    dashboard: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
    users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
    userplus: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M19 8v6M22 11h-6',
    calendar: 'M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM16 2v4M8 2v4M3 10h18',
    clock: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20M12 6v6l4 2',
    shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10zM9 12l2 2 4-4',
    settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 2.6 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 8 2.6h.1A2 2 0 1 1 12 1v.1A1.7 1.7 0 0 0 15 2.6a1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0 1.2 2.9H23a2 2 0 1 1 0 4h-.1',
    alert: 'M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01',
    upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12',
    download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
    refresh: 'M23 4v6h-6M1 20v-6h6M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15',
    trash: 'M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M10 11v6M14 11v6',
    logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
    search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3',
    plus: 'M12 5v14M5 12h14',
    check: 'M20 6 9 17l-5-5',
    x: 'M18 6 6 18M6 6l12 12',
  }
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <P d={paths[name] || paths.dashboard} />
    </svg>
  )
}

/* -------------------------------------------------------------------- bố cục */
export const Card = ({ title, extra, className = '', children }) => (
  <div className={`card p-5 ${className}`}>
    {(title || extra) && (
      <div className="flex items-center justify-between mb-4">
        {title && <h3 className="font-bold text-slate-100">{title}</h3>}
        {extra}
      </div>
    )}
    {children}
  </div>
)

export const PageHeader = ({ title, subtitle, actions }) => (
  <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
    <div>
      <h1 className="text-2xl font-extrabold text-white tracking-tight">{title}</h1>
      {subtitle && <p className="text-sm text-slate-400 mt-1">{subtitle}</p>}
    </div>
    {actions && <div className="flex gap-2">{actions}</div>}
  </div>
)

export const Stat = ({ label, value, tone = 'brand', sub }) => {
  const tones = {
    brand: 'text-brand-400', cyan: 'text-cyan-400',
    mint: 'text-mint-400', amber: 'text-amber-400', rose: 'text-rose-400',
  }
  return (
    <div className="card p-4">
      <div className={`text-3xl font-extrabold leading-none ${tones[tone]}`}>{value}</div>
      <div className="text-xs text-slate-400 mt-2">{label}</div>
      {sub && <div className="text-[11px] text-slate-500 mt-0.5">{sub}</div>}
    </div>
  )
}

/* ---------------------------------------------------------------- trạng thái */
export const StatusPill = ({ status }) => {
  const map = {
    present: ['Đúng giờ', 'bg-mint-400/15 text-mint-400'],
    late: ['Đi muộn', 'bg-amber-400/15 text-amber-400'],
    absent: ['Vắng', 'bg-rose-400/15 text-rose-400'],
  }
  const [text, cls] = map[status] || [status, 'bg-slate-500/15 text-slate-400']
  return <span className={`pill ${cls}`}>{text}</span>
}

export const Empty = ({ text = 'Chưa có dữ liệu', hint }) => (
  <div className="text-center py-12">
    <div className="text-slate-400 text-sm">{text}</div>
    {hint && <div className="text-slate-600 text-xs mt-1">{hint}</div>}
  </div>
)

export const Spinner = ({ text = 'Đang tải…' }) => (
  <div className="flex items-center justify-center gap-3 py-12 text-slate-400 text-sm">
    <span className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    {text}
  </div>
)

export const Alert = ({ tone = 'error', children, onClose }) => {
  if (!children) return null
  const tones = {
    error: 'border-rose-400/40 bg-rose-400/10 text-rose-300',
    ok: 'border-mint-400/40 bg-mint-400/10 text-mint-300',
    warn: 'border-amber-400/40 bg-amber-400/10 text-amber-300',
  }
  return (
    <div className={`border rounded-xl px-4 py-3 text-sm mb-4 flex justify-between gap-3 ${tones[tone]}`}>
      <div>{children}</div>
      {onClose && (
        <button onClick={onClose} className="opacity-60 hover:opacity-100">
          <Icon name="x" className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------------- bảng */
export function Table({ columns, rows, empty = 'Chưa có dữ liệu' }) {
  if (!rows?.length) return <Empty text={empty} />
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full border-collapse">
        <thead>
          <tr>{columns.map((c) => <th key={c.key} className="th">{c.title}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id ?? i} className="hover:bg-ink-600/40">
              {columns.map((c) => (
                <td key={c.key} className="td">
                  {c.render ? c.render(row) : (row[c.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Modal({ open, title, onClose, children, footer }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
         onClick={onClose}>
      <div className="card w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-lg text-white">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <Icon name="x" />
          </button>
        </div>
        {children}
        {footer && <div className="flex justify-end gap-2 mt-6">{footer}</div>}
      </div>
    </div>
  )
}
