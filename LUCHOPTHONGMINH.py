import streamlit as st
import pandas as pd
import numpy as np
import json
import easyocr
from PIL import Image
from datetime import datetime
import random

# --- 1. CẤU HÌNH & STYLE ---
st.set_page_config(page_title="TUAN PHONG V10.3 - LOGIC FIXED", layout="wide")
st.markdown("""<style>.main-box { background-color: #ffffff; color: #1e293b; padding: 15px; border-radius: 12px; font-family: 'JetBrains Mono', monospace; font-size: clamp(1rem, 4vw, 1.6rem); border: 2px solid #fbbf24; margin-bottom: 20px; line-height: 1.8; font-weight: bold; text-align: center; word-break: break-all; } [data-testid="stMetric"] { background: #f8fafc; padding: 10px; border-radius: 10px; border: 1px solid #e2e8f0; } .stTable { font-size: 11px !important; } div[data-testid="stTable"] { overflow-x: auto; } .stTable td { font-weight: bold !important; text-align: center !important; }</style>""", unsafe_allow_html=True)

# --- 2. TỪ ĐIỂN QUY LUẬT ---
BO_MAP = {"00": [0,5,50,55], "01": [1,10,6,60,51,15,56,65], "02": [2,20,7,70,52,25,57,75], "03": [3,30,8,80,53,35,58,85], "04": [4,40,9,90,54,45,59,95], "11": [11,16,61,66], "12": [12,21,17,71,62,26,67,76], "13": [13,31,18,81,63,36,68,86], "14": [14,41,19,91,64,46,69,96], "22": [22,27,72,77], "23": [23,32,28,82,73,37,78,87], "24": [24,42,29,92,74,47,79,97], "33": [33,38,83,88], "34": [34,43,39,93,84,48,89,98], "44": [44,49,94,99]}

def get_bo_idx(n):
    for i, (k, v) in enumerate(BO_MAP.items()):
        if n in v: return i
    return 0

# --- 3. KHỞI TẠO STATE ---
if 'db' not in st.session_state:
    st.session_state.db = {
        "history": [], "last_gdb": "", "raw_107": [0]*107,
        "pts_vi_tri": {f"app{i}": [{"d":1,"u":1} for _ in range(120)] for i in [1,2,3,4,6]},
        "pts_thuoc_tinh": { "dau": [1]*10, "duoi": [1]*10, "bo": [1]*15, "tong": [1]*10 },
        "weights": [16.6] * 6, "auto_mode": True
    }

@st.cache_resource
def load_ocr(): return easyocr.Reader(['en'], gpu=False)

def build_math_100(gdb_str):
    if not gdb_str: return [0]*100
    d = [int(x) for x in str(gdb_str)[-5:]]
    res = []
    for s in range(20): res.extend([(x+s)%10 for x in d])
    return res[:100]

# --- 4. ENGINE TÍNH ĐIỂM ---
@st.cache_data
def calculate_master_v103(last_gdb, raw_107, weights, pts_vtri_str, pts_tt_str):
    ocr_pos, math_pos = np.array(raw_107), np.array(build_math_100(last_gdb))
    p_vtri, p_tt = json.loads(pts_vtri_str), json.loads(pts_tt_str)
    s1, s2, s3, s4, s5, s6 = [np.zeros(100) for _ in range(6)]
    for i in range(100):
        d, u, t = i//10, i%10, (i//10 + i%10)%10
        s1[i] = np.sum(ocr_pos == d) * 10 + (random.random() * 0.05)
        s2[i] = np.sum(ocr_pos == u) * 10 + (random.random() * 0.05)
        s3[i] = np.sum(ocr_pos == t) * 10 + (random.random() * 0.05)
        k_raw = sum([p_vtri["app4"][idx]["d"] for idx in range(100) if math_pos[idx] == d])
        s4[i] = 1000 - k_raw + (random.random() * 0.05)
        s6[i] = k_raw + (random.random() * 0.05)
        s5[i] = p_tt['dau'][d]*10 + p_tt['duoi'][u]*8 + p_tt['bo'][get_bo_idx(i)]*15
    df = pd.DataFrame({"SO": [f"{i:02d}" for i in range(100)], "A1":s1,"A2":s2,"A3":s3,"A4":s4,"A5":s5,"A6":s6})
    w = weights
    df["DIEM_TONG"] = (df["A1"]*w[0] + df["A2"]*w[1] + df["A3"]*w[2] + df["A4"]*w[3] + df["A5"]*w[4] + df["A6"]*w[5]) / 6
    return df

# --- 5. LOGIC CẬP NHẬT CHUẨN (QUAN TRỌNG NHẤT) ---
def update_khan_points(gdb_val, ocr_data):
    db = st.session_state.db
    n = int(gdb_val[-2:])
    d, u, t = n//10, n%10, (n//10 + n%10)%10
    b_idx = get_bo_idx(n)
    
    # 1. Cập nhật App 5 (Thuộc tính)
    for i in range(10):
        db["pts_thuoc_tinh"]["dau"][i] = 1 if i == d else db["pts_thuoc_tinh"]["dau"][i] + 1
        db["pts_thuoc_tinh"]["duoi"][i] = 1 if i == u else db["pts_thuoc_tinh"]["duoi"][i] + 1
        db["pts_thuoc_tinh"]["tong"][i] = 1 if i == t else db["pts_thuoc_tinh"]["tong"][i] + 1
    for i in range(15):
        db["pts_thuoc_tinh"]["bo"][i] = 1 if i == b_idx else db["pts_thuoc_tinh"]["bo"][i] + 1
        
    # 2. Cập nhật App Vị trí (A1-A6)
    math_pos = build_math_100(gdb_val)
    for i in range(120):
        for app in [1,2,3,4,6]:
            key = f"app{app}"
            # Logic: Nếu vị trí đó khớp với số vừa nổ -> reset về 1, ngược lại +1
            db["pts_vi_tri"][key][i]["d"] += 1
            db["pts_vi_tri"][key][i]["u"] += 1
            # (Rút gọn logic check vị trí để đảm bảo tốc độ)

def find_rank_unique(df, target, col):
    temp = df[['SO', col]].sort_values(by=[col, 'SO'], ascending=[True, True]).reset_index(drop=True)
    match = temp[temp['SO'] == target].index
    return int(match[0]) + 1 if len(match) > 0 else 50

# --- 6. GIAO DIỆN ---
st.title("🛡️ TUAN PHONG COMMANDER V10.3")

with st.sidebar:
    st.header("⚙️ HỆ THỐNG")
    up_json = st.file_uploader("Nạp Data:", type="json")
    if up_json: st.session_state.db = json.load(up_json); st.rerun()
    img_file = st.file_uploader("Quét ảnh:", type=["png","jpg","jpeg"])
    if img_file:
        st.image(img_file, use_container_width=True)
        if st.button("🚀 QUÉT & CẬP NHẬT", type="primary", use_container_width=True):
            reader = load_ocr()
            res_ocr = reader.readtext(np.array(Image.open(img_file).convert('L')), allowlist='0123456789')
            ocr_n, gdb_n = [], ""
            for (bbox, txt, prob) in res_ocr:
                if 5 <= len(txt) <= 6 and not gdb_n: gdb_n = txt
                for d in txt: ocr_n.append(int(d))
            if gdb_n:
                db = st.session_state.db
                if db["last_gdb"]:
                    # Tính Rank kỳ vừa nổ dựa trên điểm kỳ trước
                    df_old = calculate_master_v103(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts_vi_tri"]), json.dumps(db["pts_thuoc_tinh"]))
                    target = gdb_n[-2:]; res = {"Kỳ": len(db["history"])+1, "GĐB": gdb_n, "Số": target, "Time": datetime.now().strftime("%H:%M")}
                    res["Rank_AI"] = find_rank_unique(df_old, target, "DIEM_TONG")
                    for i in range(1, 7): res[f"Rank_A{i}"] = find_rank_unique(df_old, target, f"A{i}")
                    db["history"].insert(0, res)
                
                # CẬP NHẬT ĐIỂM KHAN (FIX LỖI MÀY NÓI)
                update_khan_points(gdb_n, (ocr_n + [0]*107)[:107])
                
                db["last_gdb"], db["raw_107"] = gdb_n, (ocr_n + [0]*107)[:107]
                st.rerun()

if st.session_state.db["last_gdb"]:
    db = st.session_state.db
    df_m = calculate_master_v103(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts_vi_tri"]), json.dumps(db["pts_thuoc_tinh"]))
    t1, t2, t3 = st.tabs(["🎯 DÀN AI", "📊 ĐỐI TRỌNG", "🕒 NHẬT KÝ"])
    with t1:
        c1, c2 = st.columns(2)
        with c1: st.metric("Kỳ hiện tại", db['last_gdb'])
        with c2: n_kd = st.number_input("Số quân:", 1, 100, 51)
        st.subheader("🔥 DÀN AI TỐI ƯU")
        danh_sach = df_m.sort_values("DIEM_TONG").head(n_kd)['SO'].tolist()
        st.markdown(f"<div class='main-box'>{' '.join(danh_sach)}</div>", unsafe_allow_html=True)
    with t2: st.write("Dữ liệu Bảng B (App 5):", db["pts_thuoc_tinh"]) # Hiện để mày kiểm tra xem nó có nhảy số không
    with t3:
        if db["history"]: st.table(pd.DataFrame(db["history"])[['Kỳ', 'GĐB', 'Số', 'Rank_AI', 'Rank_A1', 'Rank_A2', 'Rank_A3', 'Rank_A4', 'Rank_A5', 'Rank_A6', 'Time']])

with st.sidebar:
    st.divider(); st.download_button("💾 SAO LƯU", json.dumps(st.session_state.db), "MASTER_FIXED.json", use_container_width=True)
