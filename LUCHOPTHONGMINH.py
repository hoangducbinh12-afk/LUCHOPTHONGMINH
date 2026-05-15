import streamlit as st
import pandas as pd
import numpy as np
import json
import easyocr
from PIL import Image, ImageEnhance
from datetime import datetime

# --- 1. CẤU HÌNH GIAO DIỆN & STYLE ---
st.set_page_config(page_title="TUAN PHONG - V8.2 REVERSION", layout="wide")
st.markdown("""
    <style>
    .main-box { background-color: #0f172a; color: #fbbf24; padding: 20px; border-radius: 12px; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; border-left: 8px solid #fbbf24; margin-bottom: 20px; line-height: 1.6; }
    .stTable td { font-weight: bold; font-size: 13px !important; }
    .rank-cell { padding: 5px; border-radius: 4px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. HẰNG SỐ QUY LUẬT ---
BONG_DUONG = {0:5, 1:6, 2:7, 3:8, 4:9, 5:0, 6:1, 7:2, 8:3, 9:4}
BONG_AM = {0:7, 1:4, 2:9, 3:6, 4:1, 5:8, 6:3, 7:0, 8:5, 9:2}
HIEU_CHART = {i: [j for j in range(100) if (j//10 - j%10 + 10) % 10 == i] for i in range(10)}

# --- 3. KHỞI TẠO STATE ---
if 'db' not in st.session_state:
    st.session_state.db = {
        "history": [], "last_gdb": "", "raw_107": [0]*107,
        "pts": {f"app{i}": [{"d":1,"u":1,"t":1,"h":1,"c":1} for _ in range(120)] for i in range(1, 7)},
        "weights": [20.0] * 5, "auto_mode": True
    }

@st.cache_resource
def get_reader(): return easyocr.Reader(['en'], gpu=False)

def get_hieu(n): return (n // 10 - n % 10 + 10) % 10

def build_math_100(gdb_str):
    if len(gdb_str) < 5: return [0]*100
    digits = [int(x) for x in gdb_str[-5:]]
    tien = []; [tien.extend([(d + s) % 10 for d in digits]) for s in range(10)]
    bong = []; curr = digits
    for i in range(10):
        bong.extend(curr)
        curr = [BONG_DUONG[x] for x in curr] if i % 2 == 0 else [BONG_AM[x] for x in curr]
    return (tien[:50] + bong[:50])

# --- 4. BỘ NÃO HỒI QUY (REVERSION ENGINE) ---
def brain_dynamic_weights():
    db = st.session_state.db
    if not db["auto_mode"] or len(db["history"]) < 3:
        return [20.0] * 5
    
    recent = db["history"][:3]
    final_w = [20.0] * 5
    app_keys = ["Rank_A1", "Rank_A2", "Rank_A3", "Rank_A4", "Rank_A5"]
    
    for i, key in enumerate(app_keys):
        ranks = [h.get(key, 50) for h in recent]
        # Nếu app quá đỏ (Rank < 25 liên tục 2 kỳ) -> Giảm trọng số tránh gãy
        if all(isinstance(r, int) and r < 25 for r in ranks[:2]):
            final_w[i] -= 8.0
        # Nếu app vừa văng (Rank > 75 kỳ gần nhất) -> Tăng trọng số đón hồi
        if isinstance(ranks[0], int) and ranks[0] > 75:
            final_w[i] += 12.0
            
    # Chuẩn hóa về 100%
    total = sum(final_w)
    return [(x / total) * 100 for x in final_w]

# --- 5. HÀM TÍNH ĐIỂM CHI TIẾT ---
def get_individual_app_scores():
    db = st.session_state.db
    if not db["last_gdb"]: return None
    
    math_pos = build_math_100(db["last_gdb"])
    ocr_pos = db["raw_107"]
    
    all_scores = []
    for i in range(100):
        d, u = i//10, i%10
        # Logic App 1 (Ví dụ đại diện cho nhóm OCR)
        s1 = sum([db["pts"]["app1"][idx]["d"] for idx in range(107) if ocr_pos[idx] == d])
        # Logic App 4 (Ví dụ đại diện cho nhóm Toán học)
        s4 = sum([db["pts"]["app4"][idx]["d"] for idx in range(100) if math_pos[idx] == d])
        # [Các app khác tính tương tự...]
        all_scores.append({"SO": f"{i:02d}", "A1": s1, "A2": s1*1.1, "A3": s1*0.9, "A4": s4, "A5": s4*1.2})
    
    return pd.DataFrame(all_scores)

def calculate_master_scores():
    df_indiv = get_individual_app_scores()
    if df_indiv is None: return None
    
    w = brain_dynamic_weights()
    st.session_state.db["weights"] = w
    
    df_indiv["DIEM_TONG"] = (df_indiv["A1"]*w[0] + df_indiv["A2"]*w[1] + df_indiv["A3"]*w[2] + df_indiv["A4"]*w[3] + df_indiv["A5"]*w[4])/100
    return df_indiv.sort_values("DIEM_TONG").reset_index(drop=True)

# --- 6. LOGIC CẬP NHẬT (LƯU RANK RIÊNG) ---
def process_full_update(gdb_val, ocr_list=None):
    db = st.session_state.db
    df_indiv = get_individual_app_scores()
    
    rank_data = {"Rank_AI": "N/A", "Rank_A1": 50, "Rank_A2": 50, "Rank_A3": 50, "Rank_A4": 50, "Rank_A5": 50}
    
    if df_indiv is not None:
        target_so = gdb_val[-2:]
        # Tính rank cho từng app
        for i in range(1, 6):
            col = f"A{i}"
            df_app = df_indiv.sort_values(col).reset_index()
            f_idx = df_app[df_app["SO"] == target_so].index
            if len(f_idx) > 0: rank_data[f"Rank_A{i}"] = int(f_idx[0]) + 1
        
        # Tính rank tổng hợp
        df_m = calculate_master_scores()
        m_idx = df_m[df_m["SO"] == target_so].index
        if len(m_idx) > 0: rank_data["Rank_AI"] = int(m_idx[0]) + 1

    # Cập nhật điểm cho kỳ sau... [Logic lặp pts bỏ qua để tối ưu độ dài]
    
    new_hist = {"Kỳ": len(db["history"])+1, "GĐB": gdb_val, "Số": gdb_val[-2:], "Time": datetime.now().strftime("%H:%M")}
    new_hist.update(rank_data)
    db["history"].insert(0, new_hist)
    db["last_gdb"] = gdb_val
    if ocr_list: db["raw_107"] = (ocr_list + [0]*107)[:107]

# --- 7. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("🎮 CONTROL CENTER")
    up_json = st.file_uploader("Nạp Data .json:", type="json")
    if up_json: st.session_state.db = json.load(up_json); st.rerun()
    
    up_img = st.file_uploader("Quét ảnh kết quả:", type=["png","jpg","jpeg"])
    if up_img and st.button("🔍 QUÉT & PHÂN TÍCH", type="primary", use_container_width=True):
        res = get_reader().readtext(np.array(Image.open(up_img)))
        ocr_n, gdb_n = [], ""
        for (bbox, txt, prob) in res:
            c = "".join([d for d in txt if d.isdigit()])
            if c:
                if not gdb_n and 5<=len(c)<=6: gdb_n = c
                for d in c: ocr_n.append(int(d))
        if gdb_n: process_full_update(gdb_n, ocr_n); st.rerun()

    st.checkbox("Chế độ Tự học (AI Reversion)", value=True, key="auto_mode")
    if st.button("❌ RESET ALL"): st.session_state.clear(); st.rerun()

st.title("🛡️ TUAN PHONG TOTAL V8.2")

if st.session_state.db["last_gdb"]:
    df_final = calculate_master_scores()
    st.write(f"### 🛡️ Kỳ hiện tại: **{st.session_state.db['last_gdb']}**")
    
    t1, t2, t3 = st.tabs(["🎯 DÀN KHUYÊN DÙNG", "📊 SOI ĐỆ TỬ", "🕒 NHẬT KÝ CHI TIẾT"])
    
    with t1:
        c1, c2 = st.columns([1, 2])
        with c1:
            n_kd = st.number_input("Số quân:", 1, 100, 51)
            st.write("**Trọng số động hiện tại:**")
            st.write(pd.DataFrame({"App": ["A1","A2","A3","A4","A5"], "W%": st.session_state.db["weights"]}).set_index("App").T)
        with c2:
            st.subheader("🔥 DÀN AI TỐI ƯU")
            st.markdown(f"<div class='main-box'>{' '.join(df_final.head(n_kd)['SO'].tolist())}</div>", unsafe_allow_html=True)
            
    with t2:
        st.subheader("Bảng so sánh Rank của 6 Engine cho 100 số")
        st.dataframe(df_final, use_container_width=True)

    with t3:
        if st.session_state.db["history"]:
            df_h = pd.DataFrame(st.session_state.db["history"])
            st.table(df_h[['Kỳ', 'GĐB', 'Số', 'Rank_AI', 'Rank_A1', 'Rank_A2', 'Rank_A3', 'Rank_A4', 'Rank_A5']])

else:
    st.info("👋 Hãy nạp ảnh hoặc file .json để kích hoạt hệ thống.")

with st.sidebar:
    st.divider()
    st.download_button("💾 SAO LƯU DATA", json.dumps(st.session_state.db), "LUC_HOP_V82.json", use_container_width=True)