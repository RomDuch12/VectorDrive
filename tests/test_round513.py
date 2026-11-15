"""Round 513 : serveur de vignettes de l'explorateur — plusieurs demandes à la fois, tracées sur des
processus ; aucun processus de calcul ne survit à son parent (serveur arrêté, application tuée)."""
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive import thumbshell as TS


class FakeConn:
    def __init__(self, req):
        self.req, self.sent, self.closed = req, None, False

    def recv_bytes(self, _n):
        return self.req

    def send_bytes(self, data):
        self.sent = data

    def close(self):
        self.closed = True


class TestServer(unittest.TestCase):
    def test_handle(self):
        c = FakeConn(b'VIGNETTE\t64\tabsent.dxf')
        TS.handle(c, renderer=lambda req: b'PNG' + req[:3])
        self.assertEqual((c.sent, c.closed), (b'PNGVIG', True))
        c = FakeConn(b'x')

        def broken(_req):
            raise RuntimeError('processus perdu')
        TS.handle(c, renderer=broken)                      # repli : tracé sur place (ici : refusé)
        self.assertEqual((c.sent, c.closed), (b'', True))

    @unittest.skipUnless(sys.platform == 'win32', 'processus Windows')
    def test_children_exit_with_parent(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = textwrap.dedent('''
            import os, sys
            sys.path.insert(0, %r)
            if __name__ == '__main__':
                import multiprocessing
                from concurrent.futures import ProcessPoolExecutor
                from vectordrive.core import workers
                pool = ProcessPoolExecutor(2, mp_context=multiprocessing.get_context('spawn'),
                                           initializer=workers._start_process, initargs=(False,))
                print(pool.submit(os.getpid).result(timeout=60), flush=True)
                os._exit(0)                                  # parent tué : sans arrêt du réservoir
        ''' % root)
        f = os.path.join(tempfile.mkdtemp(), 'parent.py')
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write(script)
        out = subprocess.run([sys.executable, f], capture_output=True, text=True, timeout=120,
                             env=dict(os.environ, QT_QPA_PLATFORM='offscreen'))
        child = int(out.stdout.strip().splitlines()[-1])
        alive = True
        for _ in range(50):
            r = subprocess.run(['tasklist', '/FI', f'PID eq {child}', '/NH'], capture_output=True, text=True)
            alive = str(child) in r.stdout
            if not alive:
                break
            time.sleep(0.2)
        self.assertFalse(alive, 'processus de calcul orphelin')


if __name__ == '__main__':
    unittest.main()
