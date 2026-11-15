# research-analytics-mcp

MCP server + agent skills untuk **riset jurnal (Scopus), evidence medis, analitik data observasi,
market research, dan Learning & Development** — dari pencarian literatur sampai evaluasi pelatihan,
dengan database riset lokal (SQLite).

*An MCP server and agent skills for literature reviews and journal targeting, medical evidence,
statistics on observational data, market sizing, and evidence-based training design and evaluation.*

## Isi

| Bagian | Tools | Sumber data |
|:--|:--|:--|
| Literatur | `search_openalex`, `topic_trend`, `citation_graph`, `search_semantic_scholar`, `search_pubmed`, `pubmed_abstracts`, `lookup_doi` | OpenAlex, Semantic Scholar, PubMed (NCBI E-utilities), Crossref |
| Medis | `search_clinical_trials`, `who_indicators`, `who_indicator_data` (+ evidence level di hasil PubMed) | ClinicalTrials.gov v2, WHO GHO |
| Jurnal | `journal_profile`, `journals_for_topic` | OpenAlex sources |
| Database riset | `db_create_project`, `db_add_papers`, `db_update_paper`, `db_literature_matrix`, `db_log_search`, `db_prisma`, `db_add_note`, `db_save_journal`, `db_add_observations`, `db_import_observations_csv`, `db_query_observations`, `db_export_csv` | SQLite lokal |
| Statistik | `stats_describe`, `stats_compare_groups`, `stats_paired`, `stats_crosstab`, `stats_correlate`, `stats_trend`, `stats_kappa`, `stats_sample_size` | CSV / records / observasi |
| Market research | `market_size_model`, `market_regional_split`, `market_example_assumptions` | Asumsi bersumber (BPS, register, literatur) |
| Training / L&D | `training_blueprint`, `training_observation_checklist`, `training_evaluation_report`, `training_storyboard` | Database proyek |
| Media training | `media_generate`, `media_result`, `media_upload` | [Open-Higgsfield](https://github.com/Anil-matcha/Open-Higgsfield-AI) via MuAPI (berbayar, butuh `confirm=true`) |
| Video pengajaran | `video_lesson_plan`, `video_captions`, `video_probe`, `media_search_openverse` | Database proyek, ffprobe, Openverse (Wikimedia Commons dll., tanpa kunci) |

Skills (format Agent Skills `SKILL.md`) di folder [`skills/`](skills):

- [`research-journalscopus`](skills/research-journalscopus/SKILL.md) — topik → literatur → matriks → research gap → shortlist jurnal Scopus
- [`marketresearch`](skills/marketresearch/SKILL.md) — market size 3 skenario, regional & white space, harga, pesaing, proses bisnis
- [`medical-analytics`](skills/medical-analytics/SKILL.md) — PICO/MeSH, evidence level, uji statistik, PRISMA
- [`learning-development`](skills/learning-development/SKILL.md) — desain modul, checklist observasi, Kirkpatrick L1–L4, video training
- [`edit-videoremotion`](skills/edit-videoremotion/SKILL.md) — video pengajaran medis & materi: bukti → naskah → aset berlisensi → voiceover → caption → FFmpeg/Remotion → QA klinis → evaluasi

## MCP Training & Learning Development

Paket untuk membuat pelatihan kesehatan berbasis bukti dari hulu ke hilir:

1. **Bukti** — `search_pubmed`, `search_openalex`, medical-mcp, NotebookLM, MarkItDown.
2. **Desain** — `training_blueprint` (Bloom, agenda, rencana Kirkpatrick), `training_observation_checklist`.
3. **Materi & video** — skill `edit-videoremotion`: `video_lesson_plan` (durasi per adegan, cek sumber
   angka klinis, prinsip multimedia), aset Openverse/Pixabay/Unsplash, B-roll Open-Higgsfield (MuAPI),
   voiceover ElevenLabs, `video_captions` (SRT + Remotion), FFmpeg + Remotion, `video_probe` untuk QA.
4. **Evaluasi** — `db_add_observations` → `training_evaluation_report` (reaction, normalised gain,
   pass rate checklist, kappa antar-observer, outcome) dan `stats_*`.

Server MCP pendamping yang direkomendasikan (13 server, semua kolom kunci kosong): [`mcp-servers/`](mcp-servers/README.md).

## Instalasi

Butuh Python ≥ 3.10 dan [uv](https://docs.astral.sh/uv/).

```bash
uvx --from git+https://github.com/Mrbongs2/research-analytics-mcp research-analytics-mcp
```

Atau dari clone lokal:

```bash
git clone https://github.com/Mrbongs2/research-analytics-mcp && cd research-analytics-mcp
uv venv && uv pip install -e ".[dev]"
```

### Konfigurasi klien MCP

**Codex CLI** (`~/.codex/config.toml`) — contoh lengkap (plus server pendamping) di [`mcp-servers/codex-config.toml`](mcp-servers/codex-config.toml):

```toml
[mcp_servers.research-analytics]
command = "uvx"
args = ["--from", "git+https://github.com/Mrbongs2/research-analytics-mcp", "research-analytics-mcp"]

[mcp_servers.research-analytics.env]
OPENALEX_MAILTO = "you@example.com"
```

**Klien lain** yang memakai `mcpServers` JSON: lihat [`mcp-servers/mcp.json`](mcp-servers/mcp.json).

### Memasang skills

Salin folder skill ke direktori skills klien Anda, misalnya:

```bash
cp -r skills/* ~/.codex/skills/
```

## Variabel lingkungan (semua opsional)

| Variabel | Fungsi |
|:--|:--|
| `RA_MCP_DB` | Lokasi database (default `~/.research-analytics-mcp/research.db`) |
| `OPENALEX_API_KEY`, `OPENALEX_MAILTO` | Kuota OpenAlex lebih besar |
| `SEMANTIC_SCHOLAR_API_KEY` | Menghindari rate limit Semantic Scholar |
| `NCBI_API_KEY` | 10 request/detik ke PubMed |
| `MUAPI_API_KEY`, `MUAPI_BASE_URL` | Generasi media Open-Higgsfield / MuAPI |
| `PIXABAY_API_KEY`, `UNSPLASH_ACCESS_KEY` | Skrip stok media skill `edit-videoremotion` |

Lihat [`.env.example`](.env.example).

## Contoh alur

1. *"Riset silver diamine fluoride untuk karies anak, mau publish di jurnal Scopus Q2, APC < 1000 USD"*
   → skill `research-journalscopus` + `medical-analytics`.
2. *"Hitung potensi pasar aligner di Indonesia per provinsi"* → skill `marketresearch`.
3. *"Buat pelatihan hand hygiene untuk perawat lalu evaluasi pre/post dan observasi 6 minggu"*
   → skill `learning-development`.
4. *"Buat video 3 menit teknik menyikat gigi metode Bass untuk orang tua, 16:9 + versi Reels"*
   → skill `edit-videoremotion`.

## Prinsip

- Tidak ada paper, DOI, angka, atau kuartil yang dikarang: semua dari hasil tool.
- OpenAlex **tidak** mengonfirmasi indeks Scopus atau kuartil SJR; cek di scopus.com/sources dan scimagojr.com.
- Hasil market model diberi label *estimasi model*, dan setiap input wajib punya sumber.
- Generasi media berbayar hanya berjalan dengan `confirm=true`.
- Jangan memasukkan data pasien yang dapat diidentifikasi; gunakan kode subjek.

## Pengembangan

```bash
pytest -m "not network"   # unit test offline
pytest -m network         # smoke test ke API publik
ruff check .
```

Kontribusi: lihat [CONTRIBUTING.md](CONTRIBUTING.md). Lisensi: [MIT](LICENSE).
