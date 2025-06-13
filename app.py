import streamlit as st
import pandas as pd
import plotly.express as px
from gspread_dataframe import get_as_dataframe
from google.oauth2.service_account import Credentials
from datetime import datetime

# Konfigurasi Halaman
st.set_page_config(page_title="Dashboard Analisis Stres", layout="wide")

# --- KONFIGURASI & OTENTIKASI GOOGLE SHEETS ---
try:
    creds = st.secrets["gcp_service_account"]
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_info(creds, scopes=scopes)
except Exception as e:
    st.error(f"Gagal memuat kredensial: {e}")
    st.stop()

# --- FUNGSI UNTUK MEMBACA DATA ---
@st.cache_data(ttl=60)
def load_data():
    try:
        from gspread import authorize
        gc = authorize(credentials)
        spreadsheet = gc.open("SmartwatchData")
        worksheet = spreadsheet.worksheet("Sheet1")
        
        df = get_as_dataframe(worksheet, evaluate_formulas=True)
        df.dropna(how='all', inplace=True)
        return df, worksheet
    except Exception as e:
        st.error(f"Gagal saat mengambil data dari Google Sheet: {e}")
        return pd.DataFrame(), None

# --- MEMUAT DAN MEMPROSES DATA ---
df, worksheet = load_data()

if not df.empty:
    try:
        # =====================================================================
        # PERBAIKAN ADA DI SINI
        # =====================================================================

        if 'Date' not in df.columns or 'Time' not in df.columns:
            st.error("ERROR: Kolom 'Date' atau 'Time' tidak ditemukan di Google Sheet.")
            st.stop()
            
        # 1. Mengubah menjadi datetime dan mengabaikan format yang salah
        df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
        
        # 2. Menghapus baris yang format waktunya salah (yang ditandai sebagai 'tidak valid')
        df.dropna(subset=['Timestamp'], inplace=True)

        # ... sisa kode di blok ini tidak perlu diubah ...
        numeric_cols = {
            'Heart Rate (BPM)': 'Heart Rate',
            'Stress Level (1-10)': 'Stress Level',
            'Temperature (°C)': 'Temperature',
            'Humidity (%)': 'Humidity'
        }
        
        for old_name, new_name in numeric_cols.items():
            if old_name in df.columns:
                df[new_name] = pd.to_numeric(df[old_name], errors='coerce')
            else:
                st.error(f"Kolom yang diharapkan '{old_name}' tidak ditemukan.")
                st.stop()

    except Exception as e:
        st.error(f"Terjadi error saat memproses data: {e}")
        st.stop()

# --- JUDUL & DESKRIPSI APLIKASI ---
st.title("🩺 Dashboard Analisis Tingkat Stres & Cuaca")
st.markdown("Visualisasi data smartwatch untuk memahami hubungan antara aktivitas, cuaca, dan tingkat stres.")

# --- VISUALISASI DATA ---
if not df.empty:
    st.header("📊 Visualisasi Interaktif")
    
    col1, col2 = st.columns(2)
    with col1:
        date_start = st.date_input("Tanggal Mulai", df['Timestamp'].min().date())
    with col2:
        date_end = st.date_input("Tanggal Akhir", df['Timestamp'].max().date())
    
    start_datetime = pd.to_datetime(date_start)
    end_datetime = pd.to_datetime(date_end)
    filtered_df = df[(df['Timestamp'] >= start_datetime) & (df['Timestamp'] <= end_datetime)]

    if not filtered_df.empty:
        avg_stress = filtered_df['Stress Level'].mean()
        avg_hr = filtered_df['Heart Rate'].mean()
        avg_humidity = filtered_df['Humidity'].mean() # PERUBAHAN: Metrik baru

        m1, m2, m3 = st.columns(3)
        m1.metric("Rata-rata Tingkat Stres", f"{avg_stress:.1f} / 10")
        m2.metric("Rata-rata Detak Jantung", f"{avg_hr:.0f} BPM")
        m3.metric("Rata-rata Kelembaban", f"{avg_humidity:.0f}%") # PERUBAHAN: Metrik baru

        st.subheader("Tren Tingkat Stres & Detak Jantung Harian")
        fig_line = px.line(filtered_df, x='Timestamp', y=['Stress Level', 'Heart Rate'], title="Tren Harian")
        st.plotly_chart(fig_line, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Stres vs. Kondisi Cuaca")
            stress_by_weather = filtered_df.groupby('Weather Condition')['Stress Level'].mean().sort_values()
            fig_bar = px.bar(stress_by_weather, x=stress_by_weather.index, y='Stress Level', title="Rata-rata Stres Berdasarkan Cuaca", color=stress_by_weather.index)
            st.plotly_chart(fig_bar, use_container_width=True)

        with c2:
            # PERUBAHAN: Grafik scatter plot diubah karena tidak ada 'Steps'
            st.subheader("Stres vs. Kelembaban")
            fig_scatter = px.scatter(filtered_df, x='Humidity', y='Stress Level', color='Weather Condition', title="Hubungan Kelembaban dan Stres", trendline="ols")
            st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.warning("Tidak ada data pada rentang tanggal yang dipilih.")
else:
    st.warning("Data tidak ditemukan atau kosong.")

# --- FORM UNTUK MENAMBAHKAN DATA BARU ---
if worksheet and not df.empty:
    st.header("✍️ Catat Data Baru")
    with st.form("tambah_data_form", clear_on_submit=True):
        st.write("Isi formulir di bawah ini untuk menambahkan data smartwatch baru.")
        
        # =====================================================================
        # PERUBAHAN BESAR: Formulir disesuaikan dengan kolom baru
        # =====================================================================
        col_form1, col_form2 = st.columns(2)
        with col_form1:
            hr = st.number_input("Heart Rate (BPM)", min_value=40, max_value=200, value=75)
            stress = st.slider("Stress Level (1-10)", 1, 10, 5)
            weather = st.selectbox("Kondisi Cuaca", df['Weather Condition'].unique())
        with col_form2:
            temp = st.number_input("Temperatur (°C)", value=28.0, step=0.5, format="%.1f")
            humidity = st.number_input("Kelembaban (%)", value=70.0, step=0.5, format="%.1f")
            
        submitted = st.form_submit_button("Tambahkan Catatan")
        if submitted:
            try:
                # Menyiapkan baris baru sesuai urutan kolom di Sheet
                date_now = datetime.now().strftime('%Y-%m-%d')
                time_now = datetime.now().strftime('%H:%M:%S')

                # Urutan: Date, Time, Heart Rate (BPM), Stress Level (1-10), dst.
                new_row = [date_now, time_now, hr, stress, temp, humidity, weather]
                
                worksheet.append_row(new_row, value_input_option='USER_ENTERED')
                
                st.success("✅ Data baru berhasil ditambahkan!")
                st.balloons()
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Gagal menambahkan data: {e}")

# --- MENAMPILKAN DATA MENTAH ---
st.header("📄 Data Lengkap")
st.dataframe(df)