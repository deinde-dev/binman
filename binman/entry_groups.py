# SPDX-License-Identifier: GPL-2.0+
# Copyright 2026 Simon Glass <sjg@chromium.org>
#
"""Groups of entry types, for their documentation

The documentation of the entry types lists them in these groups, so that
someone working on a particular project can find the ones which apply to it.
Every entry type must be in exactly one group: the tests check this.

This module has no imports, so that the documentation build can load it
without binman's dependencies.
"""

# Each group has a title, a description and the entry types in it, by module
# name. The groups appear in this order.
GROUPS = [
    ('Building blocks',
     'Entry types for the contents of any image: files, sections, padding '
     'and text.',
     ['blob', 'blob_ext', 'blob_ext_list',
      'blob_named_by_arg', 'collection', 'encrypted', 'files', 'fill', 'null',
      'section', 'text']),
    ('Image formats and metadata',
     'Entry types which produce a standard format, or describe the image so '
     'that firmware and tools can find its parts.',
     ['efi_capsule', 'efi_empty_capsule', 'fdtmap', 'fit', 'image_header',
      'mkimage', 'pre_load', 'x509_cert']),
    ('Arm and RISC-V firmware',
     'Entry types for ARM Trusted Firmware (TF-A), OP-TEE, OpenSBI and other '
     'firmware which runs alongside the bootloader.',
     ['atf_bl1', 'atf_bl31', 'atf_fip', 'opensbi', 'scp', 'tee_os']),
    ('coreboot and Chromium OS',
     "Entry types for coreboot's CBFS and flash maps, and for Chromium OS's "
     'verified boot.',
     ['cbfs', 'coreboot_rom', 'cros_ec_rw', 'fmap', 'gbb', 'vblock']),
    ('x86',
     'Entry types for the firmware which Intel and AMD platforms need.',
     ['amd_fw', 'intel_cmc', 'intel_descriptor', 'intel_fit', 'intel_fit_ptr',
      'intel_fsp', 'intel_fsp_m', 'intel_fsp_s', 'intel_fsp_t', 'intel_ifwi',
      'intel_me', 'intel_mrc', 'intel_osip', 'intel_refcode', 'intel_vbt',
      'intel_vga']),
    ('SoC vendors',
     'Entry types for the boot images and firmware of particular SoCs.',
     ['nxp_header_ddrfw', 'nxp_imx8mcst', 'nxp_imx8mimage', 'nxp_imx9image',
      'renesas_rcar4_sa0', 'rockchip_tpl', 'ti_board_config', 'ti_dm',
      'ti_secure', 'ti_secure_rom', 'xilinx_bootgen']),
    ('U-Boot',
     "Entry types for U-Boot's own binaries, for each of its phases, and for "
     'code which U-Boot provides for particular architectures.',
     ['alternates_fdt', 'blob_dtb', 'blob_phase',
      'powerpc_mpc85xx_bootpg_resetvec', 'u_boot',
      'u_boot_dtb', 'u_boot_dtb_with_ucode', 'u_boot_elf', 'u_boot_env',
      'u_boot_expanded', 'u_boot_img', 'u_boot_nodtb', 'u_boot_spl',
      'u_boot_spl_bss_pad', 'u_boot_spl_dtb', 'u_boot_spl_elf',
      'u_boot_spl_expanded', 'u_boot_spl_nodtb', 'u_boot_spl_pubkey_dtb',
      'u_boot_spl_with_ucode_ptr', 'u_boot_tpl', 'u_boot_tpl_bss_pad',
      'u_boot_tpl_dtb', 'u_boot_tpl_dtb_with_ucode', 'u_boot_tpl_elf',
      'u_boot_tpl_expanded', 'u_boot_tpl_nodtb', 'u_boot_tpl_with_ucode_ptr',
      'u_boot_ucode', 'u_boot_vpl', 'u_boot_vpl_bss_pad', 'u_boot_vpl_dtb',
      'u_boot_vpl_elf', 'u_boot_vpl_expanded', 'u_boot_vpl_nodtb',
      'u_boot_with_ucode_ptr', 'x86_reset16', 'x86_reset16_spl',
      'x86_reset16_tpl', 'x86_start16', 'x86_start16_spl',
      'x86_start16_tpl']),
]


def group_modules(modules):
    """Sort entry-type modules into their groups

    Args:
        modules (list of str): Names of the modules, e.g. 'u_boot_spl'

    Returns:
        tuple:
            list of tuple: For each group which has any of the modules:
                str: Title
                str: Description
                list of str: The modules in the group, sorted
            list of str: Modules which are not in any group, sorted

    Raises:
        ValueError: A module is in more than one group
    """
    seen = set()
    groups = []
    for title, desc, members in GROUPS:
        dups = seen.intersection(members)
        if dups:
            raise ValueError(
                f"Entry types in more than one group: {', '.join(sorted(dups))}")
        seen.update(members)
        found = sorted(set(members).intersection(modules))
        if found:
            groups.append((title, desc, found))
    return groups, sorted(set(modules) - seen)
