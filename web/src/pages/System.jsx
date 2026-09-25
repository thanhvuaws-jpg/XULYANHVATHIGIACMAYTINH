import React, { useEffect, useState } from 'react'
import { Alert, Card, Icon, PageHeader, Spinner, Table } from '../components/ui.jsx'
import { api, auth, fmt } from '../lib/api.js'

export default function System() {
  const [info, setInfo] = useState(null)
  const [models, setModels] = useState([])
  const [audit, setAudit] = useState([])
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState('')

  const load = () => {
    api.info().then(setInfo).catch((e) => setMsg({ tone: 'error', text: e.message }))
    api.models().then(setModels).catch(() => {})
    if (auth.can('admin')) api.audit().then(setAudit).catch(() => {})
  }
  useEffect(() => { load() }, [])

  const run = async (name, fn, label) => {
    setBusy(name); setMsg(null)
    try {
      const r = await fn()
      setMsg({ tone: 'ok', text: `${label}: ${JSON.stringify(r)}` })
      load()
    } catch (e) {
      setMsg({ tone: 'error', text: e.message })
    } finally {
      setBusy('')
    }
  }

  if (!info) return <Spinner />

  const rows = [
    ['Bộ phát hiện', info.engine.detector],
    ['Bộ trích đặc trưng', info.engine.embedder],
    ['Nhãn mô hình', info.engine.model_tag],
    ['Số chiều vector', info.engine.embed_dim],
    ['Kích thước ảnh vào', `${info.engine.chip_size} px`],
    ['Cổng chất lượng', info.engine.quality_gate ? 'bật' : 'tắt'],
    ['Bám vết', info.engine.tracking ? 'bật' : 'tắt'],
    ['Chống giả mạo', info.settings.liveness_backend],
    ['Chỉ mục tra cứu', info.index.backend],
    ['Ngưỡng nhận diện', info.settings.match_threshold],
    ['Ngưỡng ghi điểm danh', info.settings.min_confidence],
    ['Thời gian nguội', `${info.settings.checkin_cooldown_minutes} phút`],
  ]

  return (
    <>
      <PageHeader title="Hệ thống" subtitle="Cấu hình engine và công cụ bảo trì" />

      {msg && <Alert tone={msg.tone} onClose={() => setMsg(null)}>{msg.text}</Alert>}

      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="Cấu hình engine" className="lg:col-span-2">
          <dl className="grid sm:grid-cols-2 gap-x-6">
            {rows.map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-line-soft py-2 text-sm">
                <dt className="text-slate-400">{k}</dt>
                <dd className="font-semibold text-slate-100">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card title="Chỉ mục tra cứu">
          <div className="text-center py-4">
            <div className="text-4xl font-extrabold text-brand-400">{info.index.vectors}</div>
            <div className="text-xs text-slate-400 mt-1">vector đang nạp</div>
            <div className="text-2xl font-bold text-cyan-400 mt-4">{info.index.people}</div>
            <div className="text-xs text-slate-400 mt-1">người nhận diện được</div>
          </div>
          {auth.can('operator') && (
            <div className="space-y-2 mt-2">
              <button className="btn w-full justify-center" disabled={!!busy}
                      onClick={() => run('reindex', api.reindex, 'Dựng lại chỉ mục')}>
                <Icon name="refresh" className="w-4 h-4" />
                {busy === 'reindex' ? 'Đang chạy…' : 'Dựng lại chỉ mục'}
              </button>
              {auth.can('admin') && (
                <button className="btn w-full justify-center" disabled={!!busy}
                        onClick={() => run('reembed', api.reembedAll, 'Trích đặc trưng lại')}>
                  {busy === 'reembed' ? 'Đang chạy…' : 'Trích đặc trưng lại toàn bộ'}
                </button>
              )}
            </div>
          )}
          <p className="text-[11px] text-slate-500 mt-3 leading-relaxed">
            Chỉ mục dựng lại được từ cơ sở dữ liệu nên mất nó không mất dữ liệu. Chỉ cần
            trích đặc trưng lại sau khi đổi mô hình.
          </p>
        </Card>
      </div>

      <Card title="Mô hình có sẵn" className="mt-4">
        <Table
          rows={models}
          empty="Không tìm thấy mô hình nào"
          columns={[
            { key: 'label', title: 'Tên',
              render: (r) => (
                <span className="font-semibold text-slate-100">
                  {r.label}
                  {r.current && <span className="pill bg-mint-400/15 text-mint-400 ml-2">đang dùng</span>}
                </span>
              ) },
            { key: 'backend', title: 'Loại' },
            { key: 'size_mb', title: 'Dung lượng', render: (r) => `${r.size_mb} MB` },
            { key: 'weights', title: 'Đường dẫn',
              render: (r) => <span className="text-[11px] text-slate-500 font-mono">{r.weights || '—'}</span> },
          ]}
        />
        <p className="text-xs text-slate-500 mt-3">
          Đổi mô hình bằng biến môi trường <code className="text-slate-400">FACEID_EMBED_BACKEND</code> và{' '}
          <code className="text-slate-400">FACEID_EMBED_WEIGHTS</code>, khởi động lại máy chủ, rồi
          bấm <b>Trích đặc trưng lại toàn bộ</b>.
        </p>
      </Card>

      {auth.can('admin') && audit.length > 0 && (
        <Card title="Nhật ký thao tác" className="mt-4">
          <Table
            rows={audit.slice(0, 20)}
            columns={[
              { key: 'ts', title: 'Thời điểm',
                render: (r) => <span className="text-xs">{fmt.datetime(r.ts)}</span> },
              { key: 'actor', title: 'Người thực hiện' },
              { key: 'action', title: 'Hành động',
                render: (r) => <span className="font-mono text-xs text-brand-400">{r.action}</span> },
              { key: 'entity_id', title: 'Đối tượng' },
              { key: 'meta', title: 'Chi tiết',
                render: (r) => (
                  <span className="text-[11px] text-slate-500">
                    {r.meta ? JSON.stringify(r.meta) : '—'}
                  </span>
                ) },
            ]}
          />
        </Card>
      )}
    </>
  )
}
