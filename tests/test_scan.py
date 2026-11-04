import tempfile
import unittest
from pathlib import Path
from axon_codemap.cli import scan

FIXTURE = Path(__file__).parent / 'fixtures'
class ScanTest(unittest.TestCase):
    def test_realistic_axon_flow(self):
        result = scan(FIXTURE)
        self.assertEqual(len(result['commands']), 3)
        self.assertEqual(len(result['consumers']), 2)
        c = next(c for c in result['commands'] if c['type'] == 'demo.CreateOrder')
        self.assertEqual(c['events'][0]['type'], 'demo.OrderCreated')
        self.assertEqual(c['events'][0]['line'], 7)
        self.assertEqual([h['owner'] for h in result['consumers'] if h['type'] == c['events'][0]['type']], ['OrderProjection'])
        self.assertTrue(any('not a direct constructor' in w for w in result['warnings']))
    def test_tests_excluded_and_imports_distinguish_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for p, content in {'a/A.java':'package a; class Same {}', 'b/B.java':'package b; class Same {}', 'x/C.java':'package x; import a.Same; class C { @CommandHandler void c(Do cmd) { apply(new Same()); } }', 'x/P.java':'package x; import b.Same; class P { @EventHandler void on(Same e) {} }', 'src/test/T.java':'class T { @CommandHandler void c(Test c) {} }'}.items():
                path=root/p; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content)
            data=scan(root)
            self.assertEqual(len(data['commands']),1)
            self.assertEqual(data['commands'][0]['events'][0]['type'],'a.Same')
            self.assertEqual(data['consumers'][0]['type'],'b.Same')
            self.assertEqual(len(scan(root,True)['commands']),2)
if __name__ == '__main__': unittest.main()
