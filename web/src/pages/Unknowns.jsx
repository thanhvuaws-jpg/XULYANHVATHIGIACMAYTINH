import React, { useEffect, useState } from 'react'
import { Alert, Card, Empty, Icon, PageHeader, Spinner, Table } from '../components/ui.jsx'
import { api, fmt } from '../lib/api.js'

export default function Unknowns() {
  const [rows, setRows] = useState(null)
  const [msg, setMsg] = useState(null)

  const load = () =>
    api.unknowns().then(setRows).catch((e) => setMsg({ tone: 'error', text: e.message }))
  useEffect(() => { load() }, [])

  const spoofs = rows?.filter((r) => r.liveness_score != null && r.liveness_score < 0.4) || []

  return (
    <>
      <PageHeader
        title="Cảnh báo người lạ"
        subtitle="Những lần hệ thống từ chối điểm danh"
        actions={
          <button className="btn" onClick={load}>
            <Icon name="refresh" className="w-4 h-4" /> Làm mới
          </button>
        }
      />

      {msg && <Alert tone={msg.tone} onClose={() => setMsg(null)}>{msg.text}</Alert>}

      {spoofs.length > 0 && (
        <Alert tone="warn">
          Có <b>{spoofs.length}</b> lần nghi ngờ giả mạo (điểm sống thấp) — nhiều khả năng
          ai đó đã giơ ảnh trên điện thoại hoặc ảnh in trước camera.
        </Alert>
      )}

      <Card>
        {rows === null ? <Spinner /> : rows.length === 0 ? (
          <Empty text="Chưa có cảnh báo nào"
                 hint="Sự kiện được ghi khi hệ thống thấy người không nhận ra, hoặc nghi giả mạo" />
        ) : (
          <Table
            rows={rows}
            columns={[
              { key: 'ts', title: 'Thời điểm',
                render: (r) => <span className="text-xs">{fmt.datetime(r.ts)}</span> },
              { key: 'best_score', title: 'Điểm khớp cao nhất',
                render: (r) => (
                  <span className="tabular-nums text-xs text-slate-400">
                    {r.best_score.toFixed(3)}
                  </span>
                ) },
              { key: 'liveness_score', title: 'Điểm sống',
                render: (r) =>
                  r.liveness_score == null ? (
                    <span className="text-slate-600 text-xs">không đo</span>
                  ) : (
                    <span className={`pill ${r.liveness_score < 0.4
                      ? 'bg-rose-400/15 text-rose-400' : 'bg-mint-400/15 text-mint-400'}`}>
                      {r.liveness_score.toFixed(2)}
                      {r.liveness_score < 0.4 ? ' · nghi giả mạo' : ''}
                    </span>
                  ) },
              { key: 'device_id', title: 'Thiết bị',
                render: (r) => <span className="text-xs text-slate-500">{r.device_id || '—'}</span> },
              { key: 'snapshot_path', title: 'Ảnh chụp',
                render: (r) => (
                  <span className="text-[11px] text-slate-600 font-mono">
                    {r.snapshot_path ? r.snapshot_path.split(/[\\/]/).pop() : '—'}
                  </span>
                ) },
            ]}
          />
        )}
      </Card>

      <p className="text-xs text-slate-500 mt-3">
        Ảnh chụp được lưu trong thư mục <code className="text-slate-400">storage/snapshots/</code> trên máy chủ.
      </p>
    </>
  )
}
