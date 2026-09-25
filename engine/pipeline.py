"""Ghép bảy tầng thành một pipeline dùng được.

Hai chế độ chạy, khác nhau ở chỗ có bám vết hay không:

  • `process_image()` — một ảnh rời rạc. Dùng khi đăng ký, khi nhận diện ảnh tải
    lên, và khi chạy đánh giá. Mỗi khuôn mặt được trích đặc trưng đúng một lần.

  • `process_frame()` — một khung trong luồng video. Có bám vết và bỏ phiếu, và
    chỉ trích đặc trưng lại mỗi N khung trên mỗi vết. Đây là chế độ dùng cho
    kiosk và cho luồng WebSocket.

Backend và các client chỉ nên gọi qua lớp này, không gọi thẳng vào từng tầng.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from . import quality as quality_mod
from .align import align_face, crop_face
from .detect import build_detector
from .embed import build_embedder
from .index import build_index
from .settings import EngineSettings
from .track import FaceTracker, Track
from .types import Detection, Face, Identity


class FacePipeline:
    def __init__(self, settings: EngineSettings | None = None):
        self.settings = settings or EngineSettings()
        s = self.settings

        self.detector = build_detector(s.detect)
        self.embedder = build_embedder(s.embed)
        self.index = build_index(s.index, dim=self.embedder.dim)
        self.tracker = FaceTracker(s.track)
        self.liveness = self._build_liveness()

        # Kích thước căn chỉnh do chính embedder quyết định, không hardcode.
        self.chip_size = self.embedder.image_size
        self._timings: dict[str, float] = {}

    def _build_liveness(self):
        if not self.settings.liveness.enabled:
            return None
        from .liveness import build_liveness
        return build_liveness(self.settings.liveness, self.settings.models_dir)

    # ------------------------------------------------------------ các tầng lẻ
    def detect_faces(self, image_bgr: np.ndarray, *, align: bool = True,
                     check_quality: bool | None = None) -> list[Face]:
        """detect → quality → align. Chưa trích đặc trưng."""
        t0 = time.perf_counter()
        dets = self.detector.detect(image_bgr)
        self._timings["detect"] = (time.perf_counter() - t0) * 1000

        use_quality = self.settings.quality.enabled if check_quality is None else check_quality
        faces: list[Face] = []
        t0 = time.perf_counter()
        for det in dets:
            report = (quality_mod.assess(image_bgr, det, self.settings.quality)
                      if use_quality else None)
            chip = (align_face(image_bgr, det.landmarks, self.chip_size) if align
                    else crop_face(image_bgr, det, self.chip_size))
            if chip is None:
                continue
            faces.append(Face(detection=det, chip=chip, quality=report))
        self._timings["quality+align"] = (time.perf_counter() - t0) * 1000
        return faces

    def embed_faces(self, faces: list[Face]) -> list[Face]:
        """Điền `.embedding` cho từng khuôn mặt. Sửa tại chỗ và trả về chính list."""
        if not faces:
            return faces
        t0 = time.perf_counter()
        vectors = self.embedder.embed([f.chip for f in faces])
        for face, vec in zip(faces, vectors):
            face.embedding = vec
        self._timings["embed"] = (time.perf_counter() - t0) * 1000
        return faces

    def check_liveness(self, faces: list[Face], image_bgr: np.ndarray) -> list[Face]:
        """Điền `.liveness`. Không bật thì bỏ qua, để None."""
        if self.liveness is None or not faces:
            return faces
        t0 = time.perf_counter()
        for face, score in zip(faces, self.liveness.score(image_bgr, [f.detection for f in faces])):
            face.liveness = float(score)
        self._timings["liveness"] = (time.perf_counter() - t0) * 1000
        return faces

    def identify(self, faces: list[Face]) -> list[Identity]:
        """Tra chỉ mục cho từng khuôn mặt đã có embedding."""
        t0 = time.perf_counter()
        out = []
        for face in faces:
            if face.embedding is None:
                out.append(Identity(Identity.UNKNOWN, -1.0))
                continue
            ident = self.index.identify(face.embedding, self.settings.match_threshold)
            # Nghi ngờ giả mạo thì không cho nhận, dù vector có khớp đến đâu.
            if (face.liveness is not None
                    and face.liveness >= 0        # -1.0 = chưa đo được
                    and face.liveness < self.settings.liveness.threshold):
                ident = Identity(label=Identity.UNKNOWN, score=ident.score)
            out.append(ident)
        self._timings["identify"] = (time.perf_counter() - t0) * 1000
        return out

    # ------------------------------------------------------------ chế độ ảnh
    def process_image(self, image_bgr: np.ndarray, *, align: bool = True
                      ) -> list[tuple[Face, Identity]]:
        """Nhận diện trên một ảnh rời rạc, không bám vết."""
        faces = self.detect_faces(image_bgr, align=align)
        if not faces:
            return []
        self.check_liveness(faces, image_bgr)
        self.embed_faces(faces)
        return list(zip(faces, self.identify(faces)))

    # ---------------------------------------------------------- chế độ video
    def process_frame(self, image_bgr: np.ndarray) -> list[Track]:
        """Nhận diện một khung video, có bám vết và bỏ phiếu.

        Chỉ những vết đến hạn mới chạy qua mạng trích đặc trưng — đây là lý do
        chế độ này nhanh hơn hẳn việc gọi `process_image` mỗi khung.
        """
        if not self.settings.track.enabled:
            pairs = self.process_image(image_bgr)
            dets = [f.detection for f, _ in pairs]
            tracks = self.tracker.update(dets)
            for track, (_, ident) in zip(tracks, pairs):
                self.tracker.vote(track, ident)
            return tracks

        dets = self.detector.detect(image_bgr)
        tracks = self.tracker.update(dets)

        due = self.tracker.tracks_needing_embedding()
        if due:
            faces: list[Face] = []
            kept: list[Track] = []
            for track in due:
                det = track.detection
                report = (quality_mod.assess(image_bgr, det, self.settings.quality)
                          if self.settings.quality.enabled else None)
                chip = align_face(image_bgr, det.landmarks, self.chip_size)
                if chip is None:
                    continue
                # Ảnh quá kém thì bỏ phiếu trắng thay vì đoán bừa — nhưng phải
                # NÓI RA lý do. Trước đây câu nhắc bị bỏ đi ngay tại đây, nên
                # người dùng chỉ thấy "Chưa nhận ra" mà không biết là do mình
                # cử động, do thiếu sáng hay do đứng quá xa.
                if report is not None and not report.passed:
                    track.hint = quality_mod.hint_for(report)
                    self.tracker.vote(track, Identity(Identity.UNKNOWN, -1.0))
                    continue
                track.hint = ""
                faces.append(Face(detection=det, chip=chip, quality=report))
                kept.append(track)

            if faces:
                self.check_liveness(faces, image_bgr)
                self.embed_faces(faces)
                for track, face, ident in zip(kept, faces, self.identify(faces)):
                    track.liveness = face.liveness
                    self.tracker.vote(track, ident)

        return tracks

    def newly_confirmed(self) -> list[Track]:
        """Các vết vừa đủ tin cậy — backend dùng để ghi bản ghi điểm danh."""
        return self.tracker.newly_confirmed()

    # --------------------------------------------------------------- đăng ký
    def embed_for_enrollment(self, images_bgr: list[np.ndarray], *, strict: bool = True
                             ) -> tuple[np.ndarray, list[dict]]:
        """Trích đặc trưng cho một loạt ảnh đăng ký của MỘT người.

        Trả về (ma trận vector, báo cáo từng ảnh). `strict=True` thì loại luôn
        những ảnh không qua cổng chất lượng — nên bật khi đăng ký, vì một ảnh mờ
        lọt vào gallery sẽ gây nhận nhầm về sau.
        """
        vectors, reports, chips = [], [], []
        for i, img in enumerate(images_bgr):
            det = self.detector.detect_largest(img)
            if det is None:
                reports.append({"index": i, "ok": False, "reason": "không thấy khuôn mặt"})
                continue
            report = quality_mod.assess(img, det, self.settings.quality)
            if strict and not report.passed:
                reports.append({"index": i, "ok": False,
                                "reason": ", ".join(report.reasons),
                                "quality": round(report.score, 3)})
                continue
            chip = align_face(img, det.landmarks, self.chip_size)
            if chip is None:
                reports.append({"index": i, "ok": False, "reason": "căn chỉnh thất bại"})
                continue
            chips.append(chip)
            reports.append({"index": i, "ok": True, "quality": round(report.score, 3)})

        if chips:
            vectors = self.embedder.embed(chips)
        return (np.asarray(vectors, dtype=np.float32) if len(chips)
                else np.zeros((0, self.embedder.dim), np.float32)), reports

    # --------------------------------------------------------------- chỉ mục
    def load_index(self, path: str | Path) -> None:
        self.index.load(path)

    def save_index(self, path: str | Path) -> None:
        self.index.save(path)

    def add_to_index(self, vectors: np.ndarray, label: str,
                     person_id: int | None = None) -> None:
        n = len(np.atleast_2d(vectors))
        self.index.add(vectors, [label] * n, [person_id] * n)

    # --------------------------------------------------------------- tiện ích
    @property
    def timings(self) -> dict[str, float]:
        """Độ trễ từng tầng ở lần chạy gần nhất, tính bằng ms."""
        return dict(self._timings)

    def describe(self) -> dict:
        return {
            "detector": self.detector.name,
            "embedder": self.embedder.name,
            "embed_dim": self.embedder.dim,
            "chip_size": self.chip_size,
            "index": self.index.name,
            "index_size": self.index.size,
            "people": self.index.num_people,
            "quality_gate": self.settings.quality.enabled,
            "tracking": self.settings.track.enabled,
            "liveness": self.settings.liveness.enabled,
            "match_threshold": self.settings.match_threshold,
        }
