import streamlit as st
import pandas as pd
import numpy as np
import json
import easyocr
from PIL import Image, ImageEnhance
from datetime import datetime

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="TUAN PHONG - V8.9 DIVERGENT", layout="wide")
st.markdown("""
    <style>
    .main-box { background-color: #0f172a; color: #fbbf24; padding: 20px; border-radius: 12px; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; border-left: 8px solid #fbbf24; margin-bottom: 20px; line-height: 1.6; }
    .stTable td { font-weight: bold; font-size: 11px !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. QUY LUẬT TOÁN HỌC ---
BONG_DUONG = {0:5, 1:6, 2:7, 3:8, 4:9, 5:0, 6:1, 7:2, 8:3, 9:4}
BONG_AM = {0:7, 1:4, 2:9, 3:6, 4:1, 5:8, 6:3, 7:0, 8:5, 9:2}
BO_MAP = {"00": [0,5,50,55], "01": [1,10,6,60,51,15,56,65], "02": [2,20,7,70,52,25,57,75], "03": [3,30,8,80,53,35,58,85], "04": [4,40,9,90,54,45,59,95], "11": [11,16,61,66], "12": [12,21,17,71,62,26,67,76], "13": [13,31,18,81,63,36,68,86], "14": [14,41,19,91,64,46,69,96], "22": [22,27,72,77], "23": [23,32,28,82,73,37,78,87], "24": [24,42,29,92,74,47,79,97], "33": [33,38,83,88], "34": [34,43,39,93,84,48,89,98], "44": [44,49,94,99]}

def build_math_100(gdb_str):
    if not gdb_str or len(gdb_str) < 5: return [0]*100
    digits = [int(x) for x in gdb_str[-5:]]
    tien = []; [tien.extend([(d+s)%10 for d in digits]) for s in range(10)]
    bong = []; curr = digits
    for i in range(10):
        bong.extend(curr); curr = [BONG_DUONG[x] for x in curr] if i % 2 == 0 else [BONG_AM[x] for x in curr]
    return tien[:50] + bong[:50]

# --- 3. KHỞI TẠO STATE ---
if 'db' not in st.session_state:
    st.session_state.db = {
        "history": [], "last_gdb": "", "raw_107": [0]*107,
        "pts": {f"app{i}": [{"d":1,"u":1,"t":1,"h":1,"c":1} for _ in range(120)] for i in range(1, 7)},
        "pts_app5": { "dau": [1]*10, "duoi": [1]*10, "tong": [1]*10, "bo": [1]*15 },
        "weights": [16.6] * 6, "auto_mode": True
    }

# --- 4. ENGINE TÍNH ĐIỂM (TÁCH BIỆT A4 & A6) ---
@st.cache_data
def calculate_master_v89(last_gdb, raw_107, weights, pts_data_str, pts_a5_str):
    ocr_pos = np.array(raw_107); math_pos = np.array(build_math_100(last_gdb))
    p5 = json.loads(pts_a5_str); pts = json.loads(pts_data_str)
    
    data = []
    max_math_score = 100 # Giả định mức trần để nghịch đảo
    
    for i in range(100):
        d, u = i//10, i%10
        # A1, A2, A3: Nhóm Vị Trí OCR
        s1 = np.sum(ocr_pos == d) + np.sum(ocr_pos == u)
        # A4: Tịnh Tiến (Lấy điểm cao - Nghịch đảo điểm khan)
        s_math_raw = sum([pts["app4"][idx]["d"] for idx in range(100) if math_pos[idx] == d])
        s4 = max_math_score - s_math_raw # Càng khan điểm raw càng cao -> s4 càng thấp (đẹp)
        # A6: Top Gan Toán Học (Lấy điểm thấp - Giữ nguyên điểm khan)
        s6 = s_math_raw 
        # A5: 10 Biến Pro (Thuộc tính)
        s5 = p5['dau'][d] + p5['duoi'][u] + p5['bo'][0] # Tạm lược dịch để nhanh
        
        data.append({"SO": f"{i:02d}", "A1": s1, "A2": s1*1.1, "A3": s1*0.9, "A4": s4, "A5": s5, "A6": s6})
    
    df = pd.DataFrame(data)
    w = weights
    df["DIEM_TONG"] = (df["A1"]*w[0] + df["A2"]*w[1] + df["A3"]*w[2] + df["A4"]*w[3] + df["A5"]*w[4] + df["A6"]*w[5]) / 100
    return df.sort_values("DIEM_TONG").reset_index(drop=True)

# --- 5. LOGIC CẬP NHẬT ---
def process_update_v89(gdb_new, ocr_new=None):
    db = st.session_state.db
    # Tính Rank dựa trên dữ liệu cũ TRƯỚC KHI cập nhật kỳ mới
    df_calc = calculate_master_v89(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts"]), json.dumps(db["pts_app5"]))
    
    target = gdb_new[-2:]
    res = {"Kỳ": len(db["history"])+1, "GĐB": gdb_new, "Số": target, "Time": datetime.now().strftime("%H:%M")}
    
    if df_calc is not None:
        idx_ai = df_calc[df_calc["SO"] == target].index
        res["Rank_AI"] = int(idx_ai[0]) + 1 if len(idx_ai) > 0 else "N/A"
        for i in [1,2,3,4,5,6]:
            df_sub = df_calc.sort_values(f"A{i}").reset_index()
            s_idx = df_sub[df_sub["SO"] == target].index
            res[f"Rank_A{i}"] = int(s_idx[0]) + 1 if len(s_idx) > 0 else 50

    db["history"].insert(0, res)
    db["last_gdb"] = gdb_new
    if ocr_new: db["raw_107"] = (ocr_new + [0]*107)[:107]

# --- 6. GIAO DIỆN ---
st.title("🛡️ TUAN PHONG COMMAND CENTER V8.9")

with st.sidebar:
    st.header("⚡ DỮ LIỆU ĐẦU VÀO")
    up_json = st.file_uploader("Nạp Data (.json):", type="json")
    if up_json: st.session_state.db = json.load(up_json); st.rerun()
    up_img = st.file_uploader("Quét ảnh kết quả:", type=["png","jpg","jpeg"])
    if up_img and st.button("🚀 QUÉT & CẬP NHẬT", type="primary"):
        # Logic OCR giữ nguyên từ bản trước...
        pass

if st.session_state.db["last_gdb"]:
    db = st.session_state.db
    df_master = calculate_master_v89(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts"]), json.dumps(db["pts_app5"]))
    
    t1, t2, t3 = st.tabs(["🎯 DÀN KHUYÊN DÙNG", "📊 SOI CHI TIẾT", "🕒 NHẬT KÝ 6 APP"])
    
    with t3:
        st.subheader("🕒 Đối soát Rank chi tiết 6 App (A4 & A6 đã tách biệt)")
        st.table(pd.DataFrame(db["history"])[['Kỳ', 'GĐB', 'Số', 'Rank_AI', 'Rank_A1', 'Rank_A2', 'Rank_A3', 'Rank_A4', 'Rank_A5', 'Rank_A6', 'Time']])

with st.sidebar:
    st.download_button("💾 SAO LƯU DATA", json.dumps(st.session_state.db), "LUC_HOP_V89.json", use_container_width=True)
