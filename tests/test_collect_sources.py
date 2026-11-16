import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'collect_sources', ROOT / 'database' / 'src' / 'collect_sources.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class CollectSourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.source = Path(self.tmp.name) / 'sample.md'
        self.source.write_text('first version\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, url=None, extra_source=None):
        data = {
            'version': 1,
            'sources': [
                {'id': 'local', 'enabled': True, 'kind': 'metadata',
                 'download_images': False,
                 'consumer_skill': 'novel2anima-test',
                 'target_fields': 'test_fixture',
                 'used_in_step': 'unit test',
                 'files': {'sample': {'url': url or self.source.as_uri(),
                                      'dest': 'local/sample.md',
                                      'source_revision': 'fixture-v1'}}},
                {'id': 'disabled', 'enabled': False, 'download_images': False,
                 'files': {'ignored': {'url': self.source.as_uri(),
                                       'dest': 'disabled/ignored.md'}}},
            ]
        }
        if extra_source:
            data['sources'].append(extra_source)
        return data

    def test_fetch_skip_history_and_verify(self):
        manifest = self.manifest()
        imports = self.root / 'database' / 'imports'
        first = collector.fetch_one(imports, 'local', 'sample',
                                    manifest['sources'][0]['files']['sample'])
        self.assertEqual(first['status'], 'FETCHED')
        dest = imports / 'local' / 'sample.md'
        self.assertTrue(dest.exists())
        meta = json.loads((imports / 'local' / 'sample.md.meta.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['sha256'], first['sha256'])
        second = collector.fetch_one(imports, 'local', 'sample',
                                     manifest['sources'][0]['files']['sample'])
        self.assertEqual(second['status'], 'SKIPPED')
        self.source.write_text('second version\n', encoding='utf-8')
        third = collector.fetch_one(imports, 'local', 'sample',
                                    manifest['sources'][0]['files']['sample'])
        self.assertEqual(third['status'], 'FETCHED')
        self.assertEqual(dest.read_text(encoding='utf-8'), 'second version\n')
        history = list((imports / 'local' / '.history').glob('*-sample.md'))
        self.assertEqual(len(history), 1)
        with contextlib.redirect_stdout(io.StringIO()):
            code = collector.command_verify(manifest, self.root)
        self.assertEqual(code, 0)

    def test_disabled_sources_are_not_listed(self):
        manifest = self.manifest()
        rows = list(collector.iter_files(manifest))
        self.assertEqual([r[0] for r in rows], ['local'])

    def test_enabled_source_requires_consumer_contract(self):
        manifest = self.manifest()
        del manifest['sources'][0]['consumer_skill']
        with self.assertRaisesRegex(ValueError, 'consumer_skill'):
            list(collector.iter_files(manifest))

    def test_disabled_file_is_skipped(self):
        manifest = self.manifest()
        manifest['sources'][0]['files']['sample']['enabled'] = False
        self.assertEqual(list(collector.iter_files(manifest)), [])

    def test_rejects_images_and_path_traversal(self):
        with self.assertRaises(ValueError):
            collector.safe_dest(Path('/tmp/imports'), '../outside.md')
        with self.assertRaises(ValueError):
            collector.safe_dest(Path('/tmp/imports'), 'img/picture.png')
        manifest = self.manifest(extra_source={
            'id': 'bad', 'enabled': True, 'download_images': True,
            'files': {'x': {'url': self.source.as_uri(), 'dest': 'bad/x.md'}}})
        with self.assertRaises(ValueError):
            list(collector.iter_files(manifest))

    def test_command_fetch_writes_run_log(self):
        manifest = self.manifest()
        with contextlib.redirect_stdout(io.StringIO()):
            code = collector.command_fetch(manifest, self.root, None, None,
                                           False, 10, 0, False)
            self.assertEqual(code, 0)
        log = self.root / 'database' / 'imports' / 'collection_runs.jsonl'
        self.assertTrue(log.exists())
        lines = log.read_text(encoding='utf-8').strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])['status'], 'FETCHED')


if __name__ == '__main__':
    unittest.main()
