# SPDX-License-Identifier: GPL-2.0+
# Copyright 2026 Simon Glass <sjg@chromium.org>
#
# Entry-type module for a coreboot ROM image
#

from collections import namedtuple
import os

from binman import elf
from binman import fmd_util
from binman.entry import Entry, EntryArg
from binman.etype.section import Entry_section
from dtoc import fdt_util
from u_boot_pylib import tools

# A file to add to the CBFS
#
# entry (Entry): Entry providing the data
# name (str): Name of the file in CBFS
# ftype (str): Type of file, e.g. 'raw', 'stage' or 'bootblock'
# compress (str): Compression to use, or None for cbfstool's default
# load (int): Load address, for a flat binary
# entry_addr (int): Entry address, for a flat binary
# options (list of str): Further arguments for cbfstool
# region (str): Flash-map region to write the data to, instead of adding it to
#    the CBFS, or None
CbfsFile = namedtuple(
    'CbfsFile', 'entry,name,ftype,compress,load,entry_addr,options,region')

class Entry_coreboot_rom(Entry_section):
    """Coreboot ROM image, updated to contain the given payload

    Properties / Entry arguments:
        - coreboot-rom-path: Filename of the coreboot ROM to use (entry
            argument, e.g. from the COREBOOT_ROM environment variable). This
            is a complete flash image as produced by the coreboot build (with
            any Intel descriptor / ME regions already in place), typically
            built with no payload, or with a payload which will be replaced
        - coreboot-filename: Default filename to use if the entry argument is
            not given; it is looked up in the input directories (see
            BINMAN_INDIRS) and defaults to "coreboot.rom"
        - cbfs-name: Name of the payload file in CBFS, defaulting to
            "fallback/payload"
        - cbfs-load-addr: Address to which the payload is loaded. This is
            optional; when omitted it is taken from the ELF of the payload's
            first stage (SPL, or U-Boot itself when there is no SPL)
        - cbfs-entry-addr: Entry-point address. This is optional; it defaults
            to the SPL ELF's entry point, or to cbfs-load-addr when that is
            given explicitly
        - cbfs-compress: Compression to use ("lzma", "lz4" or "none"),
            defaulting to lzma
        - fmap-filename: Binary flash map (FMAP) from which to create a new
            image, instead of starting from a coreboot ROM. It is looked up in
            the input directories
        - fmd-filename: Flash-map descriptor (fmd file), as used by coreboot,
            from which to create a new image, instead of an FMAP. Binman works
            out the layout and produces the FMAP in the same way as coreboot's
            fmaptool. It is looked up in the input directories
        - cbfs-regions: Regions of the flash map which hold a CBFS, separated
            by commas. This defaults to the regions with the CBFS flag in the
            fmd file, else to "COREBOOT"

    This supports building U-Boot as a coreboot payload: the coreboot build
    provides everything up to the payload (bootblock, romstage, ramstage,
    FSP, microcode) as a ready-made flash image and this entry inserts the
    payload into its CBFS using the cbfstool bintool, replacing any existing
    file of the same name.

    The contents of this entry, built in the usual way from its subnodes,
    become the payload, added as a flat binary. For example, for a 64-bit
    build entered via SPL::

        rom {
            filename = "u-boot.rom";
            coreboot-rom {
                coreboot-filename = "coreboot.rom";
                cbfs-name = "fallback/payload";

                u-boot-spl {
                };
                u-boot {
                    offset = <0x10000>;
                };
            };
        };

    The load and entry addresses are taken from the u-boot-spl ELF, so they
    do not need to be specified here.

    Adding files
    ~~~~~~~~~~~~

    Instead of building a single payload, each subnode can be added to the
    CBFS as a file of its own, by giving it a 'cbfs-name' property. This
    works with any payload and other files, such as SeaBIOS and its VGA
    ROM. A subnode can instead be written to a region of the flash map
    which is not a CBFS, such as one for vital product data, by giving it
    an 'fmap-region' property. If any subnode has 'cbfs-name' or
    'fmap-region' then all of them must have one of these. The properties of
    each subnode are:

        - cbfs-name: Name of the file in CBFS. Any existing file of this name
            is removed first
        - cbfs-type: Type of file:

            raw
                The data is added as it is (this is the default)
            payload
                The data must be an ELF file, which cbfstool converts to a
                payload, keeping its segments and entry point
            flat
                The data is added as a flat-binary payload, loaded to
                'cbfs-load-addr', with execution starting at
                'cbfs-entry-addr' (which defaults to the load address)
            stage
                The data must be an ELF file, which cbfstool adds as a stage

            Any other type which cbfstool knows, such as "bootblock" or
            "cmos_layout", adds the data as it is, with that type

        - cbfs-compress: Compression to use ("lzma", "lz4" or "none"). This
            defaults to "lzma" for payloads and flat binaries, otherwise to
            cbfstool's default, which is no compression
        - cbfs-options: Further arguments for cbfstool, as a list of strings,
            e.g. the region with "-r", "COREBOOT", a position with "-b" or an
            alignment with "-a". For 'fmap-region', "-u" fills the rest of the
            region, after the data
        - fmap-region: Name of the region to write the data to, instead of
            adding it to a CBFS

    For example, to boot SeaBIOS on coreboot, with a file to configure it::

        rom {
            filename = "coreboot-seabios.rom";
            coreboot-rom {
                coreboot-filename = "coreboot.rom";

                seabios {
                    type = "blob";
                    filename = "bios.bin.elf";
                    cbfs-name = "fallback/payload";
                    cbfs-type = "payload";
                };
                boot-menu-wait {
                    type = "text";
                    text = "2000";
                    cbfs-name = "etc/boot-menu-wait";
                };
            };
        };

    Creating an image
    ~~~~~~~~~~~~~~~~~

    With 'fmap-filename' or 'fmd-filename', the entry creates a new image
    laid out by a coreboot flash map, with an empty CBFS in each region given
    by 'cbfs-regions', then adds each subnode as a file. This allows binman to
    build a coreboot image from the pieces which coreboot's build produces,
    still using cbfstool to add each one. For example, on x86, where the
    bootblock goes at the end of the CBFS::

        coreboot-rom {
            fmd-filename = "build/fmap.fmd";

            bootblock {
                type = "blob";
                filename = "build/cbfs/fallback/bootblock.bin";
                cbfs-name = "bootblock";
                cbfs-type = "bootblock";
                cbfs-options = "-b", "-16384";
            };
            romstage {
                type = "blob";
                filename = "build/cbfs/fallback/romstage.elf";
                cbfs-name = "fallback/romstage";
                cbfs-type = "stage";
                cbfs-options = "--xip", "-S", ".car.data", "-P", "0x10000";
            };
        };

    Note that binman's own 'cbfs' entry type can also create a CBFS, but
    it lays it out for U-Boot's use and does not relocate coreboot's stages
    to their execute-in-place addresses. This entry uses cbfstool for each
    file instead, so that the result matches what coreboot's build produces.
    """
    def ReadNode(self):
        super().ReadNode()
        fname, = self.GetEntryArgsOrProps(
            [EntryArg('coreboot-rom-path', str)])
        if not fname:
            fname = fdt_util.GetString(self._node, 'coreboot-filename',
                                       'coreboot.rom')
        self._coreboot_fname = fname
        self._cbfs_name = fdt_util.GetString(self._node, 'cbfs-name',
                                             'fallback/payload')
        self._cbfs_load_addr = fdt_util.GetInt(self._node, 'cbfs-load-addr')
        self._cbfs_entry_addr = fdt_util.GetInt(self._node, 'cbfs-entry-addr')
        self._cbfs_compress = fdt_util.GetString(self._node, 'cbfs-compress',
                                                 'lzma')
        self._fmap_fname = fdt_util.GetString(self._node, 'fmap-filename')
        self._fmd_fname = fdt_util.GetString(self._node, 'fmd-filename')
        if self._fmap_fname and self._fmd_fname:
            self.Raise("Use either 'fmap-filename' or 'fmd-filename'")
        self._cbfs_regions = fdt_util.GetString(self._node, 'cbfs-regions')

        # Subnodes with a 'cbfs-name' or 'fmap-region' are each added as a
        # file of their own, or written to a region
        self._files = []
        for entry in self.GetEntries().values():
            node = entry._node
            name = fdt_util.GetString(node, 'cbfs-name')
            region = fdt_util.GetString(node, 'fmap-region')
            if not name and not region:
                continue
            if name and region:
                entry.Raise("Use either 'cbfs-name' or 'fmap-region'")
            ftype = fdt_util.GetString(node, 'cbfs-type', 'raw')
            compress = fdt_util.GetString(
                node, 'cbfs-compress',
                'lzma' if ftype in ('payload', 'flat') else None)
            load = fdt_util.GetInt(node, 'cbfs-load-addr')
            if ftype == 'flat' and load is None:
                entry.Raise("A flat binary needs 'cbfs-load-addr'")
            entry_addr = fdt_util.GetInt(node, 'cbfs-entry-addr', load)
            options = fdt_util.GetStringList(node, 'cbfs-options', [])
            self._files.append(CbfsFile(entry, name, ftype, compress, load,
                                        entry_addr, options, region))
        if self._files and len(self._files) != len(self.GetEntries()):
            self.Raise("Either all subnodes or none must have 'cbfs-name' or "
                       "'fmap-region'")

    def _FindElfFname(self, entry):
        """Find the ELF filename for an entry, recursing into any subnodes

        Args:
            entry (Entry): Entry to search

        Returns:
            str: ELF filename (e.g. 'spl/u-boot-spl') or None if none is found
        """
        if entry.elf_fname:
            return entry.elf_fname
        # U-Boot proper's entries do not record their ELF, but it is always
        # 'u-boot': this covers a payload with no SPL, entered directly
        if entry.etype in ('u-boot', 'u-boot-nodtb'):
            return 'u-boot'
        entries = entry.GetEntries()
        if entries:
            for subent in entries.values():
                fname = self._FindElfFname(subent)
                if fname:
                    return fname
        return None

    def _GetPayloadAddrs(self):
        """Work out the load and entry addresses for the payload

        When the addresses are not given explicitly they are taken from the
        ELF of the first stage in the payload, i.e. SPL when there is one and
        otherwise U-Boot itself: the load address is the lowest load address
        in the ELF and the entry address is its entry point. This avoids
        having to hard-code CONFIG_SPL_TEXT_BASE or CONFIG_TEXT_BASE in the
        devicetree.

        Returns:
            tuple:
                int: Load address of the payload
                int: Entry address (where execution starts)

        Raises:
            ValueError: No load address is given and there is no ELF payload
                to derive it from
        """
        load = self._cbfs_load_addr
        entry = self._cbfs_entry_addr
        if load is None:
            elf_fname = None
            for subent in self.GetEntries().values():
                elf_fname = self._FindElfFname(subent)
                if elf_fname:
                    break
            if not elf_fname:
                self.Raise("Missing 'cbfs-load-addr' and no ELF payload to "
                           'derive it from')
            info = elf.DecodeElf(
                tools.read_file(tools.get_input_filename(elf_fname)), 0)
            load = info.load
            if entry is None:
                entry = info.entry
        if entry is None:
            entry = load
        return load, entry

    def BuildSectionData(self, required):
        """Build the ROM by inserting the payload into the coreboot image

        The subnodes of this entry are built into the payload in the same way
        as a normal section, then inserted into a copy of the coreboot image
        using cbfstool.

        Args:
            required (bool): True if the data must be present, False if it is
                OK to return None

        Returns:
            bytes: Contents of the ROM (or None if not ready)
        """
        if self._files:
            contents = [entry.GetData(required) for entry, *_ in self._files]
            if None in contents:
                return None
        else:
            payload = super().BuildSectionData(required)
            if payload is None:
                return None

        # Start from a new image laid out by a flash map, or from a ROM
        pathname = tools.get_input_filename(
            self._fmd_fname or self._fmap_fname or self._coreboot_fname,
            self.section.GetAllowMissing())
        if not pathname:
            self.missing = True
            return tools.get_bytes(0, 1024)
        uniq = self.GetUniqueName()
        rom_fname = tools.get_output_filename(f'coreboot-rom.{uniq}')
        regions = self._cbfs_regions or 'COREBOOT'
        if self._fmd_fname:
            pathname, fmd_regions = self._ReadFmd(pathname, uniq)
            regions = self._cbfs_regions or fmd_regions
        if self._fmap_fname or self._fmd_fname:
            if os.path.exists(rom_fname):
                os.remove(rom_fname)
            if self.cbfstool.create_from_fmap(rom_fname, pathname,
                                              regions) is None:
                self.record_missing_bintool(self.cbfstool)
                return tools.get_bytes(0, 1024)
        else:
            tools.write_file(rom_fname, tools.read_file(pathname))

        if self._files:
            for seq, (cfile, data) in enumerate(zip(self._files, contents)):
                fname = tools.get_output_filename(f'cbfs-file.{uniq}.{seq}')
                tools.write_file(fname, data)
                if not self._AddFile(rom_fname, cfile, fname, data):
                    self.record_missing_bintool(self.cbfstool)
                    return tools.get_bytes(0, 1024)
        else:
            payload_fname = tools.get_output_filename(f'payload.{uniq}')
            tools.write_file(payload_fname, payload)

            load_addr, entry_addr = self._GetPayloadAddrs()

            # The coreboot image may or may not already have a payload
            self.cbfstool.remove(rom_fname, self._cbfs_name)
            if self.cbfstool.add_flat_binary(
                    rom_fname, self._cbfs_name, payload_fname,
                    load_addr, entry_addr, self._cbfs_compress) is None:
                self.record_missing_bintool(self.cbfstool)
                return tools.get_bytes(0, 1024)

        return tools.read_file(rom_fname)

    def _ReadFmd(self, pathname, uniq):
        """Read a flash-map descriptor and write the FMAP which it describes

        Args:
            pathname (str): Path to the fmd file
            uniq (str): Unique name to use for the FMAP file

        Returns:
            tuple:
                str: Path to the FMAP file
                str: Regions which hold a CBFS, separated by commas, the
                    primary CBFS first

        Raises:
            ValueError: The fmd file is not valid
        """
        try:
            root, cbfs = fmd_util.read_fmd(tools.read_file(pathname,
                                                           binary=False))
            fmap = fmd_util.encode_fmap(root)
        except fmd_util.FmdError as exc:
            self.Raise(f"Flash-map descriptor '{self._fmd_fname}': {exc}")
        fmap_fname = tools.get_output_filename(f'fmap.{uniq}')
        tools.write_file(fmap_fname, fmap)
        return fmap_fname, ','.join(region.name for region in cbfs)

    def _AddFile(self, rom_fname, cfile, fname, data):
        """Add a file to the CBFS in the ROM, replacing any of the same name

        A new image created from a flash map has no files to replace. A file
        with a region is written to that region of the flash map instead.

        Args:
            rom_fname (str): Filename of the ROM to update
            cfile (CbfsFile): File to add
            fname (str): Filename holding the file's data
            data (bytes): The file's data

        Returns:
            bool: True if the file was added, False if cbfstool is missing
        """
        if cfile.region:
            out = self.cbfstool.write_region(rom_fname, cfile.region, fname,
                                             cfile.options)
            return out is not None
        if cfile.ftype in ('payload', 'stage') and data[:4] != b'\x7fELF':
            cfile.entry.Raise(
                f"cbfs-type '{cfile.ftype}' needs an ELF file")
        if not self._fmap_fname and not self._fmd_fname:
            self.cbfstool.remove(rom_fname, cfile.name)
        options = list(cfile.options)
        if cfile.ftype == 'flat':
            options += ['-l', f'{cfile.load:#x}', '-e',
                        f'{cfile.entry_addr:#x}']
        out = self.cbfstool.add_file(rom_fname, cfile.name, fname, cfile.ftype,
                                     cfile.compress, options)
        return out is not None

    def SetImagePos(self, image_pos):
        """Set the position in the image

        The subnodes are positioned within the payload (which is loaded to
        its link address at run time), not within the ROM, so give them
        positions relative to the payload, as for a standalone image. The
        binman symbols in SPL then match those of the image produced by a
        plain build, so SPL can find U-Boot.
        """
        Entry.SetImagePos(self, image_pos)
        for entry in self.GetEntries().values():
            entry.SetImagePos(0)

    def CheckEntries(self):
        # The subnodes make up the payload and are positioned relative to its
        # load address (see SetImagePos), not placed within the coreboot ROM.
        # So the section's overlap and bounds checks do not apply; skip them.
        pass

    def CheckMissing(self, missing_list):
        # Check the coreboot ROM itself (an external image, which sets
        # self.missing when absent) as well as the payload subnodes. The base
        # implementation covers only the ROM and the section only the subnodes,
        # so both are needed here.
        Entry.CheckMissing(self, missing_list)
        super().CheckMissing(missing_list)

    def ProcessContents(self):
        # The payload may have changed, e.g. due to WriteSymbols()
        ok = super().ProcessContents()
        data = self.BuildSectionData(True)
        ok2 = self.ProcessContentsUpdate(data)
        return ok and ok2

    def AddBintools(self, btools):
        super().AddBintools(btools)
        self.cbfstool = self.AddBintool(btools, 'cbfstool')
