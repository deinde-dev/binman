# SPDX-License-Identifier: GPL-2.0+
# Copyright 2026 Canonical Ltd
# Written by Simon Glass <simon.glass@canonical.com>
#
"""Blob store implementations for fetching firmware blobs

This module provides different store types for fetching blobs:
- LocalBlobStore: Fetch from local directories
- UrlBlobStore: Fetch from HTTP/HTTPS URLs
- BuildBlobStore: Delegate to the blob handler's build() method

The stores and blob types come from blobstores.yaml in the binman package,
followed by the user's own configuration (see user_config_files()).
"""

import os
import shutil
import tempfile
import urllib.request

import yaml

from u_boot_pylib import tout

BINMAN_DIR = os.path.dirname(os.path.realpath(__file__))

# The user's configuration file, read after the one in the binman package
USER_CONFIG = '~/.config/binman/blobstores.yaml'

# Environment variable holding a list of further configuration files
CONFIG_ENV = 'BINMAN_BLOBSTORES'

# Timeout in seconds for downloading a blob
DOWNLOAD_TIMEOUT = 60

# Cache for the loaded configuration
_config = None

# Format string for listing stores
STORE_FORMAT = '%-20.20s %-15.15s %5s  %s'

# Types of store. 'git-release' is another name for 'url'
STORE_TYPES = ('build', 'local', 'url', 'git-release')

# Keys allowed in each part of the configuration
STORE_KEYS = ('type', 'priority', 'desc', 'repo')
BLOB_KEYS = ('desc', 'handler', 'version', 'files', 'stores')
BLOB_STORE_KEYS = ('store', 'pattern')


def user_config_files():
    """Get the user's configuration files, in the order to read them

    These are USER_CONFIG, if it exists, followed by any files listed in the
    CONFIG_ENV environment variable, separated by os.pathsep. This allows
    stores and blob types to be set up, for example to use a private server,
    without changing the binman package.

    Returns:
        list of str: Paths of the files
    """
    fnames = []
    user = os.path.expanduser(USER_CONFIG)
    if os.path.exists(user):
        fnames.append(user)
    fnames += [fname for fname in os.environ.get(CONFIG_ENV, '').split(
        os.pathsep) if fname]
    return fnames


def merge_config(config, extra):
    """Merge further configuration into the configuration

    Stores and blob types in the extra configuration are added, replacing any
    with the same name.

    Args:
        config (dict): Configuration to update
        extra (dict): Configuration to merge in
    """
    for key in ('stores', 'blobs'):
        config.setdefault(key, {}).update(extra.get(key) or {})


def _read_yaml(fname):
    """Read a YAML configuration file

    Args:
        fname (str): Path to the file

    Returns:
        dict: Configuration, empty if the file is empty
    """
    with open(fname, 'r', encoding='utf-8') as inf:
        return yaml.safe_load(inf) or {}


def _check_keys(where, item, allowed):
    """Check that a part of the configuration has only the allowed keys

    Args:
        where (str): Description of the part, for errors
        item (dict): Part of the configuration
        allowed (tuple of str): Keys which are allowed

    Raises:
        ValueError: The part is not a mapping or has an unknown key
    """
    if not isinstance(item, dict):
        raise ValueError(f'{where}: expected a mapping')
    for key in item:
        if key not in allowed:
            raise ValueError(f"{where}: unknown key '{key}' (expected "
                             f"{', '.join(allowed)})")


def check_config(config, fname):
    """Check the contents of a configuration file

    Args:
        config (dict): Configuration read from the file
        fname (str): Path to the file, for errors

    Raises:
        ValueError: The configuration is not valid
    """
    _check_keys(fname, config, ('stores', 'blobs'))
    stores = config.get('stores') or {}
    if not isinstance(stores, dict):
        raise ValueError(f'{fname}: stores: expected a mapping')
    for name, store in stores.items():
        where = f"{fname}: store '{name}'"
        _check_keys(where, store, STORE_KEYS)
        store_type = store.get('type', 'url')
        if store_type not in STORE_TYPES:
            raise ValueError(f"{where}: unknown type '{store_type}' (expected "
                             f"{', '.join(STORE_TYPES[:3])})")
        if not isinstance(store.get('priority', 0), int):
            raise ValueError(f'{where}: priority must be an integer')

    blobs = config.get('blobs') or {}
    if not isinstance(blobs, dict):
        raise ValueError(f'{fname}: blobs: expected a mapping')
    for name, blob in blobs.items():
        where = f"{fname}: blob type '{name}'"
        _check_keys(where, blob, BLOB_KEYS)
        # A version such as 2.10 would be read as a number, then used as 2.1
        version = blob.get('version', '')
        if not isinstance(version, (str, int)) or isinstance(version, bool):
            raise ValueError(f'{where}: version {version} is not a string; '
                             "quote it, e.g. '2.10', so it is not read as a "
                             'number')
        files = blob.get('files', [])
        if (not isinstance(files, list) or
                not all(isinstance(item, str) for item in files)):
            raise ValueError(f'{where}: files must be a list of filenames')
        refs = blob.get('stores', [])
        if not isinstance(refs, list):
            raise ValueError(f'{where}: stores must be a list')
        for ref in refs:
            _check_keys(f'{where}: stores', ref, BLOB_STORE_KEYS)
            if 'store' not in ref:
                raise ValueError(f"{where}: each of its stores needs 'store'")


def check_refs(config, origins):
    """Check that the blob types refer to stores which are set up

    Args:
        config (dict): Merged configuration
        origins (dict): Path of the file which gave each blob type, for errors

    Raises:
        ValueError: A blob type refers to an unknown store or lacks a pattern
    """
    stores = config.get('stores', {})
    for name, blob in config.get('blobs', {}).items():
        where = f"{origins[name]}: blob type '{name}'"
        for ref in blob.get('stores', []):
            store_name = ref['store']
            if store_name not in stores:
                raise ValueError(f"{where}: unknown store '{store_name}'")
            store_type = stores[store_name].get('type', 'url')
            if store_type != 'build' and not ref.get('pattern'):
                raise ValueError(
                    f"{where}: store '{store_name}' needs a 'pattern'")


def _load_config():
    """Load the configuration, from the package and then the user's files

    Each file is checked as it is read, then the merged configuration is
    checked to make sure that each blob type's stores are set up.

    Returns:
        dict: The configuration data

    Raises:
        ValueError: The configuration is not valid
    """
    global _config  # pylint: disable=global-statement
    if _config is None:
        config = {}
        origins = {}
        fnames = []
        config_path = os.path.join(BINMAN_DIR, 'blobstores.yaml')
        if os.path.exists(config_path):
            fnames.append(config_path)
        for fname in fnames + user_config_files():
            extra = _read_yaml(fname)
            check_config(extra, fname)
            merge_config(config, extra)
            origins.update({name: fname for name in extra.get('blobs') or {}})
        check_refs(config, origins)
        _config = config
    return _config


def find_blobs_for_file(fname, compatibles):
    """Find the blob types which provide a file for a board

    A blob type which lists the files it provides ('files') is named after a
    compatible string, such as a board's ('google,coral') or its SoC's
    ('intel,apollolake'), and is used for boards whose devicetree root node
    has that compatible string. This lets a board's own blobs take precedence
    over blobs shared by all boards with that SoC.

    Args:
        fname (str): Filename to look for, e.g. 'fsp_m.bin'
        compatibles (list of str): Compatible strings of the board, most
            specific first, as in its devicetree root node

    Returns:
        list of str: Compatible strings of the blob types which provide the
            file, most specific first
    """
    blobs = get_all_blobs()
    return [compat for compat in compatibles
            if fname in ((blobs.get(compat) or {}).get('files') or [])]


def download(url):
    """Download a file to a temporary directory

    Args:
        url (str): URL to download

    Returns:
        tuple:
            str: Path to the downloaded file
            str: Temporary directory holding it, to remove when done

    Raises:
        OSError: The file could not be downloaded, e.g. HTTP error
    """
    tmpdir = tempfile.mkdtemp(prefix='binmanblob.')
    fname = os.path.join(tmpdir, url.rstrip('/').split('/')[-1])
    try:
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as resp:
            with open(fname, 'wb') as outf:
                shutil.copyfileobj(resp, outf)
    except Exception:
        shutil.rmtree(tmpdir)
        raise
    return fname, tmpdir


def get_handler_for_compatible(compatible):
    """Get the handler module name for a compatible string

    Args:
        compatible: Compatible string (e.g. 'arm,trusted-firmware-a')

    Returns:
        str: Handler module name (e.g. 'atf'), or None if not found
    """
    config = _load_config()
    blobs = config.get('blobs', {})
    blob_info = blobs.get(compatible, {})
    return blob_info.get('handler')


def get_blob_info(compatible):
    """Get information about a blob

    Args:
        compatible: Compatible string

    Returns:
        dict: Blob information, or None if not found
    """
    config = _load_config()
    blobs = config.get('blobs', {})
    return blobs.get(compatible)


def get_all_blobs():
    """Get information about all known blobs

    Returns:
        dict: Map of compatible string to blob info
    """
    config = _load_config()
    return config.get('blobs', {})


def get_stores_for_compatible(compatible):
    """Get the stores configured for a compatible string

    Args:
        compatible: Compatible string

    Returns:
        list of BlobStore: List of store objects that can fetch this blob
    """
    config = _load_config()
    blobs = config.get('blobs', {})
    stores_config = config.get('stores', {})

    blob_info = blobs.get(compatible, {})
    blob_stores = blob_info.get('stores', [])

    stores = []
    for store_ref in blob_stores:
        store_name = store_ref.get('store')
        store_config = stores_config.get(store_name, {})
        store_type = store_config.get('type', 'url')
        priority = store_config.get('priority', 50)
        pattern = store_ref.get('pattern', '')

        store = create_store(store_name, store_type, priority,
                            store_config.get('desc', ''), pattern,
                            store_config)
        if store:
            stores.append(store)

    return stores


def list_stores():
    """List all configured stores"""
    config = _load_config()
    stores = config.get('stores', {})

    print(STORE_FORMAT % ('Name', 'Type', 'Pri', 'Description'))
    print(STORE_FORMAT % ('-' * 19, '-' * 14, '-' * 5, '-' * 30))

    for name, store_config in sorted(stores.items()):
        print(STORE_FORMAT % (
            name,
            store_config.get('type', 'url'),
            store_config.get('priority', 50),
            store_config.get('desc', '')
        ))


def create_store(name, store_type, priority, desc, pattern, config):
    """Create a store object

    Args:
        name: Store name
        store_type: Type of store ('local', 'url', 'git-release')
        priority: Priority (lower is tried first)
        desc: Description
        pattern: URL/path pattern with placeholders
        config: Additional store configuration

    Returns:
        BlobStore: A store object, or None if type is unknown
    """
    if store_type == 'local':
        return LocalBlobStore(name, priority, desc, pattern)
    elif store_type in ('url', 'git-release'):
        return UrlBlobStore(name, priority, desc, pattern, config)
    elif store_type == 'build':
        return BuildBlobStore(name, priority, desc)
    else:
        tout.warning(f"Unknown store type: {store_type}")
        return None


class BlobStore:
    """Base class for blob stores

    A store represents a source from which blobs can be fetched.

    Attributes:
        name: Name of the store
        store_type: Type of store
        priority: Priority (lower numbers are tried first)
        desc: Description of the store
    """

    def __init__(self, name, store_type, priority, desc):
        """Create a new BlobStore

        Args:
            name: Store name
            store_type: Type of store
            priority: Priority (lower is tried first)
            desc: Description
        """
        self.name = name
        self.store_type = store_type
        self.priority = priority
        self.desc = desc

    def fetch(self, compatible, version, arch, plat, fname=None):
        """Fetch a blob from this store

        Args:
            compatible: Compatible string
            version: Version to fetch
            arch: Target architecture
            plat: Target platform
            fname: File to fetch, for a blob type which provides several

        Returns:
            tuple:
                str: Path to fetched file
                str: Temp directory to clean up, or None
            or None if fetch failed
        """
        raise NotImplementedError()

    @staticmethod
    def substitute_pattern(pattern, version, arch, plat, fname=None):
        """Substitute placeholders in a pattern

        Placeholders:
            {version} - Version string
            {arch} - Architecture
            {plat} - Platform
            {file} - Filename

        Args:
            pattern: Pattern string with placeholders
            version: Version string
            arch: Architecture
            plat: Platform
            fname: Filename

        Returns:
            str: Pattern with placeholders substituted
        """
        result = pattern
        for name, value in (('version', version), ('arch', arch),
                            ('plat', plat), ('file', fname)):
            if value:
                result = result.replace('{%s}' % name, value)
        return result


class LocalBlobStore(BlobStore):
    """Store that fetches blobs from local directories"""

    def __init__(self, name, priority, desc, pattern):
        """Create a LocalBlobStore

        Args:
            name: Store name
            priority: Priority
            desc: Description
            pattern: Path pattern with placeholders
        """
        super().__init__(name, 'local', priority, desc)
        self.pattern = pattern

    def fetch(self, compatible, version, arch, plat, fname=None):
        """Fetch a blob from local directories

        Args:
            compatible: Compatible string
            version: Version to fetch
            arch: Target architecture
            plat: Target platform
            fname: File to fetch, for a blob type which provides several

        Returns:
            tuple: (filepath, None) if found, or None
        """
        path = self.substitute_pattern(self.pattern, version, arch, plat,
                                       fname)
        path = os.path.expanduser(path)

        if os.path.exists(path):
            tout.info(f"Found blob at '{path}'")
            return path, None

        tout.debug(f"Blob not found at '{path}'")
        return None


class UrlBlobStore(BlobStore):
    """Store that fetches blobs from URLs"""

    def __init__(self, name, priority, desc, pattern, config):
        """Create a UrlBlobStore

        Args:
            name: Store name
            priority: Priority
            desc: Description
            pattern: URL pattern with placeholders
            config: Additional configuration (may contain 'repo' for git-release)
        """
        super().__init__(name, 'url', priority, desc)
        self.pattern = pattern
        self.config = config

    def fetch(self, compatible, version, arch, plat, fname=None):
        """Fetch a blob from a URL

        Args:
            compatible: Compatible string
            version: Version to fetch
            arch: Target architecture
            plat: Target platform
            fname: File to fetch, for a blob type which provides several

        Returns:
            tuple: (filepath, tmpdir) if fetched, or None
        """
        # Build the URL
        repo = self.config.get('repo', '')
        if repo and not self.pattern.startswith('http'):
            url = f"{repo.rstrip('/')}/{self.pattern}"
        else:
            url = self.pattern

        url = self.substitute_pattern(url, version, arch, plat, fname)

        try:
            tout.info(f"Fetching from '{url}'")
            return download(url)
        except OSError as exc:
            tout.warning(f"Failed to fetch from '{url}': {exc}")
            return None


class BuildBlobStore(BlobStore):
    """Store that delegates to the blob handler's build() method"""

    def __init__(self, name, priority, desc):
        """Create a BuildBlobStore

        Args:
            name: Store name
            priority: Priority
            desc: Description
        """
        super().__init__(name, 'build', priority, desc)

    def fetch(self, compatible, version, arch, plat, fname=None):
        """Fetch by building from source

        This delegates to the blob handler's build() method.

        Args:
            compatible: Compatible string
            version: Version to build
            arch: Target architecture
            plat: Target platform
            fname: File to fetch (unused, since the handler builds the blob)

        Returns:
            tuple: (filepath, tmpdir) if built, or None
        """
        from binman import blob

        try:
            handler = blob.Blob.create(compatible)
            return handler.build(version, arch, plat)
        except Exception as exc:
            tout.debug(f"Failed to build '{compatible}': {exc}")
            return None
