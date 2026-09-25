import React, { useEffect, useState } from 'react'
import { Alert, Card, Icon, PageHeader, Spinner, StatusPill, Table } from '../components/ui.jsx'
import { api, fmt } from '../lib/api.js'
import { ketNoiSuKien } from '../lib/realtime.js'

export default function Attendance() {
  const [rows, setRows] = useState(null)
  const [f, setF] = useState({ day_from: fmt.today(), day_to: fmt.today(), status: '' })
  const [msg, setMsg] = useState(null)
  const [live, setLive] = useState({ ok: false, text: 'Đang kết nối…' })
  const [vuaThem, setVuaThem] = useState([])   // id các dòng vừa tới, để làm nổi bật

  const load = () =>
    api.attendance({ ...f, limit: 500 })
      .then(setRows)
      .catch((e) => setMsg({ tone: 'error', text: e.message }))

  useEffect(() => { load() }, [f])

  // Nghe sự kiện đẩy từ máy chủ. Chỉ mở MỘT kết nối cho cả vòng đời trang, và
  // dọn sạch khi rời đi — thiếu bước dọn thì mỗi lần chuyển trang lại bỏ lại một
  // kết nối chạy ngầm, đến lúc phát hiện thì đã hàng chục cái.
  useEffect(() => {
    const ngat = ketNoiSuKien({
      onStatus: setLive,
      onEvent: (e) => {
        if (e.type !== 'attendance') return
        // Tải lại từ máy chủ thay vì tự chèn dòng vào bảng: bộ lọc ngày và
        // trạng thái đang bật có thể khiến bản ghi mới KHÔNG thuộc danh sách
        // đang xem. Tự chèn sẽ hiện ra một dòng lẽ ra phải bị lọc đi.
        load()
        setVuaThem((cu) => [...cu, e.attendance_id])
        setTimeout(() => setVuaThem((cu) => cu.filter((x) => x !== e.attendance_id)), 6000)
      },
    })
    return ngat
  }, [f])

  const download = async (dang = 'xlsx') => {
    try {
      const res = await api.exportUrl(f.day_from, f.day_to, dang)
      const blob = await res.blob()
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `diemdanh_${f.day_from}_${f.day_to}.${dang}`
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (e) {
      setMsg({ tone: 'error', text: e.message })
    }
  }

  return (
    <>
      <PageHeader
        title="Điểm danh"
        subtitle="Tra cứu và xuất báo cáo"
        actions={
          <div className="flex items-center gap-3">
            {/* Trạng thái kết nối phải NHÌN THẤY được. Một bảng không tự cập nhật
                trông giống hệt một bảng không có gì mới — người dùng không thể
                phân biệt, và sẽ tin nhầm là lớp chưa ai điểm danh. */}
            <span className="flex items-center gap-1.5 text-xs text-slate-400"
                  title={live.text}>
              <span className={`w-2 h-2 rounded-full ${live.ok
                ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
              {live.text}
            </span>
            <button className="btn" onClick={() => download('csv')} disabled={!rows?.length}
                    title="Dữ liệu thô, không định dạng — dùng khi đưa sang công cụ khác">
              <Icon name="download" className="w-4 h-4" /> CSV
            </button>
            <button className="btn btn-primary" onClick={() => download('xlsx')}
                    disabled={!rows?.length}
                    title="Có định dạng, cột đã chỉnh sẵn, kèm trang Đi muộn riêng">
              <Icon name="download" className="w-4 h-4" /> Xuất Excel
            </button>
          </div>
        }
      />

      {msg && <Alert tone={msg.tone} onClose={() => setMsg(null)}>{msg.text}</Alert>}

      <Card>
        <div className="grid sm:grid-cols-4 gap-3 mb-4">
          <div>
            <label className="label">Từ ngày</label>
            <input type="date" className="input" value={f.day_from}
                   onChange={(e) => setF({ ...f, day_from: e.target.value })} />
          </div>
          <div>
            <label className="label">Đến ngày</label>
            <input type="date" className="input" value={f.day_to}
                   onChange={(e) => setF({ ...f, day_to: e.target.value })} />
          </div>
          <div>
            <label className="label">Trạng thái</label>
            <select className="input" value={f.status}
                    onChange={(e) => setF({ ...f, status: e.target.value })}>
              <option value="">Tất cả</option>
              <option value="present">Đúng giờ</option>
              <option value="late">Đi muộn</option>
            </select>
          </div>
          <div className="flex items-end">
            <button className="btn w-full justify-center" onClick={load}>
              <Icon name="refresh" className="w-4 h-4" /> Làm mới
            </button>
          </div>
        </div>

        {rows === null ? <Spinner /> : (
          <>
            <div className="text-xs text-slate-400 mb-2">{rows.length} bản ghi</div>
            <Table
              rows={rows}
              empty="Không có bản ghi nào trong khoảng thời gian này"
              columns={[
                { key: 'day', title: 'Ngày' },
                { key: 'person_code', title: 'Mã',
                  render: (r) => <span className="font-mono text-xs text-brand-400">{r.person_code}</span> },
                { key: 'person_name', title: 'Họ tên',
                  render: (r) => <span className="font-semibold text-slate-100">{r.person_name}</span> },
                { key: 'session_name', title: 'Ca' },
                { key: 'check_in', title: 'Vào', render: (r) => fmt.time(r.check_in) },
                { key: 'check_out', title: 'Ra', render: (r) => fmt.time(r.check_out) },
                { key: 'status', title: 'Trạng thái',
                  render: (r) => (
                    <div className="flex items-center gap-2">
                      <StatusPill status={r.status} />
                      {r.late_minutes > 0 && (
                        <span className="text-[11px] text-amber-400">+{r.late_minutes} phút</span>
                      )}
                    </div>
                  ) },
                { key: 'confidence', title: 'Tin cậy',
                  render: (r) => <span className="tabular-nums text-xs">{r.confidence.toFixed(3)}</span> },
                { key: 'device_id', title: 'Thiết bị',
                  render: (r) => <span className="text-xs text-slate-500">{r.device_id || '—'}</span> },
              ]}
            />
          </>
        )}
      </Card>
    </>
  )
}
