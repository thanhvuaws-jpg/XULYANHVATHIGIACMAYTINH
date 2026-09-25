import React, { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Alert, Card, Empty, Icon, PageHeader, Spinner } from '../components/ui.jsx'
import { api } from '../lib/api.js'

/** Các tư thế nên chụp — đa dạng góc quan trọng hơn số lượng ảnh. */
const POSES = [
  'Nhìn thẳng', 'Quay trái nhẹ', 'Quay phải nhẹ',
  'Hơi ngẩng', 'Hơi cúi', 'Cười',
]

export default function Enroll() {
  const [params] = useSearchParams()
  const [people, setPeople] = useState(null)
  const [personId, setPersonId] = useState(params.get('person') || '')
  const [person, setPerson] = useState(null)
  const [images, setImages] = useState([])          // {file, url}
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [strict, setStrict] = useState(true)
  const [camOn, setCamOn] = useState(false)
  const videoRef = useRef(null)
  const streamRef = useRef(null)

  useEffect(() => { api.persons().then(setPeople).catch(() => setPeople([])) }, [])

  useEffect(() => {
    if (!personId) { setPerson(null); return }
    api.person(personId).then(setPerson).catch(() => setPerson(null))
  }, [personId, msg])

  // Tắt camera khi rời trang — nếu không, đèn webcam vẫn sáng và trình duyệt vẫn
  // giữ thiết bị, người dùng tưởng bị theo dõi.
  useEffect(() => () => stopCam(), [])

  const startCam = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
      streamRef.current = s
      if (videoRef.current) videoRef.current.srcObject = s
      setCamOn(true)
    } catch {
      setMsg({ tone: 'error', text: 'Không mở được camera — kiểm tra quyền truy cập của trình duyệt' })
    }
  }

  const stopCam = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setCamOn(false)
  }

  const capture = () => {
    const v = videoRef.current
    if (!v) return
    const c = document.createElement('canvas')
    c.width = v.videoWidth; c.height = v.videoHeight
    c.getContext('2d').drawImage(v, 0, 0)
    c.toBlob((blob) => {
      const file = new File([blob], `chup_${Date.now()}.jpg`, { type: 'image/jpeg' })
      setImages((prev) => [...prev, { file, url: URL.createObjectURL(file) }])
    }, 'image/jpeg', 0.95)
  }

  const addFiles = (e) => {
    const list = [...e.target.files].map((f) => ({ file: f, url: URL.createObjectURL(f) }))
    setImages((prev) => [...prev, ...list])
    e.target.value = ''
  }

  const removeAt = (i) => setImages((prev) => prev.filter((_, k) => k !== i))

  const upload = async () => {
    setBusy(true); setMsg(null)
    try {
      const r = await api.uploadImages(personId, images.map((i) => i.file), strict)
      const detail = r.rejected
        ? ` — loại ${r.rejected} ảnh: ${r.rejected_detail.map((d) => d.reason).filter(Boolean).slice(0, 3).join(', ')}`
        : ''
      setMsg({
        tone: r.accepted ? 'ok' : 'warn',
        text: `Đã nạp ${r.accepted} vector cho ${person?.full_name}${detail}`,
      })
      setImages([])
    } catch (e) {
      setMsg({ tone: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  if (people === null) return <Spinner />

  return (
    <>
      <PageHeader title="Đăng ký khuôn mặt"
                  subtitle="Chụp hoặc tải ảnh lên — hệ thống tự lọc ảnh kém chất lượng" />

      {msg && <Alert tone={msg.tone} onClose={() => setMsg(null)}>{msg.text}</Alert>}

      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="1 · Chọn người" className="lg:col-span-1">
          <select className="input" value={personId} onChange={(e) => setPersonId(e.target.value)}>
            <option value="">— Chọn người —</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code} — {p.full_name} ({p.num_vectors} vector)
              </option>
            ))}
          </select>

          {person && (
            <div className="mt-4 p-3 rounded-xl bg-ink-800 border border-line-soft text-sm space-y-1.5">
              <div className="font-bold text-slate-100">{person.full_name}</div>
              <div className="text-slate-400 text-xs">{person.code} · {person.role}</div>
              <div className="flex gap-4 pt-1.5 text-xs">
                <span className={person.num_vectors ? 'text-mint-400' : 'text-rose-400'}>
                  {person.num_vectors} vector
                </span>
                <span className="text-slate-400">{person.num_images} ảnh</span>
              </div>
            </div>
          )}

          <div className="mt-4 text-xs text-slate-400 space-y-2">
            <p className="font-semibold text-slate-300">Nên chụp các tư thế:</p>
            <div className="flex flex-wrap gap-1.5">
              {POSES.map((p) => (
                <span key={p} className="pill bg-brand-500/15 text-brand-400">{p}</span>
              ))}
            </div>
            <p className="pt-2 leading-relaxed">
              <b className="text-slate-300">20 ảnh đa dạng</b> tốt hơn 50 ảnh giống nhau.
              Ánh sáng và góc nhìn khác nhau giúp nhận diện ổn định hơn nhiều.
            </p>
          </div>

          <label className="flex items-center gap-2 mt-4 text-xs text-slate-400 cursor-pointer">
            <input type="checkbox" checked={strict} onChange={(e) => setStrict(e.target.checked)}
                   className="accent-brand-500" />
            Bật cổng chất lượng (loại ảnh mờ, thiếu sáng, quay ngang)
          </label>
        </Card>

        <Card title="2 · Chụp hoặc tải ảnh" className="lg:col-span-2">
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <div className="aspect-[4/3] rounded-xl bg-black border border-line overflow-hidden grid place-items-center">
                {camOn ? (
                  <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
                ) : (
                  <span className="text-slate-600 text-sm">Camera đang tắt</span>
                )}
              </div>
              <div className="flex gap-2 mt-3">
                {!camOn ? (
                  <button className="btn flex-1 justify-center" onClick={startCam}>Bật camera</button>
                ) : (
                  <>
                    <button className="btn btn-primary flex-1 justify-center" onClick={capture}>
                      <Icon name="plus" className="w-4 h-4" /> Chụp
                    </button>
                    <button className="btn" onClick={stopCam}>Tắt</button>
                  </>
                )}
              </div>
            </div>

            <div>
              <label className="aspect-[4/3] rounded-xl border-2 border-dashed border-line
                                grid place-items-center cursor-pointer hover:border-brand-400 transition">
                <div className="text-center text-slate-400">
                  <Icon name="upload" className="w-7 h-7 mx-auto mb-2" />
                  <div className="text-sm">Chọn ảnh từ máy</div>
                  <div className="text-xs text-slate-600 mt-0.5">có thể chọn nhiều ảnh</div>
                </div>
                <input type="file" accept="image/*" multiple className="hidden" onChange={addFiles} />
              </label>
            </div>
          </div>

          <div className="mt-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-slate-300">
                Khay ảnh: {images.length}
              </span>
              {images.length > 0 && (
                <button className="btn !py-1 !px-2.5 text-xs" onClick={() => setImages([])}>
                  Xoá hết
                </button>
              )}
            </div>

            {images.length === 0 ? (
              <Empty text="Chưa có ảnh nào" hint="Chụp bằng camera hoặc chọn từ máy" />
            ) : (
              <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-8 gap-2">
                {images.map((im, i) => (
                  <div key={i} className="relative group aspect-square">
                    <img src={im.url} className="w-full h-full object-cover rounded-lg border border-line" />
                    <button onClick={() => removeAt(i)}
                            className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-rose-400
                                       text-ink-900 grid place-items-center opacity-0
                                       group-hover:opacity-100 transition">
                      <Icon name="x" className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <button className="btn btn-primary w-full justify-center mt-4"
                    disabled={busy || !personId || !images.length} onClick={upload}>
              {busy ? 'Đang xử lý…' : `Nạp ${images.length} ảnh vào hệ thống`}
            </button>
            <p className="text-[11px] text-slate-500 mt-2 text-center">
              Không cần huấn luyện lại — ảnh được chuyển thành vector và thêm vào chỉ mục ngay.
            </p>
          </div>
        </Card>
      </div>
    </>
  )
}
