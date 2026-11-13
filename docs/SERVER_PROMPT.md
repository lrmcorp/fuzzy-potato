# Prompt deploy ARAH ke server LRM, dari A sampai Z

Dokumen ini punya dua bagian:

- **Bagian A, untuk pemilik:** menyiapkan nilai rahasia. Dikerjakan sekali, di komputer Anda sendiri.
- **Bagian B, untuk orang server:** blok prompt yang diserahkan utuh. Orang server (atau agen AI di server)
  mengerjakannya sampai ARAH tayang, tanpa perlu kembali bertanya.

## Bagian A: yang disiapkan pemilik

| Nilai | Wajib? | Cara mendapatkan |
|---|---|---|
| `ARAH_PASSWORD` | Wajib | Kata sandi dashboard pilihan Anda. Minimal 12 karakter, tanpa tanda kutip tunggal (`'`). |
| `OPENROUTER_API_KEY` | Wajib untuk analisa AI | openrouter.ai, menu Keys, buat kunci baru. Pastikan saldonya terisi. |
| `STOCKBIT_SESSION` | Opsional: harga saham IDX realtime | Lihat langkah di bawah. |
| `CLAUDE_CODE_OAUTH_TOKEN` | Opsional: cadangan AI | Di komputer Anda: `npm install -g @anthropic-ai/claude-code`, lalu `claude setup-token`, salin token yang muncul. |
| `TELEGRAM_BOT_TOKEN` | Opsional | Chat @BotFather di Telegram, kirim `/newbot`, salin tokennya. |
| `TELEGRAM_CHAT_ID` | Opsional | Chat @userinfobot, salin angka "Id". Kirim satu pesan apa saja ke bot Anda sebelum deploy. |

**Mengambil `STOCKBIT_SESSION`** (di komputer, Chrome atau Edge):

1. Buka jendela private/incognito, login di stockbit.com seperti biasa.
2. Tekan F12, buka tab Application, lalu Cookies, lalu `https://stockbit.com`.
3. Klik dua kali kolom Value pada baris `credentialStorage`, salin seluruh isinya (panjang, diawali `%7B`).
4. Tutup jendela itu tanpa logout. Jangan pakai sesi yang sama di aplikasi lain.

Sebaiknya pakai akun Stockbit yang tidak terhubung ke rekening efek atau dana: ARAH hanya membaca harga,
tetapi nilai sesi itu sendiri setara akses ke akun.

Isi nilai-nilai itu ke blok `VALUES` di Bagian B, lalu kirim Bagian B ke orang server lewat jalur pribadi.
Baris yang tidak Anda isi biarkan berisi `...`; baris itu dilewati.

## Bagian B: prompt untuk orang server

```text
TUGAS
Deploy ARAH by LRM ke server ini sampai https://arah.hasseedev.com bisa dibuka, meminta kata sandi pemilik,
menampilkan grafik live dan prakiraan, dan memperbarui dirinya sendiri setiap ada commit baru di branch
main. Kerjakan sampai selesai tanpa bertanya balik, kecuali bagian MASALAH menyuruh melapor ke pemilik.
Langkah yang sama dipakai untuk pemasangan pertama maupun pembaruan; skrip aman dijalankan ulang.

SERVER
- Tencent Lighthouse, Ubuntu 24.04, Docker, IP publik 43.152.240.47. Jalankan semua perintah sebagai root.
  Lebih aman lewat SSH ("sudo -i"); fitur "Run commands" Tencent juga root tetapi mungkin menyimpan isi
  perintah di riwayatnya. Folder rumah pengguna adalah /home/ubuntu.
- Port 80 dan 443 dipegang kontainer Caddy ln-demo-caddy-1 dari repo lrmcorp/ln. Jangan pasang web server
  lain dan jangan buka port lain.
- DNS arah.hasseedev.com -> 43.152.240.47 sudah aktif.
- Koneksi keluar yang dipakai: github.com, registry.npmjs.org, pypi.org, Docker Hub, query1 dan query2.finance.yahoo.com, api.frankfurter.dev,
  news.google.com, www.cnbcindonesia.com, www.bca.co.id, nfs.faireconomy.media, openrouter.ai,
  data-api.binance.vision, exodus.stockbit.com, api.telegram.org.

CARA KERJANYA
ARAH berjalan sebagai kontainer Docker "arah" di jaringan lnint-edge, tanpa port yang dibuka ke host. Caddy
meneruskan https://arah.hasseedev.com ke arah:8787. Skrip deploy/server-deploy.sh mengerjakan semuanya:
1. memeriksa server (Docker, disk, Caddy, DNS);
2. menyimpan pengaturan ke /home/ubuntu/arah/.env.vps (izin 600, nilai lama dipertahankan);
3. membangun dan menjalankan kontainer, lalu menunggu sampai sehat;
4. memastikan Caddy melayani arah.hasseedev.com;
5. menguji dari dalam jaringan Docker, di server lewat HTTPS, dan dari internet;
6. memeriksa fitur: riwayat harga, grafik live per sumber, prakiraan 1/2/3 bulan, dan sesi Stockbit;
7. memasang pembaruan otomatis tiap 5 menit yang kembali ke versi sebelumnya bila versi baru gagal.

LANGKAH 1: JALANKAN (satu perintah)
cd /home/ubuntu && if [ -d arah/.git ]; then git -C arah pull --ff-only; else git clone https://github.com/lrmcorp/fuzzy-potato.git arah; fi && bash /home/ubuntu/arah/deploy/server-deploy.sh <<'VALUES'
ARAH_PASSWORD=...
OPENROUTER_API_KEY=...
STOCKBIT_SESSION=...
CLAUDE_CODE_OAUTH_TOKEN=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
VALUES

Satu nilai per baris, tanpa spasi di sekitar tanda =, tanpa komentar. Build pertama butuh beberapa menit.
Skrip diakhiri blok "ARAH DEPLOY REPORT": setiap baris berawalan OK, WARN atau FAIL, dan setiap masalah
membawa kode [T1] sampai [T9] yang dijelaskan di bagian MASALAH.

LANGKAH 2: PASTIKAN BERHASIL
Deploy selesai bila semua ini benar:
1. Laporan tidak memuat FAIL.
2. Ada baris "OK    https://arah.hasseedev.com answers 200 with a valid certificate".
3. Ada baris "OK    forecast IHSG 1m", "2m" dan "3m".
4. Ada baris "OK    live BTC: binance, realtime".
5. Jika STOCKBIT_SESSION diisi: ada "OK    Stockbit session usable". Pada jam bursa (Senin sampai Jumat,
   09.00 sampai 16.00 WIB) ada juga "OK    live IHSG: stockbit, realtime". Di luar jam bursa baris itu
   boleh menyebut sumber lain; ulangi pemeriksaan pada jam bursa dengan:
   docker compose -f /home/ubuntu/arah/deploy/compose.yaml exec -T arah arah selfcheck
6. docker ps --format '{{.Names}} {{.Status}}' | grep arah   menunjukkan "(healthy)".
7. systemctl is-active arah-update.timer   menjawab "active".
8. Di browser, https://arah.hasseedev.com menampilkan logo LRM dan kolom kata sandi. Setelah masuk:
   - halaman Ringkasan punya empat kartu bergrafik dan pilihan 1 / 2 / 3 bulan;
   - membuka satu kartu menampilkan grafik "Hari ini", kotak Kesimpulan, grafik "Arah grafik ke depan",
     dan daftar teknik;
   - halaman Atur, bagian Sistem, menunjukkan status Stockbit dan tim analis AI.
   Ringkasan pertama muncul sekitar satu menit setelah kontainer menyala.
9. Jika Telegram diisi: kirim /brief ke bot, bot membalas.

RELAY CLOUDFLARE (bila Yahoo menjawab 429 atau Stockbit menolak server)
Pemilik membuat Cloudflare Worker sesuai deploy/cloudflare/README.md dan memberi dua nilai. Pasang dengan:
cd /home/ubuntu/arah && git pull --ff-only origin main && bash deploy/server-deploy.sh <<'VALUES'
ARAH_RELAY_URL=https://arah-relay.<nama-akun>.workers.dev
ARAH_RELAY_KEY=...
STOCKBIT_SESSION=...
VALUES
(STOCKBIT_SESSION diisi nilai credentialStorage yang baru dari pemilik; biarkan ... bila tidak berubah.)
Berhasil bila laporan memuat "INFO Yahoo and Stockbit go through the relay", "OK   daily history USDIDR"
dengan ratusan hari, dan "OK   stock screen: 30 ID and 25 US". Pada jam bursa juga
"OK   live IHSG: stockbit, realtime".
[T10] Relay bermasalah:
     - "the relay refused ARAH's key": ARAH_RELAY_KEY tidak sama dengan RELAY_KEY di Worker. Samakan.
     - "set but not usable": URL harus diawali https:// dan kunci minimal 24 karakter.
     - Yahoo lewat relay masih 429 atau Stockbit lewat relay 403: laporkan ke pemilik beserta baris
       selfcheck-nya. Jangan mencoba relay atau layanan proxy lain.

MASALAH (perbaiki, lalu jalankan ulang LANGKAH 1; baris VALUES boleh dibiarkan ..., nilai tersimpan dipakai)
[T1] Perintah atau Docker tidak ada / tidak jalan.
     apt-get update && apt-get install -y git curl openssl; systemctl start docker; docker compose version
     Jika plugin compose tidak ada: apt-get install -y docker-compose-plugin
[T2] Disk kurang dari 4G.
     docker image prune -af && docker builder prune -af   lalu cek dengan df -h
     Jangan menghapus volume (docker volume prune): isinya data aplikasi lain.
[T3] Pengaturan ditolak. Biasanya ARAH_PASSWORD kurang dari 12 karakter atau berisi tanda kutip tunggal.
     Perbaiki nilainya di blok VALUES. Jangan mencetak isi /home/ubuntu/arah/.env.vps.
[T4] Kontainer tidak sehat. Lihat log yang dicetak skrip, atau:
     cd /home/ubuntu/arah && docker compose -f deploy/compose.yaml logs --tail 100 arah
     - Build gagal mengunduh paket (npm, pypi, Docker Hub): periksa koneksi keluar, lalu ulangi.
     - "Refusing to listen ... without ARAH_PASSWORD": lihat [T3].
     - Error lain: laporkan ke pemilik beserta 100 baris log terakhir.
[T5] Caddy bermasalah.
     - ln-demo-caddy-1 tidak ada atau tidak jalan: repo lrmcorp/ln belum ter-deploy. Laporkan; jangan
       membuat Caddy sendiri.
     - "Caddyfile does not parse": Caddy tidak di-restart, situs lain aman. Kembalikan cadangan
       Caddyfile.domain.bak.* di folder yang sama bila berkas itu berubah, lalu laporkan.
     - "cannot reach arah:8787": jalankan
       docker network inspect lnint-edge --format '{{range .Containers}}{{.Name}} {{end}}'
       Harus memuat ln-demo-caddy-1 dan kontainer arah. Jika arah tidak ada:
       cd /home/ubuntu/arah && docker compose -f deploy/compose.yaml up -d --force-recreate
[T6] HTTPS dari luar belum 200.
     - "HTTPS on the server answers 200" tetapi dari luar gagal: firewall Tencent. Di konsol Lighthouse,
       tab Firewall, izinkan TCP 80 dan 443 dari 0.0.0.0/0.
     - Di server pun gagal: docker logs --tail 50 ln-demo-caddy-1 | grep -i -E "arah|certificate|error"
       Sertifikat terbit saat diakses pertama kali dan butuh port 80 terbuka. Tunggu 2 menit, ulangi.
     - DNS ke alamat lain: perbaiki record A "arah" di Cloudflare (hasseedev.com) ke 43.152.240.47,
       mode DNS only (awan abu-abu), tanpa AAAA.
[T7] Pembaruan otomatis tidak terpasang. Jalankan bash /home/ubuntu/arah/deploy/install-auto-update.sh dan
     laporkan pesannya bila gagal.
[T8] Stockbit.
     - "session expired or refused": sesi habis atau sudah dipakai di tempat lain. Minta pemilik mengambil
       nilai credentialStorage yang baru (Bagian A), lalu jalankan ulang LANGKAH 1 dengan hanya baris
       STOCKBIT_SESSION yang diisi.
     - "Stockbit is set but was not used": lihat penyebabnya, tanpa token:
       cd /home/ubuntu/arah && docker compose -f deploy/compose.yaml logs --tail 200 arah | grep -i stockbit
       Jika ada "CDN refused this server (HTTP 403)", Stockbit menolak alamat server ini. Itu bukan masalah
       yang bisa diperbaiki di server; laporkan ke pemilik. ARAH tetap jalan dengan harga tertunda.
     - Jangan mencoba token atau akun lain, dan jangan menjalankan alat Stockbit lain dengan sesi yang sama.
[T9] "Yahoo refused this server (429)": Yahoo membatasi alamat server. ARAH berhenti memanggil Yahoo
     sendiri (15 menit, berlipat sampai 2 jam) supaya blokirnya lepas; kurs memakai kurs harian ECB
     dan grafik live memakai harga penutupan harian selama itu. Jangan restart berulang: setiap start
     memanggil Yahoo lagi. Tunggu, lalu ulangi selfcheck.
     Grafik live atau prakiraan gagal untuk satu aset.
     - Ulangi pemeriksaan setelah 2 menit (sumber gratis kadang membatasi permintaan):
       docker compose -f /home/ubuntu/arah/deploy/compose.yaml exec -T arah arah selfcheck
     - "live BTC" gagal terus: cek curl -sI https://data-api.binance.vision/api/v3/ping dari server.
       ARAH otomatis memakai Yahoo bila Binance gagal, jadi aplikasi tetap jalan.
     - "forecast" gagal dengan "not enough history": data harian belum terunduh; tunggu 5 menit, ulangi.

ATURAN
- Jangan pernah menampilkan, menyalin, atau mengirim isi /home/ubuntu/arah/.env.vps atau nilai rahasia,
  termasuk di laporan.
- Jangan membuka port 8787 ke host atau internet, dan jangan menonaktifkan kata sandi dashboard.
- Jangan mengubah berkas di /home/ubuntu/ln selain yang dilakukan skrip: folder itu ditimpa setiap deploy ln.
  Blok arah.hasseedev.com sudah ada di repo lrmcorp/ln, jadi tidak hilang pada deploy berikutnya.
- Jangan mengubah berkas di /home/ubuntu/arah dengan tangan: pembaruan otomatis berhenti bila ada perubahan
  lokal. Ubah pengaturan dengan menjalankan ulang LANGKAH 1 berisi nilai baru.
- Jika satu masalah tidak selesai setelah dua kali percobaan sesuai bagian MASALAH, berhenti dan laporkan.

PERAWATAN
- Pemeriksaan fitur:   docker compose -f /home/ubuntu/arah/deploy/compose.yaml exec -T arah arah selfcheck
- Log aplikasi:        cd /home/ubuntu/arah && docker compose -f deploy/compose.yaml logs -f --tail 100 arah
- Log pembaruan:       journalctl -u arah-update -n 30 --no-pager
- Restart:             cd /home/ubuntu/arah && docker compose -f deploy/compose.yaml restart arah
- Ganti kata sandi, kunci, atau sesi Stockbit: jalankan ulang LANGKAH 1 hanya dengan baris yang berubah.
  Ganti kata sandi membuat semua perangkat keluar.
- Cadangan data:       docker run --rm -v arah_arah_data:/d -v /root:/b alpine tar czf /b/arah-data.tgz -C /d .
                       ditambah /home/ubuntu/arah/.env.vps. Simpan di luar server.

LAPOR KE PEMILIK
1. Seluruh blok "ARAH DEPLOY REPORT" (tidak berisi rahasia).
2. Keluaran dari:
   docker ps --format '{{.Names}} {{.Status}}' | grep arah ; systemctl is-active arah-update.timer
3. Jika Stockbit diisi dan deploy dilakukan di luar jam bursa: keluaran "arah selfcheck" pada jam bursa.
4. Hal yang tidak sesuai dengan prompt ini, beserta perintah dan keluarannya.
```

## Catatan untuk pemilik

- Skrip deploy dan jalur Stockbit belum pernah dijalankan di server sungguhan: lingkungan build tidak punya
  Docker dan tidak punya sesi Stockbit. Yang sudah diuji: sintaks dan shellcheck semua skrip, penulis
  pengaturan, logika pembaruan otomatis termasuk kembali ke versi lama, aplikasi yang dipasang seperti di dalam
  image, dan pemeriksaan fitur (termasuk peringatan saat sesi Stockbit kedaluwarsa).
- Sesi Stockbit bertahan sekitar seminggu tanpa dipakai dan diperpanjang sendiri selama ARAH berjalan.
- Tanpa token Claude Code, ARAH tetap jalan dengan DeepSeek lewat OpenRouter.
