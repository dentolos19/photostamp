import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import piexif
from PIL import Image, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine import get_items
from main import process
from media import get_image_date, write_image_date, write_video_date


class MediaTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        self.temporary_directory = tempfile.TemporaryDirectory(dir=ROOT / ".tmp")
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.date = datetime(2021, 2, 3, 4, 5, 6).astimezone()

    def test_reads_original_date_from_exif_subdirectory(self):
        path = self.directory / "photo.jpg"
        exif = piexif.dump(
            {"Exif": {piexif.ExifIFD.DateTimeOriginal: b"2021:02:03 04:05:06"}}
        )
        Image.new("RGB", (2, 2), "red").save(path, exif=exif)
        self.assertEqual(get_image_date(path), self.date)

    def test_image_write_preserves_source_on_save_failure(self):
        path = self.directory / "photo.tiff"
        Image.new("RGB", (2, 2), "red").save(path)
        original = path.read_bytes()
        with (
            patch.object(Image.Image, "save", side_effect=OSError("disk full")),
            self.assertRaisesRegex(OSError, "disk full"),
        ):
            write_image_date(path, self.date)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(self.directory.iterdir()), [path])

    def test_stamps_common_formats_and_preserves_permissions(self):
        for extension in (".jpg", ".png", ".tiff", ".webp"):
            with self.subTest(extension=extension):
                path = self.directory / f"photo{extension}"
                Image.new("RGB", (2, 2), "red").save(path)
                path.chmod(0o640)
                with Image.open(path) as image:
                    pixels = image.tobytes()
                write_image_date(path, self.date)
                self.assertEqual(get_image_date(path), self.date)
                self.assertEqual(path.stat().st_mode & 0o777, 0o640)
                with Image.open(path) as image:
                    self.assertEqual(image.tobytes(), pixels)

    def test_png_text_and_resolution_are_preserved(self):
        path = self.directory / "photo.png"
        info = PngImagePlugin.PngInfo()
        info.add_text("Description", "original description")
        info.add(b"vpAg", b"private metadata", after_idat=True)
        Image.new("RGB", (2, 2), "red").save(path, pnginfo=info, dpi=(96, 96))

        def chunks(data):
            position = 8
            found = []
            while position < len(data):
                length = int.from_bytes(data[position : position + 4], "big")
                chunk = data[position : position + length + 12]
                if chunk[4:8] != b"eXIf":
                    found.append(chunk)
                position += length + 12
            return found

        original_chunks = chunks(path.read_bytes())
        write_image_date(path, self.date)
        self.assertEqual(chunks(path.read_bytes()), original_chunks)
        with Image.open(path) as image:
            self.assertEqual(image.info["Description"], "original description")
            self.assertAlmostEqual(image.info["dpi"][0], 96, places=1)

    def test_multi_frame_images_are_not_overwritten(self):
        path = self.directory / "IMG-20210531-WA0000.tiff"
        image = Image.new("RGB", (2, 2), "red")
        image.save(
            path,
            save_all=True,
            append_images=[Image.new("RGB", (2, 2), "blue")],
        )
        original = path.read_bytes()
        item = get_items([path])[0]
        self.assertFalse(item.can_write_metadata)
        self.assertFalse(item.should_write_metadata)
        with self.assertRaisesRegex(ValueError, "multi-frame"):
            write_image_date(path, self.date)
        self.assertEqual(path.read_bytes(), original)
        output = StringIO()
        with redirect_stdout(output):
            process([item], apply=True)
        self.assertIn("metadata writing is unsupported", output.getvalue())
        self.assertEqual(item.path.read_bytes(), original)

    def test_animated_png_keeps_every_frame(self):
        path = self.directory / "animation.png"
        Image.new("RGB", (2, 2), "red").save(
            path, save_all=True, append_images=[Image.new("RGB", (2, 2), "blue")]
        )
        with Image.open(path) as image:
            original = []
            for frame in range(getattr(image, "n_frames", 1)):
                image.seek(frame)
                original.append(image.tobytes())
        write_image_date(path, self.date)
        self.assertEqual(get_image_date(path), self.date)
        with Image.open(path) as image:
            self.assertEqual(getattr(image, "n_frames", 1), len(original))
            for frame, pixels in enumerate(original):
                image.seek(frame)
                self.assertEqual(image.tobytes(), pixels)

    def test_animated_webp_keeps_canvas_and_frames(self):
        path = self.directory / "animation.webp"
        first = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        second = first.copy()
        first.putpixel((1, 1), (255, 0, 0, 255))
        second.putpixel((14, 14), (0, 0, 255, 255))
        first.save(path, save_all=True, append_images=[second], duration=100, loop=2)
        header = path.read_bytes()[:30]
        with Image.open(path) as image:
            original = []
            for frame in range(getattr(image, "n_frames", 1)):
                image.seek(frame)
                original.append(image.convert("RGBA").tobytes())
        write_image_date(path, self.date)
        updated_header = path.read_bytes()[:30]
        self.assertEqual(updated_header[20], header[20] | 0x08)
        self.assertEqual(updated_header[21:30], header[21:30])
        self.assertEqual(get_image_date(path), self.date)
        with Image.open(path) as image:
            self.assertEqual(image.size, (16, 16))
            self.assertEqual(image.info["loop"], 2)
            self.assertEqual(getattr(image, "n_frames", 1), len(original))
            for frame, pixels in enumerate(original):
                image.seek(frame)
                self.assertEqual(image.convert("RGBA").tobytes(), pixels)

    def test_symlink_is_preserved(self):
        target = self.directory / "target"
        Image.new("RGB", (2, 2), "red").save(target, format="PNG")
        link = self.directory / "photo.png"
        link.symlink_to(target.name)
        write_image_date(link, self.date)
        self.assertTrue(link.is_symlink())
        self.assertEqual(get_image_date(link), self.date)

    def test_video_temporary_file_is_removed_on_failure(self):
        path = self.directory / "video.mp4"
        path.write_bytes(b"original")
        with (
            patch("media.run", side_effect=OSError("ffmpeg unavailable")),
            self.assertRaisesRegex(OSError, "ffmpeg unavailable"),
        ):
            write_video_date(path, self.date)
        self.assertEqual(path.read_bytes(), b"original")
        self.assertEqual(list(self.directory.iterdir()), [path])

    def test_processing_link_alone_keeps_original_target(self):
        target = self.directory / "photo.jpg"
        Image.new("RGB", (2, 2), "red").save(target)
        link = self.directory / "IMG-20210531-WA0000.jpg"
        link.symlink_to(target.name)
        item = get_items([link])[0]
        item.rename()
        item.write_metadata()
        self.assertTrue(item.path.is_symlink())
        self.assertEqual(item.path.resolve(), target)
        self.assertIsNotNone(get_image_date(target))

    def test_link_before_its_target_can_be_renamed_and_stamped(self):
        target = self.directory / "photo.jpg"
        Image.new("RGB", (2, 2), "red").save(target)
        link = self.directory / "IMG-20210531-WA0000.jpg"
        link.symlink_to(target.name)
        link_item, target_item = get_items([link, target])
        link_item.rename()
        link_item.write_metadata()
        target_item.rename()
        self.assertTrue(link_item.path.is_symlink())
        self.assertEqual(link_item.path.resolve(), target_item.path)
        self.assertTrue(target_item.path.is_file())
        self.assertIsNotNone(get_image_date(target_item.path))

    def test_failed_link_rename_keeps_original(self):
        target = self.directory / "photo.jpg"
        Image.new("RGB", (2, 2), "red").save(target)
        link = self.directory / "IMG-20210531-WA0000.jpg"
        link.symlink_to(target.name)
        item = get_items([link])[0]
        with (
            patch.object(Path, "symlink_to", side_effect=OSError("permission denied")),
            self.assertRaisesRegex(OSError, "permission denied"),
        ):
            item.rename()
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), target)

    def test_rename_does_not_overwrite_dangling_symlink(self):
        source = self.directory / "IMG-20210531-WA0000.jpg"
        Image.new("RGB", (2, 2), "red").save(source)
        item = get_items([source])[0]
        destination = source.with_name(item.proposed_name)
        destination.symlink_to("missing.jpg")
        with self.assertRaises(FileExistsError):
            item.rename()
        self.assertTrue(source.is_file())
        self.assertTrue(destination.is_symlink())

    def test_directory_link_cycles_are_skipped(self):
        first = self.directory / "first"
        second = self.directory / "second"
        first.mkdir()
        second.mkdir()
        (first / "next").symlink_to(second, target_is_directory=True)
        (second / "previous").symlink_to(first, target_is_directory=True)
        items = get_items([first])
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].is_cycle)
        output = StringIO()
        with redirect_stdout(output):
            process(items)
        self.assertIn("skipped cyclic directory link", output.getvalue())


if __name__ == "__main__":
    unittest.main()
