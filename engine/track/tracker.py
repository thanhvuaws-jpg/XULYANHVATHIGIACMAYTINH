"""Bám vết khuôn mặt qua các khung hình + bỏ phiếu theo thời gian.

Vấn đề cần giải: nhận diện độc lập từng khung hình cho ra nhãn nhấp nháy — cùng
một người có thể lần lượt là "Nam", "Unknown", "Nam", "Huy" chỉ vì một khung bị
mờ hay chớp mắt. Với hệ thống điểm danh thì điều đó còn tệ hơn khó chịu: nó tạo
ra bản ghi sai.

Cách giải: ghép các hộp bao giữa hai khung liên tiếp bằng IoU để biết "đây vẫn là
người lúc nãy", rồi cho mỗi vết một hàng đợi phiếu bầu. Nhãn hiển thị là nhãn
chiếm đa số, và chỉ khi một nhãn giành được đủ số phiếu lẫn đủ tỉ lệ thì vết mới
được **xác nhận** — đó mới là lúc được phép ghi nhận điểm danh.

Ba lợi ích, tất cả đều đo được để đưa vào báo cáo:
  1. nhãn ngừng nhấp nháy;
  2. chỉ cần trích đặc trưng lại mỗi N khung trên mỗi vết → giảm tải rất nhiều;
  3. một khung nhận nhầm không còn đủ sức tạo ra bản ghi sai.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field

import numpy as np

from ..settings import TrackSettings
from ..types import Detection, Identity


def iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
    """Tỉ lệ giao trên hợp của hai hộp bao dạng (x1, y1, x2, y2)."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


@dataclass
class Track:
    """Trạng thái của một khuôn mặt đang được bám."""
    track_id: int
    detection: Detection
    votes: deque = field(default_factory=lambda: deque(maxlen=12))
    identity: Identity = field(default_factory=lambda: Identity(Identity.UNKNOWN, -1.0))
    age: int = 0                 # tổng số khung đã tồn tại
    misses: int = 0              # số khung liên tiếp không ghép được
    frames_since_embed: int = 10_000   # ép trích đặc trưng ngay ở khung đầu
    confirmed: bool = False
    announced: bool = False      # đã phát sự kiện điểm danh cho vết này chưa
    best_score: float = -1.0
    liveness: float | None = None    # điểm chống giả mạo gần nhất, None = không bật
    #: Câu nhắc khi khung hình trượt cổng chất lượng, ví dụ "Giữ yên máy, đừng cử
    #: động". Không có trường này thì người đứng trước camera chỉ thấy "Chưa nhận
    #: ra" và không đoán nổi phải làm gì — trong khi hệ thống **đã biết** lý do
    #: nhưng vứt đi ngay sau khi kiểm tra.
    hint: str = ""

    @property
    def box(self) -> np.ndarray:
        return self.detection.box

    @property
    def vote_ratio(self) -> float:
        if not self.votes:
            return 0.0
        return Counter(self.votes).most_common(1)[0][1] / len(self.votes)

    @property
    def majority_label(self) -> str:
        if not self.votes:
            return Identity.UNKNOWN
        return Counter(self.votes).most_common(1)[0][0]


class FaceTracker:
    """Ghép hộp bao bằng IoU tham lam + bỏ phiếu đa số cho mỗi vết."""

    def __init__(self, settings: TrackSettings | None = None):
        self.s = settings or TrackSettings()
        self.tracks: list[Track] = []
        self._next_id = 1

    # ------------------------------------------------------------------ bám vết
    def update(self, detections: list[Detection]) -> list[Track]:
        """Ghép các phát hiện của khung hiện tại vào các vết đang có.

        Trả về danh sách vết còn sống sau khung này.
        """
        for t in self.tracks:
            t.age += 1
            t.frames_since_embed += 1

        unmatched_tracks = list(range(len(self.tracks)))
        unmatched_dets = list(range(len(detections)))

        if self.tracks and detections:
            # Ma trận IoU rồi ghép tham lam theo thứ tự giảm dần. Khuôn mặt hiếm
            # khi chồng lấn nên tham lam đủ tốt, không cần thuật toán Hungary.
            pairs = []
            for ti, t in enumerate(self.tracks):
                for di, d in enumerate(detections):
                    score = iou(t.box, d.box)
                    if score >= self.s.iou_threshold:
                        pairs.append((score, ti, di))
            pairs.sort(reverse=True)

            used_t, used_d = set(), set()
            for _, ti, di in pairs:
                if ti in used_t or di in used_d:
                    continue
                used_t.add(ti)
                used_d.add(di)
                self.tracks[ti].detection = detections[di]
                self.tracks[ti].misses = 0
            unmatched_tracks = [i for i in range(len(self.tracks)) if i not in used_t]
            unmatched_dets = [i for i in range(len(detections)) if i not in used_d]

        for ti in unmatched_tracks:
            self.tracks[ti].misses += 1

        for di in unmatched_dets:
            self.tracks.append(Track(track_id=self._next_id,
                                     detection=detections[di],
                                     votes=deque(maxlen=self.s.vote_window)))
            self._next_id += 1

        self.tracks = [t for t in self.tracks if t.misses <= self.s.max_age]
        return self.tracks

    # ------------------------------------------------------- lịch trích đặc trưng
    def tracks_needing_embedding(self) -> list[Track]:
        """Những vết đến hạn trích đặc trưng lại ở khung này.

        Đây là chỗ tiết kiệm tính toán: một vết đã ổn định chỉ cần chạy lại mạng
        mỗi `embed_every` khung, thay vì mọi khung.
        """
        out = []
        for t in self.tracks:
            if t.misses > 0:                       # khung này không thấy mặt
                continue
            if t.frames_since_embed >= self.s.embed_every:
                out.append(t)
        return out

    # -------------------------------------------------------------- bỏ phiếu
    def vote(self, track: Track, identity: Identity) -> None:
        """Ghi một phiếu cho vết, rồi tính lại nhãn đa số."""
        track.votes.append(identity.label)
        track.frames_since_embed = 0
        if identity.score > track.best_score:
            track.best_score = identity.score

        label = track.majority_label
        ratio = track.vote_ratio

        # Điểm hiển thị: điểm tốt nhất từng đạt được cho nhãn đang thắng.
        score = identity.score if identity.label == label else track.best_score
        track.identity = Identity(label=label, score=score, person_id=identity.person_id)

        track.confirmed = (
            label != Identity.UNKNOWN
            and len(track.votes) >= self.s.min_votes
            and ratio >= self.s.min_ratio
        )

    def newly_confirmed(self) -> list[Track]:
        """Các vết vừa đủ tin cậy và chưa từng phát sự kiện.

        Backend gọi hàm này để biết khi nào nên ghi một bản ghi điểm danh. Mỗi
        vết chỉ phát đúng một lần, nên một người đứng trước camera 30 giây cũng
        chỉ tạo ra một bản ghi.
        """
        out = [t for t in self.tracks if t.confirmed and not t.announced]
        for t in out:
            t.announced = True
        return out

    def reset(self) -> None:
        self.tracks.clear()
        self._next_id = 1

    @property
    def stats(self) -> dict:
        return {
            "tracks": len(self.tracks),
            "confirmed": sum(1 for t in self.tracks if t.confirmed),
            "next_id": self._next_id,
        }
