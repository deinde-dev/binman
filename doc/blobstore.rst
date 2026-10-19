.. SPDX-License-Identifier: GPL-2.0+

Setting up a blob store
=======================

Firmware images often need blobs from other projects, such as a flash
descriptor or a memory-init binary. Rather than having everyone copy these
files into place, they can be put in a blob store, from which binman fetches
them when it needs them. A store can be a web server, or just a directory.

This page sets up a small store on a local web server, then uses it to build
an image. See 'Fetching firmware blobs' in the manual for the full details of
the configuration.


Serving the blobs
-----------------

A store serves the blob files themselves, one per URL. Binman does not unpack
archives. Put the files in a directory for each blob type and version, so
that a new version can be added without disturbing the old one::

    $ mkdir -p blobs/example/1
    $ echo 'example firmware' > blobs/example/1/fw.bin

Then serve the directory. Any web server will do: here Python's own web server
serves it on port 8000. Leave it running, in another terminal::

    $ python3 -m http.server --directory blobs 8000

The server must return an HTTP error, such as 404, for a file which it does not
have, which every web server does. Binman does not support authentication, so a
private server must be reachable without credentials, for example over a VPN.


Describing the store
--------------------

Tell binman about the store, and about a blob type which it provides, in a
configuration file. Binman reads ``~/.config/binman/blobstores.yaml`` and any
files listed in the ``BINMAN_BLOBSTORES`` environment variable. Put this in
``example.yaml``::

    stores:
      example-server:
        type: url
        repo: http://localhost:8000
        desc: Example blob server

    blobs:
      example,board:
        desc: Firmware for the example board
        version: '1'
        files: [fw.bin]
        stores:
          - store: example-server
            pattern: example/{version}/{file}

The blob type is named after the compatible string of the board which needs
its files. The pattern gives the location of each file on the server: here
``fw.bin`` is at ``http://localhost:8000/example/1/fw.bin``.

Point binman at the file and check that it understands it. Binman reports any
mistake in the file, naming it::

    $ export BINMAN_BLOBSTORES=$PWD/example.yaml
    $ binman blob --list-stores
    $ binman blob --info example,board

Then fetch the blob type's files into binman's cache, to check that the store
works. Add ``-v5`` to see the URL which binman tries::

    $ binman blob --fetch example,board


Building an image
-----------------

Binman also fetches a blob when building an image which needs it. Describe
an image for the example board in ``image.dts``. Its root node has the board's
compatible string, which tells binman which blob type to use::

    /dts-v1/;

    / {
        compatible = "example,board";

        binman {
            blob-ext {
                filename = "fw.bin";
            };
        };
    };

Then build it::

    $ binman build -d image.dts -I . -O out
    $ cat out/image.bin
    example firmware

The ``-I .`` option is needed: without an input directory, binman does not
notice that ``fw.bin`` is missing, so it does not fetch it.

Binman found that ``fw.bin`` was not in the input directory, so it took it
from the cache, which it fills from the store as needed.


Updating the blobs
------------------

Binman does not fetch a file again once it is in the cache, even if it
changes on the server. So to change the blobs, add them as a new version,
e.g. in ``blobs/example/2/``, and change the version in the configuration.
Binman then fetches the new version when it is next needed.

Binman does not check the contents of the files which it fetches, so only use
stores which you trust.
