"""Actual installed capture loop and ZeroMQ publisher across process boundaries.

A stopped synthetic decoder ends each capture generation. The publisher stays
idle while real subscribers connect/close, as with repeatedly offline cameras.
Only synthetic frames and IPC sockets inside the disposable lab are used.
"""
import ast
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

sys.path.insert(0, '/opt/frigate')

ITERATIONS = 1200
WARMUP = 120
MAX_GROWTH_KIB = 4 * 1024


def publisher():
    from frigate.comms.config_updater import ConfigPublisher
    Path('/tmp/cache').mkdir(parents=True, exist_ok=True)
    instance = ConfigPublisher()
    print('READY', flush=True)
    try:
        for line in sys.stdin:
            if line.strip() == 'publish':
                instance.publish('config/cameras/synthetic_reconnect/enabled', True)
                print('PUBLISHED', flush=True)
            else:
                break
    finally:
        instance.stop()


def capture_method():
    # Execute the installed function unchanged, avoiding unrelated detector
    # auto-imports. Its actual subscriber classes and native libzmq are retained.
    from frigate.config.camera.updater import (
        CameraConfigUpdateEnum, CameraConfigUpdateSubscriber,
    )
    source = Path('/opt/frigate/frigate/video/ffmpeg.py').read_text()
    node = next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name == 'capture_frames')
    module = ast.Module(body=[ast.ImportFrom(module='__future__',
                        names=[ast.alias(name='annotations')], level=0), node],
                        type_ignores=[])

    class Rate:
        def start(self): pass
        def update(self): pass
        def eps(self): return 0

    logger = logging.getLogger('synthetic_capture')
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    scope = dict(CameraConfigUpdateEnum=CameraConfigUpdateEnum,
                 CameraConfigUpdateSubscriber=CameraConfigUpdateSubscriber,
                 EventsPerSecond=Rate, datetime=datetime, queue=queue, logger=logger)
    exec(compile(ast.fix_missing_locations(module), 'installed_capture_frames', 'exec'), scope)
    return scope['capture_frames']


class Frames:
    def __init__(self):
        self.writes = 0
        self.closed = 0

    def write(self, name):
        self.writes += 1
        return memoryview(bytearray(12))

    def close(self, name):
        self.closed += 1


def invoke(method, enabled=True, callback=None, stopped=False):
    config = SimpleNamespace(name='synthetic_reconnect', enabled=enabled)
    stop = threading.Event()
    if stopped:
        stop.set()

    class Output:
        def read(self, size):
            if callback:
                return callback(config, stop)
            # Allow the native IPC handshake to complete before disconnecting.
            time.sleep(0.025)
            return b''

    frames = Frames()
    output = queue.Queue()
    decoder = SimpleNamespace(stdout=Output(), poll=lambda: 1)
    method(decoder, config, 2, 0, (3, 4), frames, output,
           SimpleNamespace(value=0), SimpleNamespace(value=0),
           SimpleNamespace(value=0), stop)
    return frames, output


def functional_contracts(method):
    frames, output = invoke(method, enabled=False)
    assert frames.writes == 0 and output.empty(), 'Disabled capture must not read frames'
    frames, output = invoke(method, stopped=True)
    assert frames.writes == 0 and output.empty(), 'Stopped capture must not read frames'

    def disable(config, stop):
        # Simulate the existing watchdog updating its shared CameraConfig.
        config.enabled = False
        return b'x' * 12

    frames, output = invoke(method, callback=disable)
    assert frames.writes == 1 and frames.closed == 1 and output.qsize() == 1, \
        'Shared enabled updates must stop capture after the current frame'
    return {'disabled_without_read': True, 'stop_without_read': True,
            'shared_enabled_update': True, 'synthetic_frame_preserved': True}


def rss_anon_kib(pid):
    for line in Path(f'/proc/{pid}/status').read_text().splitlines():
        if line.startswith('RssAnon:'):
            return int(line.split()[1])
    raise AssertionError('Publisher anonymous memory could not be measured')


def run(arm):
    child = subprocess.Popen([sys.executable, '-u', __file__, 'publisher'],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'READY', 'Publisher did not initialize'
        method = capture_method()
        contracts = functional_contracts(method)
        for _ in range(WARMUP):
            invoke(method)
        before = rss_anon_kib(child.pid)
        samples = [before]
        started = time.monotonic()
        for i in range(ITERATIONS):
            invoke(method)
            if arm == 'publish' and i % 25 == 24:
                child.stdin.write('publish\n'); child.stdin.flush()
                assert child.stdout.readline().strip() == 'PUBLISHED'
            if i % 100 == 99:
                assert child.poll() is None, 'Publisher unexpectedly exited'
                samples.append(rss_anon_kib(child.pid))
        growth = max(samples) - before
        evidence = {'arm': arm, 'iterations': ITERATIONS, 'warmup': WARMUP,
                    'publisher_before_anon_kib': before, 'publisher_anon_samples_kib': samples,
                    'publisher_growth_kib': growth, 'max_growth_kib': MAX_GROWTH_KIB,
                    'elapsed_seconds': round(time.monotonic() - started, 2),
                    'contracts': contracts}
        print(json.dumps(evidence), flush=True)
        assert growth < MAX_GROWTH_KIB, 'Reconnect publisher grew beyond the bounded memory contract'
    finally:
        if child.poll() is None:
            child.stdin.write('stop\n'); child.stdin.flush()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=5)
                raise AssertionError('Publisher cleanup failed')
        child.stdin.close(); child.stdout.close()
        if sys.exc_info()[0] is None:
            assert child.returncode == 0, 'Publisher exited abnormally'


if __name__ == '__main__':
    if sys.argv[1] == 'publisher': publisher()
    else: run(sys.argv[1])
