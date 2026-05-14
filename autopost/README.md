# Auto-Post System untuk Promosi Ebook

Sistem otomatis untuk posting promosi ebook ke **Threads** (auto) dan **X/Twitter** (manual export).

---

## Cara Kerja

```
marketing/*.md → generate_queue.py → content_queue.json → post_threads.py → Threads
                                    → x_export.txt → Copy-paste ke X/Buffer
```

**Jadwal Auto-Post Threads:**
- Pagi: 07:00 WIB (jam emas pagi)
- Malam: 19:00 WIB (jam emas malam)

**X (Twitter):**
- X API berbayar ($100/bulan), jadi untuk X kita pakai manual export
- File `x_export.txt` berisi semua post rapi, tinggal copy-paste ke X atau schedule via Buffer Free

---

## Setup (Satu Kali)

### 1. Dapatkan Threads API Token

1. Buka [Meta for Developers](https://developers.facebook.com/)
2. Buat App baru → pilih "Other" → pilih "Consumer"
3. Di menu kiri, klik **Add Product** → pilih **Threads API**
4. Klik **Customize** → masuk ke pengaturan Threads
5. Di tab **Permissions**, aktifkan:
   - `threads_basic`
   - `threads_content_publish`
6. Generate **Access Token** (pilih Long-Lived Token, berlaku 60 hari)
7. Catat **Threads User ID** (terlihat di dashboard)

> **Penting:** Long-lived token berlaku 60 hari. Refresh sebelum expired!
> Untuk refresh: `GET /oauth/access_token?grant_type=th_exchange_token&access_token={TOKEN}`

### 2. Setup GitHub Secrets

Buka repo GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Tambahkan 2 secret:

| Secret Name | Isi |
|-------------|-----|
| `THREADS_USER_ID` | User ID Threads kamu (angka) |
| `THREADS_ACCESS_TOKEN` | Long-lived access token dari Meta |

### 3. Generate Content Queue (Pertama Kali)

Jalankan manual di lokal atau trigger workflow:

```bash
# Lokal
cd Dilz-ebook
python autopost/generate_queue.py
```

Atau di GitHub → tab **Actions** → **Regenerate Content Queue** → **Run workflow**

### 4. Test Manual Posting

Bisa trigger manual di GitHub → tab **Actions** → **Auto Post to Threads** → **Run workflow**

---

## File-file

| File | Fungsi |
|------|--------|
| `generate_queue.py` | Parse marketing/*.md → content_queue.json + x_export.txt |
| `post_threads.py` | Ambil post berikutnya dari queue, posting ke Threads |
| `content_queue.json` | Antrian konten (auto-generated) |
| `x_export.txt` | Export teks untuk X/Twitter (manual copy-paste) |
| `tracker.json` | Track post mana yang sudah diposting |
| `requirements.txt` | Python dependencies |

---

## Workflow GitHub Actions

| Workflow | Trigger | Fungsi |
|----------|---------|--------|
| `auto-post-threads.yml` | Cron 07:00 & 19:00 WIB + manual | Post ke Threads |
| `generate-queue.yml` | Push ke marketing/ + manual | Regenerate queue |

---

## Strategi Posting untuk X (Gratis)

Karena X API berbayar, gunakan salah satu opsi gratis:

### Opsi A: Buffer Free
1. Daftar di [buffer.com](https://buffer.com) (gratis, 1 channel)
2. Connect akun X kamu
3. Buka `x_export.txt`, copy 1 post per hari
4. Schedule di Buffer (bisa schedule 10 post sekaligus)

### Opsi B: Manual via X App
1. Buka `x_export.txt`
2. Copy 1 post
3. Buka X → New Post → Paste → Post
4. Ulangi 1-2x per hari

### Opsi C: TweetDeck (X Pro) - Gratis untuk user X Premium
Jika kamu punya X Premium, bisa schedule langsung dari TweetDeck.

---

## Maintenance

### Refresh Token Threads (Tiap 60 Hari)
Token Threads expired setiap 60 hari. Refresh dengan:

```bash
curl "https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token&access_token=TOKEN_LAMA"
```

Lalu update secret `THREADS_ACCESS_TOKEN` di GitHub.

### Tambah Konten Baru
1. Edit/tambah file di `marketing/`
2. Push ke main → workflow `generate-queue.yml` otomatis jalan
3. Queue akan di-regenerate dan commit otomatis

### Reset Queue (Posting dari Awal)
Edit `tracker.json`:
```json
{
  "threads_index": 0,
  "x_index": 0,
  "posted": []
}
```

---

## FAQ

**Q: Berapa lama stok konten ini bertahan?**
A: Dengan 60+ post di queue dan 2x posting/hari, cukup untuk ~30 hari. Setelah habis, queue reset otomatis dari awal.

**Q: Apakah bisa custom jadwal?**
A: Ya! Edit cron di `.github/workflows/auto-post-threads.yml`. Format: `menit jam * * *` (UTC).

**Q: Gimana kalo posting gagal?**
A: Cek tab Actions di GitHub. Error log akan terlihat. Biasanya penyebab: token expired atau rate limit.

**Q: Rate limit Threads API?**
A: Maks 250 post per 24 jam. Dengan 2 post/hari, sangat aman.

---

## Lisensi

Sistem ini untuk mendukung promosi ebook @pinokioarab.
