import json
import numpy as np
import pathlib

from deeplearning.clgen import validation_database
from eupy.native import logger as l
from eupy.native import plotter as plt

class tensorMonitorHook(object):
  def __init__(self, 
               cache_path: pathlib.Path, 
               current_step: int, 
               step_freq: int,
               flush_freq: int = None,
               average: bool = True,
               ):
    self.cache_path   = cache_path
    self.current_step = current_step
    self.step_freq    = step_freq
    self.flush_freq   = flush_freq
    self.average      = average

    self.jsonfile         = cache_path / "training.json"
    self.tensors          = []
    self.plot_tensors     = {}
    self.epoch_tensors    = {}
    self.delay_checkpoint = True if current_step != 0 else False
    self._initTensors()

    self.monitor_func = [
      self._tensor2JSON,
      self._tensor2plot,
    ]
    return

  @property
  def current_loss(self):
    return self.tensors[-1]['total_loss']

  def step(self, **tensors):
    for key, value in tensors.items():
      if value is None:
        continue
      if key in self.epoch_tensors:
        self.epoch_tensors[key] += value
      else:
        self.epoch_tensors[key] = value

    if self._step_triggered():
      self._logTensors()
      self.epoch_tensors = {}
    return

  def _initTensors(self):
    if self.current_step > 0:
      if self.jsonfile.exists():
        with open(self.jsonfile, 'r') as js:
          loaded_tensors = json.load(js)
          if loaded_tensors[-1]['step'] > self.current_step:
            # If previous sessions have written beyond current step, overwrite them.
            back_index = -2
            while loaded_tensors[back_index]['step'] > self.current_step:
              back_index -= 1
            self.tensors = loaded_tensors[:back_index + 1]
          else:
            self.tensors = loaded_tensors
      else:
        raise FileNotFoundError(self.jsonfile)
    return

  def _step_triggered(self):
    self.current_step += 1
    if self.delay_checkpoint:
      self.delay_checkpoint = False
      return False
    if (self.current_step) % self.step_freq == 0 or self.current_step - 1 == 0:
      return True
    return False

  def _logTensors(self):

    effective_step = self.current_step if self.current_step - 1 != 0 else 0
  
    if self.average is True:
      epoch_tensors = (self.epoch_tensors if effective_step == 0
                     else {k: v / self.step_freq for k, v in self.epoch_tensors.items()})
    else:
      epoch_tensors = (self.epoch_tensors if effective_step == 0
                     else {k: v for k, v in self.epoch_tensors.items()})

    self.tensors.append(epoch_tensors)
    self.tensors[-1]['step'] = effective_step
    
    for key, value in epoch_tensors.items():
      if key not in self.plot_tensors:
        self.plot_tensors[key] = {'value': [], 'step': []}
      self.plot_tensors[key]['value'].append(value)
      self.plot_tensors[key]['step'].append(effective_step)

    for func in self.monitor_func:
      func()
    return

  def _tensor2JSON(self):
    with open(self.jsonfile, 'w') as js:
      json.dump(self.tensors, js, indent = 2, sort_keys = True)
    return

  def _tensor2plot(self):
    for (key, value) in self.plot_tensors.items():
      if key != "step":
        plt.linesSingleAxis(
          {key: {'y': value['value'], 'x': value['step'] } },
          y_label = (key, 13),
          x_label = ("Train step", 13),
          plot_title = (key, 20),
          x_lim   = [0, 1.01 * value['step'][-1]],
          y_lim   = 1.1 * max(value['value']),
          legend  = False,
          showfig = False,
          savefig = str(self.cache_path / "{}.png".format(key)),
          force_init = True,
        )
    return

class validationSampleHook(object):
  """Real time storage hook for validation results"""

  def __init__(self,
               url,
               atomizer,
               batch_size,
               model_step,
               ):

    self.atomizer   = atomizer
    self.val_db     = validation_database.ValidationDatabase(url)
    self.val_id     = self.val_db.count
    self.batch_size = batch_size
    self.model_step = model_step
    self.mask_accuracy = [0, 0]
    self.nsp_accuracy  = [0, 0]
    return

  def step(self,
           inputs,
           outputs,
           ) -> None:
    """
      Requested tensors are evaluated and their values are available
    """

    seen_in_training      = inputs['seen_in_training'].cpu().numpy()
    original_input        = inputs['original_input'].cpu().numpy()
    input_ids             = inputs['input_ids'].cpu().numpy()
    input_mask            = inputs['input_mask'].cpu().numpy()
    masked_lm_lengths     = inputs['masked_lm_lengths'].cpu().numpy()
    next_sentence_labels  = inputs['next_sentence_labels'].cpu().numpy()
    
    masked_lm_ids = [[x for x in batch if x != -100] for batch in inputs['mask_labels'].cpu().numpy()]
    masked_lm_positions = [[idx for idx, x in enumerate(batch) if x != -100] for batch in inputs['mask_labels'].cpu().numpy()]

    masked_lm_predictions = [
          [np.argmax(outputs.prediction_logits.cpu().numpy()[batch][x]) for x in masked_lm_positions[batch]] 
          for batch in range(self.batch_size)
        ]
    next_sentence_predictions = [[np.argmax(x) for x in batch][-1] for batch in outputs.seq_relationship_logits.cpu().numpy()]

    for target, prediction in zip(masked_lm_ids, masked_lm_predictions):
      if target == prediction:
        self.mask_accuracy[0] += 1
      self.mask_accuracy[1] += 1

    for target, prediction in zip(next_sentence_labels, next_sentence_predictions):
      if target == prediction:
        self.nsp_accuracy[0] += 1
      self.nsp_accuracy[1] += 1

    with self.val_db.Session(commit = True) as session:
      for b in range(self.batch_size):
        val_trace = validation_database.BERTValFile(
          **validation_database.BERTValFile.FromArgs(
            atomizer = self.atomizer,
            id       = self.val_id,
            train_step                = self.model_step,
            seen_in_training          = seen_in_training[b],
            original_input            = original_input[b],
            input_ids                 = input_ids[b],
            input_mask                = input_mask[b],
            masked_lm_positions       = masked_lm_positions[b],
            masked_lm_ids             = masked_lm_ids[b],
            masked_lm_weights         = [],
            masked_lm_lengths         = masked_lm_lengths[b],
            next_sentence_labels      = next_sentence_labels[b],
            masked_lm_predictions     = masked_lm_predictions[b],
            next_sentence_predictions = next_sentence_predictions[b],
          )
        )
        try:
          exists = session.query(validation_database.BERTValFile.sha256).filter_by(sha256 = val_trace.sha256).scalar() is not None
        except sqlalchemy.orm.exc.MultipleResultsFound as e:
          l.getLogger().error("Selected sha256 has been already found more than once.")
          raise e
        if not exists:
          session.add(val_trace)
          self.val_id += 1
    return

  def final(self,
            val_set: str,
            masked_lm_loss: float,
            next_sentence_loss: float,
           ) -> None:
    masked_lm_accuracy = self.mask_accuracy[0] / self.mask_accuracy[1]
    next_sentence_accuracy = self.nsp_accuracy[0] / self.nsp_accuracy[1]
    r = [
      "masked_lm_accuracy: {}".format(masked_lm_accuracy),
      "masked_lm_loss: {}".format(masked_lm_loss),
      "next_sentence_accuracy: {}".format(next_sentence_accuracy),
      "next_sentence_loss: {}".format(next_sentence_loss),
    ]
    with self.val_db.Session(commit = True) as session:
      exists = session.query(validation_database.ValResults.key).filter_by(key = val_set).scalar() is not None
      if exists:
        entry = session.query(validation_database.ValResults).filter_by(key = val_set).first()
        entry.results = "\n".join(r)
      else:
        session.add(validation_database.ValResults(key = val_set, results = "\n".join(r)))