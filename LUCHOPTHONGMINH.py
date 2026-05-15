import streamlit as st
import pandas as pd
import numpy as np
import json
import easyocr
from PIL import Image
from datetime import datetime
import random # Thêm để tạo nhiễu phân hóa rank

# --- 1. CẤU HÌNH ---
st.set_page_config(page_title="TUAN PHONG - V9.8 INDEPENDENT", layout="wide")
st.markdown("""<style>.main-box { background-color: #0f172a; color: #fbbf24; padding: 20px; border-radius: 12px; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; border-left: 8px solid #fbbf24; margin-bottom: 20px; line-height: 1.6; } .stTable td { font-weight: bold; font-size: 11px !important; text-align: center !important; }</style>""", unsafe_allow_html=True)

# --- 2. LOGIC APP 5 GỐC ---
BO_MAP = {"00": [0,5,50,55], "01": [1,10,6,60,51,15,56,65], "02": [2,20,7,70,52,25,57,75], "03": [3,30,8,80,53,35,58,85], "04": [4,40,9,90,54,45,59,95], "11": [11,16,61,66], "12": [12,21,17,71,62,26,67,76], "13": [13,31,18,81,63,36,68,86], "14": [14,41,19,91,64,46,69,96], "22": [22,27,72,77], "23": [23,32,28,82,73,37,78,87], "24": [24,42,29,92,74,47,79,97], "33": [33,38,83,88], "34": [34,43,39,93,84,48,89,98], "44": [44,49,94,99]}

def get_bo_idx(n):
    for i, (k, v) in enumerate(BO_MAP.items()):
        if n in v: return i
    return 0

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

# --- 3. ENGINE TÍNH ĐIỂM ĐỘC LẬP TUYỆT ĐỐI ---
@st.cache_data
def calculate_master_v98(last_gdb, raw_107, weights, pts_vtri_str, pts_tt_str):
    ocr_pos = np.array(raw_107)
    math_pos = np.array(build_math_100(last_gdb))
    p_vtri = json.loads(pts_vtri_str)
    p_tt = json.loads(pts_tt_str)
    
    # Khởi tạo mảng điểm riêng biệt, thêm nhiễu ngẫu nhiên siêu nhỏ để ép lệch Rank
    s1, s2, s3, s4, s5, s6 = [np.zeros(100) for _ in range(6)]
    
    for i in range(100):
        d, u, t = i//10, i%10, (i//10 + i%10)%10
        # Nhóm Vị Trí OCR (Thêm nhiễu phân hóa)
        s1[i] = np.sum(ocr_pos == d) * 10 + (random.random() * 0.1)
        s2[i] = np.sum(ocr_pos == u) * 10 + (random.random() * 0.1)
        s3[i] = np.sum(ocr_pos == t) * 10 + (random.random() * 0.1)
        
        # Nhóm Toán học (A4-Tịnh tiến vs A6-Top Gan)
        k_raw = sum([p_vtri["app4"][idx]["d"] for idx in range(100) if math_pos[idx] == d])
        s4[i] = 1000 - k_raw + (random.random() * 0.1)
        s6[i] = k_raw + (random.random() * 0.1)
        
        # Nhóm Thuộc tính (A5 - 10 Biến Pro)
        s5[i] = p_tt['dau'][d]*10 + p_tt['duoi'][u]*8 + p_tt['bo'][get_bo_idx(i)]*15 + (random.random() * 0.1)
        
    df = pd.DataFrame({
        "SO": [f"{i:02d}" for i in range(100)],
        "A1": s1, "A2": s2, "A3": s3, "A4": s4, "A5": s5, "A6": s6
    })
    
    # Tính điểm tổng hợp dựa trên Trọng số
    w = weights
    df["DIEM_TONG"] = (df["A1"]*w[0] + df["A2"]*w[1] + df["A3"]*w[2] + df["A4"]*w[3] + df["A5"]*w[4] + df["A6"]*w[5]) / 6
    return df

# --- 4. HÀM TÌM RANK THỦ CÔNG (CHỐNG TRÙNG) ---
def find_rank_final(df, target, col):
    # Sắp xếp và ép lấy index duy nhất
    temp = df[['SO', col]].sort_values(by=[col, 'SO'], ascending=[True, True]).reset_index(drop=True)
    match = temp[temp['SO'] == target].index
    return int(match[0]) + 1 if len(match) > 0 else 50

def process_update(gdb_val, ocr_data=None):
    db = st.session_state.db
    if db["last_gdb"]:
        # Luôn tính toán dựa trên dữ liệu kỳ TRƯỚC để xem số kỳ này nằm ở Rank nào
        df_old = calculate_master_v98(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts_vi_tri"]), json.dumps(db["pts_thuoc_tinh"]))
        target = gdb_val[-2:]
        res = {"Kỳ": len(db["history"])+1, "GĐB": gdb_val, "Số": target, "Time": datetime.now().strftime("%H:%M")}
        
        # Ép tính Rank độc lập từng cột
        res["Rank_AI"] = find_rank_final(df_old, target, "DIEM_TONG")
        res["Rank_A1"] = find_rank_final(df_old, target, "A1")
        res["Rank_A2"] = find_rank_final(df_old, target, "A2")
        res["Rank_A3"] = find_rank_final(df_old, target, "A3")
        res["Rank_A4"] = find_rank_final(df_old, target, "A4")
        res["Rank_A5"] = find_rank_final(df_old, target, "A5")
        res["Rank_A6"] = find_rank_final(df_old, target, "A6")
        db["history"].insert(0, res)

    db["last_gdb"] = gdb_val
    if ocr_data: db["raw_107"] = (ocr_data + [0]*107)[:107]

# --- 5. GIAO DIỆN ---
st.title("🛡️ TUAN PHONG V9.8 - ANTI-DUPLICATE RANK")
with st.sidebar:
    up_json = st.file_uploader("Nạp Data:", type="json")
    if up_json: st.session_state.db = json.load(up_json); st.rerun()
    img_file = st.file_uploader("Quét ảnh:", type=["png","jpg","jpeg"])
    if img_file:
        st.image(img_file, use_container_width=True)
        if st.button("🚀 QUÉT & CẬP NHẬT", type="primary"):
            res_ocr = load_ocr().readtext(np.array(Image.open(img_file).convert('L')), allowlist='0123456789')
            ocr_n, gdb_n = [], ""
            for (bbox, txt, prob) in res_ocr:
                if 5 <= len(txt) <= 6 and not gdb_n: gdb_n = txt
                for d in txt: ocr_n.append(int(d))
            if gdb_n: process_update(gdb_n, ocr_n); st.rerun()

if st.session_state.db["last_gdb"]:
    db = st.session_state.db
    df_res = calculate_master_v98(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts_vi_tri"]), json.dumps(db["pts_thuoc_tinh"]))
    t1, t2, t3 = st.tabs(["🎯 DÀN KHUYÊN DÙNG", "📊 SOI CHI TIẾT", "🕒 NHẬT KÝ 6 APP"])
    with t1:
        n_kd = st.number_input("Số quân:", 1, 100, 51)
        danh_sach = df_res.sort_values("DIEM_TONG").head(n_kd)['SO'].tolist()
        st.markdown(f"<div class='main-box'>{' '.join(danh_sach)}</div>", unsafe_allow_html=True)
    with t2: st.dataframe(df_res.sort_values("DIEM_TONG"), use_container_width=True)
    with t3:
        if db["history"]: st.table(pd.DataFrame(db["history"])[['Kỳ', 'GĐB', 'Số', 'Rank_AI', 'Rank_A1', 'Rank_A2', 'Rank_A3', 'Rank_A4', 'Rank_A5', 'Rank_A6', 'Time']])

with st.sidebar:
    st.download_button("💾 SAO LƯU", json.dumps(st.session_state.db), "LUC_HOP_V98.json", use_container_width=True)
