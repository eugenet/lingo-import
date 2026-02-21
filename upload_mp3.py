#!/usr/bin/env python3
"""Upload MP3 files to LingQ courses via API. Supports single file or batch via wildcard."""

import argparse
import glob
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests_toolbelt.multipart.encoder import MultipartEncoder

BASE_URL = "https://www.lingq.com/api/v3"
TITLE_MAX = 60
DESC_MAX = 200


def _natural_sort_key(s: str) -> list:
    """Key for natural sort: chapter_1, chapter_2, chapter_10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def expand_mp3_files(pattern: str) -> list[str]:
    """Expand wildcard to sorted list of matching MP3 paths."""
    paths = glob.glob(pattern)
    return sorted(paths, key=lambda p: _natural_sort_key(os.path.basename(p)))


def derive_title(
    mp3_path: str,
    title: str | None,
    title_prefix: str | None,
    title_template: str | None,
) -> str:
    """Derive lesson title from args and filename."""
    basename = Path(mp3_path).stem
    if title:
        return title[:TITLE_MAX]
    if title_template:
        t = title_template.replace("{basename}", basename)
        return t[:TITLE_MAX]
    if title_prefix:
        return (title_prefix + basename)[:TITLE_MAX]
    return basename[:TITLE_MAX]


def _get_my_collections(api_key: str, lang: str) -> list[dict]:
    """Fetch user's collections for language. Returns list of course dicts."""
    url = f"{BASE_URL}/{lang}/collections/my/"
    headers = {"Authorization": api_key}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("results", [])


def resolve_course_id(api_key: str, lang: str, course_spec: str) -> int | None:
    """Resolve --course to a numeric ID. If course_spec is digits, return it; else find by title."""
    if str(course_spec).strip().isdigit():
        return int(course_spec)
    name = str(course_spec).strip()
    courses = _get_my_collections(api_key, lang)
    name_lower = name.lower()
    for c in courses:
        if c.get("title", "").strip().lower() == name_lower:
            return int(c.get("pk") or c.get("id"))
    return None


def list_courses(api_key: str, lang: str) -> int:
    """List user courses for language. Returns 0 on success."""
    try:
        for c in _get_my_collections(api_key, lang):
            cid = c.get("pk") or c.get("id", "?")
            print(f"  {cid}\t{c.get('title', '')}")
        return 0
    except requests.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        if hasattr(e, "response") and e.response is not None:
            print(e.response.text, file=sys.stderr)
        return 1


def upload_lesson(
    api_key: str,
    lang: str,
    course_id: int,
    level: int,
    mp3_path: str,
    title: str,
    description: str | None = None,
    image_path: str | None = None,
    status: str = "private",
) -> tuple[bool, str]:
    """Upload one lesson. Returns (success, message)."""
    url = f"{BASE_URL}/{lang}/lessons/import/"
    mp3_name = os.path.basename(mp3_path)

    files_to_close = []
    try:
        audio_f = open(mp3_path, "rb")
        files_to_close.append(audio_f)
        fields = [
            ("title", title[:TITLE_MAX]),
            ("text", title[:TITLE_MAX]),
            ("status", status),
            ("collection", str(course_id)),
            ("level", str(level)),
            ("save", "true"),
            ("audio", (mp3_name, audio_f, "audio/mpeg")),
        ]
        if description:
            fields.append(("description", description[:DESC_MAX]))
        if image_path:
            img_f = open(image_path, "rb")
            files_to_close.append(img_f)
            fields.append(("image", (os.path.basename(image_path), img_f, "image/jpeg")))

        m = MultipartEncoder(fields)
        headers = {
            "Authorization": api_key,
            "Content-Type": m.content_type,
        }
        r = requests.post(url, data=m, headers=headers, timeout=120)
        r.raise_for_status()
        data = r.json()
        lesson_url = data.get("url", data.get("id", "unknown"))
        return True, str(lesson_url)
    except requests.RequestException as e:
        msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                msg = e.response.text or msg
            except Exception:
                pass
        return False, msg
    finally:
        for f in files_to_close:
            f.close()


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Upload MP3 files to LingQ courses (Import audio for transcription)."
    )
    parser.add_argument(
        "--mp3",
        help="MP3 file or wildcard pattern (e.g. audio/*.mp3); not required for --list-courses",
    )
    parser.add_argument("--course", help="Course ID or course name (e.g. Donato)")
    parser.add_argument("--lang", help="Language code (e.g. es, en)")
    parser.add_argument(
        "--level",
        type=int,
        choices=range(7),
        metavar="0-6",
        help="Level: 0=No Knowledge, 1-2=Beginner, 3-4=Intermediate, 5-6=Advanced",
    )
    parser.add_argument("--title", help="Lesson title (single file); max 60 chars")
    parser.add_argument(
        "--title-prefix",
        help="Batch: prefix for title from filename (e.g. 'Capítulo ')",
    )
    parser.add_argument(
        "--title-template",
        help="Batch: template with {basename} (e.g. 'Lesson {basename}')",
    )
    parser.add_argument(
        "--description",
        help="Description; max 200 chars (shared in batch)",
    )
    parser.add_argument("--image", help="Optional image file path")
    parser.add_argument(
        "--status",
        choices=("private", "shared"),
        default="private",
        help="Lesson status",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("LINGQ_API_KEY"),
        help="LingQ API key (or LINGQ_API_KEY env)",
    )
    parser.add_argument(
        "--list-courses",
        action="store_true",
        help="List courses for --lang and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matched files and titles, no upload",
    )

    args = parser.parse_args()

    api_key = args.api_key

    if args.list_courses:
        if not api_key:
            print("Error: --api-key or LINGQ_API_KEY required for --list-courses", file=sys.stderr)
            return 1
        lang = args.lang or os.getenv("LINGQ_LANGUAGE", "en")
        return list_courses(api_key, lang)

    if not args.dry_run and not api_key:
        print("Error: --api-key or LINGQ_API_KEY required", file=sys.stderr)
        return 1

    if not args.mp3:
        print("Error: --mp3 required for upload or --dry-run", file=sys.stderr)
        return 1

    course_spec = args.course or os.getenv("LINGQ_COURSE_ID")
    lang = args.lang or os.getenv("LINGQ_LANGUAGE")
    level = args.level
    if level is None:
        lev_env = os.getenv("LINGQ_LEVEL")
        level = int(lev_env) if lev_env else 3

    if not args.dry_run and (not course_spec or not lang):
        print("Error: --course and --lang required (or set env)", file=sys.stderr)
        return 1

    course_id = None
    if not args.dry_run and course_spec and lang and api_key:
        course_id = resolve_course_id(api_key, lang, str(course_spec))
        if course_id is None:
            print(f"Error: course '{course_spec}' not found. Use --list-courses --lang {lang} to see names.", file=sys.stderr)
            return 1

    if args.description and len(args.description) > DESC_MAX:
        print(f"Error: description max {DESC_MAX} chars", file=sys.stderr)
        return 1

    files = expand_mp3_files(args.mp3)
    if not files:
        print(f"No files matched: {args.mp3}", file=sys.stderr)
        return 1

    if args.dry_run:
        for i, p in enumerate(files, 1):
            title = derive_title(
                p, args.title, args.title_prefix, args.title_template
            )
            print(f"[{i}/{len(files)}] {p} -> title: {title}")
        return 0

    if len(files) > 1 and args.title:
        print(
            "Warning: --title ignored in batch mode; use --title-prefix or --title-template",
            file=sys.stderr,
        )

    failures = 0
    for i, mp3_path in enumerate(files, 1):
        title = derive_title(
            mp3_path, args.title, args.title_prefix, args.title_template
        )
        print(f"[{i}/{len(files)}] Uploading {os.path.basename(mp3_path)}...", end=" ")
        ok, msg = upload_lesson(
            api_key=api_key,
            lang=lang,
            course_id=course_id,
            level=level,
            mp3_path=mp3_path,
            title=title,
            description=args.description,
            image_path=args.image,
            status=args.status,
        )
        if ok:
            print(f"OK -> {msg}")
        else:
            print(f"FAILED: {msg}")
            failures += 1

    return failures


if __name__ == "__main__":
    sys.exit(main())
