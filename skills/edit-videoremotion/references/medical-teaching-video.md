# Video pengajaran medis: pedagogi, etika, dan QA

## 1. Prinsip desain (Mayer, multimedia learning)

| Prinsip | Terapkan di video |
|:--|:--|
| Coherence | Buang musik/gambar dekoratif yang tidak membantu memahami. |
| Signaling | Panah, highlight, "Langkah 2 dari 5" pada hal yang sedang dibahas. |
| Redundancy | Jangan menampilkan paragraf teks yang sama dengan narasi; teks layar = kata kunci. Caption tetap tersedia untuk aksesibilitas. |
| Spatial / temporal contiguity | Label diletakkan di dekat struktur yang dimaksud, muncul bersamaan dengan narasinya. |
| Segmenting | Satu tujuan belajar per video atau per bab; 2–6 menit. |
| Pre-training | Perkenalkan istilah/alat kunci sebelum prosedur. |
| Modality | Jelaskan gambar dengan suara, bukan teks panjang. |
| Personalization & voice | Gaya bicara percakapan ("Anda"), suara manusia yang jelas. |
| Embodiment | Untuk keterampilan: sudut pandang operator (POV), tangan terlihat jelas. |

Struktur adegan yang disarankan:
1. **Hook** (5–10 dtk): masalah klinis nyata atau pertanyaan.
2. **Tujuan belajar** (1 kalimat per tujuan).
3. **Konsep / pre-training** (istilah, alat, indikasi–kontraindikasi).
4. **Demonstrasi** langkah demi langkah dengan penanda langkah; ulangi langkah kritis.
5. **Kesalahan umum** dan cara menghindarinya.
6. **Ringkasan** 3 poin + pertanyaan kuis.
7. **Referensi** dan kredit (sumber, reviewer, lisensi aset, label AI).

## 2. Naskah

- 130–150 kata per menit (Bahasa Indonesia), awam lebih lambat (≈ 120).
- Kalimat ≤ 20 kata; satu ide per kalimat; istilah teknis + penjelasan sederhana.
- Angka klinis (dosis, durasi, konsentrasi) **wajib** dengan sumber dan ditampilkan di layar.
- Untuk pasien/awam: hindari menakut-nakuti; sebutkan kapan harus ke tenaga kesehatan.
- Tandai setiap klaim dengan `paper_id`/guideline; `[PERLU SUMBER]` bila belum ada.

## 3. Etika & regulasi

- **Consent**: pasien atau peraga yang dapat dikenali harus memberi persetujuan tertulis untuk
  rekaman *dan* publikasi; simpan di `source/consent/` (jangan di repo publik).
- **Kerahasiaan**: hapus nama, nomor RM, tanggal lahir, wajah, tato, layar monitor dengan data pasien.
- **Promosi**: video edukasi tidak menyebut merek obat/alat secara promosi; sebutkan nama generik.
- **AI**: label media AI; jangan membuat "pasien" AI yang tampil sebagai kasus nyata.
- **Hak cipta**: hanya aset milik sendiri, lisensi bebas (Pixabay, Unsplash), atau CC dengan atribusi.
  Gambar dari jurnal/buku teks hanya dengan izin penerbit atau lisensi terbuka (CC BY).

## 4. Aksesibilitas

- Caption tertutup (SRT) untuk setiap video; ≤ 2 baris, ≤ 42 karakter/baris, ≤ 17 karakter/detik.
- Kontras teks ≥ 4.5:1; font ≥ 48 px pada 1080p untuk teks layar.
- Hindari kedipan cepat (> 3 kali/detik).
- Sediakan transkrip teks untuk LMS.

## 5. Checklist QA sebelum publikasi

| Area | Cek |
|:--|:--|
| Akurasi | Reviewer klinis (nama, kredensial, tanggal) menyetujui naskah dan potongan akhir; semua klaim bersumber. |
| Mutakhir | Guideline yang dipakai versi terbaru; tanggal pencarian tercatat. |
| Privasi | Tidak ada data pasien yang dapat diidentifikasi; consent tersimpan. |
| Lisensi | `stock-credits.md` lengkap; atribusi CC BY di end card/deskripsi. |
| Aksesibilitas | Caption sinkron; kontras; kecepatan bicara. |
| Teknis | Resolusi/fps sesuai rencana, audio −16 LUFS (e-learning) atau −14 LUFS (sosial), tidak ada clipping, durasi ±0.5 dtk dari rencana. |
| Pedagogi | Tujuan belajar tampil di awal, ringkasan + kuis di akhir. |

## 6. Evaluasi (Kirkpatrick)

- L1: kepuasan & kejelasan (skala 1–5) → `reaction_*`.
- L2: pre/post kuis → `pre_score`, `post_score` → normalised gain.
- L3: checklist observasi di tempat kerja 4–8 minggu kemudian → `step_NN`.
- L4: indikator layanan (mis. indeks plak pasien, kepatuhan hand hygiene) → `outcome_*`.
