---
name: edit-videoremotion
description: Membuat dan mengedit video pengajaran medis & materi pelatihan (kedokteran, kedokteran gigi, keperawatan, farmasi, kesehatan masyarakat) dari bukti ilmiah sampai MP4 — naskah per adegan dari literatur (research-analytics MCP), storyboard, aset gratis berlisensi jelas (Pixabay, Unsplash, Openverse/Wikimedia), B-roll AI Open-Higgsfield (MuAPI), voiceover (ElevenLabs atau lokal), caption SRT/Remotion, editing FFmpeg, teks animasi Remotion, QA akurasi klinis & aksesibilitas, lalu kuis dan evaluasi pelatihan. Use for "/edit-videoremotion", "video edukasi kesehatan", "video pembelajaran", "materi training", "video prosedur klinis", "video DHE/penyuluhan", "explainer medis", "edit video", "potong/gabung klip", "9:16", "subtitle/caption", "voiceover", "Reels/Shorts/TikTok edukasi".
metadata:
  version: "2.0"
  requires: research-analytics MCP server; ffmpeg/ffprobe; Node.js for Remotion (optional); see references/setup-mcp.md for optional servers
---

# /edit-videoremotion — video pengajaran medis

Skill ini adalah **orkestrator**: bukti ilmiah → naskah → aset → suara → caption → edit → QA →
evaluasi. Bahasa ke pengguna: ikuti pengguna (biasanya Bahasa Indonesia).

| Bagian | Alat |
|:--|:--|
| Bukti & tujuan belajar | `research-analytics` MCP: `search_pubmed`, `search_openalex`, `db_*`, `training_blueprint` |
| Rencana video & caption | `video_lesson_plan`, `video_captions` (research-analytics) |
| Cek file video | `video_probe` (research-analytics, memakai ffprobe) atau `ffprobe` di shell |
| Aset stok | `media_search_openverse` (tanpa kunci), Pixabay MCP / `scripts/pixabay.py`, Unsplash / `scripts/unsplash.py`, `scripts/openverse.py` |
| B-roll AI (berbayar) | `training_storyboard` → `media_generate` (Open-Higgsfield via MuAPI) |
| Voiceover | ElevenLabs MCP (`elevenlabs-mcp`), atau TTS lokal pilihan pengguna |
| Editing | FFmpeg — **[references/ffmpeg-recipes.md](references/ffmpeg-recipes.md)** |
| Teks animasi & render | Remotion (`npx create-video@latest`), docs lewat Remotion MCP (`@remotion/mcp`) |
| Evaluasi | `training_observation_checklist`, `training_evaluation_report` |

Pedagogi, privasi pasien, dan QA klinis: **[references/medical-teaching-video.md](references/medical-teaching-video.md)**.
Setup server opsional (tanpa kunci di repo): **[references/setup-mcp.md](references/setup-mcp.md)**.

---

## 0. Aturan wajib

1. **Kunci API tidak pernah ditulis di kode, skill, repo, atau chat.** Kunci hanya di `env`
   konfigurasi MCP klien atau `~/.config/research-analytics-mcp/.env` (chmod 600). Kalau pengguna
   menempelkan kunci di chat, jangan diulang.
2. **Akurasi klinis**: setiap klaim di naskah harus berasal dari sumber yang tercatat di
   database proyek (paper, guideline). Klaim tanpa sumber ditandai `[PERLU SUMBER]` dan tidak
   masuk render final. Naskah diperiksa oleh tenaga kesehatan yang kompeten sebelum dipublikasi.
3. **Privasi pasien**: tidak ada wajah, nama, rekam medis, atau foto klinis yang dapat
   diidentifikasi tanpa persetujuan tertulis (informed consent untuk publikasi). Blur bila ragu.
4. **Generasi berbayar butuh izin eksplisit** (MuAPI, ElevenLabs): sebutkan jumlah klip/detik, tunggu "ya".
   `media_generate` tanpa `confirm=true` hanya dry run.
5. **Jangan menimpa file sumber.** Output ke `work/` atau `out/`; ffmpeg memakai `-n`.
6. **Cek dulu, baru potong**: `video_probe`/ffprobe setiap file sebelum ffmpeg.
7. **Render final hanya bila diminta**; default berhenti di preview.
8. Aset AI dan stok diberi label; media AI tidak boleh tampil sebagai foto klinis nyata.

---

## 1. Cek alat

```bash
command -v ffmpeg ffprobe node npx uvx; ffmpeg -hide_banner -version | head -1
ffmpeg -hide_banner -filters | grep -E " (subtitles|drawtext|xfade|loudnorm) "
```
Tanpa `subtitles`/`drawtext` → teks & caption dikerjakan di Remotion (mode hybrid).

## 2. Intake (sekali, ringkas, pakai default)

- **Topik & tujuan belajar** (mis. "teknik menyikat gigi Bass untuk orang tua"), **audiens**
  (pasien/awam, mahasiswa, tenaga kesehatan), **level**.
- **Format**: 16:9 1920×1080 (kelas/LMS, default), 9:16 1080×1920 (Reels/TikTok edukasi), 1:1.
- **Durasi**: microlearning 2–6 menit per tujuan belajar (default 3 menit).
- **Gaya**: explainer animasi, demonstrasi prosedur, talking head + slide, studi kasus.
- **Footage milik pengguna** (path) dan status consent-nya.
- **Suara**: naskah ada / perlu ditulis; ElevenLabs / suara pengguna sendiri / TTS lokal.
- **Caption**: wajib untuk aksesibilitas (default ON).

Mode: **FFmpeg-only** (potong, gabung, reformat, audio) · **Remotion** (teks animasi, label
anatomi, caption) · **Hybrid** (default bila ada teks animasi).

Struktur folder:
```
<proyek>/
  source/      # footage asli (read-only) + consent/
  stock/       # aset unduhan + stock-credits.md
  work/        # hasil antara
  voiceover/   # scene-01.mp3 …
  captions/    # captions.srt, captions.json
  out/         # hasil akhir
  lesson-plan.json / edit-plan.md
```

## 3. Bukti → naskah → rencana

1. `db_create_project(name, kind="training")`, lalu cari bukti (skill `medical-analytics`):
   `search_pubmed` (MeSH), guideline, `db_add_papers`, tandai `included` + isi `finding`.
2. `training_blueprint(topic, audience, duration_minutes, project=...)` → tujuan belajar (Bloom).
3. Tulis naskah per adegan: satu ide per adegan, 130–150 kata/menit bahasa Indonesia,
   kalimat pendek, istilah medis dijelaskan saat pertama muncul. Setiap klaim → `paper_id`.
4. `video_lesson_plan(title, scenes, fmt, out_dir, project)` → `lesson-plan.json` + `edit-plan.md`:
   durasi per adegan dari jumlah kata, cek sumber per klaim, daftar aset, peringatan pedagogi.

## 4. Aset (urutan: milik pengguna → gratis → AI)

- **Openverse/Wikimedia (tanpa kunci)**: `media_search_openverse(query, kind="image"|"audio", license="commercial"|"pd")`
  atau `python3 -I scripts/openverse.py images "<query>"` → `download` menulis kredit ke `stock-credits.md`.
  Ilustrasi anatomi CC BY/BY-SA **wajib atribusi**.
- **Pixabay** (video & foto): Pixabay MCP atau `python3 -I scripts/pixabay.py videos "<query>" --orientation horizontal`.
- **Unsplash** (foto): `python3 -I scripts/unsplash.py search "<query>"` (memicu `download_location` sesuai aturan API).
- Hindari foto klinis stok yang tidak akurat (alat salah, APD salah); cek dengan reviewer.
- **B-roll AI** (opsional, berbayar): `training_storyboard(objectives)` → `media_generate` dry run →
  izin → `confirm=true`. Simpan ke `stock/ai/`, label "AI-generated".

## 5. Voiceover

Naskah per adegan → `voiceover/scene-XX.mp3`.
- ElevenLabs MCP (`elevenlabs-mcp`, model multibahasa untuk Bahasa Indonesia), pilih suara dari
  daftar tool, jangan menebak `voice_id`.
- Atau rekaman suara pengguna/dosen (paling dipercaya audiens klinis).
- Ukur durasi: `video_probe("voiceover/scene-01.mp3")`; perbarui durasi adegan di rencana.
- Lafal istilah medis/obat: cek hasil TTS; tulis ejaan fonetis di naskah bila salah.

## 6. Caption

- `video_captions(scenes, out_dir)` → `captions.srt` (FFmpeg/LMS/YouTube) + `captions.json`
  (format `Caption` Remotion: `text`, `startMs`, `endMs`, `timestampMs`, `confidence`), dipecah
  ≤ 42 karakter per baris, ≤ 2 baris, ≤ 17 karakter/detik.
- Timing kata dari audio nyata: Whisper (`@remotion/install-whisper-cpp`, model multibahasa, bukan `*.en`).

## 7. Edit FFmpeg

Resep lengkap: [references/ffmpeg-recipes.md](references/ffmpeg-recipes.md). Ringkas: normalisasi
semua klip (resolusi, 30 fps, yuv420p, AAC 48 kHz) → concat / `xfade` → VO + musik dengan ducking →
`loudnorm` (−16 LUFS untuk e-learning, −14 untuk media sosial) → ekspor H.264 `+faststart`.

## 8. Remotion (teks animasi)

- `npx create-video@latest --yes --blank --no-tailwind <nama>`; `npx remotion add @remotion/media @remotion/transitions @remotion/captions @remotion/google-fonts`.
- Animasi lewat `useCurrentFrame()` + `interpolate()`; baca docs lewat Remotion MCP bila tersedia, jangan menebak API.
- Komponen untuk pengajaran: `TitleCard` (judul + tujuan belajar), `LowerThird` (nama & kredensial
  narasumber), `StepCounter` ("Langkah 2 dari 5"), `Label` + panah untuk anatomi/alat,
  `KeyPoint`, `Captions`, `QuizCard` (pertanyaan jeda), `References` (daftar sumber di akhir).
- Preview: `npx remotion studio`; render hanya bila diminta:
  `npx remotion render <CompId> out/<nama>.mp4 --codec=h264 --crf=18`.

## 9. QA (sebelum dibagikan)

Checklist di [references/medical-teaching-video.md](references/medical-teaching-video.md):
akurasi klinis (reviewer + daftar sumber), privasi/consent, aksesibilitas (caption, kontras,
kecepatan bicara), teknis (`video_probe`: resolusi, fps, durasi, audio, loudness), lisensi aset
(`stock-credits.md` lengkap, atribusi di end card).

## 10. Evaluasi pembelajaran

- Kuis 3–5 soal per tujuan belajar (pre/post), checklist observasi untuk keterampilan:
  `training_observation_checklist`.
- Data → `db_add_observations` → `training_evaluation_report` (Kirkpatrick L1–L4, normalised gain).

## 11. Laporan ke pengguna

Yang sudah jadi + path (`out/…`, `lesson-plan.json`, `captions/`, `stock/stock-credits.md`),
yang belum (review klinis, consent, VO, render), dan sumber yang dipakai.
