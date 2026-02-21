# LingQ MP3 Upload Script

Upload MP3 files to LingQ courses via API, matching the "Import audio for transcription" UI. Supports single files or batch upload via wildcard patterns. LingQ generates transcripts server-side using Whisper AI.

## Setup

1. Get your API key from [lingq.com/accounts/apikey](https://www.lingq.com/en/accounts/apikey/).
2. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set your values:

   ```bash
   cp .env.example .env
   # Edit .env: LINGQ_API_KEY=Token your_key_here, LINGQ_COURSE_ID=..., etc.
   ```

## Usage

### List courses (find course ID)

```bash
python upload_mp3.py --list-courses --lang es
```

### Single file

```bash
python upload_mp3.py --mp3 "Donato 20260220 1035.mp3" --title "Donato Lesson" --course 50220 --lang es --level 3
```

### Batch (wildcard)

```bash
python upload_mp3.py --mp3 "audio/chapter_*.mp3" --course 50220 --lang es --level 3 --title-prefix "Capítulo "
```

Titles are derived from filenames (e.g. `chapter_1` → "Capítulo chapter_1"). Use `--title-template "{basename}"` for custom patterns.

### Dry run (preview matched files)

```bash
python upload_mp3.py --mp3 "*.mp3" --course 50220 --lang es --dry-run
```

### Options

| Option | Description |
|--------|-------------|
| `--mp3` | MP3 file path or wildcard (e.g. `audio/*.mp3`) |
| `--course` | Course ID (collection pk) |
| `--lang` | Language code: `es`, `en`, `fr`, etc. |
| `--level` | 0–6: 0=No Knowledge, 1–2=Beginner, 3–4=Intermediate, 5–6=Advanced |
| `--title` | Lesson title (single file); max 60 chars |
| `--title-prefix` | Batch: prefix for title from filename |
| `--title-template` | Batch: template with `{basename}` |
| `--description` | Optional; max 200 chars |
| `--image` | Optional image file |
| `--status` | `private` (default) or `shared` |
| `--list-courses` | List courses for `--lang` and exit |
| `--dry-run` | List matched files, no upload |

Environment variables `LINGQ_API_KEY`, `LINGQ_COURSE_ID`, `LINGQ_LANGUAGE`, `LINGQ_LEVEL` can replace CLI args.

## Exit codes

- `0` – Success (all uploads OK, or dry-run)
- `1` – Usage/config error, or list-courses failure
- `N` – Number of failed uploads in batch (continues on failure)

## Tests

```bash
python -m unittest tests.test_upload_mp3 -v
```

### Test coverage

```bash
pip install coverage
coverage run -m unittest tests.test_upload_mp3
coverage report
```

For a line-by-line HTML report:
```bash
coverage run -m unittest tests.test_upload_mp3
coverage html
# Open htmlcov/index.html in a browser
```
