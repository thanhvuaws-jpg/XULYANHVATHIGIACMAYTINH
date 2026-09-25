"""Tai dataset khuon mat tu Kaggle ve data/kaggle/ .

YEU CAU 1 LAN:
  1. pip install kaggle
  2. Vao kaggle.com -> Settings -> API -> "Create New Token"  => tai ve kaggle.json
  3. Chep kaggle.json vao:  C:\\Users\\<ten_windows>\\.kaggle\\kaggle.json
     (hoac dat bien moi truong KAGGLE_CONFIG_DIR tro toi thu muc chua no)

DUNG:
  python -m src.download_kaggle --dataset pins
  python -m src.download_kaggle --dataset lfw
  python -m src.download_kaggle --dataset celeb5
  python -m src.download_kaggle --list

Sau khi tai xong, cau truc can la:  data/kaggle/<bo_du_lieu>/<ten_nguoi>/<anh>.jpg
Neu giai nen ra khac, tu sap xep lai roi chay:
  python -m src.preprocess --src data/kaggle/<bo_du_lieu> --dst data/aligned
"""
import argparse
import subprocess
import sys
from pathlib import Path

from . import config

# slug Kaggle (dataset "owner/name"). Kiem tra lai ten trang truoc khi tai.
CATALOG = {
    "pins":   ("hereisburak/pins-face-recognition",
               "105 nguoi noi tieng, ~17k anh. Tot nhat de TRAIN CNN cho do an."),
    "lfw":    ("jessicali9530/lfw-dataset",
               "Labeled Faces in the Wild - benchmark chuan nganh (verification)."),
    "celeb5": ("dansbecker/5-celebrity-faces-dataset",
               "5 nguoi, ~100 anh. Tap nho de chay thu pipeline end-to-end."),
    "celeba": ("jessicali9530/celeba-dataset",
               "CelebA - 200k anh, 10k nguoi (nang, chi tai neu can)."),
    "att":    ("kasikrit/att-database-of-faces",
               "AT&T/ORL - 40 nguoi, 400 anh. Co dien, hop minh hoa PCA/Eigenfaces."),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=list(CATALOG), help="Bo du lieu can tai")
    ap.add_argument("--list", action="store_true", help="Liet ke bo du lieu ho tro")
    ap.add_argument("--out", default=str(config.KAGGLE_DIR))
    args = ap.parse_args()

    if args.list or not args.dataset:
        print("Cac bo du lieu ho tro san (--dataset <key>):\n")
        for k, (slug, desc) in CATALOG.items():
            print(f"  {k:<8s} {slug}\n           {desc}\n")
        print("Tim them tren https://www.kaggle.com/datasets?search=face+recognition")
        return

    slug, desc = CATALOG[args.dataset]
    dest = Path(args.out) / args.dataset
    dest.mkdir(parents=True, exist_ok=True)
    print(f"[i] Tai '{slug}'  ({desc})\n    -> {dest}")

    try:
        subprocess.run(
            [sys.executable, "-m", "kaggle", "datasets", "download",
             "-d", slug, "-p", str(dest), "--unzip"],
            check=True,
        )
    except FileNotFoundError:
        raise SystemExit("Chua cai 'kaggle'. Chay: pip install kaggle")
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            f"Tai that bai ({e}). Kiem tra kaggle.json da dat dung cho, "
            f"va ban da bam 'I Understand and Accept' tren trang dataset.")

    print(f"\n[OK] Xong. Kiem tra cau truc thu muc trong {dest} phai la <ten_nguoi>/<anh>.jpg")
    print(f"     Buoc tiep: python -m src.preprocess --src {dest} --dst data/aligned")


if __name__ == "__main__":
    main()
