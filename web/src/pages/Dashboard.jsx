import React, { useEffect, useState } from 'react'
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Card, Empty, PageHeader, Spinner, Stat, StatusPill, Table } from '../components/ui.jsx'
import { api, fmt } from '../lib/api.js'

export default function Dashboard() {
  const [data, setData] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () =>
      Promise.all([api.summary(), api.trend(14), api.attendance({ limit: 8 }), api.stats()])
        .then(([summary, trend, recent, stats]) => alive && setData({ summary, trend, recent, stats }))
        .catch(() => alive && setData({ error: true }))
    load()
    // Bảng điều khiển treo trên màn hình lớn nên tự làm mới; 20 giây đủ tươi mà
    // không tạo tải đáng kể lên máy chủ.
    const t = setInterval(load, 20000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  if (!data) return <Spinner />
  if (data.error) return <Empty text="Không tải được dữ liệu" hint="Kiểm tra máy chủ đã chạy chưa" />

  const { summary: s, trend, recent, stats } = data
  const chart = trend.map((d) => ({
    ngay: d.day.slice(5),
    'Có mặt': d.present,
    'Đi muộn': d.late,
  }))

  return (
    <>
      <PageHeader title="Tổng quan"
                  subtitle={`Hôm nay ${new Date().toLocaleDateString('vi-VN')} · tự làm mới mỗi 20 giây`} />

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
        <Stat label="Đã đăng ký" value={s.enrolled} tone="brand" />
        <Stat label="Đã điểm danh" value={s.checked_in} tone="cyan" />
        <Stat label="Đúng giờ" value={s.present} tone="mint" />
        <Stat label="Đi muộn" value={s.late} tone="amber" />
        <Stat label="Tỉ lệ chuyên cần" value={fmt.pct(s.rate)} tone="rose"
              sub={`vắng ${s.absent}`} />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="Chuyên cần 14 ngày" className="lg:col-span-2">
          {chart.every((d) => !d['Có mặt'] && !d['Đi muộn']) ? (
            <Empty text="Chưa có dữ liệu điểm danh" hint="Số liệu sẽ hiện khi có người điểm danh" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={chart} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#34d399" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#fbbf24" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#fbbf24" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#232a44" vertical={false} />
                <XAxis dataKey="ngay" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} tickLine={false} allowDecimals={false} />
                <Tooltip contentStyle={{ background: '#161b2d', border: '1px solid #2b3350',
                                         borderRadius: 12, fontSize: 12 }} />
                <Area type="monotone" dataKey="Có mặt" stroke="#34d399" fill="url(#g1)" strokeWidth={2} />
                <Area type="monotone" dataKey="Đi muộn" stroke="#fbbf24" fill="url(#g2)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title="Toàn hệ thống">
          <dl className="space-y-3 text-sm">
            {[
              ['Người đang hoạt động', stats.persons_active],
              ['Vector khuôn mặt', stats.embeddings],
              ['Bản ghi điểm danh', stats.attendance],
              ['Sự kiện người lạ', stats.unknown_events],
              ['Dòng nhật ký', stats.audit_entries],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-line-soft pb-2">
                <dt className="text-slate-400">{k}</dt>
                <dd className="font-bold text-slate-100">{v}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      <Card title="Điểm danh gần nhất" className="mt-4">
        <Table
          empty="Chưa có ai điểm danh"
          rows={recent}
          columns={[
            { key: 'person_code', title: 'Mã' },
            { key: 'person_name', title: 'Họ tên' },
            { key: 'session_name', title: 'Ca' },
            { key: 'check_in', title: 'Giờ vào', render: (r) => fmt.time(r.check_in) },
            { key: 'status', title: 'Trạng thái', render: (r) => <StatusPill status={r.status} /> },
            { key: 'confidence', title: 'Tin cậy',
              render: (r) => <span className="tabular-nums">{r.confidence.toFixed(3)}</span> },
          ]}
        />
      </Card>
    </>
  )
}
