import React, { useEffect, useState } from 'react'
import { Alert, Card, Icon, Modal, PageHeader, Spinner, Table } from '../components/ui.jsx'
import { api, auth } from '../lib/api.js'

const DAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
const EMPTY = {
  name: '', start_time: '07:30', end_time: '11:30',
  late_after_min: 10, location: '', weekdays: '0,1,2,3,4',
}

const HAI_SO = (n) => String(n).padStart(2, '0')
const GIO = Array.from({ length: 24 }, (_, i) => HAI_SO(i))
const PHUT = Array.from({ length: 12 }, (_, i) => HAI_SO(i * 5))

// Chọn giờ kiểu 24 giờ bằng hai ô chọn, thay cho <input type="time">.
// Ô giờ của trình duyệt hiển thị theo ngôn ngữ máy: Chrome tiếng Anh dùng kiểu
// 12 giờ AM/PM, nên gõ "12" mà để nguyên AM thành 00:00 (nửa đêm), gõ 1 giờ chiều
// mà quên đổi PM thành 01:00. Hai ô chọn 00–23 không có chỗ cho nhầm lẫn đó.
function GioPhut({ value, onChange }) {
  const [h, m] = value.split(':')
  // Giá trị cũ không chia hết cho 5 (VD 07:47) vẫn phải hiện đúng, không bị nhảy.
  const phut = PHUT.includes(m) ? PHUT : [...PHUT, m].sort()
  return (
    <div className="flex items-center gap-1.5">
      <select className="input !px-2 tabular-nums" value={h} aria-label="Giờ"
              onChange={(e) => onChange(`${e.target.value}:${m}`)}>
        {GIO.map((g) => <option key={g} value={g}>{g} giờ</option>)}
      </select>
      <span className="text-slate-500">:</span>
      <select className="input !px-2 tabular-nums" value={m} aria-label="Phút"
              onChange={(e) => onChange(`${h}:${e.target.value}`)}>
        {phut.map((p) => <option key={p} value={p}>{p} phút</option>)}
      </select>
    </div>
  )
}

export default function Sessions() {
  const [rows, setRows] = useState(null)
  const [form, setForm] = useState(null)
  const [msg, setMsg] = useState(null)

  const load = () =>
    api.sessions().then(setRows).catch((e) => setMsg({ tone: 'error', text: e.message }))
  useEffect(() => { load() }, [])

  const toggleDay = (i) => {
    const set = new Set(form.weekdays.split(',').filter(Boolean))
    const key = String(i)
    if (set.has(key)) set.delete(key)
    else set.add(key)
    setForm({ ...form, weekdays: [...set].sort().join(',') })
  }

  // "HH:MM" so sánh chuỗi được vì luôn đủ hai chữ số.
  const gioHopLe = !form || form.end_time > form.start_time

  const save = async () => {
    try {
      await api.createSession({
        ...form,
        start_time: form.start_time + ':00',
        end_time: form.end_time + ':00',
      })
      setMsg({ tone: 'ok', text: `Đã tạo ca "${form.name}"` })
      setForm(null)
      load()
    } catch (e) {
      setMsg({ tone: 'error', text: e.message })
    }
  }

  const remove = async (s) => {
    if (!confirm(`Xoá ca "${s.name}"?`)) return
    try {
      await api.deleteSession(s.id)
      load()
    } catch (e) {
      setMsg({ tone: 'error', text: e.message })
    }
  }

  return (
    <>
      <PageHeader
        title="Ca / buổi học"
        subtitle="Khung giờ để hệ thống tính đúng giờ hay đi muộn"
        actions={auth.can('operator') && (
          <button className="btn btn-primary" onClick={() => setForm({ ...EMPTY })}>
            <Icon name="plus" className="w-4 h-4" /> Tạo ca
          </button>
        )}
      />

      {msg && <Alert tone={msg.tone} onClose={() => setMsg(null)}>{msg.text}</Alert>}

      <Card>
        {rows === null ? <Spinner /> : (
          <Table
            rows={rows}
            empty="Chưa có ca nào — không có ca thì mọi lần điểm danh đều tính là đúng giờ"
            columns={[
              { key: 'name', title: 'Tên ca',
                render: (r) => <span className="font-semibold text-slate-100">{r.name}</span> },
              { key: 'time', title: 'Khung giờ',
                render: (r) => (
                  <span className="tabular-nums text-cyan-400">
                    {r.start_time.slice(0, 5)} – {r.end_time.slice(0, 5)}
                  </span>
                ) },
              { key: 'late_after_min', title: 'Muộn sau',
                render: (r) => `${r.late_after_min} phút` },
              { key: 'weekdays', title: 'Ngày áp dụng',
                render: (r) => (
                  <div className="flex gap-1">
                    {DAYS.map((d, i) => (
                      <span key={d}
                            className={`pill w-7 justify-center ${
                              r.weekdays.split(',').includes(String(i))
                                ? 'bg-brand-500/20 text-brand-400'
                                : 'bg-ink-800 text-slate-600'}`}>
                        {d}
                      </span>
                    ))}
                  </div>
                ) },
              { key: 'location', title: 'Địa điểm' },
              { key: 'act', title: '',
                render: (r) => auth.can('admin') && (
                  <button className="btn btn-danger !px-2.5 !py-1.5 float-right"
                          onClick={() => remove(r)}>
                    <Icon name="trash" className="w-3.5 h-3.5" />
                  </button>
                ) },
            ]}
          />
        )}
      </Card>

      <Modal
        open={!!form}
        title="Tạo ca mới"
        onClose={() => setForm(null)}
        footer={
          <>
            <button className="btn" onClick={() => setForm(null)}>Huỷ</button>
            <button className="btn btn-primary" disabled={!form?.name || !gioHopLe}
                    onClick={save}>Lưu</button>
          </>
        }
      >
        {form && (
          <div className="space-y-3">
            <div>
              <label className="label">Tên ca *</label>
              <input className="input" autoFocus value={form.name}
                     placeholder="VD: Ca sáng — Xử lý ảnh"
                     onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Bắt đầu (24 giờ)</label>
                <GioPhut value={form.start_time}
                         onChange={(v) => setForm({ ...form, start_time: v })} />
              </div>
              <div>
                <label className="label">Kết thúc (24 giờ)</label>
                <GioPhut value={form.end_time}
                         onChange={(v) => setForm({ ...form, end_time: v })} />
              </div>
            </div>
            {!gioHopLe && (
              <p className="text-xs text-rose-400">
                Giờ kết thúc phải sau giờ bắt đầu — ca qua nửa đêm chưa được hỗ trợ.
              </p>
            )}
            <div>
              <label className="label">Muộn sau (phút)</label>
              <input type="number" min="0" className="input" value={form.late_after_min}
                     onChange={(e) => setForm({ ...form, late_after_min: +e.target.value })} />
            </div>
            <div>
              <label className="label">Địa điểm</label>
              <input className="input" value={form.location} placeholder="VD: Phòng A101"
                     onChange={(e) => setForm({ ...form, location: e.target.value })} />
            </div>
            <div>
              <label className="label">Ngày áp dụng trong tuần</label>
              <div className="flex gap-1.5">
                {DAYS.map((d, i) => (
                  <button key={d} type="button" onClick={() => toggleDay(i)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                            form.weekdays.split(',').includes(String(i))
                              ? 'bg-brand-500 text-white'
                              : 'bg-ink-800 text-slate-500'}`}>
                    {d}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </>
  )
}
