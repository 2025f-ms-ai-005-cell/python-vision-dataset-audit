import tempfile
import unittest
from pathlib import Path
from PIL import Image
from audit import inventory, export


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'dataset'
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def image(self, path='train/a.png', size=(100, 100)):
        path = self.root/path
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', size, 'red').save(path)
        return path

    def test_valid(self):
        self.image()
        self.assertEqual(inventory(self.root)['summary']['flagged'], 0)

    def test_overlap(self):
        a = self.image()
        b = self.root/'test/copy.png'
        b.parent.mkdir()
        b.write_bytes(a.read_bytes())
        report = inventory(self.root)
        self.assertEqual(report['summary']['cross_split_groups'], 1)
        self.assertIn('cross_split_overlap', report['images'][0]['flags'])

    def test_same_split_duplicates(self):
        self.image('train/a.png')
        self.image('train/b.png')
        self.assertEqual(inventory(self.root)['summary']['duplicate_groups'], 1)
        self.assertEqual(inventory(self.root)['summary']['cross_split_groups'], 0)

    def test_small(self):
        self.image(size=(20, 100))
        self.assertIn('small_image', inventory(self.root)['images'][0]['flags'])

    def test_corrupt(self):
        (self.root/'broken.png').write_bytes(b'not an image')
        self.assertEqual(inventory(self.root)['summary']['unreadable'], 1)

    def test_limit(self):
        self.image()
        self.assertEqual(inventory(self.root, max_pixels=50)['summary']['unreadable'], 1)

    def test_export_and_no_overwrite(self):
        self.image('train/a&b.png')
        out = Path(self.temp.name)/'report'
        export(inventory(self.root), out)
        self.assertIn('a&amp;b.png', (out/'index.html').read_text())
        self.assertTrue((out/'report.json').exists())
        self.assertTrue((out/'inventory.csv').exists())
        with self.assertRaises(FileExistsError):
            export(inventory(self.root), out)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            inventory(self.root/'missing')
        with self.assertRaises(ValueError):
            inventory(self.root, min_size=0)

    def test_empty(self):
        self.assertEqual(inventory(self.root)['summary']['images'], 0)


if __name__ == '__main__':
    unittest.main()
