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
"""This file contains the definition of tokenizers.

An tokenizer converts a block of text into a sequence of vocbulary tokens.
"""
import pathlib
import pickle
import typing
import json
import multiprocessing
import progressbar
import functools
import numpy as np
from collections import Counter
from absl import flags
from eupy.native import logger as l

from deeplearning.clgen.preprocessors import opencl

FLAGS = flags.FLAGS

def FromText(config, contentfile_separator: str, corpus_txt: str):
  mask_tokens = False if config.mask_tokens is None else config.mask_tokens

  if config.token_type   == "character":
    if config.token_list:
      l.getLogger().warning("token list in character-based tokenization is going to be ignored.")
    return AsciiCharacterTokenizer.FromText(corpus_txt, mask_tokens)
  elif config.token_type == "word":
    with open(config.token_list, 'r') as f:
      token_set = json.load(f)
      token_set = set(token_set['opencl']['tokens'])
    wpc_tok = False if config.wordpiece_tokenization is None else config.wordpiece_tokenization
    return WordTokenizer.FromText(corpus_txt,
                                 token_set, 
                                 mask_tokens, 
                                 wpc_tok
                                )
  elif config.token_type == "ast":
    if config.token_list:
      with open(config.token_list, 'r') as f:
        token_set = json.load(f)
        token_set = set(token_set['opencl']['tokens'])
    else:
      token_set = set()
    return ASTokenizer.FromText(corpus_txt, token_set, contentfile_separator, mask_tokens)
  else:
    raise NotImplementedError

class TokenizerBase(object):
  """The base class for implementing tokenizers."""

  @property
  def atoms(self) -> typing.List[str]:
    """A list of atoms in the vocabulary."""
    return list(sorted(self.vocab.keys()))

  @property
  def indices(self) -> typing.List[int]:
    """A list of vocabulary indices."""
    return list(sorted(self.vocab.values()))

  @classmethod
  def FromText(cls, text: str) -> "TokenizerBase":
    """Instantiate and specialize an tokenizer from a corpus text.

    Args:
      text: Text corpus

    Returns:
      An tokenizer instance.
    """
    raise NotImplementedError("abstract class")

  @classmethod
  def FromFile(cls, path: pathlib.Path) -> "TokenizerBase":
    """Load an tokenizer from file."""
    with open(path, "rb") as infile:
      return pickle.load(infile)

  def __init__(self, 
               vocab: typing.Dict[str, int],
               metaTokens: typing.Dict[str, str],
               ):
    """Instantiate an tokenizer.

    Args:
      vocab: A dictionary of mappings from character sequences (atoms) into
        indices.
      metaTokens: A dictionary mapping the metaTokens needed for tokenization.
        (Used when masking is selected)
    Raises:
      TypeError: If vocab is not a dictionary.
      ValueError: If the dictionary of mappings includes any duplicate values.
    """
    self.vocab      = vocab
    self.metaTokens = metaTokens
    self._UpdateVocabulary()
    self.metaTokenValues = set(value for key, value in self.__dict__.items() if key in self.metaTokens)

  def _UpdateVocabulary(self) -> None:
    """Private method which must be called if vocab is modified."""
    if not isinstance(self.vocab, dict):
      raise TypeError("vocabulary must be a dict")

    # Each atom and index must be unique to ensure deterministic encoding.
    if len(set(self.vocab.keys())) != len(self.vocab):
      raise ValueError("all atoms must be unique")
    if len(set(self.vocab.values())) != len(self.vocab):
      raise ValueError("all indices must be unique")

    self.vocab_size = len(self.vocab)
    self.decoder = {val: key for key, val in self.vocab.items()}
    # Set arbitrary object properties for meta tokens.
    self.__dict__.update({x: self.vocab[y] for x, y in self.metaTokens.items()})

  def ToFile(self, path: pathlib.Path) -> None:
    """Save an tokenizer to file."""
    with open(path, "wb") as f:
      pickle.dump(self, f)

  def TokenizeString(self, text: str) -> np.array:
    """Tokenize a text into an array of vocabulary indices.

    Args:
      text: Input text.

    Returns:
      An array of indices into vocabulary for all atoms in text.

    Raises:
      VocabError: If the input text contains elements not in the vocabulary.
    """
    raise NotImplementedError("abstract class")

  def AtomizeString(self, text: str) -> typing.List[str]:
    """Split the text into atoms, but do not encode to indices.

    Args:
      text: Input text.

    Returns:
      A list of tokens.
    """
    indices = self.TokenizeString(text)
    return list(map(lambda x: self.decoder[x], indices))

  def tokensToString(self, 
                     encoded: np.array,
                     ignore_token: int = None,
                     with_formatting: bool = False,
                     ):
    """Translate atomized code back into a string.

    Args:
      encoded: An nparray of encoded vocabulary indices.
      ignore_token: A specific token to ignore from the text string (e.g. exclude pads)
      with_formatting: Bool flag used to run clang format on stringified kernel. Used only in AST tokenizer.
    Returns:
      The decoded text.
      Returns string if nparray is one-dimensional.
      Else returns list for each extra dimension of strings.
    """
    try:
      if np.ndim(encoded) > 1:
        return [ self.tokensToString(x, ignore_token) for x in encoded ]
      elif np.ndim(encoded) == 1:
        return "".join(list(map(lambda x: self.decoder[x] if x != ignore_token else '', encoded)))
      else:
        raise ValueError("Wrong encoded array specified")
    except KeyError:
      raise KeyError("Out of vocab: {}".format(encoded))

  def ArrayToCode(self,
                  encoded: np.array,
                  with_formatting: bool = False,
                  ) -> str:
    """
    Convert encoded array to compilable code.
    Removes meta tokens and converts to string.

    Args:
      encoded: nparray of encoded vocabulary indices.
    Returns:
      Code in string format.
    """
    return self.tokensToString(
              [x for x in encoded if x not in self.metaTokenValues],
              with_formatting = with_formatting
            )

  def StringArrToCode(self,
                      text: typing.List[str],
                      with_formatting: bool = False,
                      ) -> str:
    """
    Convert string array to compilable code.
    Removes meta tokens.

    Args:
      text: String representation of encoded array. (May contain metaTokens)
      with_formatting: Select to run code through clang-format. Only usable in ASTokenizer
    Returns:
      Code in string format.
    """
    mtstr = set(self.metaTokens.values())
    return ''.join([x for x in text if x not in mtstr])

  def SrcLocationToIndex(self,
                         encoded: np.array,
                         locations: typing.List[typing.Tuple[int, int]],
                         ) -> typing.List[int]:
    """
    Maps line-column src location to corresponding token of encoded array.

    Args:
      encoded: np array encoded representation of a kernel.
      locations: list of tuples representing line-column locations in str-formatted code.

    Returns:
      List of indices pointing to mapped tokens in the sequence.
    """
    indices = []
    str_atoms = [self.tokensToString([token]) for token in encoded]
    lidx, cidx = 1, 1
    locit = iter(locations)
    try:
      l, c = next(locit)
    except StopIteration:
      return indices
    for i, token in enumerate(str_atoms):
      if token in self.metaTokens.values():
        pass
      elif token == "\n\n":
        lidx += 2
        cidx = 1
      elif token == "\n":
        lidx += 1
        cidx = 1
      else:
        cidx += len(token)

      if lidx == l and cidx > c:
        indices.append(i)
        try:
          l, c = next(locit)
        except StopIteration:
          break

    return indices

class AsciiCharacterTokenizer(TokenizerBase):
  """An tokenizer for character-level syntactic modelling."""

  @classmethod
  def FromText(cls, text: str, mask_tokens: bool) -> "AsciiCharacterTokenizer":
    """Instantiate and an tokenizer from a corpus text.

    Args:
      text: Text corpus.

    Returns:
      An tokenizer instance.
    """
    if mask_tokens:
      metaTokens = {
          'startToken'   : '[START]',
          'endToken'     : '[END]',
          'padToken'     : '[PAD]',
          'maskToken'    : '[MASK]',
          'holeToken'    : '[HOLE]',
          'endholeToken' : '[ENDHOLE]',
      }
    else:
      metaTokens = {}
    counter = Counter(text)
    count_pairs = sorted(counter.items(), key=lambda x: -x[1])
    atoms, _ = zip(*count_pairs)
    atoms = tuple(metaTokens.values()) + atoms
    vocab = dict(zip(atoms, range(len(atoms))))
    return AsciiCharacterTokenizer(vocab, metaTokens)

  def __repr__(self) -> str:
    return f"AsciiCharacterTokenizer[{self.vocab_size} chars]"

  def TokenizeString(self, text: str) -> np.array:
    """Tokenize a text into an array of vocabulary indices.

    Args:
      text: Input text.

    Returns:
      An array of indices into vocabulary for all atoms in text.
    """
    try:
      if not self.metaTokens:
        return np.array(list(map(lambda x: self.vocab[x], text)), dtype=np.int32)
      else:
        encoded = []
        skipNext = 0
        for idx, char in enumerate(text):
          if skipNext > 0:
            skipNext -= 1
            continue
          if char == '[':
            for meta in self.metaTokens.values():
              if text[idx: idx + len(meta)] == meta:
                encoded.append(self.vocab[meta])
                skipNext = len(meta) - 1
                break
          if skipNext == 0:
            encoded.append(self.vocab[char])
        return np.array(encoded, dtype = np.int32)
    except KeyError:
      raise ValueError("OoV index in string tokenizing.")

class WordTokenizer(TokenizerBase):
  """A greedy tokenizer supports multi-character tokens."""

  @classmethod
  def FromText(cls,
               text: str,
               token_list: typing.Set[str],
               mask_tokens: bool,
               wordpiece: bool,
               ) -> "WordTokenizer":
    """Instantiate and an tokenizer from a corpus text.

    Args:
      text: Text corpus
      token_list: A list of multi-character token_list.

    Returns:
      An tokenizer instance.
    """
    if not token_list:
      raise ValueError("No tokens specified")

    if wordpiece:
      raise NotImplementedError

    if mask_tokens:
      metaTokens = {
          'startToken'   : '[START]',
          'endToken'     : '[END]',
          'padToken'     : '[PAD]',
          'maskToken'    : '[MASK]',
          'holeToken'    : '[HOLE]',
          'endholeToken' : '[ENDHOLE]',
      }
    else:
      metaTokens = {}
    # Add meta token_list to token set
    for mt in metaTokens.values():
      token_list.add(mt)
    # Instantiate a greedy tokenizer using the full vocabulary.
    full_vocab = dict(zip(token_list, range(len(token_list))))
    c = WordTokenizer(full_vocab, metaTokens, determine_chars=True)
    # Derive the subset of the vocabulary required to encode the given text.
    tokens = [mt for mt in metaTokens.values()] + sorted(list(set(c.AtomizeString(text))))
    vocab_subset = dict(zip(tokens, range(len(tokens))))
    # Return a new tokenizer using the subset vocabulary.
    return WordTokenizer(vocab_subset, metaTokens)

  def __init__(self, 
               vocab:      typing.Dict[str, int], 
               metaTokens: typing.Dict[str, str],
               determine_chars = False
               ):
    super(WordTokenizer, self).__init__(vocab, metaTokens)

    self.determine_chars = determine_chars
    multichars = set(k for k in self.atoms if len(k) > 1)
    first_chars = set(a[0] for a in multichars)
    self.lookup = dict(
      (c, [a for a in multichars if a[0] == c]) for c in first_chars
    )

  def __repr__(self) -> str:
    return f"WordTokenizer[{self.vocab_size} tokens]"

  def TokenizeString(self, text: str) -> np.array:
    """Tokenize a text into an array of vocabulary indices.

    Args:
      text: Input text.

    Returns:
      An array of indices into vocabulary for all atoms in text.
    """

    def _AddToVocab(token: str) -> int:
      """Add a token to the vocabulary and return its index."""
      if self.determine_chars and token not in self.vocab:
        max_index = max(self.vocab.values())
        self.vocab[token] = max_index + 1
      return self.vocab[token]

    indices = []
    i = 0
    j = 2
    try:
      while i < len(text):
        if self.lookup.get(text[i]):
          if j <= len(text) and any(
            x.startswith(text[i:j]) for x in self.lookup[text[i]]
          ):
            j += 1
          else:
            while j > i + 1:
              if any(x == text[i:j] for x in self.lookup[text[i]]):
                indices.append(self.vocab[text[i:j]])
                i = j
                j += 2
                break
              else:
                j -= 1
            else:
              indices.append(_AddToVocab(text[i]))
              i += 1
              j += 2
        else:
          indices.append(_AddToVocab(text[i]))
          i += 1
          j += 2
    except KeyError:
      raise ValueError

    if self.determine_chars:
      self._UpdateVocabulary()

    return np.array(indices, dtype=np.int32)

class ASTokenizer(TokenizerBase):
  """A Clang AST tokenizer fully supports language grammar."""

  @classmethod
  def FromText(cls,
               text: str,
               token_set: typing.Set[str],
               contentfile_separator: str,
               mask_tokens: bool,
               ) -> "ASTokenizer":
    """Instantiate an AST tokenizer from a corpus text.

    Args:
      text: Text corpus
      token_set: Pre-defined grammar keywords of target language.

    Returns:
      An tokenizer instance.
    """
    if mask_tokens:
      metaTokens = {
          'startToken'   : '[START]',
          'endToken'     : '[END]',
          'padToken'     : '[PAD]',
          'maskToken'    : '[MASK]',
          'holeToken'    : '[HOLE]',
          'endholeToken' : '[ENDHOLE]',
      }
    else:
      metaTokens = {}

    token_list, source_tokens = set(), {}
    chunked_text  = text.split(contentfile_separator)
    bar           = progressbar.ProgressBar(max_value=len(chunked_text))
    pool          = multiprocessing.Pool()
    try:
      for tl in bar(pool.imap_unordered(functools.partial(opencl.DeriveSourceVocab, token_list = token_set), chunked_text)):
        source_tokens.update(tl)
      pool.close()
    except Exception as e:
      pool.terminate()
      raise e
    except KeyboardInterrupt as e:
      pool.terminate()
      raise e

    # source_tokens = opencl.DeriveSourceVocab(text, token_set)
    for mt in metaTokens.values():
      source_tokens[mt] = ''
      token_list.add(mt)
    token_list.update(source_tokens.keys())

    # Create full vocab and initialize AST tokenizer.
    full_vocab = dict(zip(token_list, range(len(token_list))))
    return ASTokenizer(full_vocab, metaTokens, source_tokens)

  def __init__(self, 
               vocab:      typing.Dict[str, int], 
               metaTokens: typing.Dict[str, str],
               token_del:  typing.Dict[str, str],
               ):
    super(ASTokenizer, self).__init__(vocab, metaTokens)
    self.decoder_with_delim = {
      self.vocab[k]: "{}{}".format(k.replace('-char-based', '').replace('\\', '\\\\'), v)
      for k, v in token_del.items()
    }
    """
    A little legend...
    self.vocab              : raw_string    -> encoded_value. e.g. 0-char-based: 1243
    self.decoder            : encoded_value -> raw_string.    e.g. 1243: 0-char-based
    token_del               : raw_string    -> delimiter.     e.g. 0-char-based: ''
    self.decoder_with_delim : encoded_value -> pretty_string. e.g. 1243: '0'
    """
    return

  def ManualTokenizeString(self, text: str) -> np.array:
    """Tokenize a text into an array of vocabulary indices.
    !!! This is a manual parser, which is now deprecated.
    Use regular TokenizeString below.
    Args:
      text: Input text.

    Returns:
      An array of indices into vocabulary for all atoms in text.
    """
    indices = []
    l_idx, r_idx = 0, 1
    inside_string, inside_char = False, False
    cb_del = "-char-based"
    while l_idx < len(text):
    # for idx, ch in enumerate(text):
      if text[l_idx] == '"' and not inside_char:# and (l_idx == 0 or text[l_idx - 1] != '\\'):
        inside_string ^= True
        try:
          indices.append(self.vocab["{}{}".format(text[l_idx], cb_del)])
        except KeyError:
          raise ValueError("-{}- char out of vocabulary.".format(text[l_idx]))
        l_idx += 1
      elif text[l_idx] == "'" and not inside_string:# and (l_idx == 0 or text[l_idx - 1] != '\\'):
        inside_char ^= True
        try:
          indices.append(self.vocab["{}{}".format(text[l_idx], cb_del)])
        except KeyError:
          raise ValueError("-{}- char out of vocabulary.".format(text[l_idx]))
        l_idx += 1
      elif text[l_idx] == '\n':
        if inside_string or inside_char:
          indices.append(self.vocab["n-char-based"])            
        l_idx += 1
      elif text[l_idx] == '\t':
        if inside_string or inside_char:
          indices.append(self.vocab["t-char-based"])            
        l_idx += 1
      elif text[l_idx] == ' ' or text[l_idx] == '\\':
        if inside_string or inside_char:
          try:
            indices.append(self.vocab["{}{}".format(text[l_idx], cb_del)])
          except KeyError:
            raise ValueError("-{}- char out of vocabulary.".format(text[l_idx]))
        l_idx += 1
      else:
        r_idx = l_idx
        while not inside_char and not inside_string and r_idx < len(text) and text[r_idx] not in {' ', '\n', '(', ')', '{', '}', '[', ']', ';'}:
          # Some basic tokens that mean we can't have a unified token from l_idx->r_idx.
          # Also, no word-tokenization in string literals.
          r_idx += 1
        while r_idx > l_idx and text[l_idx:r_idx+1] not in self.vocab:
          r_idx -= 1

        if r_idx == l_idx:
          # Char-based vs word-based has to be evaluated.
          if (inside_char or inside_string) or text[l_idx] not in self.vocab:
            # That is definitely a string literal or there just not is a word entry in vocab.
            try:
              indices.append(self.vocab["{}{}".format(text[l_idx], cb_del)])
            except KeyError:
              raise ValueError("Inside string but out of vocab: -{}-\n{}".format(text[l_idx], text))
          elif ("{}{}".format(text[l_idx], cb_del) not in self.vocab) or r_idx + 1 >= len(text):
            # End of file for some reason, or just there is no char-based entry.
            try:
              indices.append(self.vocab[text[l_idx]])
            except KeyError:
              raise ValueError("End of file, out of vocab: -{}-".format(text[l_idx]))
          elif text[l_idx].isalnum():
            # Char-based special chars can only be in strings.
            # Any other char-based token found must be alphanumerical.
            if text[l_idx+1].isalnum():
              try:
                indices.append(self.vocab["{}{}".format(text[l_idx], cb_del)])
              except KeyError:
                raise ValueError("Alnum out of vocab: -{}-".format(text[l_idx]))
              # print("This should def be a char-based.Why ? If current is char and next is char and should be word, why did you end up rejecting the curr+1 ?")
            elif text[l_idx - 1].isalnum() and text[l_idx] == 'e' and text[l_idx + 1] == '-':
              try:
                indices.append(self.vocab["{}{}".format(text[l_idx], cb_del)])
                indices.append(self.vocab["{}{}".format(text[l_idx+1], cb_del)])
                l_idx += 1
              except KeyError:
                raise ValueError("Floating exponent out of vocab: -{}-{}-".format(text[l_idx], text[l_idx+1]))
            elif text[l_idx+1] == '(' or text[l_idx+1] == '_':
              try:
                indices.append(self.vocab["{}{}".format(text[l_idx], cb_del)])
              except KeyError:
                raise ValueError("Alnum, next is '(' but is out of vocab: -{}-".format(text[l_idx]))
            else:
              try:
                indices.append(self.vocab[text[l_idx]])
              except KeyError:
                raise ValueError("Single-alnum word based out of vocab: -{}-".format(text[l_idx]))
          else:
            try:
              indices.append(self.vocab[text[l_idx]])
            except KeyError:
              raise ValueError("Single special char word-based out of vocab: -{}-".format(text[l_idx]))
          l_idx += 1
        else:
          if r_idx + 1 >= len(text):
            try:
              indices.append(self.vocab[text[l_idx:r_idx+1]])
            except KeyError:
              raise ValueError("String word in EOF not in vocab: -{}-".format(text[l_idx:r_idx+1]))
          elif (not text[r_idx].isalnum() and text[r_idx] != '_') or (not text[r_idx+1].isalnum() and text[r_idx+1] != '_'):
            try:
              indices.append(self.vocab[text[l_idx:r_idx+1]])
            except KeyError:
              raise ValueError("String word not in vocab: -{}-".format(text[l_idx:r_idx+1]))
          else:
            # a) we have space, next is alphanumerical or underscore
            # This is to catch a function call named intgetter() or int_getter().
            while r_idx + 1 < len(text) and text[r_idx+1].isalnum():
              r_idx += 1
            for i in range(l_idx, r_idx + 1):
              try:
                indices.append(self.vocab["{}{}".format(text[i], cb_del)])
              except KeyError:
                raise ValueError("Extended word {} to char-based letters out of vocab: -{}-".format(text[l_idx:r_idx+1], text[i]))
          l_idx = r_idx + 1
    return np.array(indices, dtype=np.int32)

  def TokenizeString(self, text: str) -> np.array:
    """Tokenize a text into an array of vocabulary indices.

    Args:
      text: Input text.

    Returns:
      An array of indices into vocabulary for all atoms in text.
    """
    return np.array([self.vocab[t] for t in self.AtomizeString(text)], dtype=np.int32)

  def AtomizeString(self, text: str) -> typing.List[str]:
    """Split the text into atoms, but do not encode to indices.

    Args:
      text: Input text.

    Returns:
      A list of tokens.

    Raises:
      ValueError: When a string atom does not belong in the vocabulary.
    """
    try:
      return [self.decoder[self.vocab[t]] for t in opencl.AtomizeSource(text, set(self.vocab.keys()))]
    except KeyError:
      raise ValueError("String index out of vocabulary")

  def tokensToString(self,
                     encoded: np.array,
                     ignore_token: int = None,
                     with_formatting: bool = False,
                     ):
    """Translate atomized code back into a string.

    Args:
      encoded: An nparray of encoded vocabulary indices.
      ignore_token: A specific token to ignore from the text string (e.g. exclude pads)
    Returns:
      The decoded text.
      Returns string if nparray is one-dimensional.
      Else returns list for each extra dimension of strings.
    """
    try:
      if np.ndim(encoded) > 1:
        return [ self.tokensToString(x, ignore_token = ignore_token, with_formatting = with_formatting)
                 for x in encoded ]
      elif np.ndim(encoded) == 1:
        if not with_formatting:
          src = []
          for idx in range(len(encoded)):
            if encoded[idx] == ignore_token:
              continue
            else:
              ct = self.decoder_with_delim[encoded[idx]]
              try:
                if (encoded[idx] in {self.vocab['e-char-based'], self.vocab['E-char-based']}
                  and encoded[idx+1] in {self.vocab['+'], self.vocab['-']}):
                  src.append(ct + " ")
                else:
                  src.append(ct)
              except IndexError:
                src.append(ct)
          src = "".join(src)
        else:
          src = opencl.ClangFormat("".join(list(map(lambda x: self.decoder_with_delim[x] if x != ignore_token else '', encoded))))
        return src
      else:
        raise ValueError("Wrong encoded array specified")
    except KeyError:
      raise KeyError("Out of vocab: {}".format(encoded))

  def StringArrToCode(self,
                      text: typing.List[str],
                      with_formatting: bool = False,
                      ) -> str:
    """
    Convert string array to compilable code.
    Removes meta tokens.

    Args:
      text: String representation of encoded array. (May contain metaTokens)
      with_formatting: Select to run code through clang-format. Only usable in ASTokenizer
    Returns:
      Code in string format.
    """
    mtstr = set(self.metaTokens.values())
    if with_formatting:
      return opencl.ClangFormat(''.join([self.decoder_with_delim[self.vocab[x]] for x in text if x not in mtstr]))
    else:
      return ''.join([self.decoder_with_delim[self.vocab[x]] for x in text if x not in mtstr])

  def SrcLocationToIndex(self,
                         encoded: np.array,
                         locations: typing.List[typing.Tuple[int, int]],
                         ) -> typing.List[int]:

    raise NotImplementedError("TODO")