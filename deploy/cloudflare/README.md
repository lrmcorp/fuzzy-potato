# Relay Cloudflare untuk ARAH

Yahoo Finance dan Stockbit menolak alamat server Tencent. Relay ini adalah Cloudflare Worker milik
Anda sendiri yang meneruskan permintaan ARAH dari alamat Cloudflare. Paket gratis cukup: ARAH memakai
jauh di bawah batas 100,000 permintaan per hari.

Keamanan relay:
- Hanya menerima permintaan yang membawa kunci rahasia (RELAY_KEY). Tanpa kunci: ditolak.
- Hanya meneruskan jalur baca data: grafik harga, data keuangan Yahoo, grafik dan antrian Stockbit,
  dan perpanjangan sesi Stockbit. Jalur untuk order atau mengubah akun tidak bisa lewat.
- Tidak mencatat atau menyimpan apa pun. Kunci relay tidak diteruskan ke Yahoo atau Stockbit.

## Langkah (sekitar 5 menit, di browser)

1. Buka https://dash.cloudflare.com dan daftar atau masuk. Paket Free sudah cukup; tidak perlu
   memindahkan domain atau DNS.
2. Menu kiri **Workers & Pages** → **Create** → **Create Worker** (template "Hello World").
   Beri nama `arah-relay` → **Deploy**.
3. Klik **Edit code**. Hapus seluruh isi editor, tempel seluruh isi berkas `worker.js` di folder ini
   (https://github.com/lrmcorp/fuzzy-potato/blob/main/deploy/cloudflare/worker.js, tombol "Copy raw file"),
   lalu **Deploy**.
4. Buat kunci rahasia: deretan acak minimal 32 huruf dan angka, misalnya dari
   https://www.random.org/strings/ (panjang 32, satu baris), atau di server: `openssl rand -hex 24`.
   Simpan di pengelola kata sandi Anda. Jangan dikirim lewat chat.
5. Di halaman Worker: **Settings** → **Variables and Secrets** → **Add**.
   Type **Secret**, Variable name `RELAY_KEY`, Value = kunci dari langkah 4 → **Deploy**.
6. Salin alamat Worker di bagian atas halaman, bentuknya `https://arah-relay.<nama-akun>.workers.dev`.
7. Uji: buka `https://arah-relay.<nama-akun>.workers.dev/yahoo/v8/finance/chart/BBCA.JK` di browser.
   Jawaban yang benar adalah **forbidden**: relay hidup dan menolak permintaan tanpa kunci.

Lalu pasang di server (lihat bagian "Relay Cloudflare" di docs/SERVER_PROMPT.md):

    ARAH_RELAY_URL=https://arah-relay.<nama-akun>.workers.dev
    ARAH_RELAY_KEY=<kunci dari langkah 4>

## Mengganti kunci

Ganti RELAY_KEY di Worker (langkah 5), lalu jalankan ulang deploy server dengan ARAH_RELAY_KEY yang baru.
Selama keduanya berbeda, data Yahoo dan Stockbit berhenti, tetapi aplikasi tetap jalan.
