import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
from io import BytesIO
import altair as alt
import math
import hashlib

st.set_page_config(page_title="Hệ Thống Quản Lý ERP", page_icon="📦", layout="wide")

# --- DANH MỤC SẢN PHẨM MẶC ĐỊNH ---
DANH_MUC_SP = ["Điện tử", "Gia dụng", "Thời trang", "Thực phẩm", "Văn phòng phẩm", "Khác"]

# --- HÀM MÃ HÓA MẬT KHẨU SHA-256 ---
def ma_hoa_mat_khau(mat_khau_goc):
    return hashlib.sha256(str(mat_khau_goc).encode('utf-8')).hexdigest()


# --- KẾT NỐI GOOGLE SHEETS PHÂN TÁN (CẬP NHẬT MỚI) ---
@st.cache_resource(ttl=600)
def ket_noi_gsheets():

    # 1. Khởi tạo xác thực
    creds_dict = json.loads(st.secrets["google_credentials"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # 2. Gọi API mở 3 file riêng biệt (Lấy Sheet đầu tiên của mỗi file)
    sheet_ns = client.open_by_url(st.secrets["url_nhansu"]).sheet1
    sheet_sp = client.open_by_url(st.secrets["url_sanpham"]).sheet1
    sheet_ls = client.open_by_url(st.secrets["url_lichsu"]).sheet1
    
    return sheet_ns, sheet_sp, sheet_ls

try:
    ws_nhansu, ws_sanpham, ws_lichsu = ket_noi_gsheets()
except Exception as e:
    st.error(f"❌ Lỗi kết nối CSDL. Vui lòng kiểm tra lại Link hoặc Quyền chia sẻ. Chi tiết: {e}")
    st.stop()

# --- BỘ NHỚ ĐỆM DỮ LIỆU (CHỐNG SẬP API QUOTA) ---
# Cache dữ liệu trong 60 giây. Nếu không có ai sửa gì, web sẽ lấy từ RAM cực nhanh.
@st.cache_data(ttl=60)
def tai_du_lieu_tu_google():
    return ws_nhansu.get_all_records(), ws_sanpham.get_all_records(), ws_lichsu.get_all_records()

# Tải dữ liệu vào biến
data_nhansu, data_sanpham, data_lichsu = tai_du_lieu_tu_google()

# TỰ ĐỘNG TẠO TÀI KHOẢN ADMIN NẾU FILE DATABASE TRỐNG
if not data_nhansu:
    try:
        ws_nhansu.append_row(['admin', ma_hoa_mat_khau('admin123'), 'Quản Trị Viên', 'admin', 'Them, Sua, Xoa, Xuat', 'HoatDong'])
        tai_du_lieu_tu_google.clear() # Xóa cache để cập nhật ngay
        st.rerun()
    except:
        st.error("Lỗi khởi tạo tài khoản Admin đầu tiên. Vui lòng kiểm tra lại file DB_NhanSu.")


    # ================= 2. LỊCH SỬ HOẠT ĐỘNG (BẢN CÓ PHÂN TRANG) =================
    elif trang_hien_tai == "📖 Lịch sử Hoạt động":
        st.title("📖 Nhật Ký Hệ Thống (Audit Trail)")
        st.info("Ghi lại toàn bộ hành vi thêm, sửa, xóa, đăng nhập của mọi thành viên để kiểm soát.")
        
        # Khởi tạo biến nhớ "Trang hiện tại" nếu chưa có
        if 'trang_lich_su' not in st.session_state:
            st.session_state.trang_lich_su = 1
            
        data_lichsu = ws_lichsu.get_all_records()
        df_ls = pd.DataFrame(data_lichsu)
        
        if not df_ls.empty:
            # Sắp xếp lịch sử: Mới nhất lên đầu
            df_ls = df_ls.sort_values(by='thoi_gian', ascending=False)
            
            # --- LOGIC PHÂN TRANG ---
            SO_DONG_MOI_TRANG = 50
            tong_so_dong = len(df_ls)
            # Tính tổng số trang (Ví dụ: 101 dòng / 50 = 2.02 -> làm tròn lên là 3 trang)
            tong_so_trang = math.ceil(tong_so_dong / SO_DONG_MOI_TRANG)
            
            # Đảm bảo số trang không bị vượt quá giới hạn nếu ai đó vừa xóa lịch sử
            if st.session_state.trang_lich_su > tong_so_trang:
                st.session_state.trang_lich_su = tong_so_trang
            if st.session_state.trang_lich_su < 1:
                st.session_state.trang_lich_su = 1
                
            # Cắt Dataframe: Lấy từ vị trí Bắt đầu đến vị trí Kết thúc
            bat_dau = (st.session_state.trang_lich_su - 1) * SO_DONG_MOI_TRANG
            ket_thuc = bat_dau + SO_DONG_MOI_TRANG
            df_hien_thi = df_ls.iloc[bat_dau:ket_thuc]
            
            # Hiển thị đúng 50 dòng của trang hiện tại
            st.dataframe(df_hien_thi, use_container_width=True)
            
            # --- GIAO DIỆN NÚT CHUYỂN TRANG ---
            col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
            
            with col_btn1:
                # Chỉ hiện nút "Trang trước" nếu không phải là trang 1
                if st.button("⬅️ Trang Trước", use_container_width=True, disabled=(st.session_state.trang_lich_su == 1)):
                    st.session_state.trang_lich_su -= 1
                    st.rerun()
                    
            with col_btn2:
                # Hiển thị thông tin tổng quan ở giữa
                st.markdown(f"<div style='text-align: center; margin-top: 8px;'><b>Trang {st.session_state.trang_lich_su} / {tong_so_trang}</b> (Tổng số: {tong_so_dong} bản ghi)</div>", unsafe_allow_html=True)
                
            with col_btn3:
                # Chỉ hiện nút "Trang tiếp" nếu chưa đến trang cuối
                if st.button("Trang Tiếp ➡️", use_container_width=True, disabled=(st.session_state.trang_lich_su == tong_so_trang)):
                    st.session_state.trang_lich_su += 1
                    st.rerun()
            
            st.divider()
            
            # Nút xóa lịch sử (Bọc trong Expander để tránh ấn nhầm)
            with st.expander("⚠️ Dọn dẹp bộ nhớ (Chỉ Admin)"):
                st.warning("Hành động này sẽ xóa vĩnh viễn toàn bộ lịch sử từ trước đến nay để giải phóng dung lượng. Hãy cân nhắc kỹ!")
                if st.button("🗑️ Xóa sạch toàn bộ lịch sử cũ", type="primary"):
                    ws_lichsu.clear()
                    ws_lichsu.append_row(["thoi_gian", "nguoi_thao_tac", "hanh_dong", "chi_tiet"])
                    st.session_state.trang_lich_su = 1 # Reset về trang 1
                    st.rerun()
        else:
            st.write("Chưa có ghi nhận nào.")


# --- GIAO DIỆN ĐĂNG NHẬP ---
if st.session_state.nguoi_dung is None:
    st.title("🔒 Đăng Nhập Hệ Thống")
    with st.form("dang_nhap"):
        tk_nhap = st.text_input("Tên đăng nhập:")
        mk_nhap = st.text_input("Mật khẩu:", type="password")
        if st.form_submit_button("Đăng Nhập"):
            user_data = next((user for user in data_nhansu if str(user['tai_khoan']) == tk_nhap and str(user['mat_khau']) == mk_nhap), None)
            if user_data:
                # KIỂM TRA TÀI KHOẢN CÓ BỊ KHÓA KHÔNG
                if str(user_data.get('trang_thai', 'HoatDong')) == 'DaKhoa':
                    st.error("❌ Tài khoản của bạn đã bị khóa! Vui lòng liên hệ Admin.")
                else:
                    st.session_state.nguoi_dung = user_data
                    ghi_log(user_data['ten_that'], "Đăng nhập", "Truy cập hệ thống")
                    st.rerun()
            else:
                st.error("❌ Sai tên đăng nhập hoặc mật khẩu!")

# --- GIAO DIỆN CHÍNH ---
else:
    user = st.session_state.nguoi_dung
    
    if st.session_state.thong_bao:
        st.toast(st.session_state.thong_bao, icon="🔔")
        st.session_state.thong_bao = None 

    with st.sidebar:
        st.success(f"👤 Chào: **{user['ten_that']}**")
        if user['vai_tro'] == 'admin':
            st.info("Quyền: TOÀN QUYỀN ADMIN")
            trang_hien_tai = st.radio("Chuyển trang:", ["📦 Quản lý Sản Phẩm", "👥 Quản lý Nhân Sự", "📖 Lịch sử Hoạt động"])
        else:
            st.info(f"Quyền: {user['quyen']}")
            trang_hien_tai = "📦 Quản lý Sản Phẩm"
            
        st.divider()
        with st.expander("🔑 Đổi Mật Khẩu", expanded=False):
            with st.form("form_doi_mk"):
                mk_cu = st.text_input("Mật khẩu cũ:", type="password")
                mk_moi = st.text_input("Mật khẩu mới:", type="password")
                if st.form_submit_button("Cập Nhật"):
                    if mk_cu != str(user['mat_khau']) or len(mk_moi) < 4:
                        st.error("Sai MK cũ hoặc MK mới quá ngắn!")
                    else:
                        cell_tk = ws_nhansu.find(str(user['tai_khoan']), in_column=1)
                        if cell_tk:
                            ws_nhansu.update(values=[[mk_moi]], range_name=f"B{cell_tk.row}")
                            st.session_state.nguoi_dung['mat_khau'] = mk_moi 
                            ghi_log(user['ten_that'], "Bảo mật", "Tự đổi mật khẩu")
                            st.success("✅ Đổi mật khẩu thành công!")
                            
        st.divider()
        if st.button("🚪 Đăng Xuất"):
            ghi_log(user['ten_that'], "Đăng xuất", "Rời hệ thống")
            st.session_state.nguoi_dung = None
            st.rerun()

    # ================= 1. QUẢN LÝ NHÂN SỰ (Có tính năng Khóa Tài Khoản) =================
    if trang_hien_tai == "👥 Quản lý Nhân Sự":
        st.title("👥 Quản Lý Nhân Sự & Phân Quyền")
        
        col_ns1, col_ns2 = st.columns(2)
        with col_ns1:
            with st.form("tao_tai_khoan", clear_on_submit=True):
                st.subheader("➕ Cấp tài khoản mới")
                tk_moi = st.text_input("Tên đăng nhập:")
                mk_moi = st.text_input("Mật khẩu:")
                ten_that_moi = st.text_input("Tên thật:")
                q_them = st.checkbox("Thêm Sản Phẩm")
                q_sua = st.checkbox("Sửa Sản Phẩm")
                q_xoa = st.checkbox("Xóa Sản Phẩm")
                q_xuat = st.checkbox("Xuất Excel")
                
                if st.form_submit_button("Tạo Tài Khoản"):
                    if tk_moi and mk_moi and ten_that_moi:
                        if tk_moi in [str(u['tai_khoan']) for u in data_nhansu]:
                            st.error("Tên đăng nhập đã tồn tại!")
                        else:
                            quyen = ", ".join([q for q, checked in zip(["Them", "Sua", "Xoa", "Xuat"], [q_them, q_sua, q_xoa, q_xuat]) if checked])
                            if not quyen: quyen = "ChiXem"
                            # Thêm HoatDong vào cột F (trang_thai)
                            ws_nhansu.append_row([tk_moi, mk_moi, ten_that_moi, 'nhan_vien', quyen, 'HoatDong'])
                            ghi_log(user['ten_that'], "Nhân sự", f"Tạo tài khoản mới: {tk_moi}")
                            st.session_state.thong_bao = "✅ Đã tạo tài khoản!"
                            st.rerun()
        
        with col_ns2:
            st.subheader("🚫 Quản Lý Trạng Thái (Khóa/Mở)")
            danh_sach_nv = [str(u['tai_khoan']) for u in data_nhansu if str(u['vai_tro']) != 'admin']
            if danh_sach_nv:
                with st.form("form_khoa_tk"):
                    tk_thao_tac = st.selectbox("Chọn tài khoản:", danh_sach_nv)
                    hanh_dong = st.radio("Hành động:", ["Mở Khóa (HoatDong)", "Đình Chỉ (DaKhoa)", "Xóa Vĩnh Viễn"])
                    if st.form_submit_button("Thực Thi"):
                        cell_tk = ws_nhansu.find(tk_thao_tac, in_column=1)
                        if cell_tk:
                            if hanh_dong == "Xóa Vĩnh Viễn":
                                ws_nhansu.delete_rows(cell_tk.row)
                                log_msg = f"Xóa vĩnh viễn tài khoản: {tk_thao_tac}"
                            else:
                                trang_thai_moi = "HoatDong" if "Mở Khóa" in hanh_dong else "DaKhoa"
                                ws_nhansu.update(values=[[trang_thai_moi]], range_name=f"F{cell_tk.row}")
                                log_msg = f"Đổi trạng thái {tk_thao_tac} thành {trang_thai_moi}"
                            ghi_log(user['ten_that'], "Nhân sự", log_msg)
                            st.session_state.thong_bao = f"✅ Đã thực thi: {log_msg}"
                            st.rerun()

        st.subheader("📋 Danh sách nhân sự hiện tại")
        df_nhansu = pd.DataFrame(data_nhansu)
        if not df_nhansu.empty:
            df_nhansu['mat_khau'] = "********"
            st.dataframe(df_nhansu, use_container_width=True)

    # ================= 2. LỊCH SỬ HOẠT ĐỘNG =================
    elif trang_hien_tai == "📖 Lịch sử Hoạt động":
        st.title("📖 Nhật Ký Hệ Thống (Audit Trail)")
        st.info("Ghi lại toàn bộ hành vi thêm, sửa, xóa, đăng nhập của mọi thành viên để kiểm soát.")
        data_lichsu = ws_lichsu.get_all_records()
        df_ls = pd.DataFrame(data_lichsu)
        if not df_ls.empty:
            df_ls = df_ls.sort_values(by='thoi_gian', ascending=False)
            st.dataframe(df_ls, use_container_width=True)
            
            if st.button("🗑️ Xóa sạch lịch sử cũ"):
                ws_lichsu.clear()
                ws_lichsu.append_row(["thoi_gian", "nguoi_thao_tac", "hanh_dong", "chi_tiet"])
                st.rerun()
        else:
            st.write("Chưa có ghi nhận nào.")

    # ================= 3. QUẢN LÝ SẢN PHẨM (Có Dashboard, Nhập Excel, Danh mục) =================
    elif trang_hien_tai == "📦 Quản lý Sản Phẩm":
        st.title("📦 Hệ Thống Kho Hàng Trực Tuyến")
        
        data_sanpham = ws_sanpham.get_all_records()
        df_sp = pd.DataFrame(data_sanpham)
        
        # Xử lý an toàn dữ liệu số
        if not df_sp.empty:
            df_sp['so_luong'] = pd.to_numeric(df_sp.get('so_luong', 0), errors='coerce').fillna(0)
            df_sp['gia_ban'] = pd.to_numeric(df_sp.get('gia_ban', 0), errors='coerce').fillna(0)
            
            # TÍNH NĂNG CẢNH BÁO TỒN KHO THẤP
            df_sp['Cảnh Báo'] = df_sp['so_luong'].apply(lambda x: "🔴 Sắp hết" if x < 5 else "🟢 Đủ hàng")

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

        # --- KHU VỰC THÊM MỚI ---
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
                            danh_sach_ma = df_sp['ma_sp'].astype(str).tolist() if not df_sp.empty else []
                            if not ma_sp or not ten_sp: st.error("Thiếu mã/tên!")
                            elif ma_sp in danh_sach_ma: st.error("Mã SP đã tồn tại!")
                            else:
                                tg = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                ws_sanpham.append_row([str(ma_sp), str(ten_sp), danh_muc, sl, gia, str(ghi_chu), user['ten_that'], tg])
                                ghi_log(user['ten_that'], "Thêm SP", f"Thêm {sl} cái {ten_sp} ({ma_sp})")
                                st.session_state.thong_bao = "✅ Đã thêm thành công!"
                                st.rerun()
            
            # NHẬP HÀNG LOẠT BẰNG EXCEL
            with col_add2:
                with st.expander("📥 Import Bằng File Excel", expanded=False):
                    st.caption("File Excel cần có các cột: ma_sp, ten_sp, danh_muc, so_luong, gia_ban, ghi_chu")
                    uploaded_file = st.file_uploader("Kéo thả file .xlsx vào đây", type=['xlsx'])
                    if uploaded_file and st.button("Bắt đầu Import"):
                        try:
                            df_import = pd.read_excel(uploaded_file).fillna("")
                            # Chuẩn bị danh sách data để đẩy lên 1 lần (Bulk Insert)
                            du_lieu_day_len = []
                            tg = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            danh_sach_ma = df_sp['ma_sp'].astype(str).tolist() if not df_sp.empty else []
                            
                            for _, row in df_import.iterrows():
                                if str(row['ma_sp']) not in danh_sach_ma:
                                    du_lieu_day_len.append([str(row['ma_sp']), str(row['ten_sp']), str(row.get('danh_muc', 'Khác')), int(row['so_luong']), int(row['gia_ban']), str(row['ghi_chu']), user['ten_that'], tg])
                                    
                            if du_lieu_day_len:
                                ws_sanpham.append_rows(du_lieu_day_len)
                                ghi_log(user['ten_that'], "Import Excel", f"Nhập hàng loạt {len(du_lieu_day_len)} sản phẩm")
                                st.session_state.thong_bao = f"✅ Đã import {len(du_lieu_day_len)} sản phẩm!"
                                st.rerun()
                            else:
                                st.warning("⚠️ Mọi mã trong file đều đã tồn tại trong kho hoặc file trống.")
                        except Exception as e:
                            st.error(f"Lỗi đọc file: Vui lòng kiểm tra lại tên các cột. Chi tiết: {e}")

        st.divider()

        # --- BẢNG DỮ LIỆU CHÍNH ---
        st.subheader("📊 Bảng Quản Lý Tương Tác")
        tu_khoa = st.text_input("🔍 Nhập Tên, Mã SP hoặc Danh Mục để lọc:")
        
        if not df_sp.empty:
            if tu_khoa:
                df_sp = df_sp[
                    df_sp['ma_sp'].astype(str).str.contains(tu_khoa, case=False, na=False) |
                    df_sp['ten_sp'].astype(str).str.contains(tu_khoa, case=False, na=False) |
                    df_sp['danh_muc'].astype(str).str.contains(tu_khoa, case=False, na=False)
                ]
                
            df_sp.insert(0, "Chọn", False)
            cot_bi_khoa = df_sp.columns.drop("Chọn").tolist()
            
            # Tùy chỉnh hiển thị cột trong bảng
            col_config = {
                "Chọn": st.column_config.CheckboxColumn("☑️", width="small"),
                "Cảnh Báo": st.column_config.TextColumn("Trạng Thái", width="medium"),
                "ma_sp": "Mã SP", "ten_sp": "Tên SP", "danh_muc": "Danh Mục", "so_luong": "SL", 
                "gia_ban": "Giá", "ghi_chu": "Ghi Chú", "nguoi_nhap": "Người Nhập", "thoi_gian": "Cập Nhật Lần Cuối"
            }
            
            edited_df = st.data_editor(df_sp, hide_index=True, use_container_width=True, disabled=cot_bi_khoa, column_config=col_config)
            
            danh_sach_chon = edited_df[edited_df["Chọn"] == True]
            sl_chon = len(danh_sach_chon)
            
            if sl_chon > 0:
                df_xuat = danh_sach_chon.drop(columns=["Chọn"])
                
                # Nút Xuất Excel
                if kiem_tra_quyen(user, 'Xuat'):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_xuat.to_excel(writer, index=False)
                    st.download_button("📥 Tải Dữ Liệu Đã Chọn", data=output.getvalue(), file_name=f"Kho_{datetime.now().strftime('%d%m%y_%H%M')}.xlsx")
                
                # Form Sửa
                if kiem_tra_quyen(user, 'Sua') and sl_chon == 1:
                    st.subheader("✏️ Chỉnh Sửa Sản Phẩm")
                    sp_dang_sua = danh_sach_chon.iloc[0]
                    with st.form("form_sua"):
                        col_s1, col_s2, col_s3 = st.columns(3)
                        with col_s1:
                            t_moi = st.text_input("Tên", value=str(sp_dang_sua['ten_sp']))
                            sl_moi = st.number_input("SL", value=int(sp_dang_sua['so_luong']))
                        with col_s2:
                            dm_moi = st.selectbox("Danh mục", DANH_MUC_SP, index=DANH_MUC_SP.index(sp_dang_sua['danh_muc']) if sp_dang_sua['danh_muc'] in DANH_MUC_SP else 0)
                            gia_moi = st.number_input("Giá", value=int(sp_dang_sua['gia_ban']))
                        with col_s3:
                            gc_moi = st.text_area("Ghi chú", value=str(sp_dang_sua['ghi_chu']))
                            
                        if st.form_submit_button("Lưu Cập Nhật"):
                            cell = ws_sanpham.find(str(sp_dang_sua['ma_sp']))
                            if cell:
                                tg_sua = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                ws_sanpham.update(values=[[str(sp_dang_sua['ma_sp']), t_moi, dm_moi, sl_moi, gia_moi, gc_moi, f"{user['ten_that']} (Sửa)", tg_sua]], range_name=f"A{cell.row}:H{cell.row}")
                                ghi_log(user['ten_that'], "Sửa SP", f"Cập nhật mã {sp_dang_sua['ma_sp']}")
                                st.session_state.thong_bao = "✅ Đã lưu cập nhật!"
                                st.rerun()
                
                # Nút Xóa
                if kiem_tra_quyen(user, 'Xoa'):
                    if st.button(f"🗑️ XÓA {sl_chon} SẢN PHẨM", type="primary"):
                        ma_xoa = danh_sach_chon['ma_sp'].astype(str).tolist()
                        rows_del = [ws_sanpham.find(m).row for m in ma_xoa if ws_sanpham.find(m)]
                        for r in sorted(rows_del, reverse=True): ws_sanpham.delete_row(r)
                        ghi_log(user['ten_that'], "Xóa SP", f"Xóa {sl_chon} sản phẩm: {', '.join(ma_xoa)}")
                        st.session_state.thong_bao = f"🗑️ Đã xóa {sl_chon} SP!"
                        st.rerun()
