# Copyright (c) 2016-2020 Chris Cummins.
#
# clgen is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# clgen is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with clgen.  If not, see <https://www.gnu.org/licenses/>.
"""Samplers for CLgen language models.

A Sampler is an object which, when passed to a mode's Sample() method,
determines the shape of the generated samples.
"""
import os
import datetime
import typing
import sqlalchemy as sql
from absl import flags
from sqlalchemy.ext import declarative

from deeplearning.clgen import cache
from deeplearning.clgen import pbutil
from deeplearning.clgen.corpuses import atomizers
from deeplearning.clgen.proto import sampler_pb2
from deeplearning.clgen.proto import internal_pb2

from labm8.py import crypto
from labm8.py import sqlutil

FLAGS = flags.FLAGS

Base = declarative.declarative_base()

def AssertConfigIsValid(config: sampler_pb2.Sampler) -> sampler_pb2.Sampler:
  """Assert that a sampler configuration contains no invalid values.

  Args:
    config: A sampler configuration proto.

  Returns:
    The sampler configuration proto.

  Raises:
    UserError: If there are configuration errors.
  """
  try:
    pbutil.AssertFieldConstraint(
      config,
      "start_text",
      lambda s: len(s),
      "Sampler.start_text must be a string",
    )
    pbutil.AssertFieldConstraint(
      config, "batch_size", lambda x: 0 < x, "Sampler.batch_size must be > 0"
    )
    pbutil.AssertFieldConstraint(
      config,
      "sequence_length",
      lambda x: 0 < x,
      "Sampler.sequence_length must be > 0",
    )
    pbutil.AssertFieldConstraint(
      config,
      "temperature_micros",
      lambda x: 0 < x,
      "Sampler.temperature_micros must be > 0",
    )
    return config
  except pbutil.ProtoValueError as e:
    raise ValueError(e)


class TerminationCriterionBase(object):
  """Base class for TerminationCriterion objects.

  A TerminationCriterion is an object with a single public function
  SampleIsComplete(), which accepts as its sole argument a sample-in-progress,
  and returns whether to stop sampling.
  """

  def Specialize(self, atomizer: atomizers.AtomizerBase) -> None:
    """Specialize a termination criteria to a vocabulary.

    This enables the termination criteria to set state specialized to a specific
    encoding vocabulary. This is guaranteed to be called before
    SampleIsComplete(), and ensures that the vocabulary used for all sample
    arguments to SampleIsComplete() is from this vocabulary.

    Args:
      atomizer: An atomizer to specialize to.
    """
    pass

  def SampleIsComplete(self, sample_in_progress: typing.List[str]) -> bool:
    """Determine whether to stop sampling.

    Args:
      sample_in_progress: A sample in progress, as a sequence of decoded tokens.

    Returns:
      True if the sample is "complete", else False to continue sampling.
    """
    raise NotImplementedError("abstract class")


class MaxlenTerminationCriterion(TerminationCriterionBase):
  """A termination criterion which limits the maximum length of a sample."""

  def __init__(self, config: sampler_pb2.MaxTokenLength):
    try:
      self.max_len = pbutil.AssertFieldConstraint(
        config,
        "maximum_tokens_in_sample",
        lambda x: x > 1,
        "MaxTokenLength.maximum_tokens_in_sample must be > 0",
      )
    except pbutil.ProtoValueError as e:
      raise ValueError(e)

  def SampleIsComplete(self, sample_in_progress: typing.List[str]) -> bool:
    """Determine whether to stop sampling."""
    return len(sample_in_progress) >= self.max_len


class SymmetricalTokenDepthCriterion(TerminationCriterionBase):
  """A termination criterion which counts symmetrical token depth.

  This is a generalization of bracked (i.e. { }) depth counting for C-syntax
  programming languages. When sampling to generate a C function, the sample
  is not "started" until the first { token is reached, and it is complete once
  the final } token has been emitted to close the function. In between those
  two tokens, there may be additional { } characters which increase and decrease
  the "depth" of the scope, respectively.
  """

  def __init__(self, config: sampler_pb2.SymmetricalTokenDepth):
    try:
      self.left_token = pbutil.AssertFieldConstraint(
        config,
        "depth_increase_token",
        lambda s: len(s) > 0,
        "SymmetricalTokenDepth.depth_increase_token must be a string",
      )
      self.right_token = pbutil.AssertFieldConstraint(
        config,
        "depth_decrease_token",
        lambda s: len(s) > 0,
        "SymmetricalTokenDepth.depth_decrease_token must be a string",
      )
    except pbutil.ProtoValueError as e:
      raise ValueError(e)
    if self.left_token == self.right_token:
      raise ValueError("SymmetricalTokenDepth tokens must be different")

  def Specialize(self, atomizer: atomizers.AtomizerBase) -> None:
    """Specialize a termination criteria to a vocabulary.

    This enables the termination criteria to set state specialized to a specific
    encoding vocabulary. This is guaranteed to be called before
    SampleIsComplete(), and ensures that the vocabulary used for all sample
    arguments to SampleIsComplete() is from this vocabulary.

    Args:
      atomizer: An atomizer to specialize to.

    Raises:
      InvalidSymtokTokens: If the depth tokens can't be encoded, or they encode
        to more than one token.
    """
    try:
      left = atomizer.AtomizeString(self.left_token)
      right = atomizer.AtomizeString(self.right_token)
      if len(left) > 1 or len(right) > 1:
        raise ValueError(
          "Sampler symmetrical depth tokens do not encode to a single "
          "token using the corpus vocabulary"
        )
    except ValueError:
      raise ValueError(
        "Sampler symmetrical depth tokens cannot be encoded using the "
        "corpus vocabulary"
      )

  def SampleIsComplete(self, sample_in_progress: typing.List[str]) -> bool:
    """Determine whether to stop sampling."""
    if len(sample_in_progress) == 0:
      return False
    if not sample_in_progress[-1] == self.right_token:
      return False
    return self.GetTokenDepth(sample_in_progress) == 0

  def GetTokenDepth(self, sample_in_progress: typing.List[str]) -> int:
    """Calculate the symmetrical token depth.

    The symmetrical token depth is the difference between the left and right
    token counts, provided that the last token is the right, left token count
    is nonzero, the right token count is less than the left token count. If
    either of those constraints are not met, the returned value is negative.
    """
    left_token_count = sample_in_progress.count(self.left_token)
    right_token_count = sample_in_progress.count(self.right_token)
    # We have descending into negative depth, so abort.
    if right_token_count and not left_token_count:
      return 0
    # We haven't started balancing the tokens yet.
    if not left_token_count:
      return -1
    return left_token_count - right_token_count


def GetTerminationCriteria(
  config: typing.List[sampler_pb2.SampleTerminationCriterion],
) -> typing.List[TerminationCriterionBase]:
  """Build a list of termination criteria from config protos.

  Args:
    config: A list of SampleTerminationCriterion protos.

  Returns:
    A list of TerminationCriterion instances.

  Raises:
    UserError: In case of invalid configs.
    InternalError: If any of the termination criteria are unrecognized.
  """
  terminators = []
  for criterion in config:
    if criterion.HasField("maxlen"):
      terminators.append(MaxlenTerminationCriterion(criterion.maxlen))
    elif criterion.HasField("symtok"):
      terminators.append(SymmetricalTokenDepthCriterion(criterion.symtok))
    else:
      raise SystemError("Unknown Sampler.termination_criteria")
  return terminators


class Sampler(object):
  """CLgen sampler for models.

  Please note sampler instances should be treated as immutable. Upon
  instantiation, a sampler's properties are used to determine its hash. If you
  modify a property after instantiation, the hash will be out of date, which
  can lead to bad things happening.
  """

  def __init__(self, config: sampler_pb2.Sampler):
    """Instantiate a sampler.

    Args:
      config: A Sampler message.

    Raises:
      TypeError: If the config argument is not a Sampler proto.
      UserError: If the config contains invalid values.
    """
    if not isinstance(config, sampler_pb2.Sampler):
      t = type(config).__name__
      raise TypeError(f"Config must be a Sampler proto. Received: '{t}'")
    self.config = sampler_pb2.Sampler()
    self.config.CopyFrom(AssertConfigIsValid(config))
    self.hash = self._ComputeHash(self.config)
    self.terminators = GetTerminationCriteria(self.config.termination_criteria)
    self.start_text = self.config.start_text
    self.temperature = self.config.temperature_micros / 1e6
    self.batch_size = self.config.batch_size
    self.sequence_length = self.config.sequence_length
    
    # Create the necessary cache directories.
    self.cache = cache.mkcache("sampler", self.hash)
    self.samples_directory = self.cache.path / "samples"
    self.samples_directory.mkdir(exist_ok=True)
    
    meta = internal_pb2.SamplerMeta()
    meta.config.CopyFrom(self.config)
    pbutil.ToFile(meta, path = self.cache.path / "META.pbtxt")
    
    # Set in Specialize().
    self.encoded_start_text = None
    self.tokenized_start_text = None
    # Set in initSampleDB
    self.sample_db = None
    self.db_name   = None
    self.db_path   = None

  def Specialize(self, atomizer: atomizers.AtomizerBase) -> None:
    """Specialize a sampler a vocabulary.

    This enables the sampler to set state specialized to a specific encoding
    vocabulary. This is guaranteed to be called before SampleIsComplete(), and
    ensures that the vocabulary used for all sample arguments to
    SampleIsComplete() is from this vocabulary.

    Args:
      atomizer: An atomizer to specialize to.

    Raises:
      InvalidStartText: If the start_text cannot be encoded using the
        vocabulary.
      UserError: In case the sampler cannot be specialized to this vocabulary.
    """
    try:
      self.encoded_start_text = atomizer.AtomizeString(self.start_text)
      self.tokenized_start_text = atomizer.TokenizeString(self.start_text)
    except ValueError:
      raise ValueError(
        "Sampler start text cannot be encoded using the corpus vocabulary: "
        f"'{self.start_text}'"
      )

    if len(self.encoded_start_text) >= self.sequence_length:
      raise ValueError(
        "Encoded sampler start text must be less than sampler sequence "
        f"length. Sampler sequence length={self.sequence_length}, encoded "
        f"start text length={len(self.encoded_start_text)}"
      )

    [terminator.Specialize(atomizer) for terminator in self.terminators]

  def initSampleDB(self, 
                   url_path   : str, 
                   db_name    : str = "samples.db", 
                   must_exist : bool = False
                   ) -> None:
    """Initialize sampling file database"""
    self.db_name   = db_name
    self.db_path   = url_path
    self.sample_db = SamplerDB(url_path, db_name, must_exist)
    return

  def symlinkModelDB(self,
                     model_hash: int,
                     ) -> None:
    """
    Create symbolic link entry in sampler workspace. In one 
    model's workspace, there is one sampler.dbfor each different
    sampler. Each sampler holds a directory of all models it has 
    sampled with symbolic links created in this function.
    """
    (self.samples_directory / model_hash).mkdir(exist_ok = True)
    symlink = self.samples_directory / model_hash / self.db_name
    if not symlink.is_symlink():
      os.symlink(
        os.path.relpath(
          self.db_path / self.db_name,
          self.samples_directory / model_hash
        ),
        symlink
      )
    return
  
  @property
  def db(self):
    return self.sample_db

  @property
  def db_file_count(self):
    if self.db is None:
      return 0
    else:
      return self.db.file_count
  
  def SampleIsComplete(self, sample_in_progress: typing.List[str]) -> bool:
    """Determine whether to stop sampling.

    Args:
      sample_in_progress: A sample in progress, as a sequence of decoded tokens.

    Returns:
      True if the sample is "complete", else False to continue sampling.
    """
    return any(t.SampleIsComplete(sample_in_progress) for t in self.terminators)

  @staticmethod
  def _ComputeHash(config: sampler_pb2.Sampler) -> str:
    """Compute sampler hash.

    The hash is computed from the serialized representation of the config
    proto.
    """
    return crypto.sha1(config.SerializeToString())

  def __eq__(self, rhs) -> bool:
    if not isinstance(rhs, Sampler):
      return False
    return rhs.hash == self.hash

  def __ne__(self, rhs) -> bool:
    return not self.__eq__(rhs)

class SamplerDBFile(Base):
  """Single inference file entry"""
  __tablename__ = "inference_contentfiles"

  # The ID of the PreprocessedContentFile.
  id               : int = sql.Column(sql.Integer, primary_key=True)
  # We store the vocabulary indices array as a string of period-separated
  # integers, e.g. '0.1.2.0.1'. To access the values as an array of integers,
  # use SamplerDBFile.indices_array.
  encoded_text     : str = sql.Column(sqlutil.ColumnTypes.UnboundedUnicodeText(), nullable = False)
  text             : str = sql.Column(sqlutil.ColumnTypes.UnboundedUnicodeText(), nullable = False)
  num_tokens       : int = sql.Column(sql.Integer, nullable=False)
  # The number of milliseconds encoding took.
  sample_time_ms   : int = sql.Column(sql.Integer, nullable=False)
  # Encoding is parallelizable, so the actual wall time of encoding may be much
  # less than the sum of all encoding_time_ms. This column counts the effective
  # number of "real" milliseconds during encoding between the last encoded
  # result and this result coming in. The idea is that summing this column
  # provides an accurate total of the actual time spent encoding an entire
  # corpus. Will be <= encoding_time_ms.
  wall_time_ms     : int = sql.Column(sql.Integer, nullable=False)
  date_added       : datetime.datetime = sql.Column(sql.DateTime, nullable=False)

class SamplerDB(sqlutil.Database):
  """A database of sampling inference files."""
  def __init__(self, 
               url_path   : str, 
               db_name    : str = "samples.db", 
               must_exist : bool = False
              ) -> None:
    url = "sqlite:///{}".format(str(url_path / db_name))
    super(SamplerDB, self).__init__(url, Base, must_exist = must_exist)

  @property
  def file_count(self):
    """Return the total number of files in the encoded corpus."""
    with self.Session() as session:
      return session.query(SamplerDBFile).count()

  @property
  def token_count(self) -> int:
    """Return the total number of tokens in the encoded corpus.

    This excludes the EOF markers which are appended to each encoded text.
    """
    with self.Session() as session:
      return session.query(func.sum(SamplerDBFile.tokencount)).scalar()
