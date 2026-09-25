// Kênh WebSocket nhận sự kiện thời gian thực từ máy chủ.
//
// Vì sao không dùng cách gọi lại API mỗi vài giây
// -----------------------------------------------
// Cách đó tạo lưu lượng liên tục kể cả khi cả buổi không ai điểm danh, và vẫn trễ
// vài giây. Ở đây máy chủ chủ động đẩy: không có bản ghi mới thì không có gói tin
// nào, và khi có thì hiện ra gần như tức thì.
//
// Ba thứ một kết nối dài hạn bắt buộc phải xử lý, nếu không nó sẽ "chạy được lúc
// demo rồi chết âm thầm sau mười phút":
//   1. tự nối lại khi rớt, có giãn cách tăng dần để không dội bom máy chủ;
//   2. gửi nhịp giữ kết nối, vì proxy thường cắt đường truyền im lặng quá lâu;
//   3. dọn sạch khi rời trang, nếu không mỗi lần chuyển trang lại thêm một kết nối.

import { auth } from './api'

const NHIP_GIU_KET_NOI = 25000      // ms — ngắn hơn mức proxy thường cắt (60s)
const CHO_TOI_DA = 15000            // ms — trần của giãn cách nối lại

export function ketNoiSuKien({ onEvent, onStatus }) {
  let ws = null
  let timerNhip = null
  let timerNoiLai = null
  let lanThu = 0
  let dongHan = false               // người dùng rời trang -> đừng nối lại nữa

  const bao = (s) => { if (onStatus) onStatus(s) }

  function don() {
    clearInterval(timerNhip); timerNhip = null
    clearTimeout(timerNoiLai); timerNoiLai = null
    if (ws) {
      ws.onclose = null             // gỡ trước khi đóng, tránh tự gọi nối lại
      ws.onerror = null
      try { ws.close() } catch { /* đã đóng rồi */ }
      ws = null
    }
  }

  function henNoiLai() {
    if (dongHan) return
    lanThu += 1
    // Giãn cách tăng gấp đôi mỗi lần: 1s, 2s, 4s… tối đa 15s. Máy chủ vừa khởi
    // động lại thì mọi trình duyệt đang mở sẽ cùng nối vào một lúc; không giãn
    // cách thì chúng dội liên tục đúng lúc máy chủ còn đang nạp mô hình.
    const cho = Math.min(1000 * 2 ** (lanThu - 1), CHO_TOI_DA)
    bao({ ok: false, text: `Mất kết nối — thử lại sau ${Math.round(cho / 1000)}s` })
    timerNoiLai = setTimeout(moKetNoi, cho)
  }

  function moKetNoi() {
    if (dongHan) return
    const token = auth.token
    if (!token) { bao({ ok: false, text: 'Chưa đăng nhập' }); return }

    don()
    const giaoThuc = location.protocol === 'https:' ? 'wss:' : 'ws:'
    bao({ ok: false, text: 'Đang kết nối…' })

    try {
      ws = new WebSocket(`${giaoThuc}//${location.host}/api/ws`)
    } catch {
      henNoiLai(); return
    }

    ws.onopen = () => {
      // Gửi thẻ đăng nhập trong THÂN gói tin, không nhét vào URL: chuỗi truy vấn
      // bị ghi vào nhật ký máy chủ, nhật ký proxy và lịch sử trình duyệt.
      ws.send(JSON.stringify({ token }))
    }

    ws.onmessage = (e) => {
      let tin
      try { tin = JSON.parse(e.data) } catch { return }
      if (tin.type === 'ready') {
        lanThu = 0
        bao({ ok: true, text: 'Đang nhận trực tiếp' })
        timerNhip = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, NHIP_GIU_KET_NOI)
        return
      }
      if (tin.type === 'pong') return
      if (onEvent) onEvent(tin)
    }

    ws.onclose = henNoiLai
    ws.onerror = () => { /* onclose sẽ chạy ngay sau, xử lý ở đó */ }
  }

  moKetNoi()
  return () => { dongHan = true; don(); bao({ ok: false, text: 'Đã ngắt' }) }
}
