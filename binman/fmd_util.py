# SPDX-License-Identifier: GPL-2.0+
# Copyright 2026 Simon Glass <sjg@chromium.org>
#
"""Support for coreboot's flash-map descriptor (fmd) files

An fmd file describes the layout of a flash image as a tree of regions, each
with a name, optional flags, an optional offset within its parent and an
optional size, e.g.:

    FLASH@0xffc00000 0x400000 {
        BIOS 0x400000 {
            FMAP 0x200
            COREBOOT(CBFS)
        }
    }

This module reads an fmd file, works out the offset and size of each region
in the same way as coreboot's fmaptool and produces the same FMAP, so that
binman can lay out a coreboot image from it.
"""

import re

from binman import fmap_util

# Region which holds the FMAP, and the primary CBFS, both of which coreboot
# requires
FMAP_REGION = 'FMAP'
PRIMARY_CBFS = 'COREBOOT'

# Size multipliers which may follow a number
MULTIPLIERS = {'K': 1 << 10, 'M': 1 << 20, 'G': 1 << 30}

# Characters which separate the words of an fmd file
SPECIAL = '#@{}()'


class FmdError(ValueError):
    """An fmd file is not valid"""


class Region:
    """A region of the flash, as described by an fmd file

    Attributes:
        name (str): Name of the region
        flags (set of str): Flags, i.e. 'CBFS' and 'PRESERVE'
        offset (int): Offset from the start of the parent region, or None if
            not known yet
        size (int): Size of the region, or None if not known yet
        children (list of Region): Regions within this one
    """
    def __init__(self, name, flags, offset, size, children):
        self.name = name
        self.flags = flags
        self.offset = offset
        self.size = size
        self.children = children

    def find(self, name):
        """Find a region by name, within this one or below

        Args:
            name (str): Name to look for

        Returns:
            Region: Region found, or None
        """
        if self.name == name:
            return self
        for child in self.children:
            found = child.find(name)
            if found:
                return found
        return None


def _tokenise(text):
    """Split an fmd file into tokens

    Args:
        text (str): Contents of the file

    Returns:
        list of tuple:
            str: Kind of token: 'int', 'str', 'flag' or the character itself
            value: Value of the token: an int for 'int', else a str

    Raises:
        FmdError: A number is in octal, which is not allowed
    """
    tokens = []
    in_flags = False
    pos = 0
    while pos < len(text):
        char = text[pos]
        if char.isspace():
            pos += 1
        elif char == '#':
            end = text.find('\n', pos)
            pos = len(text) if end == -1 else end
        elif char in SPECIAL:
            in_flags = char == '(' or (in_flags and char != ')')
            tokens.append((char, char))
            pos += 1
        else:
            match = re.compile(r'[^#@{}()\s]+').match(text, pos)
            word = match.group(0)
            pos = match.end()
            if in_flags and word in ('CBFS', 'PRESERVE'):
                tokens.append(('flag', word))
            elif re.fullmatch('(0|[1-9][0-9]*)[KMG]?', word):
                tokens.append(('int', _to_int(word, 10)))
            elif re.fullmatch('0[0-9]+[KMG]?', word):
                raise FmdError(f"Octal numbers are not supported: '{word}'")
            elif re.fullmatch('0[xX][0-9a-fA-F]+[KMG]?', word):
                tokens.append(('int', _to_int(word[2:], 16)))
            else:
                tokens.append(('str', word))
    return tokens


def _to_int(word, base):
    """Convert a number, with an optional multiplier, to an integer

    Args:
        word (str): Number, e.g. '4' or '4M'
        base (int): Base of the number

    Returns:
        int: Value
    """
    mult = MULTIPLIERS.get(word[-1], 1)
    if mult != 1:
        word = word[:-1]
    return int(word, base) * mult


class _Parser:
    """Parses the tokens of an fmd file into a tree of regions"""
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.cbfs = []

    def _peek(self):
        return self.tokens[self.pos][0] if self.pos < len(self.tokens) else None

    def _take(self, kind):
        if self._peek() != kind:
            found = (repr(self.tokens[self.pos][1]) if self._peek()
                     else 'end of file')
            raise FmdError(f'Syntax error: expected {kind}, found {found}')
        self.pos += 1
        return self.tokens[self.pos - 1][1]

    def _optional(self, kind):
        if self._peek() == kind:
            return self._take(kind)
        return None

    def _region_list(self):
        self._take('{')
        children = [self._region()]
        while self._peek() != '}':
            children.append(self._region())
        self._take('}')
        return children

    def _region(self):
        name = self._take('str')
        flags = set()
        if self._optional('('):
            flags.add(self._take('flag'))
            while self._peek() == 'flag':
                flags.add(self._take('flag'))
            self._take(')')
        offset = self._take('int') if self._optional('@') else None
        size = self._optional('int')
        children = self._region_list() if self._peek() == '{' else []
        region = Region(name, flags, offset, size, children)
        if 'CBFS' in flags:
            if children:
                raise FmdError(f"Section '{name}' cannot have flag 'CBFS'")
            if name == PRIMARY_CBFS:
                self.cbfs.insert(0, region)
            else:
                self.cbfs.append(region)
        return region

    def parse(self):
        """Parse the tokens

        Returns:
            tuple:
                Region: The root region, i.e. the whole flash
                list of Region: Regions with the 'CBFS' flag, the primary
                    CBFS first

        Raises:
            FmdError: The tokens do not form a valid fmd file
        """
        name = self._take('str')
        offset = self._take('int') if self._optional('@') else None
        size = self._take('int')
        children = self._region_list()
        if self._peek():
            raise FmdError(
                f'Syntax error: unexpected {self.tokens[self.pos][1]!r}')
        return Region(name, set(), offset, size, children), self.cbfs


def _check_region(region, end, names):
    """Check a region's name, offset and size, as far as they are known

    Unlike coreboot's fmaptool, this does not check whether the region starts
    before the end of the previous one: that region is checked against this
    one's offset first and is reported as too big.

    Args:
        region (Region): Region to check
        end (int): Highest offset at which it may end, or None if not known
        names (set of str): Names of the regions seen so far

    Raises:
        FmdError: The region is not valid
    """
    if region.name in names:
        raise FmdError(f"Multiple sections with name '{region.name}'")
    names.add(region.name)
    if region.offset is not None:
        if end is not None and region.offset > end:
            raise FmdError(f"Section '{region.name}' starts too high")
    if region.size is not None:
        if not region.size:
            raise FmdError(f"Section '{region.name}' given no space")
        if (region.offset is not None and end is not None and
                region.offset + region.size > end):
            raise FmdError(f"Section '{region.name}' too big")


def _complete_backward(regions, end):
    """Fill in offsets and sizes backwards from a known end

    Args:
        regions (list of Region): Regions to complete, each with either its
            offset or its size known
        end (int): Offset of the end of the last region

    Raises:
        FmdError: A region does not fit
    """
    for region in reversed(regions):
        if region.offset is None:
            if region.size > end:
                raise FmdError(f"Section '{region.name}' too big")
            end -= region.size
            region.offset = end
        elif region.size is None:
            if region.offset > end:
                raise FmdError(f"Section '{region.name}' starts too high")
            region.size = end - region.offset
            end = region.offset


def _complete(parent, names):
    """Work out the offsets and sizes of a region's children, recursively

    Regions are placed one after another. A region with no size fills the
    space up to the next one with a known offset, or to the end of its
    parent, and a region with no offset after it is placed back from there.

    Args:
        parent (Region): Region whose children to complete; its size must be
            known
        names (set of str): Names of the regions seen so far

    Raises:
        FmdError: The layout is not valid or cannot be worked out
    """
    incomplete = None
    watermark = 0
    children = parent.children
    for upto, region in enumerate(children):
        if incomplete is not None:
            if region.offset is not None:
                _complete_backward(children[incomplete:upto], region.offset)
                incomplete = None
                watermark = region.offset
        elif region.offset is None:
            region.offset = watermark

        end = parent.size
        if upto != len(children) - 1:
            end = children[upto + 1].offset
        _check_region(region, end, names)

        if region.size is None:
            if region.offset is None:
                raise FmdError('Cannot determine either offset or size of '
                               f"section '{region.name}'")
            incomplete = upto
        elif incomplete is None:
            watermark = region.offset + region.size

    if incomplete is not None:
        _complete_backward(children[incomplete:], parent.size)

    for region in children:
        _complete(region, names)


def read_fmd(text):
    """Read an fmd file and work out its layout

    Args:
        text (str): Contents of the file

    Returns:
        tuple:
            Region: The root region, i.e. the whole flash, with the offset and
                size of every region below it filled in
            list of Region: Regions with the 'CBFS' flag, the primary CBFS
                first

    Raises:
        FmdError: The file is not valid
    """
    root, cbfs = _Parser(_tokenise(text)).parse()
    _complete(root, set())
    if not root.find(FMAP_REGION):
        raise FmdError(f"Flashmap descriptor must have an '{FMAP_REGION}' "
                       'section')
    if not cbfs or cbfs[0].name != PRIMARY_CBFS:
        raise FmdError('Flashmap descriptor must have a '
                       f"'{PRIMARY_CBFS}' section that is annotated with "
                       "'(CBFS)'")
    return root, cbfs


def encode_fmap(root):
    """Produce the FMAP for a flash, as coreboot's fmaptool does

    The FMAP header holds the name, base address and size of the whole flash,
    then there is an area for each region below it, parents before their
    children, with offsets from the start of the flash

    Args:
        root (Region): The root region, as returned by read_fmd()

    Returns:
        bytes: FMAP

    Raises:
        FmdError: A name is too long for the FMAP
    """
    if len(root.name) >= fmap_util.FMAP_STRLEN:
        raise FmdError(f"Image name ('{root.name}') exceeds "
                       f'{fmap_util.FMAP_STRLEN - 1} character FMAP header '
                       'limit')
    areas = []

    def _add_areas(region, base):
        if len(region.name) >= fmap_util.FMAP_STRLEN:
            raise FmdError(f"Section name ('{region.name}') exceeds "
                           f'{fmap_util.FMAP_STRLEN - 1} character FMAP '
                           'format limit')
        base += region.offset
        flags = fmap_util.FMAP_AREA_PRESERVE if 'PRESERVE' in region.flags else 0
        areas.append(fmap_util.FmapArea(base, region.size,
                                        region.name.encode('utf-8'), flags))
        for child in region.children:
            _add_areas(child, base)

    for child in root.children:
        _add_areas(child, 0)
    return fmap_util.EncodeFmap(root.size, root.name.encode('utf-8'), areas,
                                base=root.offset or 0, ver_minor=1)
