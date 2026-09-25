import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Card, Icon, Modal, PageHeader, Spinner, Table } from '../components/ui.jsx'
import { api, auth, fmt } from '../lib/api.js'

const EMPTY = { code: '', full_name: '', email: '', role: 'student' }

export default function Persons() {
  const nav = useNavigate()
  const [rows, setRows] = useState(null)
  const [q, setQ] = useState('')
  const [form, setForm] = useState(null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = (query = q) =>
    api.persons(query).then(setRows).catch((e) => setMsg({ tone: 'error', text: e.message }))

  useEffect(() => { load('') }, [])

  // Gõ tới đâu lọc tới đó, nhưng chờ 300 ms để không bắn request mỗi phím.
  useEffect(() => {
    const t = setTimeout(() => load(q), 300)
    return () => clearTimeout(t)
  }, [q])

  const save = async () => {
    setBusy(true)
    try {
      await api.createPerson(form)
      setMsg({ tone: 'ok', text: `Đã thêm ${form.full_name}` })
      setForm(null)
      load()
    } catch (e) {
      setMsg({ tone: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  const remove = async (p) => {
    if (!confirm(`Xoá "${p.full_name}"? Toàn bộ vector và ảnh đăng ký sẽ mất.`)) return
    try {
      await api.deletePerson(p.id)
      setMsg({ tone: 'ok', text: `Đã xoá ${p.full_name}` })
      load()
    } catch (e) {
      setMsg({ tone: 'error', text: e.message })
    }
  }

  return (
    <>
      <PageHeader
        title="Danh sách người"
        subtitle="Những người hệ thống có thể nhận diện"
        actions={
          auth.can('operator') && (
            <button className="btn btn-primary" onClick={() => setForm({ ...EMPTY })}>
              <Icon name="plus" className="w-4 h-4" /> Thêm người
            </button>
          )
        }
      />

      {msg && <Alert tone={msg.tone} onClose={() => setMsg(null)}>{msg.text}</Alert>}

      <Card>
        <div className="relative mb-4 max-w-sm">
          <Icon name="search" className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input className="input pl-9" placeholder="Tìm theo tên hoặc mã…"
                 value={q} onChange={(e) => setQ(e.target.value)} />
        </div>

        {rows === null ? <Spinner /> : (
          <Table
            rows={rows}
            empty="Chưa có ai trong hệ thống"
            columns={[
              { key: 'code', title: 'Mã',
                render: (r) => <span className="font-mono text-xs text-brand-400">{r.code}</span> },
              { key: 'full_name', title: 'Họ tên',
                render: (r) => <span className="font-semibold text-slate-100">{r.full_name}</span> },
              { key: 'role', title: 'Vai trò' },
              { key: 'num_vectors', title: 'Vector',
                render: (r) => (
                  <span className={r.num_vectors ? 'text-mint-400 font-bold' : 'text-rose-400'}>
                    {r.num_vectors || 'chưa đăng ký'}
                  </span>
                ) },
              { key: 'num_images', title: 'Ảnh' },
              { key: 'created_at', title: 'Ngày tạo',
                render: (r) => <span className="text-slate-400 text-xs">{fmt.datetime(r.created_at)}</span> },
              { key: 'act', title: '',
                render: (r) => (
                  <div className="flex gap-1.5 justify-end">
                    <button className="btn !px-2.5 !py-1.5 text-xs"
                            onClick={() => nav(`/enroll?person=${r.id}`)}>
                      <Icon name="upload" className="w-3.5 h-3.5" /> Đăng ký
                    </button>
                    {auth.can('admin') && (
                      <button className="btn btn-danger !px-2.5 !py-1.5" onClick={() => remove(r)}>
                        <Icon name="trash" className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ) },
            ]}
          />
        )}
      </Card>

      <Modal
        open={!!form}
        title="Thêm người mới"
        onClose={() => setForm(null)}
        footer={
          <>
            <button className="btn" onClick={() => setForm(null)}>Huỷ</button>
            <button className="btn btn-primary" disabled={busy || !form?.code || !form?.full_name}
                    onClick={save}>
              {busy ? 'Đang lưu…' : 'Lưu'}
            </button>
          </>
        }
      >
        {form && (
          <div className="space-y-3">
            <div>
              <label className="label">Mã sinh viên / nhân viên *</label>
              <input className="input" value={form.code} autoFocus
                     onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </div>
            <div>
              <label className="label">Họ và tên *</label>
              <input className="input" value={form.full_name}
                     onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Email</label>
                <input className="input" value={form.email}
                       onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </div>
              <div>
                <label className="label">Vai trò</label>
                <select className="input" value={form.role}
                        onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  <option value="student">Sinh viên</option>
                  <option value="teacher">Giảng viên</option>
                  <option value="staff">Nhân viên</option>
                </select>
              </div>
            </div>
            <p className="text-xs text-slate-500 pt-1">
              Sau khi lưu, vào <b>Đăng ký khuôn mặt</b> để tải ảnh lên — chưa có ảnh thì
              hệ thống chưa nhận diện được người này.
            </p>
          </div>
        )}
      </Modal>
    </>
  )
}
