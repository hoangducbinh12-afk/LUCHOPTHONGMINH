import streamlit as st
import pandas as pd
import numpy as np
import json
import easyocr
from PIL import Image
from datetime import datetime

# --- 1. GIAO DIỆN ---
st.set_page_config(page_title="TUAN PHONG - V9.5 INDEPENDENT", layout="wide")
st.markdown("""<style>.main-box { background-color: #0f172a; color: #fbbf24; padding: 20px; border-radius: 12px; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; border-left: 8px solid #fbbf24; margin-bottom: 20px; line-height: 1.6; } .stTable td { font-weight: bold; font-size: 11px !important; text-align: center !important; }</style>""", unsafe_allow_html=True)

# --- 2. QUY LUẬT ---
BONG_DUONG = {0:5, 1:6, 2:7, 3:8, 4:9, 5:0, 6:1, 7:2, 8:3, 9:4}
BONG_AM = {0:7, 1:4, 2:9, 3:6, 4:1, 5:8, 6:3, 7:0, 8:5, 9:2}
BO_MAP = {"00": [0,5,50,55], "01": [1,10,6,60,51,15,56,65], "02": [2,20,7,70,52,25,57,75], "03": [3,30,8,80,53,35,58,85], "04": [4,40,9,90,54,45,59,95], "11": [11,16,61,66], "12": [12,21,17,71,62,26,67,76], "13": [13,31,18,81,63,36,68,86], "14": [14,41,19,91,64,46,69,96], "22": [22,27,72,77], "23": [23,32,28,82,73,37,78,87], "24": [24,42,29,92,74,47,79,97], "33": [33,38,83,88], "34": [34,43,39,93,84,48,89,98], "44": [44,49,94,99]}

def get_bo_idx(n):
    for i, (k, v) in enumerate(BO_MAP.items()):
        if n in v: return i
    return 0

if 'db' not in st.session_state:
    st.session_state.db = {
        "history": [], "last_gdb": "", "raw_107": [0]*107,
        "pts": {f"app{i}": [{"d":1,"u":1,"t":1} for _ in range(120)] for i in range(1, 7)},
        "pts_app5": { "dau": [1]*10, "duoi": [1]*10, "bo": [1]*15 },
        "weights": [16.6] * 6, "auto_mode": True
    }

@st.cache_resource
def load_ocr(): return easyocr.Reader(['en'], gpu=False)

def build_math_100(gdb_str):
    if not gdb_str or len(str(gdb_str)) < 5: return [0]*100
    digits = [int(x) for x in str(gdb_str)[-5:]]
    res = []
    for s in range(20): res.extend([(d+s)%10 for d in digits])
    return res[:100]

# --- 3. ENGINE TÍNH ĐIỂM (TÁCH BIỆT VẬT LÝ) ---
@st.cache_data
def calculate_master_v95(last_gdb, raw_107, weights, pts_main_str, pts_a5_str):
    ocr_pos = np.array(raw_107)
    math_pos = np.array(build_math_100(last_gdb))
    p5 = json.loads(pts_a5_str)
    pts = json.loads(pts_main_str)
    
    # Khởi tạo mảng điểm riêng biệt
    score_A1, score_A2, score_A3 = np.zeros(100), np.zeros(100), np.zeros(100)
    score_A4, score_A5, score_A6 = np.zeros(100), np.zeros(100), np.zeros(100)
    
    for i in range(100):
        d, u, t = i//10, i%10, (i//10 + i%10)%10
        # Nhóm Vị Trí (Sử dụng hệ số khác nhau để phân hóa Rank)
        score_A1[i] = np.sum(ocr_pos == d) * 1.5 + 1
        score_A2[i] = np.sum(ocr_pos == u) * 1.3 + 2
        score_A3[i] = np.sum(ocr_pos == t) * 1.1 + 3
        
        # Nhóm Toán học & Thuộc tính (Tách biệt hoàn toàn công thức)
        khan_raw = sum([pts["app4"][idx]["d"] for idx in range(100) if math_pos[idx] == d])
        score_A4[i] = 1000 - khan_raw # Tịnh tiến (Điểm cao đứng đầu)
        score_A6[i] = khan_raw + (i % 10) # Top Gan (Điểm thấp đứng đầu + chút biến số để lệch Rank)
        score_A5[i] = p5['dau'][d] * 5 + p5['duoi'][u] * 3 + p5['bo'][get_bo_idx(i)] * 10
        
    # Tạo DataFrame kết quả
    df = pd.DataFrame({
        "SO": [f"{i:02d}" for i in range(100)],
        "A1": score_A1, "A2": score_A2, "A3": score_A3,
        "A4": score_A4, "A5": score_A5, "A6": score_A6
    })
    
    # Tính điểm tổng hợp
    w = weights
    df["DIEM_TONG"] = (df["A1"]*w[0] + df["A2"]*w[1] + df["A3"]*w[2] + df["A4"]*w[3] + df["A5"]*w[4] + df["A6"]*w[5]) / 6
    return df.sort_values("DIEM_TONG").reset_index(drop=True)

# --- 4. LOGIC CẬP NHẬT ---
def get_rank_of_so(df_input, target_so, col_name):
    # Hàm tính Rank riêng cho từng cột để tránh bị ghi đè dữ liệu
    df_sorted = df_input.sort_values(by=col_name, ascending=True).reset_index()
    match = df_sorted[df_sorted["SO"] == target_so].index
    return int(match[0]) + 1 if len(match) > 0 else 50

def process_update(gdb_val, ocr_data=None):
    db = st.session_state.db
    if db["last_gdb"]:
        df_old = calculate_master_v95(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts"]), json.dumps(db["pts_app5"]))
        target = gdb_val[-2:]
        res = {"Kỳ": len(db["history"])+1, "GĐB": gdb_val, "Số": target, "Time": datetime.now().strftime("%H:%M")}
        
        # TÍNH RANK ĐỘC LẬP TỪNG CỘT
        res["Rank_AI"] = get_rank_of_so(df_old, target, "DIEM_TONG")
        res["Rank_A1"] = get_rank_of_so(df_old, target, "A1")
        res["Rank_A2"] = get_rank_of_so(df_old, target, "A2")
        res["Rank_A3"] = get_rank_of_so(df_old, target, "A3")
        res["Rank_A4"] = get_rank_of_so(df_old, target, "A4")
        res["Rank_A5"] = get_rank_of_so(df_old, target, "A5")
        res["Rank_A6"] = get_rank_of_so(df_old, target, "A6")
        db["history"].insert(0, res)

    db["last_gdb"] = gdb_val
    if ocr_data: db["raw_107"] = (ocr_data + [0]*107)[:107]

# --- 5. GIAO DIỆN ---
st.title("🛡️ TUAN PHONG COMMAND CENTER V9.5")
with st.sidebar:
    up_json = st.file_uploader("Nạp Data:", type="json")
    if up_json: st.session_state.db = json.load(up_json); st.rerun()
    img_file = st.file_uploader("Quét ảnh:", type=["png","jpg","jpeg"])
    if img_file and st.button("🚀 QUÉT & CẬP NHẬT", type="primary"):
        reader = load_ocr()
        res_ocr = reader.readtext(np.array(Image.open(img_file).convert('L')), allowlist='0123456789')
        ocr_n, gdb_n = [], ""
        for (bbox, txt, prob) in res_ocr:
            if 5 <= len(txt) <= 6 and not gdb_n: gdb_n = txt
            for d in txt: ocr_n.append(int(d))
        if gdb_n: process_update(gdb_n, ocr_n); st.rerun()
    if st.button("❌ RESET ALL"): st.session_state.clear(); st.rerun()

if st.session_state.db["last_gdb"]:
    db = st.session_state.db
    df_m = calculate_master_v95(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts"]), json.dumps(db["pts_app5"]))
    t1, t2, t3 = st.tabs(["🎯 DÀN KHUYÊN DÙNG", "📊 SOI CHI TIẾT", "🕒 NHẬT KÝ 6 APP"])
    with t1:
        st.write(f"### 🛡️ Kỳ hiện tại: **{db['last_gdb']}**")
        c1, c2 = st.columns([1, 2])
        with c1: n_kd = st.number_input("Số quân:", 1, 100, 51)
        with c2:
            st.subheader("🔥 DÀN AI TỐI ƯU")
            st.markdown(f"<div class='main-box'>{' '.join(df_m.head(n_kd)['SO'].tolist())}</div>", unsafe_allow_html=True)
    with t2: st.dataframe(df_m, use_container_width=True)
    with t3:
        if db["history"]:
            st.table(pd.DataFrame(db["history"])[['Kỳ', 'GĐB', 'Số', 'Rank_AI', 'Rank_A1', 'Rank_A2', 'Rank_A3', 'Rank_A4', 'Rank_A5', 'Rank_A6', 'Time']])

with st.sidebar:
    st.download_button("💾 SAO LƯU DATA", json.dumps(st.session_state.db), "LUC_HOP_V95.json", use_container_width=True)
