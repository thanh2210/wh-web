import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Hệ Thống Quản Lý", page_icon="📦", layout="wide")

# --- 1. KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def ket_noi_gsheets():
    creds_dict = json.loads(st.secrets["google_credentials"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["google_sheet_url"])
    return sheet.worksheet("NhanSu"), sheet.worksheet("SanPham")

try:
    ws_nhansu, ws_sanpham = ket_noi_gsheets()
except Exception as e:
    st.error("Chưa thể kết nối Google Sheets. Vui lòng kiểm tra lại cài đặt Secrets.")
    st.stop()

if 'nguoi_dung' not in st.session_state:
    st.session_state.nguoi_dung = None

data_nhansu = ws_nhansu.get_all_records()

# --- 2. GIAO DIỆN ĐĂNG NHẬP ---
if st.session_state.nguoi_dung is None:
    st.title("🔒 Đăng Nhập Hệ Thống")
    
    with st.form("dang_nhap"):
        tk_nhap = st.text_input("Tên đăng nhập:")
        mk_nhap = st.text_input("Mật khẩu:", type="password")
        if st.form_submit_button("Đăng Nhập"):
            user_data = next((user for user in data_nhansu if str(user['tai_khoan']) == tk_nhap and str(user['mat_khau']) == mk_nhap), None)
            
            if user_data:
                st.session_state.nguoi_dung = user_data
                st.rerun()
            else:
                st.error("❌ Sai tên đăng nhập hoặc mật khẩu!")

# --- 3. GIAO DIỆN CHÍNH ---
else:
    user = st.session_state.nguoi_dung
    with st.sidebar:
        st.success(f"👤 Chào: **{user['ten_that']}**")
        st.caption(f"Vai trò: {user['vai_tro'].upper()} | Quyền: {user['quyen'].upper()}")
        if user['vai_tro'] == 'admin':
            trang_hien_tai = st.radio("Chuyển trang:", ["📦 Quản lý Sản Phẩm", "👥 Quản lý Nhân Sự"])
        else:
            trang_hien_tai = "📦 Quản lý Sản Phẩm"
            
        st.divider()
        if st.button("🚪 Đăng Xuất"):
            st.session_state.nguoi_dung = None
            st.rerun()

    # ================= QUẢN LÝ NHÂN SỰ =================
    if trang_hien_tai == "👥 Quản lý Nhân Sự":
        st.title("👥 Quản Lý Tài Khoản Nhân Viên")
        
        with st.form("tao_tai_khoan", clear_on_submit=True):
            st.subheader("➕ Cấp tài khoản mới")
            col1, col2 = st.columns(2)
            with col1:
                tk_moi = st.text_input("Tên đăng nhập (viết liền không dấu):")
                mk_moi = st.text_input("Mật khẩu:")
            with col2:
                ten_that_moi = st.text_input("Tên thật nhân viên:")
                quyen_moi = st.selectbox("Quyền hạn:", ["chinh_sua", "chi_xem"])
                
            if st.form_submit_button("Tạo Tài Khoản"):
                if tk_moi and mk_moi and ten_that_moi:
                    danh_sach_tk = [str(u['tai_khoan']) for u in data_nhansu]
                    if tk_moi in danh_sach_tk:
                        st.error("Tên đăng nhập này đã tồn tại!")
                    else:
                        ws_nhansu.append_row([tk_moi, mk_moi, ten_that_moi, 'nhan_vien', quyen_moi])
                        st.success("Đã tạo tài khoản! Vui lòng ấn F5 để làm mới dữ liệu.")
                else:
                    st.error("Vui lòng điền đủ thông tin!")
                    
        st.divider()
        st.subheader("📋 Danh sách nhân sự hiện tại")
        df_users = pd.DataFrame(data_nhansu)
        st.dataframe(df_users, use_container_width=True)

    # ================= QUẢN LÝ SẢN PHẨM =================
    elif trang_hien_tai == "📦 Quản lý Sản Phẩm":
        st.title("📦 Ứng Dụng Quản Lý Sản Phẩm")
        
        # --- Lấy dữ liệu sản phẩm hiện tại ---
        data_sanpham = ws_sanpham.get_all_records()
        df_sp = pd.DataFrame(data_sanpham)
        
        # --- KHU VỰC 1: THÊM SẢN PHẨM MỚI ---
        if user['quyen'] == 'chinh_sua' or user['vai_tro'] == 'admin':
            with st.form("form_nhap_lieu", clear_on_submit=True):
                st.subheader("📝 Thêm Sản Phẩm Mới")
                col1, col2 = st.columns(2)
                with col1:
                    ma_sp = st.text_input("1. Mã sản phẩm (*)")
                    so_luong = st.number_input("3. Số lượng", min_value=0, step=1)
                with col2:
                    ten_sp = st.text_input("2. Tên sản phẩm (*)")
                    gia_ban = st.number_input("4. Giá bán (VNĐ)", min_value=0, step=1000)
                ghi_chu = st.text_area("5. Ghi chú")
                
                if st.form_submit_button("➕ Thêm Sản Phẩm"):
                    if ma_sp and ten_sp:
                        thoi_gian_nhap = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ws_sanpham.append_row([ma_sp, ten_sp, so_luong, gia_ban, ghi_chu, user['ten_that'], thoi_gian_nhap])
                        st.success(f"Đã lưu **{ten_sp}** lên Google Sheets! Vui lòng F5 để làm mới bảng.")
                    else:
                        st.error("Thiếu mã hoặc tên sản phẩm!")
        else:
            st.warning("⚠️ Tài khoản của bạn chỉ có quyền XEM dữ liệu, không được Thêm/Sửa/Xóa.")

        st.divider()

        # --- KHU VỰC 2: HIỂN THỊ DỮ LIỆU ---
        st.subheader("📊 Dữ Liệu Sản Phẩm Đồng Bộ Từ Google Sheets")
        if not df_sp.empty:
            st.dataframe(df_sp, use_container_width=True)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_sp.to_excel(writer, index=False, sheet_name='Sản Phẩm')
            excel_data = output.getvalue()
            
            ten_file = f"Data_SP_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            st.download_button("📥 Tải File Excel (Bản Sao)", data=excel_data, file_name=ten_file, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Chưa có dữ liệu.")
            
        st.divider()

        # --- KHU VỰC 3: SỬA HOẶC XÓA SẢN PHẨM (TÍNH NĂNG MỚI) ---
        if (user['quyen'] == 'chinh_sua' or user['vai_tro'] == 'admin') and not df_sp.empty:
            st.subheader("🛠️ Chỉnh Sửa / Xóa Sản Phẩm Đã Nhập")
            
            # Tạo danh sách các mã sản phẩm để người dùng chọn
            danh_sach_ma = df_sp['ma_sp'].astype(str).tolist()
            ma_can_sua = st.selectbox("📌 Chọn Mã Sản Phẩm cần thao tác:", danh_sach_ma)
            
            # Tìm dòng tương ứng trên Google Sheets
            # Lưu ý: Index trong Python bắt đầu từ 0. Google Sheets Dòng 1 là Tiêu đề -> Dữ liệu bắt đầu từ Dòng 2
            vitri = danh_sach_ma.index(ma_can_sua)
            dong_trong_sheet = vitri + 2 
            sp_hien_tai = data_sanpham[vitri]
            
            with st.form("form_sua_xoa"):
                st.write(f"Đang thao tác với: **{sp_hien_tai['ten_sp']}**")
                
                # Điền sẵn thông tin cũ vào các ô nhập liệu
                col1, col2 = st.columns(2)
                with col1:
                    ten_moi = st.text_input("Tên sản phẩm", value=str(sp_hien_tai['ten_sp']))
                    sl_moi = st.number_input("Số lượng", value=int(sp_hien_tai['so_luong']), step=1)
                with col2:
                    gia_moi = st.number_input("Giá bán (VNĐ)", value=int(sp_hien_tai['gia_ban']), step=1000)
                    ghi_chu_moi = st.text_area("Ghi chú", value=str(sp_hien_tai['ghi_chu']))
                
                col_btn1, col_btn2 = st.columns(2)
                btn_sua = col_btn1.form_submit_button("✏️ Cập Nhật Thông Tin")
                btn_xoa = col_btn2.form_submit_button("🗑️ Xóa Sản Phẩm Này")
                
                if btn_sua:
                    thoi_gian_sua = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    nguoi_sua = f"{user['ten_that']} (Sửa)"
                    
                    # Cập nhật đúng vào dòng đã chọn trên Google Sheets (Từ cột A đến cột G)
                    danh_sach_cap_nhat = [[ma_can_sua, ten_moi, sl_moi, gia_moi, ghi_chu_moi, nguoi_sua, thoi_gian_sua]]
                    ws_sanpham.update(range_name=f"A{dong_trong_sheet}:G{dong_trong_sheet}", values=danh_sach_cap_nhat)
                    
                    st.success(f"✅ Đã cập nhật thành công sản phẩm {ma_can_sua}! Vui lòng ấn F5 để tải lại bảng.")
                    
                if btn_xoa:
                    # Xóa dòng trực tiếp trên Google Sheets
                    ws_sanpham.delete_rows(dong_trong_sheet)
                    st.success(f"🗑️ Đã xóa sản phẩm {ma_can_sua}! Vui lòng ấn F5 để tải lại bảng.")
