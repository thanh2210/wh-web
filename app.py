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
from fpdf import FPDF

st.set_page_config(page_title="Hệ Thống ERP - Quản Lý Phiếu Kho", page_icon="📦", layout="wide")

DANH_MUC_SP = ["Điện tử", "Gia dụng", "Thời trang", "Thực phẩm", "Văn phòng phẩm", "Khác"]

# --- HÀM HỖ TRỢ ---
def get_vn_time(format_str="%Y-%m-%d %H:%M:%S"):
    return (datetime.utcnow() + timedelta(hours=7)).strftime(format_str)

def ma_hoa_mat_khau(mat_khau_goc):
    return hashlib.sha256(str(mat_khau_goc).encode('utf-8')).hexdigest()

# --- XUẤT PDF ---
class PDF_Phieu(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'HE THONG QUAN LY KHO SMART-ERP', 0, 1, 'C')
        self.set_font('Helvetica', '', 10)
        self.cell(0, 5, f'Ngay xuat: {get_vn_time()}', 0, 1, 'C')
        self.line(10, 28, 200, 28)
        self.ln(10)

def xuat_pdf_binary(nguoi_nhap, ma_sp, ten_sp, so_luong):
    pdf = PDF_Phieu()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 15, f"PHIEU {loai.upper()}", 0, 1, 'C')
    
    pdf.set_font('Helvetica', '', 12)
    pdf.ln(5)
    pdf.cell(0, 10, f'Nguoi thuc hien: {nguoi_nhap}', 0, 1)
    pdf.cell(0, 10, f'Ma san pham: {ma_sp}', 0, 1)
    pdf.cell(0, 10, f'Ten san pham: {ten_sp}', 0, 1)
    pdf.cell(0, 10, f'So luong dieu chuyen: {so_luong}', 0, 1)
    pdf.ln(5)
    
    pdf.ln(20)
    pdf.cell(95, 10, 'CHU KHO', 0, 0, 'C')
    pdf.cell(95, 10, 'NGUOI NHAN', 0, 1, 'C')
    
    return pdf.output(dest='S').encode('latin-1')
    
# --- KÊT NỐI GOOGLE ---
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
        ws_lichsu.append_row([get_vn_time(), str(nguoi_thao_tac), str(hanh_dong), str(chi_tiet)])
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
    elif trang_hien_tai == "📦 Quản lý Kho":
        st.title("📦 Hệ Thống Kho Hàng Trực Tuyến")
        
        data_sanpham = ws_sanpham.get_all_records()
        df_sp = pd.DataFrame(data_sanpham)
        
        # Xử lý an toàn dữ liệu số
        if not df_sp.empty:
            df_sp['so_luong'] = pd.to_numeric(df_sp.get('so_luong', 0), errors='coerce').fillna(0)
            df_sp['gia_ban'] = pd.to_numeric(df_sp.get('gia_ban', 0), errors='coerce').fillna(0)
            

        # --- DASHBOARD & BIỂU ĐỒ ---
        st.subheader("📈 Phân Tích Tổng Quan")
        col_m1, col_m2, col_m3 = st.columns(3)
        if not df_sp.empty:
            tong_loai = len(df_sp)
            tong_sl = int(df_sp['so_luong'].sum())
            tong_tien = int((df_sp['so_luong'] * df_sp['gia_ban']).sum())
            
            col_m1.metric("📦 Tổng Số Mẫu SP", f"{tong_loai} mã")
            col_m2.metric("🛒 Tổng Hàng Tồn", f"{tong_sl:,}".replace(",", "."))
            col_m3.metric("💰 Tổng Vốn Kho", f"{tong_tien:,}".replace(",", ".") + " đ")
            
            # Vẽ biểu đồ tỷ trọng danh mục
            df_chart = df_sp.groupby('danh_muc')['so_luong'].sum().reset_index()
            pie_chart = alt.Chart(df_chart).mark_arc(innerRadius=40).encode(
                theta=alt.Theta(field="so_luong", type="quantitative"),
                color=alt.Color(field="danh_muc", type="nominal"),
                tooltip=["danh_muc", "so_luong"]
            ).properties(height=250, title="Tỷ trọng hàng theo Danh mục")
            
            with st.expander("📊 Bấm để xem Biểu đồ Tỷ trọng"):
                st.altair_chart(pie_chart, use_container_width=True)
        else:
            st.info("Chưa có dữ liệu để vẽ biểu đồ.")
        
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
                                ws_sanpham.append_row([str(ma_sp), str(ten_sp), danh_muc, sl, gia, str(ghi_chu), user['ten_that'], get_vn_time()])
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
                            danh_sach_ma = df_sp['ma_sp'].tolist() if not df_sp.empty else []
                            
                            for _, row in df_import.iterrows():
                                if str(row['ma_sp']) not in danh_sach_ma:
                                    du_lieu_day_len.append([str(row['ma_sp']), str(row['ten_sp']), str(row.get('danh_muc', 'Khác')), int(row['so_luong']), int(row['gia_ban']), str(row['ghi_chu']), user['ten_that'], get_vn_time()])
                                    
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

        # Bảng dữ liệu tương tác
        tu_khoa = st.text_input("🔍 Tìm nhanh mã hoặc tên...")
        if not df_sp.empty:
            if tu_khoa: df_sp = df_sp[df_sp['ma_sp'].astype(str).str.contains(tu_khoa, case=False) | df_sp['ten_sp'].str.contains(tu_khoa, case=False)]
            
            # Cảnh báo tồn thấp
            df_sp['Tình trạng'] = df_sp['so_luong'].apply(lambda x: "🔴 Hết hàng" if x <= 0 else ("🟡 Sắp hết" if x < 10 else "🟢 Ổn định"))
            
            # FORM SỬA SP
                if kiem_tra_quyen(user, 'Sua') and sl_chon == 1:
                    st.subheader("✏️ Chỉnh Sửa Sản Phẩm")
                    sp_dang_sua = danh_sach_chon.iloc[0]
                    with st.form("form_sua"):
                        col_s1, col_s2, col_s3 = st.columns(3)
                        with col_s1:
                            st.text_input("Mã SP (Cố định)", value=str(sp_dang_sua['ma_sp']), disabled=True)
                            t_moi = st.text_input("Tên", value=str(sp_dang_sua['ten_sp']))
                        with col_s2:
                            dm_moi = st.selectbox("Danh mục", DANH_MUC_SP, index=DANH_MUC_SP.index(sp_dang_sua['danh_muc']) if sp_dang_sua['danh_muc'] in DANH_MUC_SP else 0)
                            sl_moi = st.number_input("SL", value=int(sp_dang_sua['so_luong']))
                        with col_s3:
                            gia_moi = st.number_input("Giá", value=int(sp_dang_sua['gia_ban']))
                            gc_moi = st.text_input("Ghi chú", value=str(sp_dang_sua['ghi_chu']))
                            
                        if st.form_submit_button("Lưu Cập Nhật"):
                            try:
                                cell = ws_sanpham.find(str(sp_dang_sua['ma_sp']), in_column=1)
                                if cell:
                                    tg_sua = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    ws_sanpham.update(values=[[str(sp_dang_sua['ma_sp']), t_moi, dm_moi, sl_moi, gia_moi, gc_moi, f"{user['ten_that']} (Sửa)", tg_sua]], range_name=f"A{cell.row}:H{cell.row}")
                                    tai_du_lieu_tu_google.clear()
                                    ghi_log(user['ten_that'], "Sửa SP", f"Cập nhật mã {sp_dang_sua['ma_sp']}")
                                    st.session_state.thong_bao = "✅ Đã lưu cập nhật!"
                                    st.rerun()
                                else:
                                    st.error("Lỗi: Mã sản phẩm này đã bị ai đó xóa mất trước đó!")
                            except Exception as e:
                                st.error(f"Lỗi khi lưu: {e}")
                
                # NÚT XÓA SP
                if kiem_tra_quyen(user, 'Xoa'):
                    if st.button(f"🗑️ XÓA {sl_chon} SẢN PHẨM", type="primary"):
                        ma_xoa = danh_sach_chon['ma_sp'].astype(str).tolist()
                        rows_del = []
                        for m in ma_xoa:
                            try:
                                cell = ws_sanpham.find(m, in_column=1)
                                if cell: rows_del.append(cell.row)
                            except: pass
                            
                        for r in sorted(rows_del, reverse=True): 
                            ws_sanpham.delete_rows(r)
                            
                        tai_du_lieu_tu_google.clear()
                        ghi_log(user['ten_that'], "Xóa SP", f"Xóa mã: {', '.join(ma_xoa)}")
                        st.session_state.thong_bao = f"🗑️ Đã xóa {len(rows_del)} SP an toàn!"
                        st.rerun()

