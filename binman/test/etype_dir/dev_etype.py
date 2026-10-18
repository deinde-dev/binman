# SPDX-License-Identifier: GPL-2.0+
#
# Entry type loaded from an extra directory, for testing --etype-dir
#

from binman.entry import Entry

class Entry_dev_etype(Entry):
    """An entry type being developed outside binman"""
    def ObtainContents(self, fake_size=0):
        self.SetContents(b'dev-etype')
        return True
