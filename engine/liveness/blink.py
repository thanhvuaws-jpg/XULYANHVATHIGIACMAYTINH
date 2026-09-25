"""Chống giả mạo chủ động — thử thách chớp mắt.

Vì sao cần lớp phòng thủ này bên cạnh phương pháp thụ động
----------------------------------------------------------
Phương pháp thụ động (`texture.py`) đọc dấu vết vật lý mà ảnh in và màn hình để
lại. Nó nhanh và không làm phiền người dùng, nhưng về bản chất là một cuộc chạy
đua: bản in càng tốt, màn hình càng nét thì dấu vết càng mờ.

Chớp mắt thì khác. Một tấm ảnh in **không thể** chớp mắt — đó không phải chuyện
chất lượng in mà là chuyện vật lý. Nên đây là lớp phòng thủ có đáy, chứ không phải
cuộc chạy đua.

(Video phát lại vẫn có thể chớp mắt. Muốn chặn cả video thì phải dùng thử thách
ngẫu nhiên: "quay đầu sang trái" — kẻ tấn công không đoán trước được yêu cầu nào
sẽ xuất hiện. `challenge_pose` bên dưới làm việc đó.)

Cách đo
-------
EAR (Eye Aspect Ratio) — tỉ lệ giữa chiều cao và chiều rộng của mắt, tính từ 6
điểm mốc:

    EAR = (‖p2−p6‖ + ‖p3−p5‖) / (2·‖p1−p4‖)

Mắt mở cho EAR khoảng 0,25–0,35; lúc chớp tụt xuống dưới 0,15 trong 2–5 khung
hình rồi bật lại. Máy trạng thái bên dưới bắt đúng chuỗi **mở → nhắm → mở**, chứ
không chỉ bắt "đang nhắm" — vì một tấm ảnh chụp người đang nhắm mắt cũng cho EAR
thấp mãi mãi.
"""
from __future__ import annotations

import time
import urllib.request
from collections import deque
from pathlib import Path

import cv2
import numpy as np

from ..settings import ROOT
from ..types import Detection
from .base import LivenessDetector

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_landmarker/"
             "face_landmarker/float16/1/face_landmarker.task")
MODEL_NAME = "face_landmarker.task"

# Chỉ số điểm mốc mắt trong lưới 478 điểm của MediaPipe FaceMesh.
LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

#: Ngưỡng chớp mắt là TƯƠNG ĐỐI so với mắt mở của chính người đó, không phải số
#: tuyệt đối.
#:
#: Vì sao không dùng ngưỡng cố định
#: --------------------------------
#: Bản đầu dùng EAR_CLOSED = 0,16 và EAR_OPEN = 0,22 — các giá trị quen thuộc lấy
#: từ tài liệu, đo trên ảnh độ phân giải cao. Trên webcam 640×480 chúng sai hoàn
#: toàn. Đo lại trên cùng một bộ ảnh, chỉ thay đổi cỡ mặt, với mắt **luôn mở**:
#:
#:      60 px  ->  EAR 0,2044
#:      80 px  ->  EAR 0,1124     <- thấp hơn cả ngưỡng "đang nhắm"
#:     100 px  ->  EAR 0,1371
#:     220 px  ->  EAR 0,2123     <- vẫn chưa chạm ngưỡng "đã mở"
#:
#: Sai số định vị điểm mốc lấn át tín hiệu thật khi mắt chỉ còn vài chục điểm
#: ảnh, nên EAR **không bất biến theo tỉ lệ** như công thức gợi ý. Hậu quả quan
#: sát được: đứng xa thì mắt bị coi là nhắm vĩnh viễn, máy trạng thái không bao
#: giờ thấy chuỗi mở → nhắm → mở, không đếm được cái chớp nào, và người thật bị
#: kết tội giả mạo. Lại gần thì đột nhiên chạy được.
#:
#: Cách sửa: mỗi khuôn mặt tự dựng đường nền EAR lúc mắt mở, rồi coi là chớp khi
#: EAR tụt xuống dưới một TỈ LỆ của đường nền ấy và bật trở lại. Cách này bất
#: biến với cả cỡ mặt lẫn hình dạng mắt từng người.
TI_LE_NHAM = 0.72        # tụt dưới 72% đường nền -> đang nhắm
TI_LE_MO = 0.85          # bật lại trên 85% đường nền -> đã mở
EAR_SAN_TOI_THIEU = 0.06  # dưới mức này coi như đo hỏng, không phải mắt nhắm

#: Slot không thấy mặt quá lâu thì xoá hẳn, kèm lịch sử chớp mắt. Xem ghi chú ở
#: `_don_slot_cu` — đây là chốt chặn ngăn ảnh giơ vào đúng chỗ mặt vừa rời đi
#: thừa hưởng bằng chứng sống của người thật.
SLOT_TIMEOUT = 0.6

#: Mặt nhỏ hơn mức này thì không đo nổi chớp mắt. Trả về -1.0 nghĩa là "KHÔNG ĐO
#: ĐƯỢC", khác hẳn 0.0 nghĩa là "đo được và kết luận là giả". Nhập nhèm hai thứ
#: này chính là cái làm người đứng xa bị báo giả mạo.
CO_MAT_TOI_THIEU = 90

#: Cho một khuôn mặt MỚI bao nhiêu giây để chớp mắt, trước khi kết luận là giả.
#:
#: Thiếu khoảng chờ này thì mọi khuôn mặt vừa bước vào khung hình đều bị gắn ngay
#: nhãn GIẢ MẠO, vì lúc đó chưa quan sát được cái chớp nào. Đó là kết tội trước
#: khi xét: hệ thống chưa có bằng chứng gì mà đã phán quyết.
#:
#: Trong khoảng chờ, điểm trả về là -1.0 ("đang kiểm tra") chứ không phải 0.0
#: ("đã xét, là giả"). Trạng thái chờ vẫn CHẶN việc ghi điểm danh, nên nó an toàn:
#: kẻ giơ ảnh cũng chỉ nhận được "đang kiểm tra" rồi chuyển sang "giả mạo" khi hết
#: giờ, chứ không lọt qua được.
#:
#: 12 giây chọn theo nhịp chớp mắt của người đang nhìn chăm chú vào màn hình:
#: khoảng 4–6 lần mỗi phút, tức cách nhau 10–15 giây.
CHO_CHOP_MAT = 12.0

#: Ngưỡng "mắt đứng im" — hệ số biến thiên của EAR (độ lệch chuẩn chia trung bình)
#: trong cửa sổ gần nhất.
#:
#: Vì sao cần thêm tín hiệu này
#: ----------------------------
#: Chỉ chờ chớp mắt thì phải chờ hết 12 giây mới dám kết luận, vì không thể phân
#: biệt "ảnh tĩnh" với "người thật chưa kịp chớp". Người dùng phản ánh đúng: chờ
#: như vậy quá lâu để dùng ở kiosk có người xếp hàng.
#:
#: Nhưng có một dấu hiệu thứ hai, và nó phân biệt được ngay: **mắt người sống
#: không bao giờ đứng yên**. Kể cả giữa hai nhịp chớp, EAR vẫn dao động vì rung
#: mắt, đảo mắt, nheo nhẹ theo ánh sáng. Một tấm ảnh thì EAR gần như là hằng số —
#: chỉ nhiễu do sai số định vị điểm mốc.
#:
#: Nhờ vậy ảnh tĩnh bị kết luận sau khoảng hai giây thay vì mười hai, còn người
#: thật vẫn được chờ đủ kiên nhẫn. Hai tín hiệu bổ sung cho nhau chứ không thay
#: thế nhau: dao động cho biết "có sự sống", chớp mắt cho biết "chắc chắn sống".
#: Đo được:
#:     ảnh tĩnh (cùng một tệp lặp lại)      hệ số biến thiên 0,00000
#:     mô phỏng người thật (thêm nhiễu nhẹ) hệ số biến thiên 0,03894
#:
#: Đặt ngưỡng 0,020 chứ không phải sát mức 0,035, vì hai loại sai không ngang giá
#: nhau. Ngưỡng cao thì bắt ảnh tĩnh nhanh hơn nhưng **kết tội oan người thật**
#: đang ngồi rất yên — sai lầm nặng hơn hẳn việc bắt chậm vài giây, vì người bị
#: từ chối không hiểu tại sao và không biết phải làm gì.
#:
#: CẢNH BÁO về chính con số này: phép đo trên dùng cùng một TỆP ảnh lặp lại, nên
#: hệ số biến thiên bằng đúng 0. Ảnh điện thoại chụp QUA CAMERA thì vẫn có nhiễu
#: cảm biến, nên số thật sẽ lớn hơn 0 — chưa đo được là bao nhiêu. Nếu thực tế
#: ảnh điện thoại vẫn phải chờ hết 12 giây thì ngưỡng này còn thấp quá và cần đo
#: lại bằng dữ liệu thật.
NGUONG_MAT_DUNG_IM = 0.020
SO_KHUNG_XET_DUNG_IM = 45      # ~1,5 giây ở 30 fps

#: Thời gian chờ tối thiểu khi mắt gần như đứng im hoàn toàn.
CHO_TOI_THIEU = 3.0

#: Mức dao động được coi là "chắc chắn có sự sống" — từ đây trở lên thì chờ đủ.
DAO_DONG_RO_RANG = 0.060

#: Một lần chớp mắt được tin trong bao lâu (giây). Quá hạn thì điểm tụt dần về 0
#: trong khoảng thời gian tương đương, nên người dùng bị từ chối sau xấp xỉ
#: 1,45 × giá trị này nếu hoàn toàn không chớp mắt.
#:
#: Vì sao 15 chứ không phải 6 như ban đầu
#: --------------------------------------
#: Người nhìn chăm chú vào màn hình chớp mắt **chậm hơn hẳn** lúc bình thường —
#: từ khoảng 15 lần mỗi phút xuống còn 4–6 lần, tức cách nhau 10–15 giây. Cửa sổ
#: 6 giây khiến người thật liên tục bị gắn nhãn giả mạo giữa hai nhịp chớp, đúng
#: hiện tượng quan sát được khi chạy thử: lúc nhận ra, lúc báo giả mạo.
#:
#: Nới cửa sổ KHÔNG làm yếu khả năng chống giả mạo, và đây là điểm mấu chốt: ảnh
#: tĩnh cho điểm 0,0 **bất kể cửa sổ dài bao nhiêu**, vì nó không bao giờ chớp
#: mắt. Cửa sổ chỉ quyết định một bằng chứng sống được tin trong bao lâu, chứ
#: không quyết định việc phát hiện ra nó.
#:
#: Cái giá thật sự của cửa sổ dài: kẻ tấn công có thể chớp mắt rồi thay ảnh vào
#: trong khoảng thời gian đó. Đòn này đòi hỏi tráo vật lý ngay trước camera trong
#: vài giây, khó hơn hẳn việc chỉ giơ một tấm ảnh lên.
BLINK_VALID_SEC = 15.0


def ensure_model(models_dir: Path | None = None) -> Path:
    models_dir = Path(models_dir) if models_dir else ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    path = models_dir / MODEL_NAME
    if not path.exists():
        urllib.request.urlretrieve(MODEL_URL, path)
    return path


def eye_aspect_ratio(pts: np.ndarray, idx: list[int]) -> float:
    p1, p2, p3, p4, p5, p6 = (pts[i] for i in idx)
    horiz = np.linalg.norm(p1 - p4) + 1e-6
    return float((np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2.0 * horiz))


class _FaceState:
    """Trạng thái chớp mắt của một khuôn mặt đang theo dõi."""

    def __init__(self):
        self.ear = deque(maxlen=90)   # ~3 giây ở 30 fps, đủ dựng đường nền
        self.closed = False           # đang trong pha nhắm
        self.last_blink = 0.0         # thời điểm chớp gần nhất
        self.blinks = 0
        self.first_seen = time.time()  # để biết đã cho đủ thời gian chớp chưa

    @property
    def duong_nen(self) -> float:
        """EAR lúc mắt MỞ của riêng khuôn mặt này.

        Lấy phân vị 80 thay vì giá trị lớn nhất: giá trị lớn nhất dễ bị một khung
        nhiễu đơn lẻ kéo lên cao, khiến ngưỡng chớp bị đặt quá xa và không bao giờ
        chạm tới.
        """
        if len(self.ear) < 12:
            return 0.0                # chưa đủ mẫu để tin
        return float(np.percentile(np.array(self.ear, dtype=np.float32), 80))

    def update(self, ear: float) -> None:
        self.ear.append(ear)
        nen = self.duong_nen
        if nen < EAR_SAN_TOI_THIEU:
            return                    # chưa đủ mẫu, hoặc phép đo hỏng

        # Máy trạng thái: chỉ tính là một cái chớp khi đi đủ mở → nhắm → mở, và
        # ngưỡng tính theo TỈ LỆ của đường nền riêng người này.
        if not self.closed and ear < nen * TI_LE_NHAM:
            self.closed = True
        elif self.closed and ear > nen * TI_LE_MO:
            self.closed = False
            self.blinks += 1
            self.last_blink = time.time()

    def mat_dung_im(self) -> bool:
        """EAR gần như không đổi trong cửa sổ gần nhất -> nhiều khả năng là ảnh tĩnh.

        Dùng hệ số biến thiên (độ lệch chuẩn / trung bình) chứ không dùng độ lệch
        chuẩn thô: EAR của mỗi người mỗi cỡ mặt có giá trị nền khác nhau, nên một
        ngưỡng tuyệt đối sẽ lại mắc đúng lỗi tỉ lệ đã gặp ở phần ngưỡng chớp mắt.
        """
        if len(self.ear) < SO_KHUNG_XET_DUNG_IM:
            return False               # chưa đủ mẫu, chưa kết luận gì
        gan_day = np.array(list(self.ear)[-SO_KHUNG_XET_DUNG_IM:], dtype=np.float32)
        tb = float(gan_day.mean())
        if tb < EAR_SAN_TOI_THIEU:
            return False               # phép đo hỏng, không phải mắt đứng im
        return float(gan_day.std()) / tb < NGUONG_MAT_DUNG_IM

    def thoi_gian_cho(self) -> float:
        """Chờ bao lâu trước khi kết luận là giả, tuỳ mức dao động quan sát được."""
        if len(self.ear) < SO_KHUNG_XET_DUNG_IM:
            return CHO_CHOP_MAT          # chưa đủ mẫu thì cứ kiên nhẫn tối đa
        gan_day = np.array(list(self.ear)[-SO_KHUNG_XET_DUNG_IM:], dtype=np.float32)
        tb = float(gan_day.mean())
        if tb < EAR_SAN_TOI_THIEU:
            return CHO_CHOP_MAT          # phép đo hỏng, đừng vội kết luận
        cv = float(gan_day.std()) / tb
        # Nội suy tuyến tính giữa hai mốc, kẹp trong [CHO_TOI_THIEU, CHO_CHOP_MAT].
        ti_le = min(max(cv / DAO_DONG_RO_RANG, 0.0), 1.0)
        return CHO_TOI_THIEU + (CHO_CHOP_MAT - CHO_TOI_THIEU) * ti_le

    def score(self) -> float:
        """1.0 nếu vừa chớp mắt; -1.0 khi chưa đủ dữ liệu; giảm dần khi quá hạn."""
        if self.blinks == 0:
            # Thời gian chờ CO GIÃN theo mức dao động của mắt, thay vì một ngưỡng
            # cứng "dưới thì kết luận ngay, trên thì chờ đủ 12 giây".
            #
            # Vì sao đổi: ngưỡng cứng buộc phải đoán đúng một con số, mà con số ấy
            # phụ thuộc nhiễu cảm biến của từng camera. Đoán thấp thì ảnh điện
            # thoại vẫn phải chờ hết 12 giây (đúng hiện tượng người dùng gặp);
            # đoán cao thì kết tội oan người ngồi yên. Cách co giãn hỏng nhẹ nhàng
            # ở cả hai phía thay vì hỏng hẳn ở một phía.
            #
            #     mắt gần như đứng im  ->  chờ  3 giây
            #     dao động vừa          ->  chờ  3–12 giây theo tỉ lệ
            #     dao động rõ ràng      ->  chờ 12 giây (kiên nhẫn tối đa)
            cho = self.thoi_gian_cho()
            if time.time() - self.first_seen < cho:
                return -1.0
            return 0.0
        age = time.time() - self.last_blink
        if age <= BLINK_VALID_SEC:
            return 1.0
        # Hết hạn thì tụt dần thay vì rơi thẳng, tránh nhấp nháy quanh mốc.
        return float(max(0.0, 1.0 - (age - BLINK_VALID_SEC) / BLINK_VALID_SEC))


class BlinkLiveness(LivenessDetector):
    name = "blink"
    temporal = True

    def __init__(self, settings=None, models_dir=None, max_faces: int = 4):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        self.s = settings
        ensure_model(models_dir)
        opts = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(ensure_model(models_dir))),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=max_faces,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._mp = mp
        self._lm = vision.FaceLandmarker.create_from_options(opts)
        self._states: dict[int, _FaceState] = {}
        #: slot_id -> (tâm hộp bao, thời điểm thấy lần cuối)
        self._slots: dict[int, tuple[tuple[float, float], float]] = {}
        self._next_slot = 0
        self._t0 = time.time()

    # ------------------------------------------------------------ ghép slot
    def _don_slot_cu(self) -> None:
        """Xoá hẳn slot không còn thấy mặt — KÈM toàn bộ lịch sử chớp mắt của nó.

        Đây là chốt chặn quan trọng nhất của cả tầng chống giả mạo, và bản đầu
        **thiếu nó** nên có một lỗ hổng nghiêm trọng:

            người thật chớp mắt  →  slot ghi nhận "vừa chớp, còn hiệu lực"
            hạ mặt xuống         →  slot VẪN giữ nguyên tín dụng đó
            giơ ảnh vào đúng chỗ →  ghép trúng slot cũ, THỪA HƯỞNG cái chớp

        Quan sát thực tế: ảnh trên điện thoại được chấm 0,92 điểm sống. Nguyên
        nhân là slot được ghép **chỉ theo vị trí trên màn hình** và sống vĩnh
        viễn, nên bằng chứng sống bị gắn vào một toạ độ chứ không vào một người.

        Xoá slot sau `SLOT_TIMEOUT` giây không thấy mặt buộc bằng chứng sống phải
        thuộc về một khuôn mặt được theo dõi **liên tục**: hạ mặt xuống rồi giơ
        ảnh lên là mất trắng tín dụng, phải chớp mắt lại từ đầu — mà ảnh thì
        không chớp được.
        """
        gio = time.time()
        for i in [i for i, s in self._slots.items() if gio - s[1] > SLOT_TIMEOUT]:
            self._slots.pop(i, None)
            self._states.pop(i, None)

    def _slot_for(self, center: tuple[float, float], diag: float) -> int:
        """Gán khuôn mặt vào một slot đang sống, hoặc mở slot mới."""
        gio = time.time()
        for i, (c, _) in self._slots.items():
            if np.hypot(center[0] - c[0], center[1] - c[1]) < diag * 0.6:
                self._slots[i] = (center, gio)
                return i
        self._next_slot += 1
        self._slots[self._next_slot] = (center, gio)
        return self._next_slot

    def score(self, image_bgr: np.ndarray, detections: list[Detection]) -> list[float]:
        if not detections:
            return []
        h, w = image_bgr.shape[:2]
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        ts = int((time.time() - self._t0) * 1000)
        try:
            res = self._lm.detect_for_video(image, ts)
        except Exception:                                # noqa: BLE001
            return [0.0] * len(detections)

        # Mỗi bộ điểm mốc → tâm mắt để ghép với hộp bao của detector.
        meshes = []
        for lms in res.face_landmarks:
            pts = np.array([[p.x * w, p.y * h] for p in lms], dtype=np.float32)
            ear = (eye_aspect_ratio(pts, LEFT_EYE) + eye_aspect_ratio(pts, RIGHT_EYE)) / 2.0
            meshes.append((pts.mean(axis=0), ear))

        self._don_slot_cu()
        out = []
        for det in detections:
            cx, cy = det.center
            diag = float(np.hypot(det.width, det.height)) + 1e-6
            # Tìm bộ điểm mốc gần tâm hộp bao nhất.
            best, best_d = None, 1e9
            for center, ear in meshes:
                d = float(np.hypot(center[0] - cx, center[1] - cy))
                if d < best_d:
                    best, best_d = ear, d
            # Mặt quá nhỏ thì KHÔNG ĐO ĐƯỢC chớp mắt — trả -1.0 chứ không trả 0.0.
            # Trả 0.0 nghĩa là "đã đo và kết luận là giả", và chính sự nhập nhèm
            # đó khiến người thật đứng xa bị kết tội giả mạo trong khi vấn đề chỉ
            # là họ cần lại gần hơn.
            if min(det.width, det.height) < CO_MAT_TOI_THIEU:
                out.append(-1.0)
                continue
            if best is None or best_d > diag * 0.8:
                out.append(-1.0)                         # không khớp được mắt nào
                continue
            state = self._states.setdefault(self._slot_for((cx, cy), diag), _FaceState())
            state.update(best)
            out.append(state.score())
        return out

    def bien_thien_gan_nhat(self) -> dict[int, float]:
        """Hệ số biến thiên EAR của từng slot — để giao diện hiện ra cho người
        dùng thấy, phục vụ việc hiệu chỉnh ngưỡng bằng số liệu thật thay vì đoán."""
        ra = {}
        for i, s in self._states.items():
            if len(s.ear) < SO_KHUNG_XET_DUNG_IM:
                continue
            e = np.array(list(s.ear)[-SO_KHUNG_XET_DUNG_IM:], dtype=np.float32)
            if e.mean() > 0:
                ra[i] = float(e.std() / e.mean())
        return ra

    def blink_counts(self) -> list[int]:
        return [s.blinks for s in self._states.values()]

    def reset(self) -> None:
        self._states.clear()
        self._slots.clear()
        self._next_slot = 0
