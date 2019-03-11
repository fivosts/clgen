# Copyright 2014-2020 Chris Cummins <chrisc.101@gmail.com>.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""A hash cache for the filesystem.

Checksums files and directories and cache results. If a file or directory has
not been modified, subsequent hashes are cache hits. Hashes are recomputed
lazily, when a directory (or any of its subdirectories) have been modified.
"""
<<<<<<< HEAD:labm8/py/hashcache.py
=======

import collections
>>>>>>> 1eed6e90b... Automated code format.:lib/labm8/hashcache.py
import os
import pathlib
import subprocess
import time
import typing

import checksumdir
<<<<<<< HEAD:labm8/py/hashcache.py
<<<<<<< HEAD:labm8/py/hashcache.py
=======
import humanize
>>>>>>> 1eed6e90b... Automated code format.:lib/labm8/hashcache.py
=======
>>>>>>> 5feb1d004... Replace third party humanize with own module.:labm8/hashcache.py
import sqlalchemy as sql
<<<<<<< HEAD:labm8/py/hashcache.py
<<<<<<< HEAD:labm8/py/hashcache.py
from sqlalchemy.ext import declarative

from labm8.py import app
from labm8.py import crypto
from labm8.py import fs
from labm8.py import humanize
from labm8.py import sqlutil
=======
from absl import flags
from absl import logging
from phd.lib.labm8 import crypto
from phd.lib.labm8 import fs
from phd.lib.labm8 import sqlutil
from sqlalchemy.ext import declarative

<<<<<<< HEAD:labm8/py/hashcache.py
>>>>>>> 386c66354... Add 'phd' prefix to labm8 imports.:lib/labm8/hashcache.py

FLAGS = app.FLAGS

Base = declarative.declarative_base()


class InMemoryCacheKey(typing.NamedTuple):
  """An in-memory cache which is optionally shared amongst all HashCache
  instances. The in-memory cache omits timestamps from records.
  """

  hash_fn: str
  path: str


=======
=======
from sqlalchemy.ext import declarative

from labm8 import app
>>>>>>> 89b790ba9... Merge absl logging, app, and flags modules.:labm8/hashcache.py
from labm8 import crypto
from labm8 import fs
from labm8 import humanize
from labm8 import sqlutil


FLAGS = app.FLAGS

Base = declarative.declarative_base()

# An in-memory cache which is optionally shared amongst all HashCache instances.
# The in-memory cache omits timestamps from records.
InMemoryCacheKey = collections.namedtuple('InMemoryCacheKey',
                                          ['hash_fn', 'path'])
>>>>>>> 150d66672... Auto format files.:labm8/hashcache.py
IN_MEMORY_CACHE: typing.Dict[InMemoryCacheKey, str] = {}


class HashCacheRecord(Base):
  """A hashed file or directory."""

  __tablename__ = "entries"

  # The absolute path to a file or directory.
  absolute_path: str = sql.Column(sql.String(4096), primary_key=True)
  # The number of seconds since the epoch that the file or directory was last
  # modified.
  last_modified: int = sql.Column(sql.Integer, nullable=False)
  # The cached hash in hexadecimal encoding. We use the length of the longest
  # supported hash function: sha256.
  hash: str = sql.Column(sql.String(64), nullable=False)


def GetDirectoryMTime(path: pathlib.Path) -> int:
  """Get the timestamp of the most recently modified file/dir in directory.

  Recursively checks subdirectory contents. This requires that the directory
  exists and is not empty.

  Params:
    abspath: The absolute path to the directory.

  Returns:
    The seconds since epoch of the last modification.
  """
  # Pure python implementation.
  # return int(max(
  #     max(os.path.getmtime(os.path.join(root, file)) for file in files) for
  #     root, _, files in os.walk(path)))
  # Faster implementation using UNIX tools. Requires GNU tools. On macOS, this
  # means having some homebrew package installed:
  #
  #    $ brew install findutils coreutils
  #
  # and the following directory in your PATH:
  #    /usr/local/opt/findutils/libexec/gnubin
  #    /usr/local/opt/coreutils/libexec/gnubin
  output = subprocess.check_output(
<<<<<<< HEAD:labm8/py/hashcache.py
    f"find '{path}' -type f | xargs -d'\n' stat -c '%Y:%n' | sort -t: -n | "
    "tail -1 | cut -d: -f1",
    universal_newlines=True,
    shell=True,
  )
=======
      f"find '{path}' -type f | xargs -d'\n' stat -c '%Y:%n' | sort -t: -n | "
      "tail -1 | cut -d: -f1",
      universal_newlines=True,
      shell=True)
>>>>>>> 150d66672... Auto format files.:labm8/hashcache.py
  return int(output)


class HashCache(sqlutil.Database):
<<<<<<< HEAD:labm8/py/hashcache.py
  def __init__(
    self, path: pathlib.Path, hash_fn: str, keep_in_memory: bool = False,
  ):
=======

  def __init__(self,
               path: pathlib.Path,
               hash_fn: str,
               keep_in_memory: bool = False):
>>>>>>> 150d66672... Auto format files.:labm8/hashcache.py
    """Instantiate a hash cache.

    Args:
      path:
      hash_fn: The name of the hash function. One of: md5, sha1, sha256.
      keep_in_memory: If True, hashes are kept in memory for the lifespan
        of the process, or until Clear() is called on any HashCache instance.
        Use this with caution, as the in-memory cache does not invalidate
        entries, so cache entries can become stale.

    Raises:
      ValueError: If hash_fn not recognized.
    """
<<<<<<< HEAD:labm8/py/hashcache.py
<<<<<<< HEAD:labm8/py/hashcache.py
    super(HashCache, self).__init__(f"sqlite:///{path.absolute()}", Base)
=======
    super(HashCache, self).__init__(
        f'sqlite:///{path}', Base, create_if_not_exist=True)
>>>>>>> bea7be482... Add MySQL and PostgreSQL to sqlutil.Database.:labm8/hashcache.py
=======
    super(HashCache, self).__init__(f'sqlite:///{path.absolute()}', Base)
>>>>>>> 234add195... Updates for sqlutil.Database API changes.:labm8/hashcache.py
    self.hash_fn_name = hash_fn
    if hash_fn == "md5":
      self.hash_fn_file = crypto.md5_file
    elif hash_fn == "sha1":
      self.hash_fn_file = crypto.sha1_file
    elif hash_fn == "sha256":
      self.hash_fn_file = crypto.sha256_file
    else:
      raise ValueError(f"Hash function not recognized: '{hash_fn}'")
    self.keep_in_memory = keep_in_memory

  def GetHash(self, path: pathlib.Path) -> str:
    """Get the hash of a file or directory.

    This method is O(n) with respect to the number of files in the directory.
    The first time this is called for a directory, this method must read every
    file in the directory. For subsequent calls, this method must check the
    mtime of every file.

    Note that the a file's mtime is used to determine cache hits. This uses
    second granularity, so if a file has been modified within a second, this
    method will erroneously return the cached checksum of the previous version.

    Args:
      path: Path to the file or directory.

    Returns:
      Hexadecimal string hash.

    Raises:
      FileNotFoundError: If the requested path does not exist.
    """
    if path.is_file():
      return self._HashFile(path)
    elif path.is_dir():
      return self._HashDirectory(path)
    else:
      raise FileNotFoundError(f"File not found: '{path}'")

  def Clear(self):
    """Empty the cache.

    If the HashCache was created with keep_in_memory=True, this clears the
    in-memory cache. Note that the in-memory cache is shared between all
    instances of HashCache.
    """
    IN_MEMORY_CACHE.clear()
    with self.Session(commit=True) as session:
      session.query(HashCacheRecord).delete()
<<<<<<< HEAD:labm8/py/hashcache.py
<<<<<<< HEAD:labm8/py/hashcache.py
    app.Log(2, "Emptied cache")
=======
    app.Debug('Emptied cache')
>>>>>>> 89b790ba9... Merge absl logging, app, and flags modules.:labm8/hashcache.py
=======
    app.Log(2, 'Emptied cache')
>>>>>>> 79a426895... Update logging API and implement --vmodule.:labm8/hashcache.py

  def _HashDirectory(self, absolute_path: pathlib.Path) -> str:
    if fs.directory_is_empty(absolute_path):
      last_modified_fn = lambda path: int(time.time())
    else:
      last_modified_fn = lambda path: GetDirectoryMTime(path)
    return self._InMemoryWrapper(
<<<<<<< HEAD:labm8/py/hashcache.py
      absolute_path,
      last_modified_fn,
      lambda x: checksumdir.dirhash(x, self.hash_fn_name),
    )
=======
        absolute_path,
        last_modified_fn, lambda x: checksumdir.dirhash(x, self.hash_fn_name))
>>>>>>> 150d66672... Auto format files.:labm8/hashcache.py

  def _HashFile(self, absolute_path: pathlib.Path) -> str:
    return self._InMemoryWrapper(
      absolute_path,
      lambda path: int(os.path.getmtime(path)),
      self.hash_fn_file,
    )

  def _InMemoryWrapper(
    self,
    absolute_path: pathlib.Path,
    last_modified_fn: typing.Callable[[pathlib.Path], int],
    hash_fn: typing.Callable[[pathlib.Path], str],
  ) -> str:
    """A wrapper around the persistent hashing to support in-memory cache."""
    if self.keep_in_memory:
      in_memory_key = InMemoryCacheKey(self.hash_fn_name, absolute_path)
      if in_memory_key in IN_MEMORY_CACHE:
<<<<<<< HEAD:labm8/py/hashcache.py
<<<<<<< HEAD:labm8/py/hashcache.py
        app.Log(2, "In-memory cache hit: '%s'", absolute_path)
=======
        app.Debug("In-memory cache hit: '%s'", absolute_path)
>>>>>>> 89b790ba9... Merge absl logging, app, and flags modules.:labm8/hashcache.py
=======
        app.Log(2, "In-memory cache hit: '%s'", absolute_path)
>>>>>>> 79a426895... Update logging API and implement --vmodule.:labm8/hashcache.py
        return IN_MEMORY_CACHE[in_memory_key]
<<<<<<< HEAD:labm8/py/hashcache.py
    hash_ = self._DoHash(
      absolute_path, last_modified_fn(absolute_path), hash_fn,
    )
=======
    hash_ = self._DoHash(absolute_path, last_modified_fn(absolute_path),
                         hash_fn)
>>>>>>> 150d66672... Auto format files.:labm8/hashcache.py
    if self.keep_in_memory:
      IN_MEMORY_CACHE[in_memory_key] = hash_
    return hash_

<<<<<<< HEAD:labm8/py/hashcache.py
  def _DoHash(
    self,
    absolute_path: pathlib.Path,
    last_modified: int,
    hash_fn: typing.Callable[[pathlib.Path], str],
  ) -> str:
=======
  def _DoHash(self, absolute_path: pathlib.Path, last_modified: int,
              hash_fn: typing.Callable[[pathlib.Path], str]) -> str:
>>>>>>> 150d66672... Auto format files.:labm8/hashcache.py
    with self.Session() as session:
      cached_entry = (
        session.query(HashCacheRecord)
        .filter(HashCacheRecord.absolute_path == str(absolute_path),)
        .first()
      )
      if cached_entry and cached_entry.last_modified == last_modified:
<<<<<<< HEAD:labm8/py/hashcache.py
<<<<<<< HEAD:labm8/py/hashcache.py
        app.Log(2, "Cache hit: '%s'", absolute_path)
        return cached_entry.hash
      elif cached_entry:
        app.Log(2, "Cache miss: '%s'", absolute_path)
        session.delete(cached_entry)
      start_time = time.time()
      checksum = hash_fn(absolute_path)
<<<<<<< HEAD:labm8/py/hashcache.py
      app.Log(
        2,
        "New cache entry '%s' in %s ms.",
        absolute_path,
        humanize.Commas(int((time.time() - start_time) * 1000)),
      )
=======
      logging.debug("New cache entry '%s' in %s ms.", absolute_path,
                    humanize.Commas(int((time.time() - start_time) * 1000)))
>>>>>>> 5feb1d004... Replace third party humanize with own module.:labm8/hashcache.py
=======
        app.Debug("Cache hit: '%s'", absolute_path)
=======
        app.Log(2, "Cache hit: '%s'", absolute_path)
>>>>>>> 79a426895... Update logging API and implement --vmodule.:labm8/hashcache.py
        return cached_entry.hash
      elif cached_entry:
        app.Log(2, "Cache miss: '%s'", absolute_path)
        session.delete(cached_entry)
      start_time = time.time()
      checksum = hash_fn(absolute_path)
      app.Log(2, "New cache entry '%s' in %s ms.", absolute_path,
                humanize.Commas(int((time.time() - start_time) * 1000)))
>>>>>>> 89b790ba9... Merge absl logging, app, and flags modules.:labm8/hashcache.py
      new_entry = HashCacheRecord(
        absolute_path=str(absolute_path),
        last_modified=last_modified,
        hash=checksum,
      )
      session.add(new_entry)
      session.commit()
      return new_entry.hash
