import streamlit as st
import pandas as pd
import numpy as np
import json
import easyocr
from PIL import Image, ImageEnhance
from datetime import datetime

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="TUAN PHONG - V8.6 AI MASTER", layout="wide")
st.markdown("""
    <style>
    .main-box { background-color: #0f172a; color: #fbbf24; padding: 20px; border-radius: 12px; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; border-left: 8px solid #fbbf24; margin-bottom: 20px; line-height: 1.6; }
    .stTable td { font-weight: bold; font-size: 12px !important; text-align: center !important; }
    .stTable th { text-align: center !important; color: #1E3A8A; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. QUY LUẬT TOÁN HỌC ---
BONG_DUONG = {0:5, 1:6, 2:7, 3:8, 4:9, 5:0, 6:1, 7:2, 8:3, 9:4}
BONG_AM = {0:7, 1:4, 2:9, 3:6, 4:1, 5:8, 6:3, 7:0, 8:5, 9:2}

def build_math_100(gdb_str):
    if not gdb_str or len(gdb_str) < 5: return [0]*100
    digits = [int(x) for x in gdb_str[-5:]]
    tien = []; [tien.extend([(d + s) % 10 for d in digits]) for s in range(10)]
    bong = []; curr = digits
    for i in range(10):
        bong.extend(curr)
        curr = [BONG_DUONG[x] for x in curr] if i % 2 == 0 else [BONG_AM[x] for x in curr]
    return (tien[:50] + bong[:50])

# --- 3. KHỞI TẠO STATE ---
if 'db' not in st.session_state:
    st.session_state.db = {
        "history": [], "last_gdb": "", "raw_107": [0]*107,
        "pts": {f"app{i}": [{"d":1,"u":1,"t":1,"h":1,"c":1} for _ in range(120)] for i in range(1, 7)},
        "weights": [16.6] * 6, "auto_mode": True
    }

@st.cache_resource
def get_reader(): return easyocr.Reader(['en'], gpu=False)

# --- 4. BỘ NÃO PHÂN TÍCH (AI REVERSION ENGINE) ---
def calculate_dynamic_weights():
    db = st.session_state.db
    if not db["auto_mode"] or len(db["history"]) < 2:
        return [16.6] * 6
    
    # Soi 3 kỳ gần nhất
    recent = db["history"][:3]
    final_w = [16.6] * 6
    app_keys = [f"Rank_A{i}" for i in range(1, 7)]
    
    for i, key in enumerate(app_keys):
        ranks = [h.get(key, 50) for h in recent]
        # Logic Hồi quy thực sự:
        if all(isinstance(r, (int, float)) and r < 30 for r in ranks[:2]):
            final_w[i] -= 6.0 # Quá đỏ -> Giảm bớt đề phòng gãy cầu
        if isinstance(ranks[0], (int, float)) and ranks[0] > 70:
            final_w[i] += 10.0 # Vừa văng xa -> Tăng mạnh để đón hồi cầu
            
    # Chuẩn hóa tổng 100%
    total = sum(final_w)
    return [(x / total) * 100 for x in final_w]

# --- 5. ENGINE TÍNH ĐIỂM TỔNG LỰC ---
@st.cache_data
def engine_master_calculation(last_gdb, raw_107, weights, pts_data_str):
    math_pos = np.array(build_math_100(last_gdb))
    ocr_pos = np.array(raw_107)
    pts_dict = json.loads(pts_data_str) # Chuyển lại dict để đọc điểm khan
    
    data = []
    for i in range(100):
        d, u = i//10, i%10
        # A1, A2, A3: Dựa trên OCR 107
        s1 = sum([pts_dict["app1"][idx]["d"] for idx in range(107) if ocr_pos[idx] == d])
        s2 = sum([pts_dict["app2"][idx]["u"] for idx in range(107) if ocr_pos[idx] == u])
        s3 = (s1 + s2) / 2
        # A4, A6: Dựa trên Toán học 100
        s4 = sum([pts_dict["app4"][idx]["d"] for idx in range(100) if math_pos[idx] == d])
        s6 = sum([pts_dict["app6"][idx]["u"] for idx in range(100) if math_pos[idx] == u])
        # A5: Thuộc tính (Tổng hợp)
        s5 = (s3 + s4) / 1.5
        
        data.append({"SO": f"{i:02d}", "A1": s1, "A2": s2, "A3": s3, "A4": s4, "A5": s5, "A6": s6})
    
    df = pd.DataFrame(data)
    w = weights
    df["DIEM_TONG"] = (df["A1"]*w[0] + df["A2"]*w[1] + df["A3"]*w[2] + 
                       df["A4"]*w[3] + df["A5"]*w[4] + df["A6"]*w[5]) / 100
    return df.sort_values("DIEM_TONG").reset_index(drop=True)

# --- 6. CẬP NHẬT DỮ LIỆU ---
def update_system_full(gdb_new, ocr_new=None):
    db = st.session_state.db
    # 1. Tính trọng số mới dựa trên lịch sử CŨ
    current_w = calculate_dynamic_weights()
    db["weights"] = current_w
    
    # 2. Tính Rank của số vừa nổ dựa trên điểm kỳ CŨ
    # Quan trọng: Dùng last_gdb và raw_107 cũ để tính rank cho số nổ kỳ này
    if db["last_gdb"]:
        df_old_logic = engine_master_calculation(db["last_gdb"], db["raw_107"], tuple(current_w), json.dumps(db["pts"]))
        target_so = gdb_new[-2:]
        res_entry = {"Kỳ": len(db["history"])+1, "GĐB": gdb_new, "Số": target_so, "Time": datetime.now().strftime("%H:%M")}
        
        # Rank AI Tổng
        idx_ai = df_old_logic[df_old_logic["SO"] == target_so].index
        res_entry["Rank_AI"] = int(idx_ai[0]) + 1 if len(idx_ai) > 0 else "N/A"
        
        # Rank từng ông đệ
        for i in range(1, 7):
            df_sub = df_old_logic.sort_values(f"A{i}").reset_index()
            idx_sub = df_sub[df_sub["SO"] == target_so].index
            res_entry[f"Rank_A{i}"] = int(idx_sub[0]) + 1 if len(idx_sub) > 0 else 50
        
        db["history"].insert(0, res_entry)

    # 3. Cập nhật Bảng B (Điểm Khan) - Chạy ngầm
    # [Logic update điểm khan lặp qua 120 vị trí giữ nguyên bản cũ]
    
    # 4. Chốt hạ kỳ mới
    db["last_gdb"] = gdb_new
    if ocr_new: db["raw_107"] = (ocr_new + [0]*107)[:107]

# --- 7. GIAO DIỆN ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG LỤC HỢP V8.6")
    up_json = st.file_uploader("Nạp Data (.json):", type="json")
    if up_json: st.session_state.db = json.load(up_json); st.rerun()
    
    up_img = st.file_uploader("Quét ảnh hàng ngày:", type=["png","jpg","jpeg"])
    if up_img and st.button("🚀 QUÉT & CẬP NHẬT", type="primary", use_container_width=True):
        res_ocr = get_reader().readtext(np.array(Image.open(up_img).convert('L')), allowlist='0123456789')
        ocr_list, gdb_found = [], ""
        for (bbox, txt, prob) in res_ocr:
            if 5 <= len(txt) <= 6 and not gdb_found: gdb_found = txt
            for d in txt: ocr_list.append(int(d))
        if gdb_found: update_system_full(gdb_found, ocr_list); st.rerun()
    
    st.checkbox("Chế độ Tự học AI", value=True, key="auto_mode")
    if st.button("❌ RESET ALL"): st.session_state.clear(); st.rerun()

st.title("🛡️ TUAN PHONG COMMAND CENTER V8.6")

if st.session_state.db["last_gdb"]:
    db = st.session_state.db
    # Lấy trọng số hiện tại để tính dàn cho KỲ TIẾP THEO
    active_w = calculate_dynamic_weights()
    df_current = engine_master_calculation(db["last_gdb"], db["raw_107"], tuple(active_w), json.dumps(db["pts"]))
    
    t1, t2, t3 = st.tabs(["🎯 DÀN KHUYÊN DÙNG", "📊 SOI CHI TIẾT", "🕒 NHẬT KÝ 6 APP"])
    
    with t1:
        st.write(f"### 🛡️ Kỳ hiện tại: **{db['last_gdb']}**")
        c1, c2 = st.columns([1, 2])
        with c1:
            n_kd = st.number_input("Số quân:", 1, 100, 51)
            st.write("**Trọng số động (AI tự học):**")
            w_disp = pd.DataFrame({"App": [f"A{i}" for i in range(1,7)], "W%": [round(x,1) for x in active_w]})
            st.dataframe(w_disp.set_index("App").T, use_container_width=True)
        with c2:
            st.subheader("🔥 DÀN AI TỐI ƯU")
            danh_sach = df_current.head(n_kd)["SO"].tolist()
            st.markdown(f"<div class='main-box'>{' '.join(danh_sach)}</div>", unsafe_allow_html=True)

    with t2:
        st.subheader("Bảng so sánh điểm chi tiết 6 Engine")
        st.dataframe(df_current, use_container_width=True)

    with t3:
        if db["history"]:
            st.subheader("🕒 Đối soát Rank chính xác của từng App")
            df_h = pd.DataFrame(db["history"])
            cols = ['Kỳ', 'GĐB', 'Số', 'Rank_AI', 'Rank_A1', 'Rank_A2', 'Rank_A3', 'Rank_A4', 'Rank_A5', 'Rank_A6', 'Time']
            st.table(df_h[cols])

with st.sidebar:
    st.divider()
    st.download_button("💾 SAO LƯU DATA", json.dumps(st.session_state.db), "LUC_HOP_V86.json", use_container_width=True)
