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

# Lấy dữ liệu nhân sự
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

    # ================= QUẢN LÝ NHÂN SỰ (Giữ nguyên) =================
    if trang_hien_tai == "👥 Quản lý Nhân Sự":
        st.title("👥 Quản Lý Tài Khoản Nhân Viên")
        with st.form("tao_tai_khoan", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                tk_moi = st.text_input("Tên đăng nhập (viết liền không dấu):")
                mk_moi = st.text_input("Mật khẩu:")
            with col2:
                ten_that_moi = st.text_input("Tên thật nhân viên:")
                quyen_moi = st.selectbox("Quyền hạn:", ["chinh_sua", "chi_xem"])
            if st.form_submit_button("➕ Tạo Tài Khoản"):
                if tk_moi and mk_moi and ten_that_moi:
                    danh_sach_tk = [str(u['tai_khoan']) for u in data_nhansu]
                    if tk_moi in danh_sach_tk:
                        st.error("Tên đăng nhập này đã tồn tại!")
                    else:
                        ws_nhansu.append_row([tk_moi, mk_moi, ten_that_moi, 'nhan_vien', quyen_moi])
                        st.success("Tạo tài khoản thành công!")
                        st.rerun() # Real-time cập nhật
                else:
                    st.error("Vui lòng điền đủ thông tin!")
        st.divider()
        st.subheader("📋 Danh sách nhân sự hiện tại")
        st.dataframe(pd.DataFrame(data_nhansu), use_container_width=True)

    # ================= QUẢN LÝ SẢN PHẨM (NÂNG CẤP BẢNG TRẮNG) =================
    elif trang_hien_tai == "📦 Quản lý Sản Phẩm":
        st.title("📦 Bảng Trắng Quản Lý Sản Phẩm (Real-time)")
        
        # --- LẤY DỮ LIỆU REAL-TIME ---
        data_sanpham = ws_sanpham.get_all_records()
        df_sp = pd.DataFrame(data_sanpham)
        
        # --- KHU VỰC 1: THÊM SẢN PHẨM MỚI ---
        if user['quyen'] == 'chinh_sua' or user['vai_tro'] == 'admin':
            with st.expander("➕ Bấm vào đây để Thêm Sản Phẩm Mới", expanded=False):
                with st.form("form_nhap_lieu", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        ma_sp = st.text_input("1. Mã sản phẩm (*)")
                        so_luong = st.number_input("3. Số lượng", min_value=0, step=1)
                    with col2:
                        ten_sp = st.text_input("2. Tên sản phẩm (*)")
                        gia_ban = st.number_input("4. Giá bán (VNĐ)", min_value=0, step=1000)
                    ghi_chu = st.text_area("5. Ghi chú")
                    
                    if st.form_submit_button("Lưu Sản Phẩm"):
                        if ma_sp and ten_sp:
                            thoi_gian_nhap = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ws_sanpham.append_row([ma_sp, ten_sp, so_luong, gia_ban, ghi_chu, user['ten_that'], thoi_gian_nhap])
                            st.toast(f"✅ Đã thêm {ten_sp} thành công!", icon="🚀")
                            st.rerun() # Tự động load lại bảng ngầm (Real-time)
                        else:
                            st.error("Thiếu mã hoặc tên sản phẩm!")
        else:
            st.warning("⚠️ Tài khoản của bạn chỉ có quyền XEM dữ liệu.")

        st.divider()

        # --- KHU VỰC 2: BẢNG TRẮNG CÓ CHECKBOX ---
        st.subheader("📊 Dữ Liệu Tổng (Chọn ô tick đầu tiên để thao tác)")
        
        if not df_sp.empty:
            # Chèn thêm cột "Chọn" (Checkbox) vào đầu Dataframe
            df_sp.insert(0, "Chọn", False)
            
            # Hiển thị bảng tương tác
            edited_df = st.data_editor(
                df_sp,
                hide_index=True,
                use_container_width=True,
                disabled=df_sp.columns.drop("Chọn"), # Khóa các cột khác, chỉ cho phép bấm cột Checkbox
                column_config={
                    "Chọn": st.column_config.CheckboxColumn("☑️ Chọn", help="Tick để chọn sản phẩm", default=False),
                    "ma_sp": "Mã SP", "ten_sp": "Tên SP", "so_luong": "Số Lượng", 
                    "gia_ban": "Giá Bán", "ghi_chu": "Ghi Chú", "nguoi_nhap": "Người Nhập", "thoi_gian": "Thời Gian"
                }
            )
            
            # Lọc ra những dòng mà người dùng đã tick chọn
            danh_sach_chon = edited_df[edited_df["Chọn"] == True]
            so_luong_chon = len(danh_sach_chon)
            
            # --- KHU VỰC 3: THAO TÁC VỚI SẢN PHẨM ĐÃ CHỌN ---
            if so_luong_chon > 0:
                st.info(f"📌 Bạn đang chọn **{so_luong_chon}** sản phẩm. Hãy chọn hành động bên dưới:")
                
                # Bỏ cột "Chọn" đi trước khi thao tác dữ liệu thật
                df_xuat_excel = danh_sach_chon.drop(columns=["Chọn"])
                
                # 1. TÍNH NĂNG XUẤT EXCEL (Tạo file riêng, không ghi đè)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_xuat_excel.to_excel(writer, index=False, sheet_name='Sản Phẩm Được Chọn')
                excel_data = output.getvalue()
                
                ten_file = f"San_Pham_Da_Chon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                st.download_button("📥 Xuất File Excel (Chỉ file được chọn)", data=excel_data, file_name=ten_file, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
                # 2. TÍNH NĂNG SỬA (Chỉ hiện khi chọn ĐÚNG 1 sản phẩm)
                if (user['quyen'] == 'chinh_sua' or user['vai_tro'] == 'admin'):
                    if so_luong_chon == 1:
                        st.subheader("✏️ Chỉnh Sửa Sản Phẩm Này")
                        
                        # Lấy index nguyên thủy của dòng được chọn để biết nó nằm ở dòng nào trên Google Sheets
                        vi_tri_index = danh_sach_chon.index[0]
                        dong_trong_sheet = vi_tri_index + 2 # +2 vì Google Sheet có dòng 1 là tiêu đề
                        
                        sp_dang_sua = df_sp.iloc[vi_tri_index]
                        
                        with st.form("form_sua"):
                            col_s1, col_s2 = st.columns(2)
                            with col_s1:
                                ten_moi = st.text_input("Tên sản phẩm", value=str(sp_dang_sua['ten_sp']))
                                sl_moi = st.number_input("Số lượng", value=int(sp_dang_sua['so_luong']), step=1)
                            with col_s2:
                                gia_moi = st.number_input("Giá bán (VNĐ)", value=int(sp_dang_sua['gia_ban']), step=1000)
                                ghi_chu_moi = st.text_area("Ghi chú", value=str(sp_dang_sua['ghi_chu']))
                            
                            if st.form_submit_button("Lưu Thay Đổi"):
                                thoi_gian_sua = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                nguoi_sua = f"{user['ten_that']} (Sửa)"
                                
                                # Cập nhật trực tiếp lên dòng tương ứng trên Google Sheets
                                # Cập nhật cột A (Mã) đến G (Thời gian)
                                ws_sanpham.update(range_name=f"A{dong_trong_sheet}:G{dong_trong_sheet}", 
                                                  values=[[str(sp_dang_sua['ma_sp']), ten_moi, sl_moi, gia_moi, ghi_chu_moi, nguoi_sua, thoi_gian_sua]])
                                
                                st.toast(f"✅ Đã cập nhật xong!", icon="🔄")
                                st.rerun() # Load lại ngay lập tức (Real-time)
                    
                    # 3. TÍNH NĂNG XÓA (Hỗ trợ xóa nhiều dòng cùng lúc)
                    else:
                        st.warning("⚠️ Chế độ Chỉnh sửa chỉ khả dụng khi bạn chọn 1 sản phẩm. Để sửa, hãy bỏ tick các sản phẩm khác.")
                    
                    if st.button(f"🗑️ XÓA {so_luong_chon} SẢN PHẨM ĐÃ CHỌN", type="primary"):
                        # Khi xóa nhiều dòng trên Google Sheets, phải xóa từ dưới lên trên để không bị lệch số dòng
                        cac_dong_can_xoa = [i + 2 for i in danh_sach_chon.index]
                        cac_dong_can_xoa.sort(reverse=True) 
                        
                        for dong in cac_dong_can_xoa:
                            ws_sanpham.delete_rows(dong)
                            
                        st.toast("🗑️ Đã xóa thành công!", icon="✅")
                        st.rerun() # Tự động làm mới bảng ngay lập tức
                        
        else:
            st.info("Bảng dữ liệu đang trống. Hãy thêm sản phẩm mới.")
