"""Unit tests for upload_mp3 module."""

import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from upload_mp3 import (
    TITLE_MAX,
    _get_my_collections,
    _natural_sort_key,
    derive_title,
    expand_mp3_files,
    list_courses,
    main,
    resolve_course_id,
    upload_lesson,
)


class TestNaturalSortKey(unittest.TestCase):
    def test_natural_sort_order(self) -> None:
        self.assertLess(_natural_sort_key("ch1"), _natural_sort_key("ch2"))
        self.assertLess(_natural_sort_key("ch2"), _natural_sort_key("ch10"))


class TestExpandMp3Files(unittest.TestCase):
    def test_empty_pattern(self) -> None:
        self.assertEqual(expand_mp3_files("/nonexistent/nothing*.mp3"), [])

    def test_natural_sort(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for n in ["10", "1", "2"]:
                (Path(d) / f"ch{n}.mp3").touch()
            got = expand_mp3_files(f"{d}/ch*.mp3")
            names = [Path(p).name for p in got]
            self.assertEqual(names, ["ch1.mp3", "ch2.mp3", "ch10.mp3"])


class TestDeriveTitle(unittest.TestCase):
    def test_explicit_title(self) -> None:
        self.assertEqual(
            derive_title("/x/foo.mp3", "My Title", None, None), "My Title"
        )

    def test_long_title_truncated(self) -> None:
        long_title = "x" * (TITLE_MAX + 10)
        self.assertEqual(
            len(derive_title("/x/a.mp3", long_title, None, None)), TITLE_MAX
        )

    def test_title_prefix(self) -> None:
        self.assertEqual(
            derive_title("/x/ch1.mp3", None, "Cap ", None), "Cap ch1"
        )

    def test_title_template(self) -> None:
        self.assertEqual(
            derive_title("/x/foo.mp3", None, None, "L{basename}"), "Lfoo"
        )

    def test_basename_fallback(self) -> None:
        self.assertEqual(
            derive_title("/path/to/lesson.mp3", None, None, None), "lesson"
        )


class TestGetMyCollections(unittest.TestCase):
    @patch("upload_mp3.requests.get")
    def test_returns_results(self, mock_get: object) -> None:
        mock_get.return_value.json.return_value = {"results": [{"pk": 1, "title": "A"}]}
        mock_get.return_value.raise_for_status = lambda: None
        got = _get_my_collections("Token x", "es")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["title"], "A")


class TestResolveCourseId(unittest.TestCase):
    def test_numeric_returns_int(self) -> None:
        self.assertEqual(resolve_course_id("x", "es", "1318696"), 1318696)

    def test_numeric_with_whitespace(self) -> None:
        self.assertEqual(resolve_course_id("x", "es", "  123  "), 123)

    @patch("upload_mp3._get_my_collections")
    def test_resolves_by_name(self, mock_get: object) -> None:
        mock_get.return_value = [{"pk": 42, "title": "Donato"}]
        self.assertEqual(resolve_course_id("Token x", "es", "Donato"), 42)

    @patch("upload_mp3._get_my_collections")
    def test_resolves_by_name_case_insensitive(self, mock_get: object) -> None:
        mock_get.return_value = [{"id": 99, "title": "My Course"}]
        self.assertEqual(resolve_course_id("Token x", "es", "my course"), 99)

    @patch("upload_mp3._get_my_collections")
    def test_not_found_returns_none(self, mock_get: object) -> None:
        mock_get.return_value = [{"pk": 1, "title": "Other"}]
        self.assertIsNone(resolve_course_id("Token x", "es", "Missing"))


class TestListCourses(unittest.TestCase):
    @patch("upload_mp3.requests.get")
    def test_success(self, mock_get: object) -> None:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "results": [{"pk": 1, "title": "Course A"}]
        }
        mock_get.return_value.raise_for_status = lambda: None

        self.assertEqual(list_courses("Token x", "es"), 0)
        mock_get.assert_called_once()

    @patch("upload_mp3.requests.get")
    def test_error(self, mock_get: object) -> None:
        import requests

        mock_get.side_effect = requests.RequestException("fail")
        self.assertEqual(list_courses("Token x", "es"), 1)

    @patch("upload_mp3.requests.get")
    def test_error_with_response_text(self, mock_get: object) -> None:
        import requests

        err = requests.RequestException("fail")
        err.response = type("R", (), {"text": "API rate limited"})()
        mock_get.side_effect = err
        with patch("sys.stderr", StringIO()):
            self.assertEqual(list_courses("Token x", "es"), 1)


class TestUploadLesson(unittest.TestCase):
    @patch("upload_mp3.requests.post")
    def test_success(self, mock_post: object) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake")
            mp3_path = f.name
        try:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                "url": "https://lingq.com/lesson/1"
            }
            mock_post.return_value.raise_for_status = lambda: None

            ok, msg = upload_lesson(
                api_key="Token x",
                lang="es",
                course_id=50220,
                level=3,
                mp3_path=mp3_path,
                title="Test",
            )
            self.assertTrue(ok)
            self.assertIn("lingq.com", msg)
        finally:
            Path(mp3_path).unlink(missing_ok=True)

    @patch("upload_mp3.requests.post")
    def test_with_description(self, mock_post: object) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake")
            mp3_path = f.name
        try:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": 123}
            mock_post.return_value.raise_for_status = lambda: None

            ok, _ = upload_lesson(
                api_key="Token x",
                lang="es",
                course_id=50220,
                level=3,
                mp3_path=mp3_path,
                title="Test",
                description="A desc",
            )
            self.assertTrue(ok)
        finally:
            Path(mp3_path).unlink(missing_ok=True)

    @patch("upload_mp3.requests.post")
    def test_failure(self, mock_post: object) -> None:
        import requests

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake")
            mp3_path = f.name
        try:
            mock_post.side_effect = requests.RequestException("Network error")

            ok, msg = upload_lesson(
                api_key="Token x",
                lang="es",
                course_id=50220,
                level=3,
                mp3_path=mp3_path,
                title="Test",
            )
            self.assertFalse(ok)
            self.assertTrue("Network" in msg or "error" in msg.lower())
        finally:
            Path(mp3_path).unlink(missing_ok=True)

    @patch("upload_mp3.requests.post")
    def test_with_image(self, mock_post: object) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_f:
            mp3_f.write(b"fake")
            mp3_path = mp3_f.name
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as img_f:
            img_f.write(b"fake")
            img_path = img_f.name
        try:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": 1}
            mock_post.return_value.raise_for_status = lambda: None

            ok, _ = upload_lesson(
                api_key="Token x",
                lang="es",
                course_id=50220,
                level=3,
                mp3_path=mp3_path,
                title="Test",
                image_path=img_path,
            )
            self.assertTrue(ok)
        finally:
            Path(mp3_path).unlink(missing_ok=True)
            Path(img_path).unlink(missing_ok=True)

    @patch("upload_mp3.requests.post")
    def test_failure_with_response_text(self, mock_post: object) -> None:
        import requests

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake")
            mp3_path = f.name
        try:
            err = requests.RequestException("bad")
            err.response = type("R", (), {"text": '{"error":"invalid"}'})()
            mock_post.side_effect = err

            ok, msg = upload_lesson(
                api_key="Token x", lang="es", course_id=50220, level=3,
                mp3_path=mp3_path, title="Test",
            )
            self.assertFalse(ok)
            self.assertIn("invalid", msg)
        finally:
            Path(mp3_path).unlink(missing_ok=True)

    @patch("upload_mp3.requests.post")
    def test_failure_response_text_raises(self, mock_post: object) -> None:
        import requests

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake")
            mp3_path = f.name
        try:
            err = requests.RequestException("bad")
            class BadResp:
                @property
                def text(self):
                    raise ValueError("decode err")
            err.response = BadResp()
            mock_post.side_effect = err

            ok, msg = upload_lesson(
                api_key="Token x", lang="es", course_id=50220, level=3,
                mp3_path=mp3_path, title="Test",
            )
            self.assertFalse(ok)
            self.assertEqual(msg, "bad")
        finally:
            Path(mp3_path).unlink(missing_ok=True)


class TestMain(unittest.TestCase):
    def _run_main(self, *args: str) -> int:
        with patch("sys.argv", ["upload_mp3"] + list(args)):
            return main()

    @patch("upload_mp3.list_courses")
    def test_list_courses_no_api_key(self, mock_list: object) -> None:
        code = self._run_main("--list-courses", "--lang", "es", "--api-key", "")
        self.assertEqual(code, 1)
        mock_list.assert_not_called()

    @patch("upload_mp3.list_courses")
    def test_list_courses_success(self, mock_list: object) -> None:
        mock_list.return_value = 0
        code = self._run_main("--list-courses", "--lang", "es", "--api-key", "Token x")
        self.assertEqual(code, 0)
        mock_list.assert_called_once()

    def test_upload_no_api_key(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x")
            path = f.name
        try:
            code = self._run_main("--mp3", path, "--course", "1", "--lang", "es", "--api-key", "")
            self.assertEqual(code, 1)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_no_mp3(self) -> None:
        code = self._run_main("--course", "1", "--lang", "es", "--api-key", "Token x")
        self.assertEqual(code, 1)

    def test_no_course_or_lang(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x")
            path = f.name
        try:
            code = self._run_main("--mp3", path, "--api-key", "Token x")
            self.assertEqual(code, 1)
        finally:
            Path(path).unlink(missing_ok=True)

    @patch("upload_mp3.resolve_course_id")
    def test_course_not_found(self, mock_resolve: object) -> None:
        mock_resolve.return_value = None
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x")
            path = f.name
        try:
            code = self._run_main(
                "--mp3", path, "--course", "Missing", "--lang", "es",
                "--api-key", "Token x",
            )
            self.assertEqual(code, 1)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_description_too_long(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x")
            path = f.name
        try:
            code = self._run_main(
                "--mp3", path, "--course", "1", "--lang", "es",
                "--description", "x" * 250, "--api-key", "Token x",
            )
            self.assertEqual(code, 1)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_no_files_matched(self) -> None:
        code = self._run_main(
            "--mp3", "/nonexistent/*.mp3", "--course", "1", "--lang", "es",
            "--api-key", "Token x",
        )
        self.assertEqual(code, 1)

    def test_dry_run(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x")
            path = f.name
        try:
            with patch("sys.stdout", StringIO()):
                code = self._run_main(
                    "--mp3", path, "--course", "1", "--lang", "es", "--dry-run",
                )
            self.assertEqual(code, 0)
        finally:
            Path(path).unlink(missing_ok=True)

    @patch("upload_mp3.upload_lesson")
    @patch("upload_mp3.resolve_course_id")
    def test_upload_success(self, mock_resolve: object, mock_upload: object) -> None:
        mock_resolve.return_value = 1318696
        mock_upload.return_value = (True, "https://lingq.com/lesson/1")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x")
            path = f.name
        try:
            with patch("sys.stdout", StringIO()):
                code = self._run_main(
                    "--mp3", path, "--course", "Donato", "--lang", "es",
                    "--api-key", "Token x",
                )
            self.assertEqual(code, 0)
            mock_resolve.assert_called_once()
            mock_upload.assert_called_once()
        finally:
            Path(path).unlink(missing_ok=True)

    @patch("upload_mp3.upload_lesson")
    @patch("upload_mp3.resolve_course_id")
    def test_batch_with_title_warning(self, mock_resolve: object, mock_upload: object) -> None:
        mock_resolve.return_value = 1318696
        mock_upload.return_value = (True, "url")
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.mp3").write_bytes(b"x")
            (Path(d) / "b.mp3").write_bytes(b"x")
            with patch("sys.stdout", StringIO()), patch("sys.stderr", StringIO()) as err:
                code = self._run_main(
                    "--mp3", f"{d}/*.mp3", "--course", "1", "--lang", "es",
                    "--title", "X", "--api-key", "Token x",
                )
            self.assertEqual(code, 0)
            self.assertIn("Warning", err.getvalue())

    @patch("upload_mp3.upload_lesson")
    @patch("upload_mp3.resolve_course_id")
    def test_upload_failure_returns_failures_count(self, mock_resolve: object, mock_upload: object) -> None:
        mock_resolve.return_value = 1318696
        mock_upload.return_value = (False, "API error")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x")
            path = f.name
        try:
            with patch("sys.stdout", StringIO()):
                code = self._run_main(
                    "--mp3", path, "--course", "1", "--lang", "es",
                    "--api-key", "Token x",
                )
            self.assertEqual(code, 1)
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
