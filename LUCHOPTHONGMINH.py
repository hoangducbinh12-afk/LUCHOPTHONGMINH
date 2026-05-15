import streamlit as st
import pandas as pd
import numpy as np
import json
import easyocr
from PIL import Image, ImageEnhance
from datetime import datetime

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="TUAN PHONG - V9.3 FINAL FIX", layout="wide")
st.markdown("""
    <style>
    .main-box { background-color: #0f172a; color: #fbbf24; padding: 20px; border-radius: 12px; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; border-left: 8px solid #fbbf24; margin-bottom: 20px; line-height: 1.6; }
    .stTable td { font-weight: bold; font-size: 11px !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. QUY LUẬT & APP 5 ---
BONG_DUONG = {0:5, 1:6, 2:7, 3:8, 4:9, 5:0, 6:1, 7:2, 8:3, 9:4}
BONG_AM = {0:7, 1:4, 2:9, 3:6, 4:1, 5:8, 6:3, 7:0, 8:5, 9:2}
BO_MAP = {"00": [0,5,50,55], "01": [1,10,6,60,51,15,56,65], "02": [2,20,7,70,52,25,57,75], "03": [3,30,8,80,53,35,58,85], "04": [4,40,9,90,54,45,59,95], "11": [11,16,61,66], "12": [12,21,17,71,62,26,67,76], "13": [13,31,18,81,63,36,68,86], "14": [14,41,19,91,64,46,69,96], "22": [22,27,72,77], "23": [23,32,28,82,73,37,78,87], "24": [24,42,29,92,74,47,79,97], "33": [33,38,83,88], "34": [34,43,39,93,84,48,89,98], "44": [44,49,94,99]}

def get_bo_idx(n):
    for i, (k, v) in enumerate(BO_MAP.items()):
        if n in v: return i
    return 0

# --- 3. KHỞI TẠO STATE ---
if 'db' not in st.session_state:
    st.session_state.db = {
        "history": [], "last_gdb": "", "raw_107": [0]*107,
        "pts": {f"app{i}": [{"d":1,"u":1} for _ in range(120)] for i in range(1, 7)},
        "pts_app5": { "dau": [1]*10, "duoi": [1]*10, "bo": [1]*15 },
        "weights": [16.6] * 6, "auto_mode": True
    }

@st.cache_resource
def load_ocr(): return easyocr.Reader(['en'], gpu=False)

def build_math_100(gdb_str):
    if not gdb_str or len(str(gdb_str)) < 5: return [0]*100
    digits = [int(x) for x in str(gdb_str)[-5:]]
    tien = []
    for s in range(20): # Tạo dư ra để không bao giờ bị IndexError
        tien.extend([(d+s)%10 for d in digits])
    return tien[:100]

# --- 4. ENGINE TỔNG LỰC (VÁ LỖI INDEX) ---
@st.cache_data
def calculate_master_v93(last_gdb, raw_107, weights, pts_main_str, pts_a5_str):
    ocr_pos = np.array(raw_107)
    math_pos = np.array(build_math_100(last_gdb))
    p5 = json.loads(pts_a5_str)
    pts = json.loads(pts_main_str)
    
    data = []
    # Bảo vệ vòng lặp không vượt quá độ dài mảng thực tế
    len_math = len(math_pos)
    
    for i in range(100):
        d, u = i//10, i%10
        # A1, A2, A3 (OCR)
        s1 = np.sum(ocr_pos == d) * 10
        s2 = np.sum(ocr_pos == u) * 8
        s3 = (s1 + s2) / 2
        
        # A4 & A6 (Toán học) - FIX INDEX TẠI ĐÂY
        khan_raw = sum([pts["app4"][idx]["d"] for idx in range(min(100, len_math)) if math_pos[idx] == d])
        s4, s6 = 200 - khan_raw, khan_raw
        
        # A5 (Thuộc tính)
        s5 = p5['dau'][d] + p5['duoi'][u] + p5['bo'][get_bo_idx(i)]
        
        data.append({"SO": f"{i:02d}", "A1": s1, "A2": s2, "A3": s3, "A4": s4, "A5": s5, "A6": s6})
    
    df = pd.DataFrame(data)
    w = weights
    df["DIEM_TONG"] = (df["A1"]*w[0] + df["A2"]*w[1] + df["A3"]*w[2] + df["A4"]*w[3] + df["A5"]*w[4] + df["A6"]*w[5]) / 100
    return df.sort_values("DIEM_TONG").reset_index(drop=True)

# --- 5. LOGIC AI ---
def update_dynamic_weights():
    db = st.session_state.db
    if not db.get("auto_mode") or len(db["history"]) < 3: return [16.6] * 6
    recent = db["history"][:3]
    final_w = [16.6] * 6
    for i in range(6):
        ranks = [h.get(f"Rank_A{i+1}", 50) for h in recent]
        if all(isinstance(r, (int, float)) and r < 30 for r in ranks[:2]): final_w[i] -= 5.0
        if isinstance(ranks[0], (int, float)) and ranks[0] > 70: final_w[i] += 8.0
    total = sum(final_w)
    return [(x/total)*100 for x in final_w]

def process_full_cycle(gdb_val, ocr_data=None):
    db = st.session_state.db
    if db["last_gdb"]:
        w_now = update_dynamic_weights()
        df_old = calculate_master_v93(db["last_gdb"], db["raw_107"], tuple(w_now), json.dumps(db["pts"]), json.dumps(db["pts_app5"]))
        target = gdb_val[-2:]
        res = {"Kỳ": len(db["history"])+1, "GĐB": gdb_val, "Số": target, "Time": datetime.now().strftime("%H:%M")}
        
        idx_ai = df_old[df_old["SO"] == target].index
        res["Rank_AI"] = int(idx_ai[0]) + 1 if len(idx_ai) > 0 else "N/A"
        for i in range(1, 7):
            df_sub = df_old.sort_values(f"A{i}").reset_index()
            s_idx = df_sub[df_sub["SO"] == target].index
            res[f"Rank_A{i}"] = int(s_idx[0]) + 1 if len(s_idx) > 0 else 50
        db["history"].insert(0, res)

    db["last_gdb"] = gdb_val
    if ocr_data: db["raw_107"] = (ocr_data + [0]*107)[:107]
    db["weights"] = update_dynamic_weights()

# --- 6. GIAO DIỆN ---
st.title("🛡️ TUAN PHONG COMMAND CENTER V9.3")

with st.sidebar:
    st.header("⚡ HỆ THỐNG NẠP")
    up_json = st.file_uploader("Nạp Data (.json):", type="json")
    if up_json: st.session_state.db = json.load(up_json); st.rerun()
    
    img_file = st.file_uploader("Quét ảnh kết quả:", type=["png","jpg","jpeg"])
    if img_file:
        st.image(img_file, use_container_width=True) # KHÔI PHỤC HIỆN ẢNH
        if st.button("🚀 QUÉT & CẬP NHẬT", type="primary", use_container_width=True):
            with st.spinner("Đang quét OCR..."):
                reader = load_ocr()
                res_ocr = reader.readtext(np.array(Image.open(img_file).convert('L')), allowlist='0123456789')
                ocr_n, gdb_n = [], ""
                for (bbox, txt, prob) in res_ocr:
                    if 5 <= len(txt) <= 6 and not gdb_n: gdb_n = txt
                    for d in txt: ocr_n.append(int(d))
                if gdb_n: process_full_cycle(gdb_n, ocr_n); st.rerun()

    st.checkbox("Chế độ Tự học AI", value=True, key="auto_mode")
    if st.button("❌ RESET ALL"): st.session_state.clear(); st.rerun()

# HIỂN THỊ CHÍNH
if st.session_state.db["last_gdb"]:
    db = st.session_state.db
    w_active = db["weights"]
    df_m = calculate_master_v93(db["last_gdb"], db["raw_107"], tuple(w_active), json.dumps(db["pts"]), json.dumps(db["pts_app5"]))
    
    t1, t2, t3 = st.tabs(["🎯 DÀN KHUYÊN DÙNG", "📊 SOI CHI TIẾT", "🕒 NHẬT KÝ 6 APP"])
    
    with t1:
        st.write(f"### 🛡️ Kỳ hiện tại: **{db['last_gdb']}**")
        c1, c2 = st.columns([1, 2])
        with c1:
            n_kd = st.number_input("Số quân:", 1, 100, 51)
            st.write("**Trọng số AI (Đã khôi phục):**")
            st.dataframe(pd.DataFrame({"App": [f"A{i}" for i in range(1,7)], "W%": [round(x,1) for x in w_active]}).set_index("App").T)
        with c2:
            st.subheader("🔥 DÀN AI TỐI ƯU")
            danh_sach = df_m.head(n_kd)['SO'].tolist()
            st.markdown(f"<div class='main-box'>{' '.join(danh_sach)}</div>", unsafe_allow_html=True)
            
    with t2: st.dataframe(df_m, use_container_width=True)
    with t3:
        if db["history"]:
            st.table(pd.DataFrame(db["history"])[['Kỳ', 'GĐB', 'Số', 'Rank_AI', 'Rank_A1', 'Rank_A2', 'Rank_A3', 'Rank_A4', 'Rank_A5', 'Rank_A6', 'Time']])

with st.sidebar:
    st.divider(); st.download_button("💾 SAO LƯU DATA", json.dumps(st.session_state.db), "LUC_HOP_V93.json", use_container_width=True)
