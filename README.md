# EDC Transaction POC

Proof-of-concept database PostgreSQL untuk pemrosesan transaksi EDC (Electronic Data Capture) di Indonesia, dibangun berdasarkan data Points of Interest (POI) nyata. Seeder menghasilkan data transaksi sintetis yang realistis lengkap dengan laporan aktivitas kartu JPEG dan laporan batch Excel.

---

## Struktur Proyek

```
poc-edc/
├── seed_data.py                  # Seeder utama — generate transaksi dari data POI
├── schema.sql                    # DDL — semua tabel, indeks, view, data referensi
├── queries.sql                   # Query SQL analitik dengan filter rentang tanggal
├── input/                        # ← buat folder ini, letakkan semua file input di sini
│   ├── poc_edc.zip               # SQL dump lengkap — restore untuk skip seeding
│   ├── poi_edc.csv               # Data POI utama (merchant aktif)
│   ├── list_new_edc.xlsx         # Merchant baru untuk di-insert ke DB
│   ├── list_update_edc.xlsx      # Merchant yang datanya diperbarui
│   ├── list_delete_edc.xlsx      # Merchant yang sudah tutup/dihapus
│   ├── list_batch.xlsx           # Data campuran: ATM (realtime) + merchant baru
│   └── list_realtime.csv         # (Di-generate otomatis) tracking sinyal ATM
└── reports/
    └── YYYYMMDD/
        ├── *.jpg                 # Kartu aktivitas JPEG per merchant
        ├── merchant_activity_report.xlsx
        └── batch_activity_report.xlsx
```

---

## Prasyarat

- PostgreSQL 13+
- Python 3.9+
- `psycopg2-binary` — driver database
- `Pillow` — generate kartu JPEG
- `openpyxl` — baca/tulis laporan Excel

```bash
pip install psycopg2-binary Pillow openpyxl
```

---

## Setup Awal

### 1. Buat folder `input/` dan tempatkan file input

```bash
mkdir input
```

Salin semua file input (`poi_edc.csv`, `list_*.xlsx`, `poc_edc.zip`, dll.) ke dalam folder `input/`.

---

### Opsi A — Restore dari SQL Dump *(lebih cepat, skip seeding)*

File `input/poc_edc.zip` berisi SQL dump lengkap database yang sudah terisi data transaksi. Gunakan ini untuk langsung mendapatkan data tanpa perlu menjalankan seeder dari awal.

```bash
# Ekstrak dump dari zip
unzip input/poc_edc.zip -d input/

# Buat database
PGPASSWORD=Manualbrew1 psql -U postgres -c "CREATE DATABASE edtransmap;"

# Restore dump
PGPASSWORD=Manualbrew1 psql -U postgres -d edtransmap -f input/poc_edc.sql
# atau jika format custom:
# PGPASSWORD=Manualbrew1 pg_restore -U postgres -d edtransmap input/poc_edc.dump
```

Setelah restore selesai, langsung jalankan laporan:

```bash
python seed_data.py --report
```

---

### Opsi B — Setup dari Nol *(seed penuh)*

### 1. Buat database dan terapkan skema

```bash
python -m venv venv
source venv/Scripts/activate          # Windows
# source venv/bin/activate            # Linux/Mac
pip install psycopg2-binary Pillow openpyxl

PGPASSWORD=Manualbrew1 psql -U postgres -c "CREATE DATABASE edtransmap;"
PGPASSWORD=Manualbrew1 psql -U postgres -d edtransmap -f schema.sql
```

### 2. Seed data awal

```bash
python seed_data.py
```

---

## Mode Seeder

| Perintah | Fungsi |
|---|---|
| `python seed_data.py` | **Default cerdas** — jika DB sudah ada data, append dari tanggal terakhir; jika kosong, seed penuh dari awal |
| `python seed_data.py --reset` | **Reset penuh** — truncate semua tabel lalu seed ulang dari awal |
| `python seed_data.py --purge` | **Purge rentang** — hapus transaksi/settlement untuk `DATE_START`–`DATE_END`, simpan merchant/kartu, lalu seed ulang transaksi |
| `python seed_data.py --report` | **Laporan saja** — skip seeding, query data yang ada, cetak kartu konsol dan simpan JPEG |
| `python seed_data.py --append` | **Append** — cari tanggal transaksi terakhir di DB, seed dari hari berikutnya hingga `DATE_END`, tidak menyentuh baris yang ada |
| `python seed_data.py --prune-closed` | **Prune merchant tutup** — baca `closed_from` dari `poi_edc.csv`, hapus transaksi/settlement pada atau setelah tanggal penutupan |
| `python seed_data.py --batch-seed` | **Batch seed** — proses semua file `list_*.xlsx` di folder `input/`, insert merchant baru, generate transaksi, hasilkan `batch_activity_report.xlsx` |
| `python seed_data.py --add-merchants` | **Tambah merchant** — insert merchant dari `poi_edc.csv` yang belum ada di DB, lalu generate transaksi |

---

## Konfigurasi

Semua pengaturan ada di bagian atas `seed_data.py`. Override koneksi DB via environment variable:

| Variable | Default | Keterangan |
|---|---|---|
| `PG_HOST` | `localhost` | Host PostgreSQL |
| `PG_PORT` | `5432` | Port PostgreSQL |
| `PG_DB` | `edtransmap` | Nama database |
| `PG_USER` | `postgres` | Username |
| `PG_PASSWORD` | `Manualbrew1` | Password |

**Rentang tanggal** — ubah dua baris ini di `seed_data.py`:

```python
DATE_START = date(2025, 1, 1)
DATE_END   = date(2026, 6, 23)   # inklusif
```

---

## Format File Input

### `poi_edc.csv` — Data POI Utama

File CSV utama yang memuat semua merchant aktif. Dibaca pada setiap mode seeding.

| Kolom | Wajib | Keterangan |
|---|---|---|
| `name1` | ✓ | Nama merchant |
| `displaylatitude` | ✓ | Latitude tampilan |
| `displaylongitude` | ✓ | Longitude tampilan |
| `routinglatitude` | | Latitude routing (opsional, fallback ke display) |
| `routinglongitude` | | Longitude routing |
| `primarycategorynm` | ✓ | Kategori POI (misal: `Restaurant`, `Coffee Shop`) |
| `hno` | | Nomor rumah/gedung |
| `streetname` | | Nama jalan |
| `postalcode` | | Kode pos |
| `admin2` | ✓ | Provinsi |
| `admin3` | ✓ | Kota/Kabupaten |
| `admin4` | | Kecamatan |
| `admin5` | | Kelurahan |
| `PHONE` | | Nomor telepon |
| `MOBILE` | | Nomor HP |
| `status` | ✓ | `ACTIVE` atau `INACTIVE` — hanya baris `ACTIVE` yang di-seed |
| `closed_from` | | Tanggal penutupan format `YYYY-MM-DD` — transaksi setelah tanggal ini tidak di-generate |
| `mondayopening` | | Jam buka Senin (desimal hari, misal `0.375` = 09:00) |
| `mondayclosing` | | Jam tutup Senin |
| *(selasa–minggu)* | | Kolom jam serupa untuk hari lainnya |

> **Format jam (day-fraction):** Nilai desimal antara 0–1 mewakili proporsi hari. Contoh: `0.375` = 9 jam × (1/24) = 09:00, `0.875` = 21:00.

---

### `list_new_edc.xlsx` — Merchant Baru

Sheet aktif: baris pertama sebagai header. Merchant yang belum ada di DB akan di-insert dan di-seed transaksinya.

| Kolom | Wajib | Keterangan |
|---|---|---|
| `supplier_poiid` | ✓ | ID unik merchant (tampil di kolom ID laporan batch) |
| `poi_nm` | ✓ | Nama merchant |
| `display_point_latitude` | ✓ | Latitude |
| `display_point_longitude` | ✓ | Longitude |
| `routing_latitude` | | Latitude routing |
| `routing_longitude` | | Longitude routing |
| `category` | ✓ | Kategori POI |
| `operating hours` | | Jam operasional teks bebas (misal: `Monday-Sunday, 08:00-22:00` atau `24/7`) |
| `house_number` | | Nomor rumah |
| `street_name` | | Nama jalan |
| `postal_code` | | Kode pos |
| `Admin 2` | ✓ | Provinsi |
| `Admin 3` | ✓ | Kota/Kabupaten |
| `Admin 4` | | Kecamatan |
| `Admin 5` | | Kelurahan |
| `phone number` | | Telepon |
| `Mobile` | | HP |

> **Format jam teks:** `Monday-Sunday, 08:00-22:00` \| `Mon-Fri, 09:00-17:00; Sat, 10:00-15:00` \| `24/7`

---

### `list_update_edc.xlsx` — Merchant Diperbarui

Merchant yang sudah ada di DB namun data POI-nya perlu diperbarui (koordinat, jam, kategori, dsb). Format kolom sama dengan `list_new_edc.xlsx` dengan tambahan kolom verifikasi.

| Kolom | Wajib | Keterangan |
|---|---|---|
| `ID` | ✓ | ID unik merchant (tampil di kolom ID laporan batch) |
| `POI name` | ✓ | Nama merchant |
| `displaylatitude` | ✓ | Latitude |
| `displaylongitude` | ✓ | Longitude |
| `routing_latitude` | | Latitude routing |
| `routing_longitude` | | Longitude routing |
| `primarycategorynm` | ✓ | Kategori POI |
| `operating_hours` | | Jam operasional teks bebas |
| `house_number` | | Nomor rumah |
| `streetname` | | Nama jalan |
| `postalcode` | | Kode pos |
| `Admin 2` | ✓ | Provinsi |
| `Admin 3` | ✓ | Kota/Kabupaten |
| `Admin 4` | | Kecamatan |
| `Admin 5` | | Kelurahan |
| `PHONE` | | Telepon |
| `MOBILE` | | HP |

---

### `list_delete_edc.xlsx` — Merchant Tutup/Dihapus

Merchant yang sudah tidak aktif. Transaksi setelah `closed_from` akan di-prune; merchant tetap ada di DB dan muncul di sheet DELETE laporan batch.

| Kolom | Wajib | Keterangan |
|---|---|---|
| `supplier_poiid` | ✓ | ID unik merchant |
| `poi_nm` | ✓ | Nama merchant |
| `displaylatitude` | ✓ | Latitude |
| `displaylongitude` | ✓ | Longitude |
| `routinglatitude` | | Latitude routing |
| `routinglongitude` | | Longitude routing |
| `primarycategorynm` | ✓ | Kategori POI |
| `hno` | | Nomor rumah |
| `streetname` | | Nama jalan |
| `postalcode` | | Kode pos |
| `admin2` | ✓ | Provinsi |
| `admin3` | ✓ | Kota/Kabupaten |
| `admin4` | | Kecamatan |
| `admin5` | | Kelurahan |
| `PHONE` | | Telepon |
| `MOBILE` | | HP |
| `mondayopening` / `mondayclosing` | | Jam operasional format day-fraction (sama seperti `poi_edc.csv`) |
| *(selasa–minggu)* | | Kolom jam serupa |
| `closed_from` | ✓ | Tanggal penutupan format `YYYY-MM-DD` — transaksi pada/setelah tanggal ini dihapus |
| `last update` | | Teks referensi tanggal penutupan (misal: `review google 2025 Q 1`) |

> Kolom `closed_from` perlu ditambahkan manual ke xlsx dengan tanggal penutupan dalam format `YYYY-MM-DD`. Jika merchant memiliki transaksi sebelum `closed_from` dalam rentang DATE_START–DATE_END, transaksi tersebut tetap dipertahankan.

---

### `list_batch.xlsx` — Data Batch Campuran (ATM + Merchant Baru)

File ini memuat data campuran. Merchant dengan `category = ATM` diperlakukan sebagai **realtime** (hanya generate kartu sinyal, tidak masuk DB). Merchant lainnya diperlakukan sebagai merchant baru seperti `list_new_edc.xlsx`.

| Kolom | Wajib | Keterangan |
|---|---|---|
| `id` | ✓ | ID unik POI |
| `poi_nm` | ✓ | Nama POI |
| `category` | ✓ | Kategori — nilai `ATM` → realtime, selainnya → merchant baru |
| `display_point_latitude` | ✓ | Latitude |
| `display_point_longitude` | ✓ | Longitude |
| `operating hours` | | Jam operasional teks bebas |
| `house_number` | | Nomor rumah |
| `street_name` | | Nama jalan (dipakai di nama kartu realtime, prefix "Jalan" otomatis dihapus) |
| `postal_code` | | Kode pos |
| `Admin 2` | ✓ | Provinsi |
| `Admin 3` | ✓ | Kota/Kabupaten |
| `Admin 4` | | Kecamatan |
| `Admin 5` | | Kelurahan |
| `phone number` | | Telepon |
| `Mobile` | | HP |
| `last update signal date time` | | Datetime sinyal terakhir (jika kosong, diganti dengan waktu acak hari ini dalam jam operasional) |
| `last_update` | | Tanggal update terakhir format `DD/MM/YYYY` (fallback jika kolom signal kosong) |

> **ATM / Realtime:** Nama pada kartu JPEG ditulis **HURUF KAPITAL** + nama jalan tanpa prefix "Jalan" (contoh: `ATM BCA Pantai Indah Kapuk`). Sinyal terakhir di-generate acak dalam jam operasional hari ini. Dianggap **AKTIF** jika sinyal dalam 90 hari terakhir.

---

### `list_realtime.csv` — Tracking Sinyal Realtime *(Di-generate Otomatis)*

File ini **tidak perlu dibuat manual**. Di-generate otomatis saat `--batch-seed` memproses `list_batch.xlsx`. Digunakan kembali oleh `--report` untuk regenerasi kartu tanpa membaca xlsx lagi.

| Kolom | Keterangan |
|---|---|
| `id` | ID POI |
| `poi_nm` | Nama POI (asli, sebelum uppercase) |
| `last_signal` | Datetime sinyal terakhir format `YYYY-MM-DD HH:MM:SS` |
| `category` | Kategori (biasanya `ATM`) |
| `street` | Nama jalan lengkap (prefix "Jalan" dihapus saat rendering kartu) |

---

## Output Laporan

Setelah seeding atau dengan `--report`, script menghasilkan:

1. **Kartu konsol** — dicetak ke terminal per merchant
2. **JPEG per merchant** — disimpan ke `reports/YYYYMMDD/`
3. **`merchant_activity_report.xlsx`** — seluruh merchant dalam satu file Excel
4. **`batch_activity_report.xlsx`** — hanya merchant dari file batch, terdiri dari 4 sheet:

| Sheet | Isi |
|---|---|
| `NEW` | Merchant dari `list_new_edc.xlsx` dan non-ATM dari `list_batch.xlsx` |
| `UPDATE` | Merchant dari `list_update_edc.xlsx` |
| `DELETE` | Merchant dari `list_delete_edc.xlsx` |
| `REALTIME` | ATM dari `list_batch.xlsx` (kartu sinyal, bukan kartu transaksi) |

Setiap baris laporan batch berisi: nomor urut, ID sumber, nama merchant, waktu sinyal terakhir, dan foto kartu JPEG.

---

## Skema Database

### Tabel

| Tabel | PK | Fungsi |
|---|---|---|
| `admin_areas` | `SERIAL` | Hierarki wilayah: Provinsi → Kota → Kecamatan → Kelurahan |
| `acquirers` | `SMALLSERIAL` | Bank acquirer EDC (BCA, Mandiri, BNI) |
| `merchants` | `UUID` | Profil merchant dengan koordinat geo dan FK area admin |
| `terminals` | `UUID` | Mesin EDC fisik, satu per merchant |
| `cards` | `BIGSERIAL` | Referensi kartu sintetis yang di-mask |
| `qris_issuers` | `SMALLSERIAL` | Sumber QRIS: GoPay, ShopeePay, Dana, OVO, LinkAja, BCA, Mandiri, BNI, BRI |
| `transactions` | `BIGSERIAL` | Semua transaksi pembayaran |
| `settlement` | `SERIAL` | Ringkasan settlement harian per merchant |
| `transaction_log` | `BIGSERIAL` | Audit trail pesan ISO 8583 mentah |

### Format Kode

| Field | Format | Contoh |
|---|---|---|
| `merchant_code` | `MCH-{MCC}-{YYYYMMDD}-{SEQ:05d}` | `MCH-5814-20250301-00001` |
| `terminal_code` | `TID-{MCC}-{YYYYMMDD}-{SEQ:05d}` | `TID-5814-20250301-00001` |
| `trace_number` | `RRN{YYYYMMDD}{SEQ:06d}` | `RRN20260601000001` |

---

## Karakteristik Data Transaksi

- **QRIS vs Kartu** — F&B dan layanan sehari-hari cenderung QRIS (55–70%); retail premium cenderung kartu (25–28%)
- **Mix transaksi** — ~85% SALE, ~3% REFUND (kartu saja), ~2% VOID
- **Approval rate** — ~88% untuk EDC kartu, ~97% untuk QRIS
- **Jam operasional** — diambil dari data nyata di CSV/xlsx. Default per kategori diterapkan jika tidak ada data jam
- **Hari libur** — hari libur nasional Indonesia (2025–2026) menyebabkan kategori tertentu (Pakaian, Bunga, Sekolah, Dokter Gigi) tidak generate transaksi. F&B dan kesehatan tetap buka

---

## Query Analitik

`queries.sql` berisi 15 query siap pakai. Set rentang tanggal di psql terlebih dahulu:

```sql
\set date_from '2025-01-01'
\set date_to   '2026-06-23'
```

| # | Query |
|---|---|
| 1 | Transaksi mentah (rentang tanggal, terbaru lebih dulu) |
| 2 | Total keseluruhan — gross sales, refund, net revenue, approval rate |
| 3 | Tren transaksi harian |
| 4 | Split channel pembayaran (QRIS vs EDC_CARD) |
| 5 | Rincian issuer QRIS dengan persentase |
| 6 | Rincian merek kartu |
| 7 | Top merchant berdasarkan volume transaksi |
| 8 | Rincian kategori/MCC dengan rata-rata tiket dan share QRIS |
| 9 | Analisis penolakan berdasarkan kode respons ISO 8583 |
| 10 | Approval rate per terminal |
| 11 | Ringkasan geografis (Provinsi → Kota → Kecamatan) |
| 12 | Status settlement per tanggal |
| 13 | Transaksi approved yang belum di-settle |
| 14 | Efek hari libur — rata-rata penjualan harian libur vs hari biasa |
| 15 | Heatmap transaksi per jam |
