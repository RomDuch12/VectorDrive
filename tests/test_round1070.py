"""Round 1070 : la portable 0.926.0 avait pris 54 Mo avec les SDK de l'assistant IA, qui font entrer scipy, pandas
et d'autres modules sans s'en servir. Ils sont exclus de la portable ; les deux SDK et l'assistant marchent sans eux."""
import ast
import pathlib
import subprocess
import sys
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DROPPED = ('scipy', 'pandas', 'pytz', 'tzdata', 'dateutil', 'zstandard', 'websockets', 'click', 'markupsafe')
BEFORE = 'avant : ces modules entrent dans la portable'


def excludes() -> list:
    """La liste `excludes=` de VectorDrive.spec."""
    tree = ast.parse((ROOT / 'VectorDrive.spec').read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == 'excludes':
            return list(ast.literal_eval(node.value))
    return []


class Portable(unittest.TestCase):

    def test_excluded(self):
        ex = excludes()
        self.assertTrue(set(DROPPED) <= set(ex), BEFORE)
        for keep in ('anthropic', 'openai', 'httpx', 'pydantic', 'numpy', 'certifi'):   # jamais ce qu'il faut
            self.assertNotIn(keep, ex)

    def test_sdks_work_without_them(self):
        """Dans un processus où ces modules sont introuvables : les deux SDK s'importent, leurs clients se font,
        l'assistant (agent.chat, avec un fournisseur de chaque sorte) aussi — sans réseau."""
        self.assertTrue(set(DROPPED) <= set(excludes()), BEFORE)
        code = textwrap.dedent(f'''
            import importlib.abc, sys
            DROPPED = {DROPPED!r}
            class Block(importlib.abc.MetaPathFinder):
                def find_spec(self, name, path=None, target=None):
                    if name.split('.')[0] in DROPPED:
                        raise ModuleNotFoundError(name)
                    return None
            sys.meta_path.insert(0, Block())
            sys.path.insert(0, {str(ROOT)!r})
            import anthropic, openai
            anthropic.Anthropic(api_key='essai')
            openai.OpenAI(api_key='essai')
            from vectordrive.agent.chat import Conversation
            class T:
                def specs(self):
                    return [{{'name': 'a', 'description': 'd', 'inputSchema': {{'type': 'object', 'properties': {{}},
                             'required': []}}}}]
                def call(self, n, a):
                    return []
            for p in ('anthropic', 'openai', 'mistral'):
                Conversation(p, '', 'essai', T())
            bad = sorted(m for m in sys.modules if m.split('.')[0] in DROPPED)
            print('chargés :', bad)
            sys.exit(1 if bad else 0)
        ''')
        r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-1500:])


if __name__ == '__main__':
    unittest.main()
