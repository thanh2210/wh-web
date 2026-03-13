import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Hệ Thống Quản Lý", page_icon="📦", layout="wide")

# --- SỬA LỖI 1: THÊM THỜI GIAN HẾT HẠN CACHE KHÔNG BỊ LỖI TOKEN GOOGLE (TTL=600s) ---
@st.cache_resource(ttl=600)
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
    st.error("❌ Lỗi kết nối Google Sheets. Vui lòng kiểm tra lại Secrets.")
    st.stop()

# --- KHỞI TẠO BIẾN BỘ NHỚ ---
if 'nguoi_dung' not in st.session_state:
    st.session_state.nguoi_dung = None
if 'thong_bao' not in st.session_state:
    st.session_state.thong_bao = None

# Lấy dữ liệu nhân sự
data_nhansu = ws_nhansu.get_all_records()

# --- GIAO DIỆN ĐĂNG NHẬP ---
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

# --- GIAO DIỆN CHÍNH ---
else:
    user = st.session_state.nguoi_dung
    
    # SỬA LỖI 4: Hiển thị thông báo ổn định sau khi web tải lại
    if st.session_state.thong_bao:
        st.success(st.session_state.thong_bao)
        st.session_state.thong_bao = None # Xóa trạng thái sau khi hiện

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
                        st.error("❌ Tên đăng nhập này đã tồn tại!")
                    else:
                        ws_nhansu.append_row([tk_moi, mk_moi, ten_that_moi, 'nhan_vien', quyen_moi])
                        st.session_state.thong_bao = "✅ Tạo tài khoản thành công!"
                        st.rerun()
                else:
                    st.error("⚠️ Vui lòng điền đủ thông tin!")
        st.divider()
        st.subheader("📋 Danh sách nhân sự hiện tại")
        st.dataframe(pd.DataFrame(data_nhansu), use_container_width=True)

    # ================= QUẢN LÝ SẢN PHẨM =================
    elif trang_hien_tai == "📦 Quản lý Sản Phẩm":
        st.title("📦 Bảng Trắng Quản Lý Sản Phẩm (Real-time)")
        
        # Lấy dữ liệu
        data_sanpham = ws_sanpham.get_all_records()
        df_sp = pd.DataFrame(data_sanpham)
        
        # Khởi tạo danh sách mã sản phẩm để check trùng lặp (SỬA LỖI 3)
        danh_sach_ma_sp = df_sp['ma_sp'].astype(str).tolist() if not df_sp.empty else []

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
                        if not ma_sp or not ten_sp:
                            st.error("⚠️ Thiếu mã hoặc tên sản phẩm!")
                        elif str(ma_sp) in danh_sach_ma_sp: # Chặn mã trùng lặp
                            st.error(f"❌ Mã sản phẩm '{ma_sp}' đã tồn tại! Vui lòng chọn mã khác.")
                        else:
                            thoi_gian_nhap = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ws_sanpham.append_row([str(ma_sp), str(ten_sp), so_luong, gia_ban, str(ghi_chu), user['ten_that'], thoi_gian_nhap])
                            st.session_state.thong_bao = f"✅ Đã thêm '{ten_sp}' thành công!"
                            st.rerun()
        else:
            st.warning("⚠️ Tài khoản của bạn chỉ có quyền XEM dữ liệu.")

        st.divider()

        # --- KHU VỰC 2: BẢNG TRẮNG TƯƠNG TÁC ---
        st.subheader("📊 Dữ Liệu Tổng (Chọn ô tick đầu tiên để thao tác)")
        
        if not df_sp.empty:
            df_sp.insert(0, "Chọn", False)
            
            # Cấu hình khóa các cột, tránh lỗi Streamlit syntax
            cot_bi_khoa = df_sp.columns.drop("Chọn").tolist()
            
            edited_df = st.data_editor(
                df_sp,
                hide_index=True,
                use_container_width=True,
                disabled=cot_bi_khoa,
                column_config={
                    "Chọn": st.column_config.CheckboxColumn("☑️ Chọn", help="Tick để chọn sản phẩm"),
                    "ma_sp": "Mã SP", "ten_sp": "Tên SP", "so_luong": "Số Lượng", 
                    "gia_ban": "Giá Bán", "ghi_chu": "Ghi Chú", "nguoi_nhap": "Người Nhập", "thoi_gian": "Thời Gian"
                }
            )
            
            danh_sach_chon = edited_df[edited_df["Chọn"] == True]
            so_luong_chon = len(danh_sach_chon)
            
            # --- KHU VỰC 3: THAO TÁC VỚI DỮ LIỆU ĐÃ CHỌN ---
            if so_luong_chon > 0:
                st.info(f"📌 Đang chọn **{so_luong_chon}** sản phẩm.")
                df_xuat_excel = danh_sach_chon.drop(columns=["Chọn"])
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_xuat_excel.to_excel(writer, index=False, sheet_name='Sản Phẩm Đã Chọn')
                
                ten_file = f"San_Pham_Da_Chon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                st.download_button("📥 Xuất File Excel (Chỉ file được chọn)", data=output.getvalue(), file_name=ten_file, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
                if (user['quyen'] == 'chinh_sua' or user['vai_tro'] == 'admin'):
                    # TÍNH NĂNG SỬA
                    if so_luong_chon == 1:
                        st.subheader("✏️ Chỉnh Sửa Sản Phẩm Này")
                        
                        # Lấy mã sản phẩm làm "mỏ neo" thay vì lấy dòng (SỬA LỖI 2)
                        ma_sp_dang_sua = str(danh_sach_chon.iloc[0]['ma_sp'])
                        
                        with st.form("form_sua"):
                            col_s1, col_s2 = st.columns(2)
                            with col_s1:
                                st.text_input("Mã SP (Không được sửa)", value=ma_sp_dang_sua, disabled=True)
                                ten_moi = st.text_input("Tên sản phẩm", value=str(danh_sach_chon.iloc[0]['ten_sp']))
                                sl_moi = st.number_input("Số lượng", value=int(danh_sach_chon.iloc[0]['so_luong']), step=1)
                            with col_s2:
                                gia_moi = st.number_input("Giá bán (VNĐ)", value=int(danh_sach_chon.iloc[0]['gia_ban']), step=1000)
                                ghi_chu_moi = st.text_area("Ghi chú", value=str(danh_sach_chon.iloc[0]['ghi_chu']))
                            
                            if st.form_submit_button("Lưu Thay Đổi"):
                                try:
                                    # Tìm kiếm trực tiếp mã SP trên Google Sheets
                                    cell = ws_sanpham.find(ma_sp_dang_sua)
                                    if cell:
                                        thoi_gian_sua = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        nguoi_sua = f"{user['ten_that']} (Sửa)"
                                        
                                        ws_sanpham.update(values=[[ma_sp_dang_sua, ten_moi, sl_moi, gia_moi, ghi_chu_moi, nguoi_sua, thoi_gian_sua]], range_name=f"A{cell.row}:G{cell.row}")
                                        
                                        st.session_state.thong_bao = "✅ Cập nhật thành công!"
                                        st.rerun()
                                    else:
                                        st.error("❌ Không tìm thấy sản phẩm trên Google Sheets!")
                                except Exception as e:
                                    st.error(f"Lỗi hệ thống: {e}")
                                    
                    else:
                        st.warning("⚠️ Để chỉnh sửa, vui lòng chỉ tick chọn 1 sản phẩm duy nhất.")
                    
                    # TÍNH NĂNG XÓA
                    if st.button(f"🗑️ XÓA {so_luong_chon} SẢN PHẨM ĐÃ CHỌN", type="primary"):
                        ma_sp_can_xoa = danh_sach_chon['ma_sp'].astype(str).tolist()
                        
                        # Tìm số dòng chính xác của từng mã sản phẩm
                        rows_to_delete = []
                        for ma in ma_sp_can_xoa:
                            try:
                                cell = ws_sanpham.find(ma)
                                if cell:
                                    rows_to_delete.append(cell.row)
                            except:
                                pass
                                
                        # Xóa từ dưới lên trên để không bị tụt dòng        
                        rows_to_delete.sort(reverse=True)
                        for r in rows_to_delete:
                            ws_sanpham.delete_row(r)
                            
                        st.session_state.thong_bao = f"🗑️ Đã xóa an toàn {len(rows_to_delete)} sản phẩm!"
                        st.rerun()
                        
        else:
            st.info("Bảng dữ liệu đang trống. Hãy thêm sản phẩm mới.")
