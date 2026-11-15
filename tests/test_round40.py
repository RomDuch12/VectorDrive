"""Round 40 : une police absente est signalée (round 924 : les essais des polices de TypeEdit abîmées sont passés
dans le plugin de l'atelier, avec leur lecteur)."""
import unittest


class TestMissingFont(unittest.TestCase):
    def test_check_flags_substitute_font(self):
        from vectordrive.core import check as CK
        from vectordrive.core import fonts
        from vectordrive.core import text as TX
        from vectordrive.core.document import Document, Text
        self.assertFalse(fonts.is_available('Police Qui Nexiste Pas'))
        self.assertTrue(fonts.is_available('Arial'))
        d = Document()
        t = Text(text='ABC', font='Police Qui Nexiste Pas', size=5)
        t.outline = TX.outline_for(t)                     # dessinée en Arial de remplacement
        d.add(t)
        self.assertIn('police_absente', {i.code for i in CK.check(d)})


if __name__ == '__main__':
    unittest.main()
