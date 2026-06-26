# EDC Transaction POC

Proof-of-concept database PostgreSQL untuk pemrosesan transaksi EDC (Electronic Data Capture) di Indonesia, dibangun berdasarkan data Points of Interest (POI) nyata. Seeder menghasilkan data transaksi sintetis yang realistis lengkap dengan laporan aktivitas kartu JPEG dan laporan batch Excel.

---

## Struktur Proyek

```
poc-edc/
├── seed_data.py                  # Seeder utama — generate transaksi dari data POI
├── config.py                     # Konstanta konfigurasi (DB, tanggal, path, lookup table)
├── helpers.py                    # Fungsi utilitas tanpa akses DB
├── schema.sql                    # DDL — semua tabel, indeks, view, data referensi
├── queries.sql                   # Query SQL analitik dengan filter rentang tanggal
├── input/                        # ← buat folder ini, letakkan semua file input di sini
│   ├── poc_edc.zip               # SQL dump lengkap — restore untuk skip seeding
│   ├── list_edc.csv              # Sumber data tunggal — semua merchant (new/update/delete/realtime)
│   └── list_realtime.csv         # (Di-generate otomatis) tracking sinyal ATM/bank
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
- `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` — upload ke Google Drive *(opsional)*

```bash
pip install psycopg2-binary Pillow openpyxl

# Opsional — hanya jika menggunakan --upload
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

---

## Setup Awal

### 1. Buat folder `input/` dan tempatkan file input

```bash
mkdir input
```

Salin `list_edc.csv` ke dalam folder `input/`.

---

### Opsi A — Restore dari SQL Dump _(lebih cepat, skip seeding)_

File `input/poc_edc.zip` berisi SQL dump lengkap database yang sudah terisi data transaksi. Gunakan ini untuk langsung mendapatkan data tanpa perlu menjalankan seeder dari awal.

```bash
# Ekstrak dump dari zip
unzip input/poc_edc.zip -d input/

# Buat database
PGPASSWORD=pgpassword psql -U postgres -c "CREATE DATABASE edtransmap;"

# Restore dump
PGPASSWORD=pgpassword psql -U postgres -d edtransmap -f input/poc_edc.sql
```

Setelah restore selesai, langsung jalankan laporan:

```bash
python seed_data.py --report
```

---

### Opsi B — Setup dari Nol _(seed penuh)_

```bash
python -m venv venv
source venv/Scripts/activate          # Windows
# source venv/bin/activate            # Linux/Mac
pip install psycopg2-binary Pillow openpyxl

PGPASSWORD=Manualbrew1 psql -U postgres -c "CREATE DATABASE edtransmap;"
PGPASSWORD=Manualbrew1 psql -U postgres -d edtransmap -f schema.sql

python seed_data.py
```

---

## Mode Seeder

| Perintah                                 | Fungsi                                                                                                                                      |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `python seed_data.py`                    | **Default cerdas** — baca `list_edc.csv`; jika DB sudah ada data, append dari tanggal terakhir; jika kosong, seed penuh dari awal           |
| `python seed_data.py --reset`            | **Reset penuh** — truncate semua tabel lalu seed ulang dari awal menggunakan `list_edc.csv`                                                 |
| `python seed_data.py --purge`            | **Purge rentang** — hapus transaksi/settlement untuk `DATE_START`–`DATE_END`, simpan merchant/kartu, lalu seed ulang transaksi               |
| `python seed_data.py --report`           | **Laporan saja** — skip seeding, query data yang ada, cetak kartu konsol dan simpan JPEG                                                    |
| `python seed_data.py --report-selected`  | **Laporan terpilih** — sama seperti `--report` tetapi hanya merchant yang ada di `list_edc.csv` (difilter berdasarkan kolom `reference`)     |
| `python seed_data.py --append`           | **Append** — cari tanggal transaksi terakhir di DB, seed dari hari berikutnya hingga `DATE_END`, tidak menyentuh baris yang ada             |
| `python seed_data.py --prune-closed`     | **Prune merchant tutup** — hapus transaksi/settlement pada atau setelah `closed_at`/`closed_from` untuk merchant berstatus delete            |
| `python seed_data.py --add-merchants`    | **Tambah merchant** — insert merchant dari `list_edc.csv` yang belum ada di DB, lalu generate transaksi                                     |
| `python seed_data.py --upload`           | **Upload GDrive** — upload `merchant_activity_report.xlsx` dan `batch_activity_report.xlsx` ke folder Google Drive yang sudah dikonfigurasi |

---

## Konfigurasi

Semua konstanta ada di `config.py`. Override koneksi DB via environment variable:

| Variable      | Default       | Keterangan      |
| ------------- | ------------- | --------------- |
| `PG_HOST`     | `localhost`   | Host PostgreSQL |
| `PG_PORT`     | `5432`        | Port PostgreSQL |
| `PG_DB`       | `edtransmap`  | Nama database   |
| `PG_USER`     | `postgres`    | Username        |
| `PG_PASSWORD` | `Manualbrew1` | Password        |

**Rentang tanggal** — ubah dua baris ini di `config.py`:

```python
DATE_START = date(2025, 1, 1)
DATE_END   = date.today()   # inklusif
```

**Google Drive** — set konstanta berikut di `config.py`:

| Konstanta          | Default            | Keterangan                                                  |
| ------------------ | ------------------ | ----------------------------------------------------------- |
| `GDRIVE_FOLDER_ID` | `""`               | ID folder Google Drive tujuan (kosongkan untuk nonaktifkan) |
| `GDRIVE_CREDENTIALS` | `credentials.json` | Path ke file OAuth2 dari Google Cloud Console             |
| `GDRIVE_TOKEN`     | `token.json`       | Token cache (dibuat otomatis setelah otorisasi pertama)     |

---

## Upload ke Google Drive

### Persiapan

1. Buka [Google Cloud Console](https://console.cloud.google.com/) → buat project baru
2. Aktifkan **Google Drive API** (APIs & Services → Enable APIs)
3. Buat kredensial: **OAuth 2.0 Client ID** dengan tipe *Desktop App*
4. Unduh file kredensial → simpan sebagai `credentials.json` di root folder proyek
5. Buka folder tujuan di Google Drive → salin ID dari URL: `.../folders/**<ID>**`
6. Set konstanta di `config.py`:
   ```python
   GDRIVE_FOLDER_ID = "your_folder_id_here"
   ```

### Menjalankan Upload

```bash
# Pastikan laporan sudah di-generate terlebih dahulu
python seed_data.py --report       # atau --batch-seed

# Upload ke Google Drive
python seed_data.py --upload
```

Pertama kali dijalankan, browser akan terbuka untuk otorisasi Google. Setelah disetujui, token disimpan ke `token.json` sehingga run berikutnya tidak perlu login ulang.

File yang di-upload ke `<designated folder>/YYYYMMDD/`:
- `merchant_activity_report.xlsx`
- `batch_activity_report.xlsx` (versi Drive memiliki hyperlink ke JPEG, bukan gambar tertanam)

Jika file sudah ada di folder yang sama, file akan **diperbarui** (tidak duplikat).

> `credentials.json` dan `token.json` sudah ditambahkan ke `.gitignore` — jangan di-commit ke repository.

---

## Format File Input

### `list_edc.csv` — Sumber Data Tunggal

File CSV tunggal yang memuat semua merchant. Kolom `report_status` menentukan tipe pemrosesan setiap baris.

| Kolom            | Wajib | Keterangan                                                                                    |
| ---------------- | ----- | --------------------------------------------------------------------------------------------- |
| `report_status`  | ✓     | `new` / `update` / `delete` / `realtime` — menentukan cara baris diproses                    |
| `id`             | ✓     | ID unik merchant — disimpan ke kolom `reference` di tabel merchants untuk pencarian cepat     |
| `name`           | ✓     | Nama merchant                                                                                 |
| `latitude`       | ✓     | Latitude tampilan                                                                             |
| `longitude`      | ✓     | Longitude tampilan                                                                            |
| `routing_lat`    |       | Latitude routing (fallback ke `latitude` jika kosong)                                        |
| `routing_lon`    |       | Longitude routing                                                                             |
| `category`       | ✓     | Kategori POI (misal: `Restaurant`, `Coffee Shop`, `ATM`)                                      |
| `operating_hours`|       | Jam operasional teks bebas (lihat format di bawah)                                            |
| `phone`          |       | Nomor telepon                                                                                 |
| `mobile`         |       | Nomor HP                                                                                      |
| `house_number`   |       | Nomor rumah/gedung                                                                            |
| `street_name`    |       | Nama jalan                                                                                    |
| `postal_code`    |       | Kode pos                                                                                      |
| `admin2`         |       | Provinsi                                                                                      |
| `admin3`         | ✓     | Kota/Kabupaten                                                                                |
| `admin4`         |       | Kecamatan                                                                                     |
| `admin5`         |       | Kelurahan                                                                                     |
| `closed_from`    |       | Wajib untuk `delete` — tanggal penutupan `YYYY-MM-DD` atau format kuartal `2025 Q1`           |

#### Nilai `report_status`

| Nilai       | Perilaku                                                                                                        |
| ----------- | --------------------------------------------------------------------------------------------------------------- |
| `new`       | Insert ke DB jika belum ada; generate transaksi dari `DATE_START` hingga `DATE_END`                             |
| `update`    | Insert ke DB jika belum ada; generate transaksi; muncul di sheet UPDATE laporan batch                           |
| `delete`    | Insert ke DB jika belum ada; generate transaksi hingga `closed_from`; prune transaksi setelahnya; set `merchant_status = INACTIVE` dan `closed_at` di DB |
| `realtime`  | Tidak masuk tabel merchants/transactions; generate kartu sinyal JPEG saja; muncul di sheet REALTIME laporan batch |

#### Format `operating_hours`

```
Monday-Sunday, 08:00-22:00
Monday-Friday, 09:00-17:00, Saturday-Sunday, 10:00-15:00
24/7
```

Jika kosong, jam default per kategori diterapkan otomatis.

#### Format `closed_from`

| Format          | Contoh        | Perilaku                                    |
| --------------- | ------------- | ------------------------------------------- |
| ISO date        | `2025-03-15`  | Digunakan langsung                          |
| Kuartal         | `2025 Q1`     | Di-generate acak dalam rentang kuartal tersebut |
| Kosong          | *(kosong)*    | Di-generate acak dalam 1 tahun terakhir     |

Tanggal yang sudah dinormalisasi ditulis kembali ke CSV secara otomatis saat `--report`, `--append`, atau `--batch-seed` dijalankan.

---

### `list_realtime.csv` — Tracking Sinyal Realtime _(Di-generate Otomatis)_

File ini **tidak perlu dibuat manual**. Di-generate otomatis saat `--batch-seed` memproses baris `realtime` dari `list_edc.csv`. Digunakan kembali oleh `--report` untuk regenerasi kartu tanpa membaca ulang CSV.

| Kolom         | Keterangan                                                       |
| ------------- | ---------------------------------------------------------------- |
| `id`          | ID POI                                                           |
| `poi_nm`      | Nama POI                                                         |
| `last_signal` | Datetime sinyal terakhir format `YYYY-MM-DD HH:MM:SS`            |
| `category`    | Kategori (biasanya `ATM`)                                        |
| `street`      | Nama jalan lengkap (prefix "Jalan" dihapus saat rendering kartu) |

---

## Output Laporan

Setelah seeding atau dengan `--report`, script menghasilkan:

1. **Kartu konsol** — dicetak ke terminal per merchant
2. **JPEG per merchant** — disimpan ke `reports/YYYYMMDD/`; nama file menggunakan `id` dari CSV jika tersedia
3. **`merchant_activity_report.xlsx`** — seluruh merchant dalam satu file Excel
4. **`batch_activity_report.xlsx`** — hanya merchant dari `list_edc.csv`, terdiri dari 4 sheet:

| Sheet      | Isi                                                              |
| ---------- | ---------------------------------------------------------------- |
| `NEW`      | Merchant dengan `report_status = new`                            |
| `UPDATE`   | Merchant dengan `report_status = update`                         |
| `DELETE`   | Merchant dengan `report_status = delete`                         |
| `REALTIME` | POI dengan `report_status = realtime` (kartu sinyal, bukan kartu transaksi) |

Setiap baris laporan batch berisi: nomor urut, ID sumber, nama merchant, waktu sinyal terakhir, dan foto kartu JPEG.

---

## Skema Database

### Tabel

| Tabel             | PK            | Fungsi                                                                    |
| ----------------- | ------------- | ------------------------------------------------------------------------- |
| `admin_areas`     | `SERIAL`      | Hierarki wilayah: Provinsi → Kota → Kecamatan → Kelurahan                 |
| `acquirers`       | `SMALLSERIAL` | Bank acquirer EDC (BCA, Mandiri, BNI)                                     |
| `merchants`       | `UUID`        | Profil merchant dengan koordinat geo dan FK area admin                    |
| `terminals`       | `UUID`        | Mesin EDC fisik, satu per merchant                                        |
| `cards`           | `BIGSERIAL`   | Referensi kartu sintetis yang di-mask                                     |
| `qris_issuers`    | `SMALLSERIAL` | Sumber QRIS: GoPay, ShopeePay, Dana, OVO, LinkAja, BCA, Mandiri, BNI, BRI |
| `transactions`    | `BIGSERIAL`   | Semua transaksi pembayaran                                                |
| `settlement`      | `SERIAL`      | Ringkasan settlement harian per merchant                                  |
| `transaction_log` | `BIGSERIAL`   | Audit trail pesan ISO 8583 mentah                                         |

### Kolom Tambahan di `merchants`

Kolom berikut ditambahkan otomatis saat seeder pertama kali dijalankan (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`):

| Kolom             | Tipe           | Keterangan                                                                 |
| ----------------- | -------------- | -------------------------------------------------------------------------- |
| `reference`       | `VARCHAR(255)` | ID dari `list_edc.csv` — hanya diisi jika NULL (tidak ditimpa)             |
| `merchant_status` | `VARCHAR(20)`  | `ACTIVE` (default) atau `INACTIVE` — di-set saat merchant berstatus delete |
| `closed_at`       | `DATE`         | Tanggal penutupan dari `closed_from` — diisi bersamaan dengan status INACTIVE |

### Format Kode

| Field           | Format                           | Contoh                    |
| --------------- | -------------------------------- | ------------------------- |
| `merchant_code` | `MCH-{MCC}-{YYYYMMDD}-{SEQ:05d}` | `MCH-5814-20250301-00001` |
| `terminal_code` | `TID-{MCC}-{YYYYMMDD}-{SEQ:05d}` | `TID-5814-20250301-00001` |
| `trace_number`  | `RRN{YYYYMMDD}{SEQ:06d}`         | `RRN20260601000001`       |

---

## Karakteristik Data Transaksi

- **QRIS vs Kartu** — F&B dan layanan sehari-hari cenderung QRIS (55–70%); retail premium cenderung kartu (25–28%)
- **Mix transaksi** — ~85% SALE, ~3% REFUND (kartu saja), ~2% VOID
- **Approval rate** — ~88% untuk EDC kartu, ~97% untuk QRIS
- **Jam operasional** — diambil dari kolom `operating_hours` di `list_edc.csv`. Default per kategori diterapkan jika kolom kosong
- **Penurunan volume** — merchant dengan `closed_from` mengalami penurunan volume bertahap menjelang tanggal penutupan
- **Hari libur** — hari libur nasional Indonesia (2025–2026) menyebabkan kategori tertentu (Pakaian, Bunga, Sekolah, Dokter Gigi) tidak generate transaksi. F&B dan kesehatan tetap buka

---

## Query Analitik

`queries.sql` berisi 15 query siap pakai. Set rentang tanggal di psql terlebih dahulu:

```sql
\set date_from '2025-01-01'
\set date_to   '2026-06-26'
```

| #   | Query                                                               |
| --- | ------------------------------------------------------------------- |
| 1   | Transaksi mentah (rentang tanggal, terbaru lebih dulu)              |
| 2   | Total keseluruhan — gross sales, refund, net revenue, approval rate |
| 3   | Tren transaksi harian                                               |
| 4   | Split channel pembayaran (QRIS vs EDC_CARD)                         |
| 5   | Rincian issuer QRIS dengan persentase                               |
| 6   | Rincian merek kartu                                                 |
| 7   | Top merchant berdasarkan volume transaksi                           |
| 8   | Rincian kategori/MCC dengan rata-rata tiket dan share QRIS          |
| 9   | Analisis penolakan berdasarkan kode respons ISO 8583                |
| 10  | Approval rate per terminal                                          |
| 11  | Ringkasan geografis (Provinsi → Kota → Kecamatan)                   |
| 12  | Status settlement per tanggal                                       |
| 13  | Transaksi approved yang belum di-settle                             |
| 14  | Efek hari libur — rata-rata penjualan harian libur vs hari biasa    |
| 15  | Heatmap transaksi per jam                                           |
