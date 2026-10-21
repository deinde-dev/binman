.. SPDX-License-Identifier: GPL-2.0+

Binman
======

Binman packages firmware binaries into images described by a devicetree. It
started as part of U-Boot and still builds U-Boot's images, but it is not tied
to U-Boot: it can build coreboot images and package the firmware for TF-A,
OP-TEE, Zephyr or any other project. To try it, see 'Getting started' in the
manual.

The project is hosted at https://github.com/deinde-dev/binman

There is a short introduction, with a demo, at https://deinde.dev/binman/

.. toctree::
   :maxdepth: 2

   binman
   blobstore
   etype_dev
   binman_tests
   changelog
