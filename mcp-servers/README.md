# Recommended MCP servers — MCP Training & Learning Development

Ready-to-copy configs: [`codex-config.toml`](codex-config.toml) (Codex CLI) and
[`mcp.json`](mcp.json) (clients that use an `mcpServers` JSON block).
**Every key field is empty on purpose.** Fill keys only in your local config file or in
`~/.config/research-analytics-mcp/.env` (chmod 600), never in this repository.

| Server | Package | Used for | Key |
|:--|:--|:--|:--|
| **research-analytics** (this repo) | `uvx --from git+…/research-analytics-mcp` | literature, journals, research DB, statistics, market model, training design & evaluation, lesson plans, captions, Openverse, MuAPI | optional: `OPENALEX_MAILTO`, `SEMANTIC_SCHOLAR_API_KEY`, `NCBI_API_KEY`, `MUAPI_API_KEY` |
| OpenAlex | `@cyanheads/openalex-mcp-server` | full OpenAlex query language, citation graph, group-by analytics | optional `OPENALEX_API_KEY` |
| medical-mcp | `medical-mcp` | FDA/EMA drug data, FAERS safety, WHO, RxNorm, guidelines, clinical trials | none |
| NotebookLM | `@m4ykeldev/notebooklm-mcp` | source-grounded Q&A over selected papers, briefing docs, study guides, quizzes, flashcards | Google sign-in (`… auth`) |
| Fetch | `mcp-server-fetch` (PyPI) | read guideline/web pages as Markdown | none |
| MarkItDown | `markitdown-mcp` (PyPI) | convert PDF, DOCX, PPTX teaching material and papers to Markdown | none |
| ElevenLabs | `elevenlabs-mcp` (PyPI) | Indonesian voiceover, transcription | `ELEVENLABS_API_KEY` |
| Pixabay | `@hanoak/pixabay-mcp-server` (unofficial) | royalty-free stock video and images | `PIXABAY_API_KEY` |
| Remotion | `@remotion/mcp` | Remotion documentation for animated text, captions, rendering | none |
| yt-dlp | `@kevinwatt/yt-dlp-mcp` | download Creative Commons / own lecture clips (no licence check: verify first) | none |
| Filesystem | `@modelcontextprotocol/server-filesystem` | file access limited to the video project folder | none |
| Sequential thinking | `@modelcontextprotocol/server-sequential-thinking` | step-by-step planning of modules and analyses | none |
| Memory | `@modelcontextprotocol/server-memory` | persistent knowledge graph of project decisions | none |

## Where to get keys (each user registers their own)

- OpenAlex: openalex.org/settings/api · Semantic Scholar: semanticscholar.org/product/api
- NCBI: ncbi.nlm.nih.gov/account/settings (API Key Management)
- ElevenLabs: elevenlabs.io → Settings → API Keys · Pixabay: pixabay.com/api/docs (logged in)
- MuAPI (Open-Higgsfield gateway): muapi.ai dashboard · Unsplash: unsplash.com/developers

Store a key without it showing on screen or in shell history:

```bash
mkdir -p ~/.config/research-analytics-mcp
read -s "K?Paste PIXABAY_API_KEY: "; echo
printf 'PIXABAY_API_KEY=%s\n' "$K" >> ~/.config/research-analytics-mcp/.env; unset K
chmod 600 ~/.config/research-analytics-mcp/.env
```

## Workflow map

```
evidence ──► design ──► material ──► delivery ──► evaluation
PubMed        training_      video_lesson_plan    LMS / class    training_observation_checklist
OpenAlex      blueprint      ElevenLabs VO        social video   db_add_observations
medical-mcp   NotebookLM     Pixabay/Openverse                   training_evaluation_report
MarkItDown    (study guide)  MuAPI B-roll                        stats_* (deeper analysis)
                             Remotion + FFmpeg
                             video_captions
```
