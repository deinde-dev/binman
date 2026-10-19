# SPDX-License-Identifier: GPL-2.0+
# Copyright 2026 Simon Glass <sjg@chromium.org>
#
"""Tests for fmd_util, which reads coreboot's flash-map descriptors"""

import unittest

from binman import fmap_util
from binman import fmd_util


def _layout(region, base=0):
    """Get the layout of a region and those below it

    Args:
        region (fmd_util.Region): Region to describe
        base (int): Offset of the region's parent from the start of the flash

    Returns:
        list of tuple: (name, absolute offset, size) for each region below
    """
    out = []
    for child in region.children:
        out.append((child.name, base + child.offset, child.size))
        out += _layout(child, base + child.offset)
    return out


class TestFmd(unittest.TestCase):
    """Tests for reading flash-map descriptors"""
    def test_simple(self):
        """Test a simple descriptor, as used for x86 boards"""
        root, cbfs = fmd_util.read_fmd('''
# A comment
FLASH@0xffc00000 0x400000 {
    BIOS@0 4M {
        FMAP@0 0x200   # FMAP comes first
        COREBOOT(CBFS)
    }
}
''')
        self.assertEqual('FLASH', root.name)
        self.assertEqual(0xffc00000, root.offset)
        self.assertEqual([('BIOS', 0, 0x400000), ('FMAP', 0, 0x200),
                          ('COREBOOT', 0x200, 0x3ffe00)], _layout(root))
        self.assertEqual(['COREBOOT'], [region.name for region in cbfs])
        self.assertIsNone(root.find('MISSING'))

    def test_numbers(self):
        """Test the forms of number, with and without multipliers"""
        root, _ = fmd_util.read_fmd(
            'FLASH 1G { FMAP 0x10 COREBOOT(CBFS) 0x1K A 2M B 0x10 }')
        self.assertEqual(1 << 30, root.size)
        self.assertEqual([('FMAP', 0, 0x10), ('COREBOOT', 0x10, 0x400),
                          ('A', 0x410, 2 << 20), ('B', 0x200410, 0x10)],
                         _layout(root))
        with self.assertRaises(fmd_util.FmdError) as exc:
            fmd_util.read_fmd('FLASH 010 { }')
        self.assertIn("Octal numbers are not supported: '010'",
                      str(exc.exception))

    def test_flags(self):
        """Test the CBFS and PRESERVE flags"""
        root, cbfs = fmd_util.read_fmd('''
FLASH 0x10000 {
    RW(CBFS PRESERVE) 0x1000
    VPD(PRESERVE) 0x1000
    FMAP 0x100
    COREBOOT(CBFS)
}
''')
        self.assertEqual({'CBFS', 'PRESERVE'}, root.find('RW').flags)
        self.assertEqual(['COREBOOT', 'RW'], [region.name for region in cbfs])
        fmap = fmd_util.encode_fmap(root)
        _, areas = fmap_util.DecodeFmap(fmap)
        self.assertEqual([fmap_util.FMAP_AREA_PRESERVE,
                          fmap_util.FMAP_AREA_PRESERVE, 0, 0],
                         [area.flags for area in areas])

    def test_layout(self):
        """Test working out offsets and sizes in both directions"""
        root, _ = fmd_util.read_fmd('''
FLASH 0x10000 {
    A 0x1000
    B
    C@0x8000 0x1000
    D
    E 0x100
    F 0x100
    FMAP@0xf000
    COREBOOT(CBFS) 0x800
}
''')
        self.assertEqual([('A', 0, 0x1000), ('B', 0x1000, 0x7000),
                          ('C', 0x8000, 0x1000), ('D', 0x9000, 0x5e00),
                          ('E', 0xee00, 0x100), ('F', 0xef00, 0x100),
                          ('FMAP', 0xf000, 0x800),
                          ('COREBOOT', 0xf800, 0x800)], _layout(root))

    def test_nested(self):
        """Test nested regions, as used by vboot"""
        root, cbfs = fmd_util.read_fmd('''
FLASH@0xff800000 0x800000 {
    SI_BIOS 0x800000 {
        RW_SECTION_A 0x3c0000 {
            VBLOCK_A 0x10000
            FW_MAIN_A(CBFS)
            RW_FWID_A 0x40
        }
        RW_VPD(PRESERVE) 0x1000
        WP_RO {
            FMAP 0x800
            COREBOOT(CBFS)
        }
    }
}
''')
        self.assertEqual(['COREBOOT', 'FW_MAIN_A'],
                         [region.name for region in cbfs])
        layout = dict((name, (offset, size))
                      for name, offset, size in _layout(root))
        self.assertEqual((0x10000, 0x3c0000 - 0x10040), layout['FW_MAIN_A'])
        self.assertEqual((0x3c1000, 0x43f000), layout['WP_RO'])
        self.assertEqual((0x3c1800, 0x43e800), layout['COREBOOT'])

    def test_encode(self):
        """Test the FMAP which is produced, matching coreboot's fmaptool"""
        root, _ = fmd_util.read_fmd(
            'FLASH@0xffc00000 0x400000 { BIOS 0x400000 { FMAP 0x200 '
            'COREBOOT(CBFS) } }')
        areas = [fmap_util.FmapArea(0, 0x400000, b'BIOS', 0),
                 fmap_util.FmapArea(0, 0x200, b'FMAP', 0),
                 fmap_util.FmapArea(0x200, 0x3ffe00, b'COREBOOT', 0)]
        expect = fmap_util.EncodeFmap(0x400000, b'FLASH', areas,
                                      base=0xffc00000, ver_minor=1)
        self.assertEqual(expect, fmd_util.encode_fmap(root))
        hdr, _ = fmap_util.DecodeFmap(expect)
        self.assertEqual((1, 1, 0xffc00000), (hdr.ver_major, hdr.ver_minor,
                                              hdr.base))

        # Without an offset the base is zero
        root, _ = fmd_util.read_fmd('FLASH 0x1000 { FMAP 0x100 '
                                    'COREBOOT(CBFS) }')
        hdr, _ = fmap_util.DecodeFmap(fmd_util.encode_fmap(root))
        self.assertEqual(0, hdr.base)

    def test_errors(self):
        """Test reporting problems with a descriptor"""
        ok = 'FMAP 0x100 COREBOOT(CBFS) 0x100'
        cases = [
            ('FLASH 0x1000 { A 0x100 A 0x100 }',
             "Multiple sections with name 'A'"),
            ('FLASH 0x1000 { A 0x200 B@0x100 0x100 }',
             "Section 'A' too big"),
            ('FLASH 0x1000 { A@0x2000 }', "Section 'A' starts too high"),
            ('FLASH 0x1000 { A 0 }', "Section 'A' given no space"),
            ('FLASH 0x1000 { A 0x2000 }', "Section 'A' too big"),
            ('FLASH 0x1000 { A B }',
             "Cannot determine either offset or size of section 'B'"),
            ('FLASH 0x1000 { A B 0x2000 }', "Section 'B' too big"),
            ('FLASH 0x1000 { A@0x800 B C@0x400 0x100 }',
             "Cannot determine either offset or size of section 'B'"),
            ('FLASH 0x1000 { A@0x800 B@0x900 0x100 C@0x400 0x100 }',
             "Section 'B' starts too high"),
            ('FLASH 0x1000 { FMAP 0x100 COREBOOT(CBFS) A@0x300 0x100 B '
             'C@0x200 0x10 }', "Section 'B' starts too high"),
            ('FLASH 0x1000 { R@0x800 S 0x100 X@0x850 0x10 }',
             "Section 'R' starts too high"),
            ('FLASH 0x1000 { A 0x100 B@0x2000 }',
             "Section 'B' starts too high"),
            ('FLASH 0x1000 { A@0x900 B@0x800 0x100 }',
             "Section 'A' starts too high"),
            ('FLASH 0x1000 { A(CBFS) { B 0x100 } }',
             "Section 'A' cannot have flag 'CBFS'"),
            ('FLASH 0x1000 { COREBOOT(CBFS) 0x100 }',
             "Flashmap descriptor must have an 'FMAP' section"),
            ('FLASH 0x1000 { FMAP 0x100 }',
             "Flashmap descriptor must have a 'COREBOOT' section"),
            ('FLASH 0x1000 { FMAP 0x100 RW(CBFS) 0x100 }',
             "Flashmap descriptor must have a 'COREBOOT' section"),
            ('FLASH { ' + ok + ' }', 'Syntax error: expected int, found'),
            ('FLASH 0x1000 { A(FRED) }',
             "Syntax error: expected flag, found 'FRED'"),
            ('FLASH 0x1000 { ' + ok + ' } extra',
             "Syntax error: unexpected 'extra'"),
            ('FLASH 0x1000 { ' + ok,
             'Syntax error: expected str, found end of file'),
        ]
        for text, expect in cases:
            with self.subTest(text=text):
                with self.assertRaises(fmd_util.FmdError) as exc:
                    fmd_util.read_fmd(text)
                self.assertIn(expect, str(exc.exception))

    def test_long_names(self):
        """Test names which are too long for the FMAP"""
        name = 'A' * fmap_util.FMAP_STRLEN
        root, _ = fmd_util.read_fmd(
            f'{name} 0x1000 {{ FMAP 0x100 COREBOOT(CBFS) }}')
        with self.assertRaises(fmd_util.FmdError) as exc:
            fmd_util.encode_fmap(root)
        self.assertIn(f"Image name ('{name}') exceeds 31 character FMAP "
                      'header limit', str(exc.exception))

        root, _ = fmd_util.read_fmd(
            f'FLASH 0x1000 {{ FMAP 0x100 COREBOOT(CBFS) 0x100 {name} }}')
        with self.assertRaises(fmd_util.FmdError) as exc:
            fmd_util.encode_fmap(root)
        self.assertIn(f"Section name ('{name}') exceeds 31 character FMAP "
                      'format limit', str(exc.exception))


if __name__ == '__main__':
    unittest.main()
