import tempfile
import unittest
from pathlib import Path
from axon_codemap.cli import scan

class PackageTests(unittest.TestCase):
    def test_imports_inventory_cycles_and_external_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sources={
                'src/a/Alpha.java': 'package a; import b.Beta; import static c.Util.helper; import java.util.List; class Alpha { Alpha() {} public void work() {} private void internal() {} }',
                'src/b/Beta.java': 'package b; import a.*; class Beta { void run() {} }',
                'src/c/Util.java': 'package c; public class Util { static void helper() {} }',
                'src/d/Other.java': 'package d; import c.*; class Other {}',
                'src/test/Hidden.java': 'package ignored; class Hidden {}',
            }
            for path,content in sources.items():
                target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)
            result=scan(root); pkgs={p['name']:p for p in result['packages']}
            self.assertEqual(set(pkgs),{'a','b','c','d'})
            self.assertEqual(pkgs['a']['uses'],['b','c'])
            self.assertEqual(pkgs['b']['uses'],['a'])
            self.assertEqual(pkgs['d']['uses'],['c'])
            self.assertEqual(pkgs['c']['uses'],[])
            self.assertEqual([m['name'] for m in pkgs['a']['files'][0]['methods']],['Alpha.Alpha()','Alpha.work()','Alpha.internal()'])
            self.assertEqual([m['public'] for m in pkgs['a']['files'][0]['methods']], [False,True,False])
            self.assertEqual(result['commands'],[])
if __name__=='__main__':unittest.main()
