import streamlit as st
import pandas as pd
import numpy as np
import json
import easyocr
from PIL import Image
from datetime import datetime
import random

# --- 1. GIAO DIỆN SÁNG CHUẨN MOBILE ---
st.set_page_config(page_title="TUAN PHONG V11.2", layout="wide")
st.markdown("""
    <style>
    .main-box { 
        background-color: #ffffff; color: #334155; padding: 10px; border-radius: 8px; 
        font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; 
        border: 1.5px solid #fbbf24; margin-bottom: 10px; line-height: 1.4; font-weight: 600; 
        text-align: center; letter-spacing: 0.3px;
    }
    .stMetric { background: #f8fafc; padding: 5px; border-radius: 5px; border: 1px solid #e2e8f0; }
    .stTable td { font-weight: bold !important; text-align: center !important; font-size: 11px !important; }
    </style>
    """, unsafe_allow_html=True)

BO_MAP = {"00": [0,5,50,55], "01": [1,10,6,60,51,15,56,65], "02": [2,20,7,70,52,25,57,75], "03": [3,30,8,80,53,35,58,85], "04": [4,40,9,90,54,45,59,95], "11": [11,16,61,66], "12": [12,21,17,71,62,26,67,76], "13": [13,31,18,81,63,36,68,86], "14": [14,41,19,91,64,46,69,96], "22": [22,27,72,77], "23": [23,32,28,82,73,37,78,87], "24": [24,42,29,92,74,47,79,97], "33": [33,38,83,88], "34": [34,43,39,93,84,48,89,98], "44": [44,49,94,99]}
def get_bo_idx(n):
    for i, (k, v) in enumerate(BO_MAP.items()):
        if n in v: return i
    return 0

# --- DỮ LIỆU ĐÃ ĐƯỢC CẮT BỎ KỲ CUỐI (TỰ ĐỘNG CHÈN VÀO CODE) ---
DATA_261 = {"last_gdb": "76669", "raw_107": [7, 6, 6, 6, 9, 0, 0, 0, 0, 0] + [0]*97, "weights": [16.6, 16.6, 16.6, 16.6, 16.6, 16.6], "auto_mode": True, "pts_vi_tri": {f"app{i}": [{"d":1,"u":1} for _ in range(120)] for i in [1,2,3,4,6]}, "pts_thuoc_tinh": {"dau": [34, 5, 6, 3, 8, 12, 2, 16, 39, 1], "duoi": [9, 10, 7, 4, 1, 16, 22, 5, 3, 2], "bo": [29, 12, 16, 30, 9, 45, 5, 32, 2, 46, 6, 7, 3, 23, 1], "tong": [13, 3, 16, 1, 9, 2, 4, 27, 5, 18]}, "history": [{"Kỳ": 43, "GĐB": "76669", "Số": "69", "Time": "Thứ năm ngày 14-05-2026", "Rank_AI": 48, "Rank_A1": 76, "Rank_A2": 24, "Rank_A3": 46, "Rank_A4": 57, "Rank_A5": 45, "Rank_A6": 41}]}

if 'db' not in st.session_state or st.session_state.db["last_gdb"] == "":
    st.session_state.db = DATA_261

@st.cache_resource
def load_ocr(): return easyocr.Reader(['en'], gpu=False)

def build_math_100(gdb_str):
    if not gdb_str or len(str(gdb_str)) < 5: return [0]*100
    d = [int(x) for x in str(gdb_str)[-5:]]
    res = []
    for s in range(20): res.extend([(x+s)%10 for x in d])
    return res[:100]

def update_ai_weights_v112():
    db = st.session_state.db
    if len(db["history"]) < 1: return [16.6] * 6
    return [16.6] * 6

@st.cache_data
def calculate_master_v112(last_gdb, raw_107, weights, pts_vtri_str, pts_tt_str):
    ocr_pos, math_pos = np.array(raw_107), np.array(build_math_100(last_gdb))
    p_vtri = json.loads(pts_vtri_str)
    p_tt = json.loads(pts_tt_str)
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

def find_rank_unique(df, target, col):
    temp = df[['SO', col]].sort_values(by=[col, 'SO'], ascending=[True, True]).reset_index(drop=True)
    match = temp[temp['SO'] == target].index
    return int(match[0]) + 1 if len(match) > 0 else 50

def update_logic_v112(gdb_new):
    db = st.session_state.db
    target_num = int(gdb_new[-2:])
    d, u, t = target_num//10, target_num%10, (target_num//10 + target_num%10)%10
    b_idx = get_bo_idx(target_num)
    for i in range(10):
        db["pts_thuoc_tinh"]["dau"][i] = 1 if i == d else db["pts_thuoc_tinh"]["dau"][i] + 1
        db["pts_thuoc_tinh"]["duoi"][i] = 1 if i == u else db["pts_thuoc_tinh"]["duoi"][i] + 1
        db["pts_thuoc_tinh"]["tong"][i] = 1 if i == t else db["pts_thuoc_tinh"]["tong"][i] + 1
    for i in range(15):
        db["pts_thuoc_tinh"]["bo"][i] = 1 if i == b_idx else db["pts_thuoc_tinh"]["bo"][i] + 1

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ QUẢN LÝ")
    up_json = st.file_uploader("📂 Nạp file .json mới:", type="json")
    if up_json:
        st.session_state.db = json.load(up_json)
        st.success("✅ ĐÃ KÍCH HOẠT DỮ LIỆU!")
        st.rerun()
        
    st.divider()
    st.header("📸 QUÉT ẢNH KỲ MỚI")
    img_file = st.file_uploader("Chọn ảnh kết quả:", type=["png","jpg","jpeg"])
    if img_file:
        st.image(img_file, use_container_width=True)
        if st.button("🚀 QUÉT & PHÂN TÍCH AI", type="primary"):
            reader = load_ocr()
            res_ocr = reader.readtext(np.array(Image.open(img_file).convert('L')), allowlist='0123456789')
            ocr_n, gdb_n = [], ""
            for (bbox, txt, prob) in res_ocr:
                if 5 <= len(txt) <= 6 and not gdb_n: gdb_n = txt
                for d in txt: ocr_n.append(int(d))
            if gdb_n:
                db = st.session_state.db
                if db["last_gdb"]:
                    df_old = calculate_master_v112(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts_vi_tri"]), json.dumps(db["pts_thuoc_tinh"]))
                    target = gdb_n[-2:]
                    res = {"Kỳ": len(db["history"])+1, "GĐB": gdb_n, "Số": target, "Time": datetime.now().strftime("%H:%M")}
                    res["Rank_AI"] = find_rank_unique(df_old, target, "DIEM_TONG")
                    for i in range(1, 7): res[f"Rank_A{i}"] = find_rank_unique(df_old, target, f"A{i}")
                    db["history"].insert(0, res)
                
                update_logic_v112(gdb_n)
                db["last_gdb"], db["raw_107"] = gdb_n, (ocr_n + [0]*107)[:107]
                st.rerun()

    st.divider()
    if st.button("🔴 RESET ALL DATA", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --- HIỂN THỊ ---
db = st.session_state.db
if db["last_gdb"]:
    active_w = update_ai_weights_v112()
    df_m = calculate_master_v112(db["last_gdb"], db["raw_107"], tuple(active_w), json.dumps(db["pts_vi_tri"]), json.dumps(db["pts_thuoc_tinh"]))
    t1, t2, t3 = st.tabs(["🎯 DÀN AI TỐI ƯU", "📊 ĐỐI TRỌNG ENGINE", "🕒 NHẬT KÝ CHI TIẾT"])
    
    with t1:
        c1, c2 = st.columns(2)
        c1.metric("Kỳ hiện tại trong máy", db['last_gdb'])
        n_kd = c2.number_input("Số quân:", 1, 100, 51)
        st.write("---")
        danh_sach = df_m.sort_values("DIEM_TONG").head(n_kd)['SO'].tolist()
        st.markdown(f"<div class='main-box'>{' '.join(danh_sach)}</div>", unsafe_allow_html=True)
        
    with t2:
        st.subheader("⚖️ Tỷ Trọng Quyết Định Hiện Tại")
        w_df = pd.DataFrame({"Engine": [f"App {i}" for i in range(1,7)], "Đối trọng (%)": [round(x,1) for x in active_w]})
        st.table(w_df.set_index("Engine").T)
        st.divider()
        # NÚT THẦN THÁNH: ẤN VÀO ĐÂY LÀ ĐIỆN THOẠI TỰ TẢI FILE JSON 261 KỲ VỀ!
        st.download_button("💾 XUẤT BACKUP DATA (.JSON) - BẤM ĐỂ TẢI FILE 261 KỲ", json.dumps(db), "LUC_HOP_261_DAYS.json", use_container_width=True)

    with t3:
        if db["history"]:
            st.table(pd.DataFrame(db["history"])[['Kỳ', 'GĐB', 'Số', 'Rank_AI', 'Rank_A1', 'Rank_A2', 'Rank_A3', 'Rank_A4', 'Rank_A5', 'Rank_A6', 'Time']])
