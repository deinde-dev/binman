/* SPDX-License-Identifier: GPL-2.0+ OR BSD-3-Clause */
/*
 * Symbol access for symbols set up by binman as part of the build.
 *
 * This allows C code to access the position of a particular part of the image
 * assembled by binman. It is a standalone version of U-Boot's
 * include/binman_sym.h, for use in any project: it needs no configuration
 * options. See 'Access to binman entry offsets at run time (symbols)' in the
 * binman documentation for how binman fills in these symbols.
 *
 * Unlike the rest of binman, this header is dual-licensed, so that projects
 * under either licence can include it.
 *
 * Copyright (c) 2017 Google, Inc
 */

#ifndef __BINMAN_SYM_H
#define __BINMAN_SYM_H

/* BSYM in little endian, keep in sync with binman/elf.py */
#define BINMAN_SYM_MAGIC_VALUE	(0x4d595342UL)
#define BINMAN_SYM_MISSING	(-1UL)

/**
 * binman_symname() - Internal function to get a binman symbol name
 *
 * @_entry_name: Name of the entry to look for (e.g. 'u_boot_spl')
 * @_prop_name: Property value to get from that entry (e.g. 'image_pos')
 * @returns name of the symbol for that entry and property
 */
#define binman_symname(_entry_name, _prop_name) \
	_binman_ ## _entry_name ## _prop_ ## _prop_name

/**
 * binman_sym_declare() - Declare a symbol that will be used at run-time
 *
 * @_type: Type of the symbol (e.g. unsigned long)
 * @_entry_name: Name of the entry to look for (e.g. 'u_boot_spl')
 * @_prop_name: Property value to get from that entry (e.g. 'image_pos')
 */
#define binman_sym_declare(_type, _entry_name, _prop_name) \
	_type binman_symname(_entry_name, _prop_name) \
		__attribute__((aligned(4), unused, section(".binman_sym")))

/**
 * binman_sym_extern() - Declare an extern symbol that will be used at run-time
 *
 * @_type: Type of the symbol (e.g. unsigned long)
 * @_entry_name: Name of the entry to look for (e.g. 'u_boot_spl')
 * @_prop_name: Property value to get from that entry (e.g. 'image_pos')
 */
#define binman_sym_extern(_type, _entry_name, _prop_name) \
	extern _type binman_symname(_entry_name, _prop_name) \
		__attribute__((aligned(4), unused, section(".binman_sym")))

/**
 * binman_sym_declare_optional() - Declare an optional symbol
 *
 * If this symbol cannot be provided by binman, an error will not be generated.
 * Instead the image will be assigned the value BINMAN_SYM_MISSING.
 *
 * @_type: Type of the symbol (e.g. unsigned long)
 * @_entry_name: Name of the entry to look for (e.g. 'u_boot_spl')
 * @_prop_name: Property value to get from that entry (e.g. 'image_pos')
 */
#define binman_sym_declare_optional(_type, _entry_name, _prop_name) \
	_type binman_symname(_entry_name, _prop_name) \
		__attribute__((aligned(4), weak, unused, \
		section(".binman_sym")))

/**
 * _binman_sym_magic - Internal magic symbol for validity checks
 *
 * When building images, binman fills in this symbol with the magic
 * value #defined above. This is used to check at runtime if the
 * symbol values were filled in and are OK to use.
 */
extern unsigned long _binman_sym_magic;

/**
 * DECLARE_BINMAN_MAGIC_SYM - Declare the internal magic symbol
 *
 * This macro declares the _binman_sym_magic symbol so that it exists. Use it
 * in exactly one file, since declaring it here would cause errors during
 * linking due to multiple definitions of the symbol.
 */
#define DECLARE_BINMAN_MAGIC_SYM \
	unsigned long _binman_sym_magic \
		__attribute__((aligned(4), section(".binman_sym")))

/**
 * BINMAN_SYMS_OK - Check if the symbol values are valid
 *
 * This macro checks if the magic symbol's value is filled properly,
 * which indicates that other symbols are OK to use as well.
 *
 * Return: 1 if binman symbol values are usable, 0 if not
 */
#define BINMAN_SYMS_OK \
	(*(unsigned long *)&_binman_sym_magic == BINMAN_SYM_MAGIC_VALUE)

/**
 * binman_sym() - Access a previously declared symbol
 *
 * This is used to get the value of a symbol. E.g.:
 *
 *    unsigned long address = binman_sym(unsigned long, u_boot_spl, image_pos);
 *
 * @_type: Type of the symbol (e.g. unsigned long)
 * @_entry_name: Name of the entry to look for (e.g. 'u_boot_spl')
 * @_prop_name: Property value to get from that entry (e.g. 'image_pos')
 *
 * Return: value of that property (filled in by binman), or
 *	   BINMAN_SYM_MISSING if the value is unavailable
 */
#define binman_sym(_type, _entry_name, _prop_name) \
	(BINMAN_SYMS_OK ? \
	 (*(_type *)&binman_symname(_entry_name, _prop_name)) : \
	 BINMAN_SYM_MISSING)

#endif
