import streamlit as st
import pandas as pd
import numpy as np
import json
import easyocr
from PIL import Image, ImageEnhance
import cv2

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="TUAN PHONG - V9.0 FIXED", layout="wide")
st.markdown("""
    <style>
    .main-box { background-color: #0f172a; color: #fbbf24; padding: 20px; border-radius: 12px; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; border-left: 8px solid #fbbf24; margin-bottom: 20px; line-height: 1.6; }
    .stTable td { font-weight: bold; font-size: 11px !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# [Các hằng số BONG, BO_MAP giữ nguyên như bản cũ để đảm bảo logic App 5]
BONG_DUONG = {0:5, 1:6, 2:7, 3:8, 4:9, 5:0, 6:1, 7:2, 8:3, 9:4}
BONG_AM = {0:7, 1:4, 2:9, 3:6, 4:1, 5:8, 6:3, 7:0, 8:5, 9:2}

# --- 2. KHỞI TẠO STATE ---
if 'db' not in st.session_state:
    st.session_state.db = {
        "history": [], "last_gdb": "", "raw_107": [0]*107,
        "pts": {f"app{i}": [{"d":1,"u":1,"t":1,"h":1,"c":1} for _ in range(120)] for i in range(1, 7)},
        "pts_app5": { "dau": [1]*10, "duoi": [1]*10, "tong": [1]*10, "bo": [1]*15 },
        "weights": [16.6] * 6, "auto_mode": True
    }

# Load OCR model một lần duy nhất
@st.cache_resource
def load_ocr_model():
    return easyocr.Reader(['en'], gpu=False)

# --- 3. HÀM QUÉT ẢNH CẢI TIẾN (FIX LỖI KHÔNG CHẠY) ---
def perform_ocr_scan(image_file):
    reader = load_ocr_model()
    # Tiền xử lý ảnh để OCR đọc chuẩn và nhanh hơn
    img = Image.open(image_file).convert('L') # Chuyển xám
    img = ImageEnhance.Contrast(img).enhance(2.5) # Tăng tương phản
    img_np = np.array(img)
    
    # Quét ảnh
    results = reader.readtext(img_np, allowlist='0123456789')
    
    ocr_numbers = []
    detected_gdb = ""
    for (bbox, text, prob) in results:
        clean_text = "".join([d for d in text if d.isdigit()])
        if clean_text:
            # Ưu tiên tìm GĐB 5-6 số
            if not detected_gdb and 5 <= len(clean_text) <= 6:
                detected_gdb = clean_text
            for char in clean_text:
                ocr_numbers.append(int(char))
                
    return detected_gdb, ocr_numbers

# --- 4. ENGINE TỔNG LỰC (A4 LÊN - A6 XUỐNG) ---
@st.cache_data
def calculate_master_v9(last_gdb, raw_107, weights, pts_str, pts_a5_str):
    ocr_pos = np.array(raw_107)
    math_pos = np.array(build_math_100(last_gdb))
    p5 = json.loads(pts_a5_str)
    pts_main = json.loads(pts_str)
    
    data = []
    for i in range(100):
        d, u = i//10, i%10
        s1 = np.sum(ocr_pos == d) + np.sum(ocr_pos == u)
        
        # TÁCH BIỆT A4 & A6
        # A4: Tịnh Tiến (Đuổi cầu - Nghịch đảo điểm khan)
        khan_raw = sum([pts_main["app4"][idx]["d"] for idx in range(100) if math_pos[idx] == d])
        s4 = 100 - khan_raw 
        # A6: Top Gan (Phục kích - Giữ nguyên điểm khan)
        s6 = khan_raw
        
        # A5: App 5 10 Biến Pro (Thuộc tính số)
        s5 = p5['dau'][d] + p5['duoi'][u] # Điểm thuộc tính nguyên bản
        
        data.append({"SO": f"{i:02d}", "A1": s1, "A2": s1*1.1, "A3": s1*0.9, "A4": s4, "A5": s5, "A6": s6})
    
    df = pd.DataFrame(data)
    w = weights
    df["DIEM_TONG"] = (df["A1"]*w[0] + df["A2"]*w[1] + df["A3"]*w[2] + df["A4"]*w[3] + df["A5"]*w[4] + df["A6"]*w[5]) / 100
    return df.sort_values("DIEM_TONG").reset_index(drop=True)

def build_math_100(gdb_str):
    if not gdb_str: return [0]*100
    digits = [int(x) for x in gdb_str[-5:]]
    tien = []; [tien.extend([(d+s)%10 for d in digits]) for s in range(10)]
    bong = []; curr = digits
    for i in range(10):
        bong.extend(curr)
        curr = [BONG_DUONG[x] for x in curr] if i % 2 == 0 else [BONG_AM[x] for x in curr]
    return tien[:50] + bong[:50]

# --- 5. HÀM CẬP NHẬT KỲ MỚI ---
def run_update_cycle(gdb_val, ocr_list):
    db = st.session_state.db
    # Tính Rank dựa trên logic kỳ cũ trước khi ghi đè
    df_calc = calculate_master_v9(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts"]), json.dumps(db["pts_app5"]))
    
    target = gdb_val[-2:]
    res = {"Kỳ": len(db["history"])+1, "GĐB": gdb_val, "Số": target, "Time": datetime.now().strftime("%H:%M")}
    
    if df_calc is not None:
        idx_ai = df_calc[df_calc["SO"] == target].index
        res["Rank_AI"] = int(idx_ai[0]) + 1 if len(idx_ai) > 0 else "N/A"
        for i in [1,2,3,4,5,6]:
            df_sub = df_calc.sort_values(f"A{i}").reset_index()
            s_idx = df_sub[df_sub["SO"] == target].index
            res[f"Rank_A{i}"] = int(s_idx[0]) + 1 if len(s_idx) > 0 else 50

    db["history"].insert(0, res)
    db["last_gdb"] = gdb_val
    db["raw_107"] = (ocr_list + [0]*107)[:107]

# --- 6. GIAO DIỆN CHÍNH ---
st.title("🛡️ TUAN PHONG COMMAND CENTER V9.0")

with st.sidebar:
    st.header("⚡ HỆ THỐNG NẠP DỮ LIỆU")
    up_json = st.file_uploader("Nạp Data (.json):", type="json")
    if up_json: 
        st.session_state.db = json.load(up_json)
        st.success("Nạp thành công!")
        st.rerun()
    
    st.divider()
    st.subheader("📸 Quét ảnh kết quả")
    img_file = st.file_uploader("Chọn ảnh hàng ngày:", type=["png","jpg","jpeg"])
    
    if img_file:
        st.image(img_file, caption="Ảnh chờ quét", use_container_width=True)
        # Nút quét được đặt riêng biệt và kiểm soát bằng State
        if st.button("🚀 BẮT ĐẦU QUÉT & CẬP NHẬT", type="primary", use_container_width=True):
            with st.spinner("Đang phân tích OCR..."):
                gdb_found, ocr_data = perform_ocr_scan(img_file)
                if gdb_found:
                    run_update_cycle(gdb_found, ocr_data)
                    st.success(f"Đã tìm thấy GĐB: {gdb_found}")
                    st.rerun()
                else:
                    st.error("Không tìm thấy GĐB trên ảnh. Hãy thử ảnh rõ nét hơn hoặc nhập tay.")

    if st.button("❌ RESET HỆ THỐNG"):
        st.session_state.clear()
        st.rerun()

# --- HIỂN THỊ KẾT QUẢ ---
if st.session_state.db["last_gdb"]:
    db = st.session_state.db
    # Tính toán dàn khuyên dùng
    df_master = calculate_master_v9(db["last_gdb"], db["raw_107"], tuple(db["weights"]), json.dumps(db["pts"]), json.dumps(db["pts_app5"]))
    
    t1, t2, t3 = st.tabs(["🎯 DÀN KHUYÊN DÙNG", "📊 SOI CHI TIẾT", "🕒 NHẬT KÝ 6 APP"])
    
    with t1:
        st.write(f"### 🛡️ Kỳ hiện tại: **{db['last_gdb']}**")
        c1, c2 = st.columns([1, 2])
        with c1:
            n_kd = st.number_input("Số quân:", 1, 100, 51)
            st.write("**Trọng số 6 App (Động):**")
            st.dataframe(pd.DataFrame({"App": [f"A{i}" for i in range(1,7)], "W%": [round(x,1) for x in db["weights"]]}).set_index("App").T, use_container_width=True)
        with c2:
            st.subheader("🔥 DÀN AI TỐI ƯU")
            st.markdown(f"<div class='main-box'>{' '.join(df_master.head(n_kd)['SO'].tolist())}</div>", unsafe_allow_html=True)

    with t3:
        st.subheader("🕒 Đối soát Rank chi tiết")
        if db["history"]:
            st.table(pd.DataFrame(db["history"])[['Kỳ', 'GĐB', 'Số', 'Rank_AI', 'Rank_A1', 'Rank_A2', 'Rank_A3', 'Rank_A4', 'Rank_A5', 'Rank_A6', 'Time']])

with st.sidebar:
    st.divider()
    st.download_button("💾 SAO LƯU DATA MỚI", json.dumps(st.session_state.db), f"LUC_HOP_V90.json", use_container_width=True)
