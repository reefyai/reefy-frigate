"""Exercise the installed watchdog reset implementation without GPU imports."""
import ast
from collections import deque
from datetime import datetime
import logging
from pathlib import Path
import subprocess as sp
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, call


def reset_method(source):
    tree = ast.parse(Path(source).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CameraWatchdog')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'reset_capture_thread')
    module = ast.Module(body=[method], type_ignores=[])
    namespace = {'sp': sp, 'datetime': datetime}
    exec(compile(ast.fix_missing_locations(module), str(source), 'exec'), namespace)
    return namespace['reset_capture_thread']


def watchdog(process):
    return SimpleNamespace(ffmpeg_detect_process=process, logger=logging.getLogger('synthetic-watchdog'),
        reconnect_timestamps=deque(), reconnects=SimpleNamespace(value=0), capture_thread=None,
        config=SimpleNamespace(name='synthetic-camera'), logpipe=SimpleNamespace(dump=lambda:None),
        start_ffmpeg_detect=MagicMock())


class ResetRegression(unittest.TestCase):
    def setUp(self):
        self.reset = reset_method('/opt/frigate/frigate/video/ffmpeg.py')
        self.process = MagicMock()
        self.watchdog = watchdog(self.process)

    def test_reset_does_not_buffer_raw_frames(self):
        self.reset(self.watchdog)
        self.process.terminate.assert_called_once()
        self.process.wait.assert_called_once_with(timeout=30)
        self.process.communicate.assert_not_called()
        self.watchdog.start_ffmpeg_detect.assert_called_once()
        self.assertEqual(self.watchdog.reconnects.value, 1)

    def test_timeout_kills_and_reaps_without_buffering(self):
        self.process.wait.side_effect = [sp.TimeoutExpired('synthetic-child',30),0]
        self.reset(self.watchdog)
        self.process.kill.assert_called_once()
        self.assertEqual(self.process.wait.call_args_list,[call(timeout=30),call()])
        self.process.communicate.assert_not_called()
        self.watchdog.start_ffmpeg_detect.assert_called_once()

    def test_already_exited_child_is_restarted_without_termination(self):
        self.reset(self.watchdog, terminate=False)
        self.process.terminate.assert_not_called()
        self.process.wait.assert_not_called()
        self.process.communicate.assert_not_called()
        self.watchdog.start_ffmpeg_detect.assert_called_once()

    def test_capture_thread_is_joined_before_restart(self):
        self.watchdog.capture_thread=MagicMock()
        self.watchdog.capture_thread.is_alive.side_effect=[True,False]
        self.reset(self.watchdog)
        self.watchdog.capture_thread.join.assert_called_once_with(timeout=5)
        self.watchdog.start_ffmpeg_detect.assert_called_once()


if __name__ == '__main__':
    unittest.main()
