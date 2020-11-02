"""
In-house plotter module that plots data.
Based on plotly module
"""
import typing
import pathlib
import numpy as np
from plotly import graph_objs as go

def SingleScatterLine(x: np.array,
                      y: np.array,
                      title : str,
                      x_name: str,
                      y_name: str,
                      plot_name: str,
                      path: pathlib.Path,
                      ) -> None:
  """Plot a single line, with scatter points at datapoints."""

  layout = go.Layout(
    title = title,
    xaxis = dict(title = x_name),
    yaxis = dict(title = y_name),
  )

  fig = go.Figure(layout = layout)
  fig.add_trace(
    go.Scatter(
      x = x, y = y,
      mode = 'lines+markers',
      name = plot_name,
      showlegend = False,
      marker_color = "#00b3b3",
      opacity = 0.75
    )
  )
  outf = lambda ext: str(path / "{}.{}".format(plot_name, ext))
  fig.write_html (outf("html"))
  fig.write_image(outf("png"))
  return

def FrequencyBars(x: np.array,
                  y: np.array,
                  title    : str,
                  x_name   : str,
                  plot_name: str,
                  path: pathlib.Path
                  ) -> None:

  layout = go.Layout(
    title = title,
    xaxis = dict(title = x_name),
    yaxis = dict(title = "# of Occurences"),
  )
  fig = go.Figure(layout = layout)
  fig.add_trace(
    go.Bar(
      x = x,
      y = y,
      showlegend = False,
      marker_color = '#ac3939',
      opacity = 0.75,
    )
  )
  outf = lambda ext: str(path / "{}.{}".format(plot_name, ext))
  fig.write_html (outf("html"))
  fig.write_image(outf("png"))
  return