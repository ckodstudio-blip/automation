import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

TEMP = tempfile.TemporaryDirectory()
os.environ.update(DB_BACKEND='sqlite', DATA_DIR=TEMP.name, SECRET_KEY='unit-test-secret-at-least-32-characters')
from autoshorts import engine as e
from autoshorts import cli, storage, video


def plan():
    return {'title': 'How stars shine', 'description': 'Discover the energy inside a star.',
            'tags': ['Stars','Space facts','Science'], 'hashtags': ['#Shorts','#Space','#Science'],
            'scenes': [{'narration': 'Stars shine because their cores release energy.', 'search': 'Energy inside stars', 'visual_prompt': 'Glowing abstract orb'} for _ in range(3)]}


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        e.initialize()

    def test_metadata_validation(self):
        p = plan()
        p['tags'].append('stars')
        p['hashtags'].append('#বাংলাবিজ্ঞান')
        value = e.validate_plan(p)
        self.assertEqual(len(value['tags']), 3)
        self.assertIn('#বাংলাবিজ্ঞান', value['hashtags'])
        p['hashtags'] = ['bad hashtag']
        with self.assertRaises(ValueError):
            e.validate_plan(p)

    def test_long_script_rejected(self):
        p = plan()
        p['scenes'] = []
        with self.assertRaises(ValueError):
            e.validate_plan(p)

    def test_token_is_encrypted_and_persistent(self):
        c = MagicMock()
        c.to_json.return_value = '{"refresh_token":"private-value"}'
        e.token_write(c)
        self.assertNotIn('private-value', e.setting('youtube_token'))
        e.initialize()
        self.assertIn('private-value', e.cipher().decrypt(e.setting('youtube_token').encode()).decode())

    def test_mysql_sql_binding(self):
        raw = MagicMock()
        with patch.object(storage, 'MYSQL', True):
            storage.Connection(raw).execute('SELECT * FROM jobs WHERE id=?',('safe',))
        raw.cursor.return_value.execute.assert_called_once_with('SELECT * FROM autoshorts_jobs WHERE id=%s',('safe',))

    def test_restart_marks_uncertain(self):
        with e.db() as c:
            c.execute('INSERT INTO jobs(id,slot,state,created) VALUES(?,?,?,?)',('a'*24,'interrupted','uploading','today'))
        e.initialize()
        with e.db() as c:
            self.assertEqual(c.execute('SELECT state FROM jobs WHERE id=?',('a'*24,)).fetchone()['state'], 'needs_check')

    def test_success_upload_metadata_and_delete(self):
        job = 'b'*24
        with e.db() as c:
            c.execute('INSERT INTO jobs(id,slot,state,created) VALUES(?,?,?,?)',(job,'success','queued','today'))
        yt = MagicMock()
        yt.videos.return_value.insert.return_value.next_chunk.return_value = (None,{'id':'youtube-test-id'})
        def render(p,folder):
            f=folder/'short.mp4'
            f.write_bytes(b'fixture')
            return f,[]
        e.lock.acquire()
        with patch.object(e,'config_errors',return_value=[]), patch.object(e,'youtube',return_value=yt), patch.object(e,'make_plan',side_effect=plan), patch.object(e,'render',side_effect=render), patch.object(e,'MediaFileUpload'):
            e.pipeline(job)
        self.assertFalse((e.DATA/job).exists())
        body=yt.videos.return_value.insert.call_args.kwargs['body']
        self.assertEqual(body['snippet']['tags'],plan()['tags'])
        self.assertIn('#Shorts #Space',body['snippet']['description'])
        self.assertNotIn('Pexels',body['snippet']['description'])
        with e.db() as c:
            row=c.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone()
        self.assertEqual(row['state'],'uploaded')
        self.assertEqual(row['video_id'],'youtube-test-id')
        self.assertTrue(e.setting('plan:'+job))

    def test_cli_no_duplicate_slot(self):
        env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'same-run-test'}
        def fake(job):
            e.update(job,state='uploaded',video_id='test-id')
            e.lock.release()
        with patch.dict(os.environ,env), patch.object(e,'config_errors',return_value=[]), patch.object(e,'pipeline',side_effect=fake) as p:
            self.assertEqual(cli.main(),0)
            self.assertEqual(cli.main(),0)
            self.assertEqual(p.call_count,1)

    def test_original_graphics_asset(self):
        target=Path(TEMP.name)/'card.png'
        video.background(plan()['scenes'][0],0,3,target)
        from PIL import Image
        with Image.open(target) as img:
            self.assertEqual(img.size,(800,1422))

    def test_actual_animation_render(self):
        folder=Path(TEMP.name)/('c'*24)
        folder.mkdir(exist_ok=True)
        real=e.run
        def voice(args,timeout=600):
            if args[0]=='test-voice':
                return real(['ffmpeg','-y','-v','error','-f','lavfi','-i','sine=frequency=440:duration=1',args[-1]])
            return real(args,timeout)
        with patch.object(video.shutil,'which',return_value='test-voice'),patch.object(e,'run',side_effect=voice):
            final=video.render_video(plan(),folder)
        self.assertTrue(final.exists())
        self.assertGreater(e.duration(final),3)
        self.assertLess(e.duration(final),5)
        probe=json.loads(real(['ffprobe','-v','error','-show_streams','-of','json',str(final)]))
        v=next(s for s in probe['streams'] if s['codec_type']=='video')
        self.assertEqual((v['width'],v['height']),(720,1280))
        self.assertTrue(any(s['codec_type']=='audio' for s in probe['streams']))


if __name__=='__main__':
    unittest.main()
