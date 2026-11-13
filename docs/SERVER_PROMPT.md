# Prompt deploy ARAH ke server LRM

Salin seluruh blok di bawah dan serahkan ke orang server (atau agen AI di server). Sebelum menyerahkan,
isi nilai di bagian NILAI. Kirim lewat jalur pribadi, karena berisi rahasia.

```text
TUGAS
Deploy ARAH by LRM ke server ini sampai https://arah.lnint.xyz bisa dibuka, meminta kata sandi pemilik,
dan memperbarui dirinya sendiri setiap ada commit baru di branch main. Kerjakan sampai selesai tanpa
bertanya balik, kecuali ada langkah yang menurut bagian MASALAH harus dilaporkan ke pemilik.

SERVER
- Tencent Lighthouse, Ubuntu 24.04, Docker, IP publik 43.152.240.47. Semua perintah dijalankan sebagai root
  (fitur "Run commands" Tencent sudah root). Folder rumah pengguna adalah /home/ubuntu.
- Port 80 dan 443 dipegang kontainer Caddy ln-demo-caddy-1 dari repo lrmcorp/ln. Jangan pasang web server
  lain dan jangan buka port lain.
- DNS arah.lnint.xyz -> 43.152.240.47 sudah aktif.

CARA KERJANYA
ARAH berjalan sebagai kontainer Docker bernama arah di jaringan lnint-edge, tanpa port yang dibuka ke host.
Caddy meneruskan https://arah.lnint.xyz ke arah:8787. Satu skrip, deploy/server-deploy.sh, mengerjakan
semuanya: memeriksa server, menulis pengaturan (izin berkas 600), membangun dan menjalankan kontainer,
memastikan Caddy melayani domainnya, menguji dari dalam dan dari luar, lalu memasang pembaruan otomatis
tiap 5 menit yang kembali ke versi sebelumnya jika versi baru gagal. Skrip aman dijalankan ulang.

NILAI (isi oleh pemilik; baris yang dibiarkan berisi ... dilewati)
ARAH_PASSWORD=...              kata sandi dashboard, minimal 12 karakter, tanpa tanda kutip tunggal
OPENROUTER_API_KEY=...         dari openrouter.ai/keys
CLAUDE_CODE_OAUTH_TOKEN=...    opsional: cadangan AI, dari perintah `claude setup-token` di komputer pemilik
STOCKBIT_SESSION=...           opsional: harga IDX realtime, nilai cookie credentialStorage dari stockbit.com
                               (cara mengambilnya ada di README, bagian "Stockbit session")
TELEGRAM_BOT_TOKEN=...         opsional: dari @BotFather
TELEGRAM_CHAT_ID=...           opsional: dari @userinfobot

LANGKAH 1: JALANKAN (satu perintah; salin nilai di atas ke dalam blok VALUES, satu nilai per baris,
tanpa spasi di sekitar = dan tanpa komentar)
cd /home/ubuntu && if [ -d arah/.git ]; then git -C arah pull --ff-only; else git clone https://github.com/lrmcorp/fuzzy-potato.git arah; fi && bash /home/ubuntu/arah/deploy/server-deploy.sh <<'VALUES'
ARAH_PASSWORD=...
OPENROUTER_API_KEY=...
CLAUDE_CODE_OAUTH_TOKEN=...
STOCKBIT_SESSION=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
VALUES

Build pertama butuh beberapa menit. Skrip diakhiri "ARAH DEPLOY REPORT". Setiap baris berawalan OK, WARN
atau FAIL, dan setiap masalah diberi kode [T1] sampai [T7] yang dijelaskan di bagian MASALAH.

LANGKAH 2: PASTIKAN BERHASIL
Deploy selesai bila semua ini benar:
- Laporan tidak memuat FAIL.
- Ada baris "OK    https://arah.lnint.xyz answers 200 with a valid certificate".
- docker ps --format '{{.Names}} {{.Status}}' | grep arah   menunjukkan "(healthy)".
- systemctl is-active arah-update.timer   menjawab "active".
- Di browser, https://arah.lnint.xyz menampilkan logo LRM dan kolom kata sandi. Setelah masuk, ringkasan
  pertama muncul dalam sekitar satu menit.
- Jika Telegram diisi: kirim /brief ke bot, bot membalas.

MASALAH (perbaiki, lalu jalankan ulang LANGKAH 1; nilai yang sudah tersimpan dipertahankan)
[T1] Perintah atau Docker tidak ada / tidak jalan.
     apt-get update && apt-get install -y git curl openssl; systemctl start docker; docker compose version
     Jika plugin compose tidak ada: apt-get install -y docker-compose-plugin
[T2] Disk kurang dari 4G.
     docker image prune -af && docker builder prune -af   lalu cek lagi dengan df -h
     Jangan hapus volume (docker volume prune) karena berisi data aplikasi lain.
[T3] Pengaturan ditolak. Biasanya ARAH_PASSWORD kurang dari 12 karakter atau berisi tanda kutip tunggal.
     Perbaiki nilainya di blok VALUES. Jangan cetak isi /home/ubuntu/arah/.env.vps.
[T4] Kontainer tidak sehat. Lihat log yang dicetak skrip, atau:
     cd /home/ubuntu/arah && docker compose -f deploy/compose.yaml logs --tail 100 arah
     - Build gagal mengunduh paket (npm, pypi, docker hub): periksa koneksi keluar server, lalu ulangi.
     - "Refusing to listen ... without ARAH_PASSWORD": nilai ARAH_PASSWORD tidak terisi, lihat [T3].
     - Error Python lain: laporkan ke pemilik beserta 100 baris log terakhir.
[T5] Caddy bermasalah.
     - Kontainer ln-demo-caddy-1 tidak ada atau tidak jalan: repo lrmcorp/ln belum ter-deploy. Laporkan ke
       pemilik; jangan membuat Caddy sendiri.
     - "Caddyfile does not parse": skrip tidak me-restart Caddy, jadi situs lain aman. Kembalikan cadangan
       Caddyfile.domain.bak.* di folder yang sama bila berkas itu diubah, lalu laporkan.
     - "cannot reach arah:8787": jalankan
       docker network inspect lnint-edge --format '{{range .Containers}}{{.Name}} {{end}}'
       Harus memuat ln-demo-caddy-1 dan kontainer arah. Jika arah tidak ada: cd /home/ubuntu/arah &&
       docker compose -f deploy/compose.yaml up -d --force-recreate
[T6] HTTPS dari luar belum 200.
     - Jika "HTTPS on the server answers 200" tetapi dari luar gagal: firewall Tencent. Di konsol Lighthouse,
       tab Firewall, pastikan TCP 80 dan 443 diizinkan dari 0.0.0.0/0.
     - Jika di server pun gagal: lihat docker logs --tail 50 ln-demo-caddy-1 | grep -i -E "arah|certificate|error"
       Sertifikat diterbitkan saat pertama kali diakses dan butuh port 80 terbuka. Tunggu 2 menit, ulangi.
     - DNS menunjuk ke alamat lain: perbaiki record A arah di DNSPod (lnint.xyz) ke 43.152.240.47, tanpa AAAA.
[T7] Pembaruan otomatis tidak terpasang. Jalankan bash /home/ubuntu/arah/deploy/install-auto-update.sh dan
     laporkan pesannya bila gagal.

ATURAN
- Jangan pernah menampilkan, menyalin, atau mengirim isi /home/ubuntu/arah/.env.vps atau nilai rahasia.
- Jangan membuka port 8787 ke host atau internet, dan jangan menonaktifkan kata sandi dashboard.
- Jangan mengubah berkas di /home/ubuntu/ln selain yang dilakukan skrip: folder itu ditimpa setiap deploy ln.
  Blok arah.lnint.xyz sudah ada di repo lrmcorp/ln, jadi tidak hilang pada deploy berikutnya.
- Jangan mengubah berkas di /home/ubuntu/arah dengan tangan: pembaruan otomatis berhenti bila ada perubahan
  lokal. Ubah pengaturan dengan menjalankan ulang LANGKAH 1 berisi nilai baru.
- Jika satu masalah tidak selesai setelah dua kali percobaan sesuai bagian MASALAH, berhenti dan laporkan.

PERAWATAN
- Log aplikasi:        cd /home/ubuntu/arah && docker compose -f deploy/compose.yaml logs -f --tail 100 arah
- Log pembaruan:       journalctl -u arah-update -n 30 --no-pager
- Restart:             cd /home/ubuntu/arah && docker compose -f deploy/compose.yaml restart arah
- Ganti kata sandi atau kunci: jalankan ulang LANGKAH 1 hanya dengan baris yang berubah. Ganti kata sandi
  membuat semua perangkat keluar.
- Cadangan data:       docker run --rm -v arah_arah_data:/d -v /root:/b alpine tar czf /b/arah-data.tgz -C /d .
                       ditambah /home/ubuntu/arah/.env.vps. Simpan di luar server.

LAPOR KE PEMILIK
1. Seluruh blok "ARAH DEPLOY REPORT" (tidak berisi rahasia).
2. Keluaran dari: docker ps --format '{{.Names}} {{.Status}}' | grep arah ; systemctl is-active arah-update.timer
3. Hal yang tidak sesuai dengan prompt ini, beserta perintah dan keluarannya.
```

## Catatan untuk pemilik

- Skrip deploy belum pernah dijalankan di server sungguhan: lingkungan build tidak punya Docker. Yang sudah
  diuji: sintaks dan shellcheck semua skrip, penulis pengaturan, logika pembaruan otomatis termasuk kembali ke
  versi lama saat gagal, dan aplikasi yang dipasang seperti di dalam image.
- Nilai yang diketik di fitur "Run commands" Tencent mungkin tersimpan di riwayat perintah konsol itu. Jika itu
  masalah, jalankan LANGKAH 1 lewat SSH biasa.
- Token Claude Code dibuat sekali di komputer Anda dengan `claude setup-token` (butuh browser untuk login).
  Tanpa token, ARAH tetap jalan dengan DeepSeek lewat OpenRouter.
