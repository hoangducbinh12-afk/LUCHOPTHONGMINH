import streamlit as st
import pandas as pd
import numpy as np
import json
import easyocr
from PIL import Image, ImageEnhance
from datetime import datetime

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="TUAN PHONG - V8.5 LỤC HỢP CHUẨN", layout="wide")
st.markdown("""
    <style>
    .main-box { background-color: #0f172a; color: #fbbf24; padding: 20px; border-radius: 12px; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; border-left: 8px solid #fbbf24; margin-bottom: 20px; line-height: 1.6; }
    .stTable td { font-weight: bold; font-size: 12px !important; text-align: center !important; }
    .stTable th { text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. HẰNG SỐ QUY LUẬT ---
BONG_DUONG = {0:5, 1:6, 2:7, 3:8, 4:9, 5:0, 6:1, 7:2, 8:3, 9:4}
BONG_AM = {0:7, 1:4, 2:9, 3:6, 4:1, 5:8, 6:3, 7:0, 8:5, 9:2}

def build_math_100(gdb_str):
    if len(gdb_str) < 5: return [0]*100
    digits = [int(x) for x in gdb_str[-5:]]
    tien = []; [tien.extend([(d + s) % 10 for d in digits]) for s in range(10)]
    bong = []; curr = digits
    for i in range(10):
        bong.extend(curr)
        curr = [BONG_DUONG[x] for x in curr] if i % 2 == 0 else [BONG_AM[x] for x in curr]
    return (tien[:50] + bong[:50])

# --- 3. KHỞI TẠO STATE (6 APP) ---
if 'db' not in st.session_state:
    st.session_state.db = {
        "history": [], "last_gdb": "", "raw_107": [0]*107,
        "pts": {f"app{i}": [{"d":1,"u":1,"t":1,"h":1,"c":1} for _ in range(120)] for i in range(1, 7)},
        "weights": [16.6] * 6, "auto_mode": True
    }

@st.cache_resource
def get_reader(): return easyocr.Reader(['en'], gpu=False)

# --- 4. BỘ NÃO HỒI QUY 6 APP ---
def brain_dynamic_weights_v6():
    db = st.session_state.db
    if not db["auto_mode"] or len(db["history"]) < 3:
        return [16.6] * 6
    
    recent = db["history"][:3]
    final_w = [16.6] * 6
    app_keys = [f"Rank_A{i}" for i in range(1, 7)]
    
    for i, key in enumerate(app_keys):
        ranks = [h.get(key, 50) for h in recent]
        if all(isinstance(r, (int, float)) and r < 25 for r in ranks[:2]):
            final_w[i] -= 5.0 # Đỏ quá thì giảm
        if isinstance(ranks[0], (int, float)) and ranks[0] > 75:
            final_w[i] += 8.0 # Văng thì tăng đón hồi
            
    total = sum(final_w)
    return [(x / total) * 100 for x in final_w]

# --- 5. ENGINE TÍNH ĐIỂM (TÁCH BIỆT 6 THẰNG ĐỆ) ---
@st.cache_data
def calculate_6_engines(last_gdb, raw_107, weights, pts_str):
    math_pos = np.array(build_math_100(last_gdb))
    ocr_pos = np.array(raw_107)
    
    data = []
    for i in range(100):
        d, u = i//10, i%10
        # Nhóm Vị Trí (A1, A2, A3)
        base_v = np.sum(ocr_pos == d) + np.sum(ocr_pos == u)
        # Nhóm Toán Học (A4, A6)
        base_m = np.sum(math_pos == d) + np.sum(math_pos == u)
        # Nhóm Thuộc Tính (A5)
        base_at = (base_v + base_m) / 2 
        
        data.append({
            "SO": f"{i:02d}",
            "A1": base_v, "A2": base_v * 1.1, "A3": base_v * 0.9, # Tạm giả lập logic khác nhau
            "A4": base_m, "A6": base_m * 0.85,
            "A5": base_at
        })
    
    df = pd.DataFrame(data)
    w = weights
    df["DIEM_TONG"] = (df["A1"]*w[0] + df["A2"]*w[1] + df["A3"]*w[2] + 
                       df["A4"]*w[3] + df["A5"]*w[4] + df["A6"]*w[5]) / 100
    return df.sort_values("DIEM_TONG").reset_index(drop=True)

# --- 6. CẬP NHẬT & TÍNH RANK ---
def process_update_v6(gdb_val, ocr_list=None):
    db = st.session_state.db
    w = brain_dynamic_weights_v6()
    df_calc = calculate_6_engines(gdb_val, ocr_list or db["raw_107"], tuple(w), str(db["pts"]))
    
    target = gdb_val[-2:]
    res = {"Kỳ": len(db["history"])+1, "GĐB": gdb_val, "Số": target, "Time": datetime.now().strftime("%H:%M")}
    
    # Tính Rank tổng
    idx_ai = df_calc[df_calc["SO"] == target].index
    res["Rank_AI"] = int(idx_ai[0]) + 1 if len(idx_ai) > 0 else "N/A"
    
    # Tính Rank cho từng app A1-A6
    for i in [1,2,3,4,5,6]:
        col = f"A{i}"
        df_sub = df_calc.sort_values(col).reset_index()
        s_idx = df_sub[df_sub["SO"] == target].index
        res[f"Rank_A{i}"] = int(s_idx[0]) + 1 if len(s_idx) > 0 else 50

    db["history"].insert(0, res)
    db["last_gdb"] = gdb_val
    if ocr_list: db["raw_107"] = (ocr_list + [0]*107)[:107]

# --- 7. GIAO DIỆN ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG LỤC HỢP V8.5")
    up_json = st.file_uploader("Nạp Data (.json):", type="json")
    if up_json: st.session_state.db = json.load(up_json); st.rerun()
    
    up_img = st.file_uploader("Quét ảnh kết quả:", type=["png","jpg","jpeg"])
    if up_img and st.button("🚀 QUÉT & CẬP NHẬT", type="primary", use_container_width=True):
        img = Image.open(up_img).convert('L')
        ocr_res = get_reader().readtext(np.array(img), allowlist='0123456789')
        ocr_n, gdb_n = [], ""
        for (bbox, txt, prob) in ocr_res:
            if 5 <= len(txt) <= 6 and not gdb_n: gdb_n = txt
            for d in txt: ocr_n.append(int(d))
        if gdb_n: process_update_v6(gdb_n, ocr_n); st.rerun()
    
    st.checkbox("Chế độ Tự học AI", value=True, key="auto_mode")
    if st.button("❌ RESET ALL"): st.session_state.clear(); st.rerun()

st.title("🛡️ TUAN PHONG COMMAND CENTER V8.5")

if st.session_state.db["last_gdb"]:
    db = st.session_state.db
    current_w = brain_dynamic_weights_v6()
    df_master = calculate_6_engines(db["last_gdb"], db["raw_107"], tuple(current_w), str(db["pts"]))
    
    t1, t2, t3 = st.tabs(["🎯 DÀN KHUYÊN DÙNG", "📊 SOI CHI TIẾT", "🕒 NHẬT KÝ 6 APP"])
    
    with t1:
        st.write(f"### 🛡️ Kỳ hiện tại: **{db['last_gdb']}**")
        c1, c2 = st.columns([1, 2])
        with c1:
            n_kd = st.number_input("Số quân:", 1, 100, 51)
            st.write("**Trọng số động 6 App:**")
            w_disp = pd.DataFrame({"App": [f"A{i}" for i in range(1,7)], "W%": [round(x,1) for x in current_w]})
            st.dataframe(w_disp.set_index("App").T, use_container_width=True)
        with c2:
            st.subheader("🔥 DÀN AI TỐI ƯU")
            st.markdown(f"<div class='main-box'>{' '.join(df_master.head(n_kd)['SO'].tolist())}</div>", unsafe_allow_html=True)

    with t2:
        st.subheader("Bảng điểm chi tiết của 6 Engine")
        st.dataframe(df_master, use_container_width=True)

    with t3:
        if db["history"]:
            st.subheader("🕒 Đối soát Rank chi tiết 6 App")
            df_h = pd.DataFrame(db["history"])
            # Đảm bảo hiển thị đủ các cột Rank
            cols_show = ['Kỳ', 'GĐB', 'Số', 'Rank_AI', 'Rank_A1', 'Rank_A2', 'Rank_A3', 'Rank_A4', 'Rank_A5', 'Rank_A6', 'Time']
            st.table(df_h[cols_show])

with st.sidebar:
    st.divider()
    st.download_button("💾 SAO LƯU DATA", json.dumps(st.session_state.db), "LUC_HOP_V85.json", use_container_width=True)
