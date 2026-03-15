import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
from io import BytesIO
import altair as alt
import math
import hashlib
import time

st.set_page_config(page_title="Hệ Thống ERP - Quản Lý Phiếu Kho", page_icon="📦", layout="wide")

DANH_MUC_SP = ["Điện tử", "Gia dụng", "Thời trang", "Thực phẩm", "Văn phòng phẩm", "Khác"]

# --- HÀM HỖ TRỢ ---
def get_vn_time(format_str="%Y-%m-%d %H:%M:%S"):
    return (datetime.utcnow() + timedelta(hours=7)).strftime(format_str)

def ma_hoa_mat_khau(mat_khau_goc):
    return hashlib.sha256(str(mat_khau_goc).encode('utf-8')).hexdigest()

@st.cache_resource(ttl=600)
def ket_noi_gsheets():
    creds_dict = json.loads(st.secrets["google_credentials"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet_ns = client.open_by_url(st.secrets["url_nhansu"]).sheet1
    sheet_sp = client.open_by_url(st.secrets["url_sanpham"]).sheet1
    sheet_ls = client.open_by_url(st.secrets["url_lichsu"]).sheet1
    return sheet_ns, sheet_sp, sheet_ls

try:
    ws_nhansu, ws_sanpham, ws_lichsu = ket_noi_gsheets()
except Exception as e:
    st.error(f"❌ Lỗi kết nối CSDL. Vui lòng kiểm tra lại Secrets.")
    st.stop()

@st.cache_data(ttl=60)
def tai_du_lieu_tu_google():
    return ws_nhansu.get_all_records(), ws_sanpham.get_all_records(), ws_lichsu.get_all_records()

data_nhansu, data_sanpham, data_lichsu = tai_du_lieu_tu_google()

if not data_nhansu:
    ws_nhansu.append_row(['admin', ma_hoa_mat_khau('admin123'), 'Quản Trị Viên', 'admin', 'Them, Sua, Xoa, Xuat', 'HoatDong'])
    st.rerun()

def ghi_log(nguoi_dung, hanh_dong, chi_tiet):
    try:
        ws_lichsu.append_row([get_vn_time(), str(nguoi_dung), str(hanh_dong), str(chi_tiet)])
        tai_du_lieu_tu_google.clear() 
    except: pass 

if 'nguoi_dung' not in st.session_state: st.session_state.nguoi_dung = None
if 'thong_bao' not in st.session_state: st.session_state.thong_bao = None

def kiem_tra_quyen(user, quyen_can_check):
    if user['vai_tro'] == 'admin': return True
    return quyen_can_check in str(user.get('quyen', '')).split(', ')

# ================= GIAO DIỆN ĐĂNG NHẬP =================
if st.session_state.nguoi_dung is None:
    st.title("🔒 Đăng Nhập Hệ Thống")
    with st.form("dang_nhap"):
        tk_nhap = st.text_input("Tên đăng nhập:")
        mk_nhap = st.text_input("Mật khẩu:", type="password")
        if st.form_submit_button("Đăng Nhập"):
            mk_hash = ma_hoa_mat_khau(mk_nhap)
            user_data = next((user for user in data_nhansu if str(user['tai_khoan']) == tk_nhap and str(user['mat_khau']) == mk_hash), None)
            if user_data:
                if str(user_data.get('trang_thai', 'HoatDong')) == 'DaKhoa':
                    st.error("❌ Tài khoản đã bị khóa!")
                else:
                    st.session_state.nguoi_dung = user_data
                    ghi_log(user_data['ten_that'], "Đăng nhập", "Truy cập hệ thống")
                    st.rerun()
            else: st.error("❌ Sai thông tin đăng nhập!")

# ================= GIAO DIỆN CHÍNH =================
else:
    user = st.session_state.nguoi_dung
    if st.session_state.thong_bao:
        st.toast(st.session_state.thong_bao, icon="🔔")
        st.session_state.thong_bao = None 

    with st.sidebar:
        st.success(f"👤 **{user['ten_that']}**")
        trang_hien_tai = st.radio("Chuyển trang:", ["📦 Quản lý Kho", "👥 Nhân Sự", "📖 Nhật Ký Phiếu"]) if user['vai_tro'] == 'admin' else "📦 Quản lý Kho"
        st.divider()
        if st.button("🚪 Đăng Xuất"):
            st.session_state.nguoi_dung = None
            st.rerun()

    # ================= 1. QUẢN LÝ NHÂN SỰ =================
    if trang_hien_tai == "👥 Nhân Sự":
        st.title("👥 Quản Lý Nhân Sự")
        col_ns1, col_ns2 = st.columns(2)
        with col_ns1:
            with st.form("tao_tk"):
                st.subheader("➕ Cấp tài khoản")
                tk = st.text_input("Username")
                mk = st.text_input("Password")
                ten = st.text_input("Họ tên")
                q = st.multiselect("Quyền", ["Them", "Sua", "Xoa", "Xuat"])
                if st.form_submit_button("Tạo"):
                    ws_nhansu.append_row([tk, ma_hoa_mat_khau(mk), ten, 'nhan_vien', ", ".join(q), 'HoatDong'])
                    tai_du_lieu_tu_google.clear()
                    st.rerun()
        st.dataframe(pd.DataFrame(data_nhansu).drop(columns=['mat_khau']), use_container_width=True)

    # ================= 2. NHẬT KÝ PHIẾU (LỊCH SỬ) =================
    elif trang_hien_tai == "📖 Nhật Ký Phiếu":
        st.title("📖 Nhật Ký Biến Động Kho")
        df_ls = pd.DataFrame(data_lichsu).sort_values(by='thoi_gian', ascending=False)
        st.dataframe(df_ls, use_container_width=True)

    # ================= 3. QUẢN LÝ KHO (TRỌNG TÂM) =================
    elif trang_hien_tai == "📦 Quản lý Sản Phẩm":
        st.title("📦 Hệ Thống Kho Hàng Trực Tuyến")
        
        df_sp = pd.DataFrame(data_sanpham)
        
        if not df_sp.empty:
            df_sp['ma_sp'] = df_sp['ma_sp'].astype(str) 
            df_sp['so_luong'] = pd.to_numeric(df_sp.get('so_luong', 0), errors='coerce').fillna(0)
            df_sp['gia_ban'] = pd.to_numeric(df_sp.get('gia_ban', 0), errors='coerce').fillna(0)
            df_sp['Cảnh Báo'] = df_sp['so_luong'].apply(lambda x: "🔴 Sắp hết" if x < 5 else "🟢 Đủ hàng")
            
            # --- DASHBOARD ---
        st.subheader("📈 Phân Tích Tổng Quan")
        col_m1, col_m2, col_m3 = st.columns(3)
        if not df_sp.empty:
            col_m1.metric("📦 Tổng Số Mẫu SP", f"{len(df_sp)} mã")
            col_m2.metric("🛒 Tổng Hàng Tồn", f"{int(df_sp['so_luong'].sum()):,}".replace(",", "."))
            col_m3.metric("💰 Tổng Vốn Kho", f"{int((df_sp['so_luong'] * df_sp['gia_ban']).sum()):,}".replace(",", ".") + " đ")
        
        st.divider()

       # --- THÊM SP & IMPORT EXCEL ---
        if kiem_tra_quyen(user, 'Them'):
            col_add1, col_add2 = st.columns(2)
            with col_add1:
                with st.expander("➕ Nhập Thủ Công", expanded=False):
                    with st.form("form_nhap"):
                        ma_sp = st.text_input("Mã SP (*)")
                        ten_sp = st.text_input("Tên SP (*)")
                        danh_muc = st.selectbox("Danh mục", DANH_MUC_SP)
                        sl = st.number_input("Số lượng", min_value=0, step=1)
                        gia = st.number_input("Giá bán", min_value=0, step=1000)
                        ghi_chu = st.text_input("Ghi chú")
                        if st.form_submit_button("Lưu Sản Phẩm"):
                            danh_sach_ma = df_sp['ma_sp'].tolist() if not df_sp.empty else []
                            if not ma_sp or not ten_sp: st.error("Thiếu mã/tên!")
                            elif str(ma_sp) in danh_sach_ma: st.error("Mã SP đã tồn tại!")
                            else:
                                tg = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                ws_sanpham.append_row([str(ma_sp), str(ten_sp), danh_muc, sl, gia, str(ghi_chu), user['ten_that'], tg])
                                tai_du_lieu_tu_google.clear()
                                ghi_log(user['ten_that'], "Thêm SP", f"Thêm {sl} cái {ten_sp} ({ma_sp})")
                                st.session_state.thong_bao = "✅ Đã thêm thành công!"
                                st.rerun()
            
            with col_add2:
                with st.expander("📥 Import Bằng File Excel", expanded=False):
                    st.caption("Cột bắt buộc: ma_sp, ten_sp, danh_muc, so_luong, gia_ban, ghi_chu")
                    uploaded_file = st.file_uploader("Kéo thả file .xlsx", type=['xlsx'])
                    if uploaded_file and st.button("Bắt đầu Import"):
                        try:
                            df_import = pd.read_excel(uploaded_file).fillna("")
                            du_lieu_day_len = []
                            tg = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            danh_sach_ma = df_sp['ma_sp'].tolist() if not df_sp.empty else []
                            
                            for _, row in df_import.iterrows():
                                if str(row['ma_sp']) not in danh_sach_ma:
                                    du_lieu_day_len.append([str(row['ma_sp']), str(row['ten_sp']), str(row.get('danh_muc', 'Khác')), int(row['so_luong']), int(row['gia_ban']), str(row['ghi_chu']), user['ten_that'], tg])
                                    
                            if du_lieu_day_len:
                                ws_sanpham.append_rows(du_lieu_day_len)
                                tai_du_lieu_tu_google.clear()
                                ghi_log(user['ten_that'], "Import Excel", f"Nhập hàng loạt {len(du_lieu_day_len)} SP")
                                st.session_state.thong_bao = f"✅ Đã import {len(du_lieu_day_len)} sản phẩm!"
                                st.rerun()
                            else:
                                st.warning("Mọi mã trong file đều đã tồn tại hoặc file trống.")
                        except Exception as e:
                            st.error(f"Lỗi đọc file Excel. Chi tiết: {e}")

        st.divider()

        # BẢNG TƯƠNG TÁC
        tu_khoa = st.text_input("🔍 Tìm kiếm nhanh...")
        if not df_sp.empty:
            if tu_khoa:
                df_sp = df_sp[df_sp['ma_sp'].astype(str).str.contains(tu_khoa, case=False) | df_sp['ten_sp'].str.contains(tu_khoa, case=False)]
            
            df_sp.insert(0, "Chọn", False)
            # Khóa cột Số lượng trong bảng hiển thị
            edited_df = st.data_editor(df_sp, hide_index=True, use_container_width=True, disabled=df_sp.columns.drop("Chọn"))
            
            chon = edited_df[edited_df["Chọn"] == True]
            if len(chon) == 1:
                st.divider()
                sp = chon.iloc[0]
                st.subheader(f"📑 Phiếu điều chuyển: {sp['ten_sp']} (Tồn hiện tại: {int(sp['so_luong'])})")
                
                col_p1, col_p2, col_p3 = st.columns([1, 1, 2])
                loai_phieu = col_p1.selectbox("Loại phiếu", ["Nhập Kho (+)", "Xuất Kho (-)"])
                so_luong_td = col_p2.number_input("Số lượng", min_value=1, step=1)
                ly_do = col_p3.text_input("Lý do / Đối tác / Khách hàng", placeholder="VD: Nhập hàng từ NCC A / Bán cho chị B...")
                
                if st.button("🚀 Xác nhận hoàn tất phiếu", type="primary"):
                    try:
                        cell = ws_sanpham.find(str(sp['ma_sp']), in_column=1)
                        ton_cu = int(sp['so_luong'])
                        ton_moi = ton_cu + so_luong_td if "Nhập" in loai_phieu else ton_cu - so_luong_td
                        
                        if ton_moi < 0:
                            st.error("❌ Lỗi: Số lượng xuất vượt quá tồn kho hiện có!")
                        else:
                            # Cập nhật số lượng mới và thời gian
                            ws_sanpham.update_cell(cell.row, 4, ton_moi) # Cột 4 là so_luong
                            ws_sanpham.update_cell(cell.row, 8, get_vn_time()) # Cột 8 là thoi_gian
                            
                            hanh_dong = "NHẬP" if "Nhập" in loai_phieu else "XUẤT"
                            ghi_log(user['ten_that'], hanh_dong, f"{hanh_dong} {so_luong_td} cái {sp['ma_sp']}. Lý do: {ly_do}. Tồn mới: {ton_moi}")
                            
                            st.session_state.thong_bao = f"✅ Đã lập phiếu {hanh_dong} thành công!"
                            tai_du_lieu_tu_google.clear()
                            st.rerun()
                    except: st.error("Lỗi đồng bộ dữ liệu.")
            
            elif len(chon) > 1:
                if st.button("🗑️ Xóa các mã đã chọn (Admin)"):
                    if user['vai_tro'] == 'admin':
                        for m in chon['ma_sp'].tolist():
                            c = ws_sanpham.find(str(m), in_column=1)
                            ws_sanpham.delete_rows(c.row)
                            time.sleep(0.5)
                        tai_du_lieu_tu_google.clear()
                        st.rerun()
