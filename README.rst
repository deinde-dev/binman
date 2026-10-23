.. image:: https://raw.githubusercontent.com/deinde-dev/binman/master/logo/binman-logo-primary.png
   :alt: Binman
   :width: 400px

Binman firmware packager
========================

.. image:: https://github.com/deinde-dev/binman/actions/workflows/test.yml/badge.svg
   :target: https://github.com/deinde-dev/binman/actions/workflows/test.yml
   :alt: Test status

.. image:: https://img.shields.io/pypi/v/binary-manager.svg
   :target: https://pypi.org/project/binary-manager/
   :alt: PyPI version

.. image:: https://readthedocs.org/projects/binman/badge/?version=latest
   :target: https://binman.readthedocs.io/en/latest/
   :alt: Documentation status

.. image:: https://img.shields.io/pypi/pyversions/binary-manager.svg
   :target: https://pypi.org/project/binary-manager/
   :alt: Supported Python versions

Binman packages firmware. Building firmware should be separate from packaging
it: build all the pieces you need, using whatever projects and build systems
they require, then use binman to stitch everything together into an image. It:

- reads an image description from a devicetree and works out what to place
  where, with padding, alignment, compression and hashing;
- supports hierarchical images and a large set of entry types, including FIT,
  coreboot's CBFS and flash maps, the ARM Trusted Firmware FIP and many
  SoC-specific formats;
- lets firmware find other binaries in the image, using linker symbols or the
  devicetree description of the image;
- inspects existing images, extracting and replacing their contents and
  repacking where needed;
- copes with missing binary blobs and fetches the external tools it needs;
- fetches firmware blobs such as TF-A, building them from source where it can,
  and keeps them in a cache.

Binman started as part of U-Boot and still builds U-Boot's images, but it is
not tied to U-Boot. It can build coreboot images from a coreboot flash-map
descriptor, and can package the firmware for TF-A, OP-TEE, Zephyr or any other
project.

Installation
------------

Install the latest release from PyPI::

    pip install binary-manager

The ``pylibfdt`` dependency is built from source, so this needs ``swig``, a C
compiler and the Python development headers (on Debian and Ubuntu:
``apt install swig build-essential python3-dev``).

The ``binman`` command is then on your path.

Quick start
-----------

Build the images described in a devicetree, taking the input files from the
current directory::

    binman build -d image.dts -I .

When run in a U-Boot build directory, or with one as an input directory,
binman treats the devicetree as U-Boot's own, updating it with the image
layout. To package U-Boot's binaries which have been copied elsewhere, select
the u-boot project::

    binman --project u-boot build -u -d u-boot.dtb -I .

List the contents of an existing image::

    binman ls -i image.bin

Binman runs external tools for some entry types. To install any which are
missing::

    binman tool -f missing

Fetch a firmware blob, here TF-A's BL31 for an Allwinner A64 board, building
it from source::

    binman blob -f arm,trusted-firmware-a --version 2.12 --arch aarch64 \
        --plat sun50i_a64

See ``binman -H`` for the complete manual, or the documentation linked below.

Documentation
-------------

Full documentation is hosted on Read the Docs:

    https://binman.readthedocs.io/

There is a short introduction, with a demo, at https://deinde.dev/binman/

Development
-----------

Run the test suite from a checkout::

    pip install -r requirements.txt
    pip install -e .[test]
    binman tool -f missing
    binman test

The tests build some small x86 ELF programs, so they need ``make`` and a gcc
which can produce 32-bit x86 code (``gcc-multilib``), or set ``CROSS_COMPILE``
to a suitable cross-compiler. They also need a recent ``mkimage`` from U-Boot,
since the expected output tracks its development; pass ``--toolpath`` to point
binman at a U-Boot ``tools/`` build directory. ``binman test -T`` checks that
the tests cover all of the code.

The ``dtoc`` and ``u_boot_pylib`` libraries are installed from PyPI, as the
``dtoc`` and ``u-boot-pylib`` packages, so no surrounding U-Boot source is
required.
