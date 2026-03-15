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
from fpdf import FPDF # Thư viện tạo PDF

# =============================================================================
# CẤU HÌNH HỆ THỐNG
# =============================================================================
st.set_page_config(page_title="Hệ Thống ERP - Quản Lý Phiếu Kho & PDF", page_icon="📦", layout="wide")

DANH_MUC_SP = ["Điện tử", "Gia dụng", "Thời trang", "Thực phẩm", "Văn phòng phẩm", "Khác"]

# --- HÀM HỖ TRỢ THỜI GIAN VIỆT NAM ---
def get_vn_time(format_str="%Y-%m-%d %H:%M:%S"):
    # Ép kiểu múi giờ sang UTC+7 để tránh lỗi giờ máy chủ Mỹ
    return (datetime.utcnow() + timedelta(hours=7)).strftime(format_str)

# --- HÀM MÃ HÓA BẢO MẬT ---
def ma_hoa_mat_khau(mat_khau_goc):
    return hashlib.sha256(str(mat_khau_goc).encode('utf-8')).hexdigest()

# =============================================================================
# LOGIC TẠO PHIẾU PDF (Đọc kỹ logic vẽ tại đây)
# =============================================================================
class PDF_PhieuKho(FPDF):
    def header(self):
        # Logo hoặc Tên công ty
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'CONG TY QUAN LY KHO SMART ERP', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 10, 'Dia chi: Quan 1, TP. Ho Chi Minh - Hotline: 1900 xxxx', 0, 1, 'C')
        self.ln(5)
        # Đường kẻ ngang
        self.line(10, 30, 200, 30)

def tao_file_pdf_phieu(loai_phieu, nguoi_lap, ma_sp, ten_sp, so_luong, ton_moi, ly_do):
    pdf = PDF_PhieuKho()
    pdf.add_page()
    
    # Tiêu đề phiếu
    pdf.set_font('Arial', 'B', 20)
    pdf.ln(10)
    tieu_de = "PHIEU NHAP KHO" if "Nhap" in loai_phieu else "PHIEU XUAT KHO"
    pdf.cell(0, 15, tieu_de, 0, 1, 'C')
    
    # Thông tin chung
    pdf.set_font('Arial', '', 12)
    pdf.ln(5)
    pdf.cell(0, 10, f'Ngay lap: {get_vn_time()}', 0, 1)
    pdf.cell(0, 10, f'Nguoi lap phieu: {nguoi_lap}', 0, 1)
    pdf.ln(5)
    
    # Bảng chi tiết sản phẩm
    # Vẽ tiêu đề bảng
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(40, 10, 'Ma San Pham', 1, 0, 'C', 1)
    pdf.cell(80, 10, 'Ten San Pham', 1, 0, 'C', 1)
    pdf.cell(30, 10, 'So Luong', 1, 0, 'C', 1)
    pdf.cell(40, 10, 'Ton Sau C.Nhat', 1, 1, 'C', 1)
    
    # Vẽ nội dung bảng
    pdf.set_font('Arial', '', 12)
    pdf.cell(40, 10, str(ma_sp), 1, 0, 'C')
    pdf.cell(80, 10, str(ten_sp), 1, 0, 'L')
    pdf.cell(30, 10, str(so_luong), 1, 0, 'C')
    pdf.cell(40, 10, str(ton_moi), 1, 1, 'C')
    
    # Ghi chú / Lý do
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 11)
    pdf.multi_cell(0, 10, f'Ly do dieu chuyen: {ly_do}')
    
    # Chữ ký
    pdf.ln(20)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(95, 10, 'NGUOI LAP PHIEU', 0, 0, 'C')
    pdf.cell(95, 10, 'THU KHO KIEM TRA', 0, 1, 'C')
    pdf.set_font('Arial', '', 10)
    pdf.cell(95, 10, '(Ky va ghi ro ho ten)', 0, 0, 'C')
    pdf.cell(95, 10, '(Ky va ghi ro ho ten)', 0, 1, 'C')
    
    # Xuất dữ liệu dưới dạng Binary để Streamlit Download được
    return pdf.output(dest='S').encode('latin-1')

# =============================================================================
# KẾT NỐI DỮ LIỆU GOOGLE SHEETS
# =============================================================================
@st.cache_resource(ttl=600)
def ket_noi_gsheets():
    creds_dict = json.loads(st.secrets["google_credentials"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # Mở 3 file riêng biệt như kiến trúc bạn đã yêu cầu
    sheet_ns = client.open_by_url(st.secrets["url_nhansu"]).sheet1
    sheet_sp = client.open_by_url(st.secrets["url_sanpham"]).sheet1
    sheet_ls = client.open_by_url(st.secrets["url_lichsu"]).sheet1
    return sheet_ns, sheet_sp, sheet_ls

try:
    ws_nhansu, ws_sanpham, ws_lichsu = ket_noi_gsheets()
except Exception as e:
    st.error("❌ Khong the ket noi database. Kiem tra Secrets ngay!")
    st.stop()

@st.cache_data(ttl=60)
def tai_du_lieu():
    return ws_nhansu.get_all_records(), ws_sanpham.get_all_records(), ws_lichsu.get_all_records()

data_nhansu, data_sanpham, data_lichsu = tai_du_lieu()

# --- HÀM GHI NHẬT KÝ ---
def ghi_log(nguoi_dung, hanh_dong, chi_tiet):
    ws_lichsu.append_row([get_vn_time(), str(nguoi_dung), str(hanh_dong), str(chi_tiet)])
    tai_du_lieu.clear()

# =============================================================================
# GIAO DIỆN CHÍNH
# =============================================================================
if 'nguoi_dung' not in st.session_state: st.session_state.nguoi_dung = None

if st.session_state.nguoi_dung is None:
    st.title("🔒 DANG NHAP HE THONG")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Vao he thong"):
            p_hash = ma_hoa_mat_khau(p)
            user = next((x for x in data_nhansu if str(x['tai_khoan'])==u and str(x['mat_khau'])==p_hash), None)
            if user:
                st.session_state.nguoi_dung = user
                ghi_log(user['ten_that'], "Dang nhap", "Vao he thong")
                st.rerun()
            else: st.error("Sai thong tin!")

else:
    user = st.session_state.nguoi_dung
    
    with st.sidebar:
        st.header(f"👤 {user['ten_that']}")
        st.write(f"Vai tro: {user['vai_tro'].upper()}")
        trang = st.radio("Menu", ["📦 QUAN LY KHO", "📖 LICHSU PHIEU", "👥 NHAN SU"])
        st.divider()
        if st.button("🚪 Dang xuat"):
            st.session_state.nguoi_dung = None
            st.rerun()

    # --- TRANG QUẢN LÝ KHO (TRỌNG TÂM CÓ XUẤT PHIẾU) ---
    if trang == "📦 QUAN LY KHO":
        st.title("📦 QUAN LY NHAP XUAT KHO & IN PHIEU")
        
        df_sp = pd.DataFrame(data_sanpham)
        
        # Dashboard nhanh
        if not df_sp.empty:
            df_sp['so_luong'] = pd.to_numeric(df_sp['so_luong']).fillna(0)
            c1, c2, c3 = st.columns(3)
            c1.metric("Tong ma hang", len(df_sp))
            c2.metric("Tong ton kho", int(df_sp['so_luong'].sum()))
            c3.metric("Gia tri kho", f"{int((df_sp['so_luong']*pd.to_numeric(df_sp['gia_ban'])).sum()):,}")

        st.divider()
        
        # Form them moi
        with st.expander("➕ KHAI BAO MA HANG MOI"):
            with st.form("add_sp"):
                c1, c2, c3 = st.columns(3)
                m = c1.text_input("Ma SP")
                t = c2.text_input("Ten SP")
                dm = c3.selectbox("Danh muc", DANH_MUC_SP)
                if st.form_submit_button("Luu ma hang"):
                    ws_sanpham.append_row([m, t, dm, 0, 0, "", user['ten_that'], get_vn_time()])
                    ghi_log(user['ten_that'], "Khai bao", f"Ma hang {m}")
                    tai_du_lieu.clear()
                    st.rerun()

        # Bang du lieu tương tác
        st.subheader("📊 BANG DIEU PHOI KHO")
        df_sp.insert(0, "Chon", False)
        edited_df = st.data_editor(df_sp, hide_index=True, use_container_width=True, disabled=df_sp.columns.drop("Chon"))
        
        chon = edited_df[edited_df["Chon"] == True]
        
        if len(chon) == 1:
            sp_focus = chon.iloc[0]
            st.success(f"Dang chon: **{sp_focus['ten_sp']}** (Ton kho: {int(sp_focus['so_luong'])})")
            
            # --- FORM LAP PHIEU CHUYEN KHO ---
            with st.container(border=True):
                st.subheader("📝 LAP PHIEU DIEU CHUYEN")
                col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
                
                type_p = col_f1.selectbox("Loai phieu", ["Nhap Kho (+)", "Xuat Kho (-)"])
                qty_p = col_f2.number_input("So luong", min_value=1, step=1)
                note_p = col_f3.text_input("Ly do dieu chuyen", placeholder="Vi du: Nhap hang tu NCC... / Xuat ban cho khach...")
                
                if st.button("🚀 XAC NHAN VA IN PHIEU", type="primary"):
                    # Logic tinh toan
                    ton_cu = int(sp_focus['so_luong'])
                    ton_moi = ton_cu + qty_p if "Nhap" in type_p else ton_cu - qty_p
                    
                    if ton_moi < 0:
                        st.error("❌ KHONG DU HANG DE XUAT!")
                    else:
                        # 1. Cap nhat Google Sheets
                        cell = ws_sanpham.find(str(sp_focus['ma_sp']), in_column=1)
                        ws_sanpham.update_cell(cell.row, 4, ton_moi) # Cot 4 la SL
                        ws_sanpham.update_cell(cell.row, 8, get_vn_time()) # Cot 8 la Gio
                        
                        # 2. Ghi vao Lich Su
                        ghi_log(user['ten_that'], "DIEU CHUYEN", f"{type_p} {qty_p} cái {sp_focus['ma_sp']}")
                        
                        # 3. Tao File PDF de in
                        pdf_data = tao_file_pdf_phieu(
                            type_p, user['ten_that'], 
                            sp_focus['ma_sp'], sp_focus['ten_sp'], 
                            qty_p, ton_moi, note_p
                        )
                        
                        st.balloons()
                        st.success("✅ Da cap nhat kho thanh cong!")
                        
                        # 4. Hien nut Download PDF ngay lap tuc
                        st.download_button(
                            label="📥 TAI PHIEU KHO (PDF) DE IN",
                            data=pdf_data,
                            file_name=f"Phieu_{sp_focus['ma_sp']}_{datetime.now().strftime('%H%M%S')}.pdf",
                            mime="application/pdf"
                        )
                        
                        # Nut de lam moi lai bang sau khi thao tac
                        if st.button("🔄 Cap nhat lai bang du lieu"):
                            tai_du_lieu.clear()
                            st.rerun()

    # --- TRANG LỊCH SỬ ---
    elif trang == "📖 LICHSU PHIEU":
        st.title("📖 NHAT KY BIEN DONG KHO")
        df_ls = pd.DataFrame(data_lichsu).sort_values(by='thoi_gian', ascending=False)
        st.dataframe(df_ls, use_container_width=True)

    # --- TRANG NHÂN SỰ ---
    elif trang == "👥 NHAN SU":
        if user['vai_tro'] == 'admin':
            st.title("👥 QUAN LY NHAN SU")
            st.dataframe(pd.DataFrame(data_nhansu).drop(columns=['mat_khau']), use_container_width=True)
        else: st.warning("Ban khong co quyen truy cap!")
