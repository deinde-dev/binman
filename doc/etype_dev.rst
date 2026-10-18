.. SPDX-License-Identifier: GPL-2.0+

Developing entry types
======================

Each kind of thing which binman can put in an image, such as a file, a FIT or
a CBFS, is handled by an entry type. Binman has about 100 of them, in the
``binman/etype/`` directory, and new ones are welcome. This page explains how
to write one, try it out and then add it to binman.

While developing an entry type, it is often easiest to keep it outside binman,
in a directory of your own, and point binman at it with ``--etype-dir``. This
works with an installed copy of binman, so there is no need to set up a
checkout until the entry type is ready. Once it works, please send it to
binman, as described below, so that others can use it. The ``--etype-dir``
option is a development aid, not a way to ship entry types.


How binman finds an entry type
------------------------------

Each node in an image description is an entry. Its type is given by its
``type`` property, or by the node name if there is no ``type``. Anything from
an ``@`` onwards is dropped, so ``u-boot@0`` has the type ``u-boot``.

Binman then imports a module named after the type, with hyphens changed to
underscores, and uses the class called ``Entry_<module>`` from it. For
example, the type ``build-marker`` is handled by class
``Entry_build_marker`` in ``build_marker.py``.

Binman looks for the module in each ``--etype-dir`` directory, in the order
given, then in its own ``etype/`` directory. So a file in an
``--etype-dir`` directory can provide a new entry type, or take the place of
one of binman's own, which is useful for trying a change to an existing entry
type. Use ``-v2`` to see which entry types binman loads this way::

    $ binman -v2 --etype-dir my-etypes build -d image.dts
    Using entry type 'build_marker' from 'my-etypes/build_marker.py'


Writing an entry type
---------------------

An entry type is a subclass of one of binman's classes. Pick the one closest
to what you need:

``Entry`` (``binman.entry``)
    The base class, for an entry which works out its own contents, such as
    ``fill`` or ``text``

``Entry_blob`` (``binman.etype.blob``)
    An entry whose contents come from a file in the input directories, such as
    ``u-boot`` or ``atf-bl31``. Set the filename in the constructor or override
    ``GetDefaultFilename()``. Set ``self.external = True`` for a file which
    comes from another project, so that binman can still build the image when
    it is missing, if ``-M`` is given

``Entry_section`` (``binman.etype.section``)
    An entry which holds other entries in its subnodes and builds its own
    contents from them, such as ``fit`` or ``cbfs``. Override
    ``BuildSectionData()`` to build the contents

Binman calls these methods of each entry in turn as it builds an image. Most
entry types only need the first two or three:

``ReadNode()``
    Reads the entry's properties from its node. Call ``super().ReadNode()``
    first, then use the functions in ``dtoc.fdt_util``, such as
    ``GetString()``, ``GetInt()`` and ``GetBool()``. Set
    ``self.required_props`` in the constructor to list properties which must
    be present

``ObtainContents()``
    Works out the contents, calling ``SetContents()`` with them, and returns
    True. If the contents depend on other entries which are not ready yet,
    return False and binman calls it again later

``ProcessContents()``
    Called after the image is packed, when the position of every entry is
    known, to update the contents, for example with a table of offsets. Pass
    the new contents to ``ProcessContentsUpdate()`` and return its result. If
    the size changes, binman packs the image again

``AddBintools()``
    Lists the external tools which the entry type uses, with
    ``self.AddBintool(btools, '<name>')``, so that binman can report them if
    they are missing and fetch them with ``binman tool -f missing``

Other useful methods are:

- ``GetEntryArgsOrProps()``, which reads values from entry arguments
  (``-a name=value`` on the command line) or properties, so that a build
  system can supply them
- ``Raise()``, which reports an error, giving the path of the node
- ``tools.get_input_filename()`` from ``u_boot_pylib``, which finds a file
  in the input directories
- ``Detail()`` and ``Info()``, which log messages for the entry, shown with
  ``-v4``

The class's docstring is its documentation. Describe the properties and entry
arguments, under a ``Properties / Entry arguments:`` heading, and give an
example of its use. When the entry type is added to binman, the docstring
appears in the list of entry types in binman's documentation, and the tests
check that it is present.

See the entry types in ``binman/etype/`` for many more examples.


An example
----------

This entry type holds a marker identifying the build, made from a prefix and
a build ID. Put it in ``my-etypes/build_marker.py``:

.. code-block:: python

    # SPDX-License-Identifier: GPL-2.0+
    #
    # Entry-type module for a marker identifying the build
    #

    from binman.entry import Entry, EntryArg
    from dtoc import fdt_util
    from u_boot_pylib import tools

    class Entry_build_marker(Entry):
        """A marker identifying the build

        Properties / Entry arguments:
            - marker-prefix: Text to put before the build ID (default "build:")
            - build-id: ID of the build, usually given as an entry argument,
              e.g. '-a build-id=1234'

        The entry holds the prefix followed by the build ID, as ASCII text.
        """
        def ReadNode(self):
            super().ReadNode()
            self.prefix = fdt_util.GetString(self._node, 'marker-prefix',
                                             'build:')
            self.build_id, = self.GetEntryArgsOrProps(
                [EntryArg('build-id', str)], required=True)

        def ObtainContents(self, fake_size=0):
            self.SetContents(tools.to_bytes(self.prefix + self.build_id))
            return True

Use it in an image description, ``image.dts``::

    /dts-v1/;

    / {
        binman {
            build-marker {
                marker-prefix = "id=";
            };
        };
    };

Then build the image, putting the output in ``out/``::

    $ binman --etype-dir my-etypes build -d image.dts -O out -a build-id=1234
    $ cat out/image.bin
    id=1234

Without ``-a build-id=...`` binman reports that the entry argument is
missing.


Debugging
---------

These options help when an entry type does not work as expected:

- ``-D`` shows a full Python backtrace when there is an error
- ``-v4`` or ``-v5`` shows what binman is doing, including messages from
  ``Detail()`` and ``Info()``
- ``-T0`` builds sections in a single thread, so that errors and debuggers
  are easier to follow
- ``-m`` writes a map file for each image, showing where each entry is
- ``binman ls -i out/image.bin`` lists the entries in an image which has an
  ``fdtmap``

For example::

    $ binman -D -v5 -T0 --etype-dir my-etypes build -d image.dts -O out -m


Adding the entry type to binman
-------------------------------

Once the entry type works, send it to binman so that it is maintained along
with everything else. See ``CONTRIBUTING.rst`` for setting up a checkout and
running the tests. Then:

1. Move the file to ``binman/etype/``.
2. Add a test description in ``binman/test/entry/``, e.g.
   ``build_marker.dts``, and a test in ``binman/ftest.py`` which builds it and
   checks the result. For example:

   .. code-block:: python

       def testBuildMarker(self):
           """Test the build-marker entry type"""
           data = self._DoReadFileDtb('entry/build_marker.dts',
                                      entry_args={'build-id': '1234'})[0]
           self.assertEqual(b'id=1234', data)

3. Add tests for any error cases, since every line of binman must be covered
   by the tests. Check this with ``binman test -T``.
4. Add an entry to ``CHANGELOG.rst``.
5. Send a pull request.

The entry type's docstring then appears in binman's documentation of entry
types, under its type name.


Limitations
-----------

- Only entry types can be loaded from a directory, not bintools or blob
  handlers.
- The ``entry-docs`` command and binman's documentation only cover binman's
  own entry types.
- An entry type loaded from a directory is imported for each run of binman,
  as ``binman.etype.<module>``, so it should not rely on module-level state
  being kept between runs.
