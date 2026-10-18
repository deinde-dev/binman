# SPDX-License-Identifier: GPL-2.0+
#
# Entry type which takes the place of the built-in 'fill', for testing
# --etype-dir
#

from binman.entry import Entry

class Entry_fill(Entry):
    """A replacement for the fill entry type"""
    def ObtainContents(self, fake_size=0):
        self.SetContents(b'over')
        return True
