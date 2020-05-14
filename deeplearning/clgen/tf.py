"""A wrapper module to include tensorflow"""
tf = None
if tf is None:
  import os
  import tensorflow
  tf = tensorflow
  tf.python.util.deprecation._PRINT_DEPRECATION_WARNINGS = False
  os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
  # tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.INFO)
  tf.compat.v1.disable_eager_execution()