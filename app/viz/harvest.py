from __future__ import division
import csv
import sys
from blaze import *
import pandas as pd
from bokeh.plotting import *
from bokeh.objects import HoverTool
from bokeh.models import ColumnDataSource
from collections import OrderedDict
import numpy as np
import datetime as dt
from bokeh.embed import components
from bokeh.resources import CDN

from plot import PlotManager


class Harvest(PlotManager):
    """Create a line plot to compare the growth of crawled and relevant pages in the crawl."""

    def __init__(self, datasource, plot):
        self.harvest_data = datasource.data_uri
        super(Harvest, self).__init__(plot)

    def update_source(self):

        df = pd.read_csv(self.harvest_data, delimiter='\t',
            names=['relevant_pages', 'downloaded_pages', 'timestamp'])
        df['harvest_rate'] = df['relevant_pages'] / df['downloaded_pages']

        source = into(ColumnDataSource, df)
        return source

    def create_and_store(self):

        self.source = self.update_source()

        output_server(self.doc_name)
        curdoc().autostore = False

        p = figure(plot_width=500, plot_height=250,
                   title="Harvest Plot", x_axis_type='datetime',
                   tools='pan, wheel_zoom, box_zoom, reset, resize, save, hover')

        p.line(x="timestamp", y="relevant_pages", color="red", width=0.2,
               legend="relevant", source=self.source)
        p.scatter(x="timestamp", y="relevant_pages", fill_alpha=0.6,
                  color="red", source=self.source)

        p.line(x="timestamp", y="downloaded_pages", color="blue", width=0.2,
               legend="downloaded", source=self.source)
        p.scatter(x="timestamp", y="downloaded_pages", fill_alpha=0.6,
                 color="blue", source=self.source)

        hover = p.select(dict(type=HoverTool))
        hover.tooltips = OrderedDict([
            ("harvest_rate", "@harvest_rate"),
        ])

        p.legend.orientation = "top_left"

        cursession().store_document(curdoc())
        return autoload_server(p, cursession()), self.source._id
