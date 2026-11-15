# Resep FFmpeg — video pengajaran medis

Semua perintah dijalankan di shell agen (atau lewat Desktop Commander MCP bila klien tidak punya shell).
Selalu: input dari `source/` atau `stock/`, output ke `work/` atau `out/`, tambah `-n` agar tidak menimpa file yang sudah ada (hapus `-n` hanya untuk file buatan skill sendiri yang memang mau diganti).
Path berisi spasi → selalu pakai tanda kutip.

## 0. Cek kemampuan build ffmpeg
```bash
ffmpeg -hide_banner -filters | grep -E " (subtitles|ass|drawtext|xfade|loudnorm|sidechaincompress|silencedetect) "
```
- Tidak ada `subtitles`/`ass`/`drawtext` → ffmpeg dibangun tanpa libass/freetype. **Teks & subtitle dikerjakan di Remotion** (disarankan), atau pengguna memasang build lengkap (mis. cek `brew info ffmpeg-full`; minta izin sebelum install).
- Bisa juga render lapisan teks dari Remotion sebagai video transparan (`remotion-render/transparent-videos.md`, ProRes 4444) lalu di-`overlay` dengan ffmpeg.

## 1. Inspeksi
```bash
# ringkasan video + format
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate,pix_fmt,bit_rate:format=duration,size -of json "in.mp4"
# audio
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of json "in.mp4"
# durasi saja (detik)
ffprobe -v error -show_entries format=duration -of csv=p=0 "in.mp4"
# jumlah keyframe di awal (cek apakah -c copy akan presisi)
ffprobe -v error -select_streams v:0 -skip_frame nokey -show_entries frame=pts_time -of csv=p=0 -read_intervals "%+10" "in.mp4"
```

## 2. Potong (cut / trim)
```bash
# cepat, tanpa re-encode (titik potong menempel ke keyframe terdekat)
ffmpeg -n -ss 00:00:05 -to 00:00:12 -i "in.mp4" -c copy -avoid_negative_ts make_zero work/cut-01.mp4
# presisi frame (re-encode)
ffmpeg -n -i "in.mp4" -ss 5.0 -to 12.0 -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 work/cut-01.mp4
```

## 3. Reformat / reframe
```bash
# isi penuh 9:16 (crop tengah) — "cover"
ffmpeg -n -i in.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1" -c:v libx264 -crf 18 -c:a copy work/v916.mp4
# crop dengan geser fokus (x offset 0–1, contoh 0.3 = agak kiri)
ffmpeg -n -i in.mp4 -vf "scale=-2:1920,crop=1080:1920:(iw-1080)*0.3:0,setsar=1" -c:v libx264 -crf 18 -c:a copy work/v916-left.mp4
# 16:9 utuh di atas latar blur 9:16
ffmpeg -n -i in.mp4 -filter_complex "[0:v]split=2[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]" -map "[v]" -map "0:a?" -c:v libx264 -crf 18 -c:a aac -b:a 192k work/v916-blur.mp4
# 1:1
ffmpeg -n -i in.mp4 -vf "scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080,setsar=1" -c:v libx264 -crf 18 -c:a copy work/v11.mp4
```

## 4. Normalisasi (WAJIB sebelum digabung)
Semua klip → resolusi, fps, pixel format, sample rate yang sama.
```bash
# klip dengan audio
ffmpeg -n -i in.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p,setsar=1" \
  -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k -ar 48000 -ac 2 work/norm-01.mp4
# klip TANPA audio (umum di footage Pixabay) → tambah audio senyap agar concat tidak rusak
ffmpeg -n -i in.mp4 -f lavfi -i anullsrc=r=48000:cl=stereo -shortest \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p,setsar=1" \
  -map 0:v -map 1:a -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k work/norm-02.mp4
```

## 5. Gabung (concat)
```bash
# semua klip sudah dinormalisasi → concat demuxer, tanpa re-encode
# PENTING: path di list.txt relatif terhadap lokasi list.txt
printf "file '%s'\n" norm-01.mp4 norm-02.mp4 norm-03.mp4 > work/list.txt
ffmpeg -n -f concat -safe 0 -i work/list.txt -c copy work/joined.mp4

# dengan transisi crossfade 0.5 dtk antara 2 klip (offset = durasi klip A − 0.5)
ffmpeg -n -i work/norm-01.mp4 -i work/norm-02.mp4 -filter_complex \
 "[0:v][1:v]xfade=transition=fade:duration=0.5:offset=6.5[v];[0:a][1:a]acrossfade=d=0.5[a]" \
 -map "[v]" -map "[a]" -c:v libx264 -crf 18 -c:a aac -b:a 192k work/joined-xfade.mp4
```
Transisi `xfade` lain: `fade`, `wipeleft`, `slideup`, `circleopen`, `dissolve`, `smoothleft`, `zoomin`. Untuk banyak klip, rantai `xfade` berurutan dengan offset kumulatif (hitung dari ffprobe, jangan menebak).

## 6. Buang jeda diam (talking head)
```bash
ffmpeg -hide_banner -i in.mp4 -af silencedetect=noise=-35dB:d=0.6 -f null - 2>&1 | grep -E "silence_(start|end)"
```
Ubah hasil `silence_start/silence_end` menjadi daftar segmen yang DISIMPAN (beri bantalan 0.1 dtk), potong tiap segmen dengan resep presisi (bagian 2), lalu concat (bagian 5). Tunjukkan daftar segmen ke pengguna sebelum memotong.

## 7. Kecepatan
```bash
# 2x lebih cepat (video + audio)
ffmpeg -n -i in.mp4 -filter_complex "[0:v]setpts=0.5*PTS[v];[0:a]atempo=2.0[a]" -map "[v]" -map "[a]" work/fast.mp4
# slow motion 0.5x
ffmpeg -n -i in.mp4 -filter_complex "[0:v]setpts=2.0*PTS[v];[0:a]atempo=0.5[a]" -map "[v]" -map "[a]" work/slow.mp4
```

## 8. Audio
```bash
# ekstrak WAV 16 kHz mono untuk Whisper
ffmpeg -n -i in.mp4 -vn -ac 1 -ar 16000 work/audio-16k.wav
# ganti audio dengan voiceover
ffmpeg -n -i work/joined.mp4 -i voiceover/full.mp3 -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest work/with-vo.mp4
# gabung file VO per adegan jadi satu
printf "file '%s'\n" scene-01.mp3 scene-02.mp3 scene-03.mp3 > voiceover/list.txt
ffmpeg -n -f concat -safe 0 -i voiceover/list.txt -c copy voiceover/full.mp3
# VO + musik dengan ducking (musik turun otomatis saat ada suara)
# apad pada sidechain WAJIB: tanpa itu musik ikut terpotong saat VO selesai (sudah diuji)
# panjang hasil = panjang musik; potong ke panjang video saat mux (-shortest)
ffmpeg -n -i music/bg.mp3 -i voiceover/full.mp3 -filter_complex \
 "[1:a]asplit=2[vo1][vo2];[vo1]apad[sc];[0:a]volume=0.35[m];[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];[duck][vo2]amix=inputs=2:duration=first:normalize=0[a]" \
 -map "[a]" -c:a aac -b:a 192k work/mix.m4a
# pasang mix ke video, potong sepanjang video
ffmpeg -n -i work/joined.mp4 -i work/mix.m4a -map 0:v -map 1:a -c:v copy -c:a aac -shortest work/with-mix.mp4
# fade in/out musik (durasi total D detik)
ffmpeg -n -i music/bg.mp3 -af "afade=t=in:d=1,afade=t=out:st=$((D-2)):d=2" work/bg-fade.mp3
# loudness sosial media: −14 LUFS, true peak −1
ffmpeg -n -i work/with-mix.mp4 -c:v copy -af loudnorm=I=-14:TP=-1:LRA=11 -c:a aac -b:a 192k work/loud.mp4
```

## 9. Overlay
```bash
# logo/watermark kanan atas
ffmpeg -n -i work/loud.mp4 -i assets/logo.png -filter_complex "[1:v]scale=200:-1[l];[0:v][l]overlay=W-w-40:120" -c:a copy work/logo.mp4
# lapisan teks transparan dari Remotion (ProRes 4444 .mov)
ffmpeg -n -i work/loud.mp4 -i work/text-layer.mov -filter_complex "[0:v][1:v]overlay=0:0:format=auto" -c:v libx264 -crf 18 -c:a copy work/with-text.mp4
# bakar subtitle (HANYA bila build punya filter subtitles — cek bagian 0)
ffmpeg -n -i work/loud.mp4 -vf "subtitles=captions/sub.srt:force_style='FontName=Montserrat,FontSize=16,Bold=1,Outline=3,Alignment=2,MarginV=220'" -c:a copy work/subbed.mp4
```

## 10. Ekspor final, preview, still
```bash
# final kompatibel IG/TikTok/YouTube/WhatsApp
ffmpeg -n -i work/with-text.mp4 -c:v libx264 -crf 18 -preset slow -profile:v high -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -ar 48000 -movflags +faststart out/final.mp4
# preview ringan
ffmpeg -n -i work/joined.mp4 -vf scale=-2:640 -c:v libx264 -crf 28 -preset veryfast -c:a aac -b:a 96k work/preview.mp4
# still untuk QA / thumbnail
ffmpeg -n -ss 3 -i out/final.mp4 -frames:v 1 work/check-1.png
# kompres untuk WhatsApp (< 16 MB kira-kira)
ffmpeg -n -i out/final.mp4 -vf scale=720:-2 -c:v libx264 -crf 28 -preset slow -c:a aac -b:a 96k -movflags +faststart out/final-wa.mp4
```

## 11. Verifikasi setiap output
```bash
ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,r_frame_rate:format=duration,size -of compact "out/final.mp4"
```
Cocokkan dengan `edit-plan.md`: durasi ±0.1 dtk, resolusi, fps, ada stream audio.
