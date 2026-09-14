from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.files.base import ContentFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from sport_shop.media_views import ResilientMediaView
from sport_shop.storage_backends import ResilientMediaStorage
from home.services.video_service import VideoService


class StorageFallbackTests(SimpleTestCase):
    @override_settings(MEDIA_URL="/media/")
    def test_fetch_remote_to_local_persists_file_when_remote_is_available(self):
        with TemporaryDirectory() as tmp_dir:
            storage = ResilientMediaStorage(location=tmp_dir, base_url="/media/")

            remote_file = ContentFile(b"video-bytes", name="videos/sample.mp4")
            remote_file.close = Mock()
            remote_storage = Mock()
            remote_storage.open.return_value = remote_file
            storage._remote_storage = remote_storage

            fetched = storage.fetch_remote_to_local("videos/sample.mp4")

            self.assertTrue(fetched)
            self.assertTrue((Path(tmp_dir) / "videos" / "sample.mp4").exists())
            self.assertEqual((Path(tmp_dir) / "videos" / "sample.mp4").read_bytes(), b"video-bytes")

    @override_settings(MEDIA_URL="/media/")
    def test_storage_url_uses_proxy_route(self):
        storage = ResilientMediaStorage(location="C:/tmp/media-test", base_url="/media/")
        self.assertEqual(storage.url("images/pic.jpg"), "/media-files/images/pic.jpg")
        self.assertEqual(storage.remote_url("images/pic.jpg"), "/media-files/images/pic.jpg")

    @override_settings(LIARA_PUBLIC_BASE_URL="https://media.egofit.ir")
    def test_remote_storage_url_uses_public_domain(self):
        storage = ResilientMediaStorage(location="C:/tmp/media-test", base_url="/media/")
        storage._remote_storage = None
        remote_storage = storage.remote_storage
        self.assertIsNotNone(remote_storage)
        self.assertEqual(remote_storage.url("images/pic.jpg"), "https://media.egofit.ir/egofit/images/pic.jpg")

    @override_settings(MEDIA_CACHE_MAX_AGE=3600)
    def test_media_view_returns_cache_headers_and_304(self):
        with TemporaryDirectory() as tmp_dir:
            media_root = Path(tmp_dir)
            file_path = media_root / "images" / "pic.jpg"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"image-bytes")

            with override_settings(MEDIA_ROOT=media_root):
                request = RequestFactory().get("/media-files/images/pic.jpg")
                response = ResilientMediaView.as_view()(request, path="images/pic.jpg")

                self.assertEqual(response.status_code, 200)
                self.assertIn("Cache-Control", response)
                self.assertEqual(response["Cache-Control"], "public, max-age=3600")
                self.assertIn("ETag", response)

                conditional_request = RequestFactory().get(
                    "/media-files/images/pic.jpg",
                    HTTP_IF_NONE_MATCH=response["ETag"],
                )
                conditional_response = ResilientMediaView.as_view()(conditional_request, path="images/pic.jpg")
                self.assertEqual(conditional_response.status_code, 304)
                response.close()
                conditional_response.close()

    def test_video_service_backfills_local_copy_even_when_remote_only_exists(self):
        with TemporaryDirectory() as tmp_dir:
            storage = ResilientMediaStorage(location=tmp_dir, base_url="/media/")
            remote_file = ContentFile(b"video-bytes", name="videos/sample.mp4")
            remote_file.close = Mock()
            remote_storage = Mock()
            remote_storage.open.return_value = remote_file
            storage._remote_storage = remote_storage

            episode = SimpleNamespace(
                season=SimpleNamespace(series=SimpleNamespace(pk=1)),
                video_file=SimpleNamespace(storage=storage, name="videos/sample.mp4"),
            )
            user = SimpleNamespace(is_authenticated=True)

            with patch("home.selectors.course_selector.CourseSelector.get_user_has_access", return_value=True):
                response = VideoService.get_video_response(episode=episode, user=user)

            self.assertEqual(response.status_code, 200)
            self.assertTrue((Path(tmp_dir) / "videos" / "sample.mp4").exists())
            response.close()
