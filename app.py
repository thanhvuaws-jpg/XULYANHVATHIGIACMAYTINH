"""App demo nhan dien khuon mat - giao dien Streamlit.

    streamlit run app.py
    (hoac: python -m streamlit run app.py)

Tabs:
  - Nhan dien truc tiep : camera CHAY LIEN TUC, co nguoi trong khung la nhan dien ngay
                          (can 'pip install streamlit-webrtc'; neu khong co -> che do chup anh)
  - Nhan dien anh       : upload anh
  - Dang ky nguoi       : them anh bang upload HOAC chup nhieu lan, xem lai, roi luu
  - Bang dieu khien     : thong ke du lieu, model, dung lai DB, chay danh gia, xem bao cao

Cot trai: thu vien anh theo tung nguoi.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from engine.anh_io import ghi_anh
from src import config
from src.face_utils import (FaceDetector, draw_results, embed_faces, load_backbone,
                            load_db, match, save_db)

try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode
    import av
    WEBRTC_OK = True
except Exception:  # noqa: BLE001
    WEBRTC_OK = False

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
RTC_CONF = {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}

st.set_page_config(page_title="Nhận diện khuôn mặt", page_icon="🙂", layout="wide")

# --------------------------------------------------------------------------- CSS
st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1300px;}
      h1, h2, h3 {letter-spacing: -.01em;}
      .app-hero {
        background: linear-gradient(120deg, #4f46e5 0%, #7c3aed 55%, #db2777 100%);
        color: #fff; border-radius: 18px; padding: 22px 26px; margin-bottom: 18px;
        box-shadow: 0 10px 30px -12px rgba(79,70,229,.55);
      }
      .app-hero h1 {margin: 0; font-size: 1.55rem; color: #fff;}
      .app-hero p  {margin: 6px 0 0; opacity: .9; font-size: .92rem;}
      .stat-card {
        background: var(--secondary-background-color); border: 1px solid rgba(128,128,128,.18);
        border-radius: 14px; padding: 14px 16px;
      }
      .stat-card .v {font-size: 1.5rem; font-weight: 700; line-height: 1;}
      .stat-card .k {font-size: .78rem; opacity: .7; margin-top: 4px;}
      .pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem;
             background:rgba(124,58,237,.15); color:#7c3aed; font-weight:600;}
      .person-row {display:flex; align-items:center; gap:8px; margin:2px 0 6px;}
      div[data-testid="stSidebarUserContent"] {padding-top: .5rem;}
      .stTabs [data-baseweb="tab-list"] {gap: 4px;}
      .stTabs [data-baseweb="tab"] {border-radius: 10px 10px 0 0; padding: 8px 16px;}
      .thumb-cap {font-size:.72rem; opacity:.6; text-align:center; margin-top:-6px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="app-hero"><h1>🙂 Hệ thống nhận diện khuôn mặt</h1>'
    '<p>Phát hiện · căn chỉnh · embedding · so khớp — kết hợp dữ liệu công khai và dữ liệu tự đăng ký.</p></div>',
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------- resources
@st.cache_resource(show_spinner="Đang nạp mô hình...")
def get_models(backbone: str, weights: str):
    w = weights if backbone == "resnet50" else None
    model, kind = load_backbone(backbone, w)
    return model, kind


@st.cache_resource(show_spinner=False)
def get_detector():
    return FaceDetector()


def db_signature(path: str) -> float:
    p = Path(path)
    return p.stat().st_mtime if p.exists() else 0.0


@st.cache_data(show_spinner=False)
def load_db_cached(path: str, _sig: float):
    return load_db(path)


def read_upload(file) -> np.ndarray | None:
    buf = np.frombuffer(file.getvalue(), np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def person_dirs(name: str):
    return [config.ENROLLED_DIR / name, config.ALIGNED_DIR / name]


def list_person_images(name: str, limit: int = 12):
    for d in person_dirs(name):
        if d.exists():
            imgs = sorted(p for p in d.iterdir() if p.suffix.lower() in IMG_EXT)
            if imgs:
                return imgs[:limit], len(imgs)
    return [], 0


def person_sig(name: str) -> float:
    s = 0.0
    for d in person_dirs(name):
        if d.exists():
            s = max(s, d.stat().st_mtime)
    return s


@st.cache_data(show_spinner=False)
def list_person_images_cached(name: str, _sig: float):
    return list_person_images(name)


# --------------------------------------------------------------------- sidebar
st.sidebar.header("⚙️ Cấu hình")
with st.sidebar.expander("Mô hình & ngưỡng", expanded=False):
    backbone = st.selectbox("Backbone", ["facenet", "resnet50"],
                            help="facenet = pretrained (chạy ngay). resnet50 = CNN bạn tự train.")
    weights = st.text_input("Weights (resnet50)", str(config.MODELS_DIR / "backbone_arcface.pt"))
    threshold = st.slider("Ngưỡng cosine", 0.0, 1.0, float(config.DEFAULT_THRESHOLD), 0.01,
                          help="Cao hơn = chặt hơn (dễ ra 'Unknown'). Chạy tab Bảng điều khiển để tìm ngưỡng tối ưu.")
    db_path = st.text_input("Database", str(config.DB_PATH))
    every = st.slider("Xử lý mỗi N khung hình (camera trực tiếp)", 1, 15, 6,
                      help="Số lớn hơn = video mượt hơn, nhãn cập nhật chậm nhịp hơn (hợp với CPU).")

try:
    model, kind = get_models(backbone, weights)
except Exception as e:  # noqa: BLE001
    st.sidebar.error(f"Lỗi nạp mô hình: {e}")
    st.stop()

detector = get_detector()
db = load_db_cached(db_path, db_signature(db_path))

st.sidebar.divider()
st.sidebar.header("👥 Người trong hệ thống")
if not db:
    st.sidebar.info("Chưa có ai. Vào tab **Đăng ký người** để thêm.")
else:
    names_sorted = sorted(db)
    st.sidebar.caption(f"{len(db)} người · {sum(v.shape[0] for v in db.values())} vector")
    st.sidebar.dataframe(
        pd.DataFrame({"Người": names_sorted,
                      "Vector": [int(db[n].shape[0]) for n in names_sorted]}),
        hide_index=True, use_container_width=True, height=210,
    )
    sel = st.sidebar.selectbox("Xem ảnh của", ["—"] + names_sorted,
                               help="Chỉ nạp ảnh khi bạn chọn — giữ web nhẹ.")
    if sel != "—":
        imgs, total = list_person_images_cached(sel, person_sig(sel))
        st.sidebar.caption(f"{total} ảnh trên đĩa" if total else "Chỉ có vector, không có ảnh gốc.")
        cols = st.sidebar.columns(3)
        for i, ip in enumerate(imgs[:9]):
            cols[i % 3].image(str(ip), use_container_width=True)
        if st.sidebar.button(f"🗑️ Xoá '{sel}' khỏi nhận diện"):
            cur = load_db(db_path)
            cur.pop(sel, None)
            save_db(cur, db_path)
            st.cache_data.clear()
            st.rerun()

# --------------------------------------------------------------------- helpers
def recognize_frame(img_bgr):
    faces = detector.detect_and_align(img_bgr)
    if not faces:
        return img_bgr, []
    embs = embed_faces(model, kind, [f["face"] for f in faces])
    items = []
    for f, emb in zip(faces, embs):
        nm, sim = match(db, emb, threshold)
        items.append({"box": f["box"], "label": nm, "score": float(sim)})
    return draw_results(img_bgr, items), items


def results_table(items):
    if not items:
        st.info("Không phát hiện khuôn mặt.")
        return
    df = pd.DataFrame([{"Tên": it["label"], "Cosine": round(it["score"], 3)} for it in items])
    st.dataframe(df, use_container_width=True, hide_index=True)


tab_live, tab_img, tab_enroll, tab_dash = st.tabs(
    ["🎥 Nhận diện trực tiếp", "🖼️ Nhận diện ảnh", "➕ Đăng ký người", "📊 Bảng điều khiển"]
)

# =========================================================== TAB 1: LIVE CAMERA
with tab_live:
    st.subheader("Camera nhận diện liên tục")
    if not db:
        st.warning("Database rỗng — hãy đăng ký người ở tab **Đăng ký người** trước.")
    if WEBRTC_OK:
        st.caption("Cho phép trình duyệt truy cập camera. Có người trong khung hình là tự nhận diện, "
                   "không cần bấm nút.")
        state = {"i": 0, "every": every, "items": []}

        def video_frame_callback(frame):
            img = frame.to_ndarray(format="bgr24")
            state["i"] += 1
            if state["i"] % state["every"] == 0:
                h, w = img.shape[:2]
                scale = 640 / w if w > 640 else 1.0           # detect tren anh nho -> nhanh hon
                small = cv2.resize(img, (int(w * scale), int(h * scale))) if scale != 1.0 else img
                faces = detector.detect_and_align(small)
                items = []
                if faces:
                    embs = embed_faces(model, kind, [f["face"] for f in faces])
                    for f, e in zip(faces, embs):
                        nm, sim = match(db, e, threshold)
                        box = (np.asarray(f["box"], dtype=float) / scale).astype(int)
                        items.append({"box": box, "label": nm, "score": float(sim)})
                state["items"] = items
            return av.VideoFrame.from_ndarray(draw_results(img, state["items"]), format="bgr24")

        webrtc_streamer(
            key="live-reco",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=RTC_CONF,
            video_frame_callback=video_frame_callback,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )
    else:
        st.warning("Chưa cài **streamlit-webrtc** nên chưa có video trực tiếp trong web. "
                   "Cài bằng: `pip install streamlit-webrtc` rồi tải lại trang.\n\n"
                   "Tạm thời dùng chế độ chụp bên dưới, hoặc chạy bản OpenCV mượt hơn:\n"
                   "`python -m src.recognize_realtime`")
        shot = st.camera_input("Chụp để nhận diện")
        if shot:
            img = read_upload(shot)
            out, items = recognize_frame(img)
            st.image(out[:, :, ::-1], use_container_width=True)
            results_table(items)

# ================================================================ TAB 2: IMAGE
with tab_img:
    st.subheader("Nhận diện trên ảnh tĩnh")
    up = st.file_uploader("Chọn ảnh (jpg/png)", type=["jpg", "jpeg", "png"])
    if up:
        img = read_upload(up)
        if img is None:
            st.error("Không đọc được ảnh.")
        else:
            out, items = recognize_frame(img)
            c1, c2 = st.columns([3, 2])
            with c1:
                st.image(out[:, :, ::-1], use_container_width=True)
            with c2:
                results_table(items)

# =============================================================== TAB 3: ENROLL
with tab_enroll:
    st.subheader("Đăng ký người mới")
    st.caption("Thêm ảnh bằng cách **tải lên** hoặc **chụp nhiều lần**. Ảnh gom vào khay bên dưới, "
               "xem lại rồi bấm **Lưu vào hệ thống**. Không cần train lại CNN.")

    ss = st.session_state
    ss.setdefault("enroll_imgs", [])      # list[np.ndarray BGR]
    ss.setdefault("enroll_sigs", set())   # chống thêm trùng
    ss.setdefault("enroll_cam_sig", None)

    name_raw = st.text_input("Tên người", placeholder="vd: nam  (không dấu, không khoảng trắng)")
    name = name_raw.strip().replace(" ", "_")

    col_u, col_c = st.columns(2)
    with col_u:
        ups = st.file_uploader("📁 Tải ảnh lên (chọn nhiều)", type=["jpg", "jpeg", "png"],
                               accept_multiple_files=True, key="enroll_up")
        for f in ups or []:
            sig = f"u:{f.name}:{f.size}"
            if sig not in ss.enroll_sigs:
                im = read_upload(f)
                if im is not None:
                    ss.enroll_imgs.append(im)
                    ss.enroll_sigs.add(sig)
    with col_c:
        cam = st.camera_input("📷 Chụp (bấm lại để chụp thêm)", key="enroll_cam")
        if cam is not None:
            csig = hashlib.md5(cam.getvalue()).hexdigest()
            if csig != ss.enroll_cam_sig:
                im = read_upload(cam)
                if im is not None:
                    ss.enroll_imgs.append(im)
                    ss.enroll_cam_sig = csig

    n_buf = len(ss.enroll_imgs)
    st.markdown(f"**Khay ảnh: {n_buf}**")
    if n_buf:
        grid = st.columns(6)
        for i, im in enumerate(list(ss.enroll_imgs)):
            with grid[i % 6]:
                st.image(im[:, :, ::-1], use_container_width=True)
                if st.button("✖", key=f"rm_{i}", help="Bỏ ảnh này"):
                    ss.enroll_imgs.pop(i)
                    st.rerun()

    b1, b2, _ = st.columns([1, 1, 3])
    with b1:
        save_click = st.button("💾 Lưu vào hệ thống", type="primary",
                               disabled=not (name and n_buf))
    with b2:
        if st.button("🧹 Xoá khay", disabled=not n_buf):
            ss.enroll_imgs.clear()
            ss.enroll_sigs.clear()
            ss.enroll_cam_sig = None
            st.rerun()

    if save_click:
        faces, no_face = [], 0
        for im in ss.enroll_imgs:
            fa = detector.largest_face(im)
            if fa is None:
                no_face += 1
            else:
                faces.append(fa)
        if not faces:
            st.error("Không tìm thấy khuôn mặt trong ảnh nào ở khay.")
        else:
            embs = embed_faces(model, kind, faces).astype(np.float32)
            cur = load_db(db_path)
            cur[name] = np.vstack([cur[name], embs]) if name in cur else embs
            save_db(cur, db_path)
            edir = config.ENROLLED_DIR / name
            edir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time() * 1000)
            for j, im in enumerate(ss.enroll_imgs):
                ghi_anh(edir / f"{name}_{ts}_{j:02d}.jpg", im)
            ss.enroll_imgs.clear()
            ss.enroll_sigs.clear()
            ss.enroll_cam_sig = None
            st.cache_data.clear()
            msg = f"Đã lưu '{name}': +{len(embs)} vector."
            if no_face:
                msg += f" (bỏ qua {no_face} ảnh không thấy mặt)"
            st.success(msg + " Xem lại ở cột trái / tab nhận diện.")
            st.rerun()

# ============================================================ TAB 4: DASHBOARD
with tab_dash:
    st.subheader("Dữ liệu huấn luyện")

    def count_tree(root: Path):
        rows = []
        if root.exists():
            for d in sorted(p for p in root.iterdir() if p.is_dir()):
                n = sum(1 for p in d.rglob("*") if p.suffix.lower() in IMG_EXT)
                if n:
                    rows.append((d.name, n))
        return rows

    aligned_rows = count_tree(config.ALIGNED_DIR)
    enrolled_rows = count_tree(config.ENROLLED_DIR)
    total_aligned = sum(n for _, n in aligned_rows)

    m1, m2, m3, m4 = st.columns(4)
    for c, v, k in [
        (m1, len(aligned_rows), "người (đã align)"),
        (m2, total_aligned, "ảnh khuôn mặt align"),
        (m3, len(enrolled_rows), "người tự đăng ký"),
        (m4, len(db), "người trong DB"),
    ]:
        c.markdown(f'<div class="stat-card"><div class="v">{v}</div><div class="k">{k}</div></div>',
                   unsafe_allow_html=True)

    if aligned_rows:
        st.markdown("**Số ảnh theo người** (`data/aligned/`)")
        df = pd.DataFrame(aligned_rows, columns=["Người", "Số ảnh"]).set_index("Người")
        st.bar_chart(df, height=260)

    st.divider()
    st.subheader("Mô hình đã có")
    mrows = []
    for pt in sorted(config.MODELS_DIR.glob("*.pt")):
        js = pt.with_suffix(".json")
        meta = {}
        if js.exists():
            import json
            try:
                meta = json.loads(js.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                meta = {}
        mrows.append({
            "File": pt.name,
            "Loss": meta.get("loss", "-"),
            "val_acc": meta.get("val_acc", "-"),
            "epochs": meta.get("epochs_trained", "-"),
            "#người": len(meta.get("classes", []) or []),
            "MB": round(pt.stat().st_size / 1e6, 1),
        })
    if mrows:
        st.dataframe(pd.DataFrame(mrows), use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có model .pt nào. Train bằng: `python -m src.train_cnn --loss arcface`")

    st.divider()
    st.subheader("Thao tác")
    st.caption("Chạy trực tiếp trên máy này. Với dữ liệu lớn nên chạy ngoài terminal để xem tiến trình.")

    def run_cmd(args: list[str], label: str):
        with st.spinner(f"{label}..."):
            p = subprocess.run([sys.executable, "-m", *args], cwd=str(config.ROOT),
                               capture_output=True, text=True)
        st.code((p.stdout or "") + ("\n" + p.stderr if p.returncode else ""), language="text")
        if p.returncode == 0:
            st.success(f"{label} — xong.")
            st.cache_data.clear()
        else:
            st.error(f"{label} — lỗi (mã {p.returncode}).")

    d1, d2 = st.columns(2)
    with d1:
        if st.button("🔃 Dựng lại database embedding"):
            args = ["src.build_db", "--backbone", backbone, "--out", db_path]
            if backbone == "resnet50":
                args += ["--weights", weights]
            run_cmd(args, "build_db")
    with d2:
        if st.button("📈 Chạy đánh giá (evaluate)"):
            args = ["src.evaluate", "--backbone", backbone, "--tag", backbone]
            if backbone == "resnet50":
                args += ["--weights", weights]
            run_cmd(args, "evaluate")

    st.divider()
    st.subheader("Báo cáo đánh giá")
    tags = sorted({p.name.split("_roc.png")[0] for p in config.REPORTS_DIR.glob("*_roc.png")})
    if tags:
        tag = st.selectbox("Chọn kết quả", tags)
        cols = st.columns(3)
        for c, suffix, title in [
            (cols[0], "roc.png", "ROC / EER"),
            (cols[1], "confusion_matrix.png", "Confusion matrix"),
            (cols[2], "far_frr.png", "FAR – FRR"),
        ]:
            fp = config.REPORTS_DIR / f"{tag}_{suffix}"
            if fp.exists():
                c.image(str(fp), caption=title, use_container_width=True)
        rep = config.REPORTS_DIR / f"{tag}_classification_report.txt"
        if rep.exists():
            with st.expander("classification_report.txt"):
                st.code(rep.read_text(encoding="utf-8"), language="text")
    else:
        st.info("Chưa có báo cáo. Bấm **Chạy đánh giá** ở trên.")
