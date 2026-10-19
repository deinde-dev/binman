Changelog
=========

All notable changes to this project are documented here. The format is
based on `Keep a Changelog <https://keepachangelog.com/en/1.1.0/>`_ and
the project follows `Semantic Versioning <https://semver.org/>`_.

Unreleased
----------

Added
~~~~~
- The ``coreboot-rom`` entry type can add each of its subnodes to the CBFS
  as a file of its own, given by ``cbfs-name``, with ``cbfs-type`` selecting
  a raw file, an ELF payload, a flat binary or a stage. This allows payloads
  other than U-Boot, such as SeaBIOS, and extra files such as configuration.
- The ``--etype-dir`` option adds a directory to search for entry types,
  before binman's own, for developing entry types.
- The ``coreboot-rom`` entry type can create an image from a coreboot flash
  map, with ``fmap-filename``, rather than starting from a coreboot ROM. Its
  files can be of any type which cbfstool knows, such as ``bootblock``, and
  ``cbfs-options`` gives further arguments for cbfstool, such as a position
  or alignment. This allows binman to build a coreboot image from the pieces
  which coreboot's build produces.

Changed
~~~~~~~
- The devicetree holding the image description is only treated as U-Boot's
  own when building for U-Boot. Binman detects a U-Boot build directory, by
  its ``u-boot.cfg`` file, and the new ``--project`` option overrides this
  choice. Otherwise U-Boot's devicetree entries are read from the input
  directories like other files, SPL, TPL and VPL devicetrees are not picked
  up, bootph properties are not propagated and the output devicetree is
  named after the input, e.g. ``image.dtb.out``. Use ``--project u-boot`` to
  package a U-Boot build from outside its build directory. See 'U-Boot mode'
  in the documentation.

0.1.3 - 2026-10-18
------------------

Changed
~~~~~~~
- The U-Boot Python library is now a dependency, from the ``u-boot-pylib``
  package, rather than a copy vendored into binman.
- The project has moved to the deinde-dev organisation on GitHub, at
  https://github.com/deinde-dev/binman

Fixed
~~~~~
- A compressed section is no longer cut short when updating the devicetree
  with ``-u`` changes its compressed size. This happened with a compressed
  ``u-boot`` entry, whose devicetree is updated, and made the image unusable.

0.1.2 - 2026-10-10
------------------

Added
~~~~~
- ``binman blob`` fetches firmware blobs, such as the BL31 image from ARM
  Trusted Firmware, preferring to build them from source. Fetched blobs are
  cached in ``~/.cache/binman/blobs``, which can be changed with
  ``--blob-dir`` or ``BINMAN_BLOB_DIR``. See 'Fetching firmware blobs' in the
  documentation.
- Blobs are built in ``~/.cache/binman/blob-build``, which is kept so that a
  later build of the same version is faster and a failed build can be
  examined. This can be changed with ``--blob-build-dir`` or
  ``BINMAN_BLOB_BUILD_DIR``. Use ``binman blob --temp-build`` to build in a
  temporary directory instead, or ``binman blob --clean-builds`` to remove the
  builds.
- Building an image fetches any external blobs it needs which are not in the
  input directories, from blob types which provide them for the board. These
  are matched by the compatible strings of the devicetree root node, so a
  board's own blobs take precedence over those shared by its SoC. Blob stores
  and blob types, such as a private server holding a board's blobs, can be set
  up in ``~/.config/binman/blobstores.yaml`` or in files listed in
  ``BINMAN_BLOBSTORES``

0.1.1 - 2026-10-04
------------------

Fixed
~~~~~
- The vendored ``u_boot_pylib`` and ``dtoc`` libraries are installed inside
  the ``binman`` package rather than as top-level packages. These shadowed
  U-Boot's own copies, breaking its dtoc tool when binman was installed in
  the same environment, and clashed with the separate ``u_boot_pylib`` and
  ``dtoc`` packages.

0.1.0 - 2026-10-04
------------------

Changed
~~~~~~~
- Binman is now developed in its own repository at
  https://github.com/deinde-dev/binman, with its history carried over from
  the U-Boot tree.
- Binman is distributed as the self-contained ``binary-manager`` package,
  with ``u_boot_pylib`` and the ``dtoc`` devicetree library vendored in,
  installable from PyPI with ``pip install binary-manager``. Its Python
  dependencies are now declared, so it no longer needs them to be installed
  separately.
- ``binman -V`` shows the version of the installed package.
- Documentation is now published at https://binman.readthedocs.io/.

Fixed
~~~~~
- ``binman tool -f fiptool`` finds the tool where current TF-A builds it,
  in ``build/fvp/release/tools/fiptool/``, instead of reporting that it was
  not produced.

Earlier releases
----------------

Releases 0.0.7 and earlier were published from the U-Boot tree and predate
this changelog.
