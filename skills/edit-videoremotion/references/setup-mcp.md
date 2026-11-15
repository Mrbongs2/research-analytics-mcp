# Setup for /edit-videoremotion

1. **ffmpeg/ffprobe**: `brew install ffmpeg` (macOS) or `sudo apt install ffmpeg`.
   `ffmpeg -hide_banner -filters | grep -E " (subtitles|drawtext) "` — if missing, do text in Remotion.
2. **Node.js ≥ 18** for Remotion (`npx create-video@latest`).
3. **MCP servers**: copy what you need from [`mcp-servers/`](../../../mcp-servers/README.md) at the
   repo root (research-analytics, ElevenLabs, Pixabay, Remotion docs, Filesystem, yt-dlp …).
4. **Keys** are never written in this skill, the scripts, or the repository. The scripts read:
   - `PIXABAY_API_KEY` — `scripts/pixabay.py`
   - `UNSPLASH_ACCESS_KEY` — `scripts/unsplash.py`
   - Openverse needs no key — `scripts/openverse.py`

   from the environment first, then from `~/.config/research-analytics-mcp/.env` (chmod 600).
   See the `read -s` snippet in `mcp-servers/README.md`.
5. **Quick check**

```bash
command -v ffmpeg ffprobe node npx uvx
python3 -I scripts/openverse.py check
python3 -I scripts/pixabay.py check
python3 -I scripts/unsplash.py check
```

Licences: Pixabay and Unsplash allow free use without mandatory attribution (credit is
appreciated, raw files may not be resold); Openverse items vary per file — CC BY / BY-SA
require the attribution line, which `download` writes to `stock-credits.md`.
