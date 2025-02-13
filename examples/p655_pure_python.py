# Copyright (c) 2020 Leeman Geophysical LLC.
# Distributed under the terms of the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause

"""
============================
Reducing p655 in Pure Python
============================

Experiment p655 was run in 2005 by Mckiernan, Rathbun, and Rowe. It was reduced by
Chris Marone. Here we use the xlook r file parser to run that r file and then get it into the
dictionary of quantity arrays like we use everywhere else and do some simple plotting
of the experiment.

For the curious, this experiment is determining the frictional response of "Ghost Rocks"
from Kodiak Alaska.

While being able to run r files is great, we'd like to move to reducing the data in Python
to really get at the full power of pylook. There are lots of ways that pylook can simplify
reduction and it is easier to follow exactly what is happening for those unfamiliar with the
r file format.

Let's start out with some imports to get rolling.
"""

import numpy as np

import pylook.calc as lc
from pylook.cbook import get_test_data
from pylook.io import read_binary
from pylook.units import units

##############################

data_path = get_test_data('p655intact100l')

##############################

data, _ = read_binary(data_path)

##############################
# The time column in these data files is really the sample rate in Hz. We want to turn that
# into a delta time and cumulatively sum to get experiment elapsed time. Notice that we are
# assigning units by multiplying them - easy! We have to take the magnitude of time for
# `cumsum` because numpy silently drops our units. We'll fix that with a `cumsum` wrapper
# in pylook soon.

data['Time'] = np.cumsum(1 / data['Time'].m) * units('s')

##############################
# Now we need to apply calibrations and units to the data - the calibrations are determined
# based on the sensor used by the experimentalist. We'll get a list of the current data column
# names so we know what they are called in the look file.

data.keys()

##############################

data['Vert_Disp'] = data['Vert_Disp'] * 0.076472 * units('micron / bit')
data['Vert_Load'] = data['Vert_Load'] * 1.597778959e-3 * units('MPa / bit')
data['Hor_Disp'] = data['Hor_Disp'] * 0.11017176 * units('micron / bit')
data['Hor_Load.'] = data['Hor_Load.'] * 3.31712805707e-3 * units('MPa / bit')

##############################

# Now that calibrations are applied, we really should rename those columns to something more
# useful. Look limited the length of column names, but pylook does not. We even allow spaces!
# The `pop` method removes that key/value pair from the dictionary and we reassign it to a
# new key.

data['Shear Displacement'] = data.pop('Vert_Disp')
data['Shear Stress'] = data.pop('Vert_Load')
data['Normal Displacement'] = data.pop('Hor_Disp')
data['Normal Stress'] = data.pop('Hor_Load.')

##############################
# There was a spike in the data that the experimentalist decided to remove. We can do that
# with an offset that sets everything in between the rows to the final value.

data['Shear Stress'] = lc.remove_offset(data['Shear Stress'], 4075, 4089, set_between=True)

##############################
# The testing machine expands when loading because it has a finite stiffness. That stiffness
# is known and can be removed from the data to create an elastically corrected displacement.
# Python is great with units here and can help you calculate the stiffness in the right units.
# We know the stiffness is 0.37 kN/micron and this experiment use samples that were 5x5cm.
# From that we let the units library do all of the hard work of calculating the stiffness in
# terms of stress.

normal_stiffness = 0.37 * units('kN/micron')
sample_normal_area = 5 * units('cm') * 5 * units('cm')
normal_stiffness = sample_normal_area / normal_stiffness
print(normal_stiffness.to('micron/MPa'))  # To just displays things in units that we expect

##############################
# pylook's elastic correction is a polynomial tool, so you can use as many coefficients as
# you'd like. Just like `np.polyval` we expect coefficients from the highest order to lowest.
# Units matter!

data['Normal Displacement'] = lc.elastic_correction(data['Normal Stress'],
                                                    data['Normal Displacement'],
                                                    [normal_stiffness, 0 * units('micron')])

##############################
# We start recording data before there is any load on the samples, so we need to find where
# the load is brought on. Easiest way to do this is to make a quick plot and find the row
# number at which we want to zero things. The `.m` after the data is a way to drop units
# (the magnitude) and is required as currently bokeh does not play well with units.

from bokeh.io import output_notebook
from bokeh.layouts import gridplot
from bokeh.plotting import figure, show

output_notebook()

##############################

p = figure(title='Find the normal stress zero row', tools='box_zoom, reset, hover')
p.line(data['rec_num'].m, data['Normal Stress'].m)
show(p)

##############################
# Row 42 looks pretty good, so we zero the normal stress there. We'd also like to set
# everything before that row to zero since it's just noise. In r files that took some math
# commands, we zero has options in pylook! We also don't need to worry about adding small
# values to avoid divide by zero errors as the friction calculation handles that properly.

data['Normal Stress'] = lc.zero(data['Normal Stress'], 42, mode='before')

##############################
# While we are zeroing, it is a good time to deal with the normal displacement as well.

data['Normal Displacement'] = lc.remove_offset(data['Normal Displacement'], 0, 42,
                                               set_between=True)

##############################
# Now we need to find the zero point for the shear load and stress.

p = figure(title='Find the shear stress zero row', tools='box_zoom, reset, hover')
p.line(data['rec_num'].m, data['Shear Stress'].m)
show(p)

##############################
# Row 1518 looks like a reasonable choice - so lets' zero those two and zero everything
# before then.

data['Shear Displacement'] = lc.zero(data['Shear Displacement'], 1518, mode='before')
data['Shear Stress'] = lc.zero(data['Shear Stress'], 1518, mode='before')

##############################
# The displacement transducer on the shear axis often runs out of travel and has to be reset
# during the experiment. We need to find those spots and record the rows at which those
# offsets start and stop so we can remove them.

p = figure(title='Find the DCDT offsets', tools='box_zoom, reset, hover')
p.line(data['rec_num'].m, data['Shear Displacement'].m)
show(p)

##############################
# Looks like we had two offsets - rows 18593 to 19058 and rows 66262 to 67830.
# Let's remove those and set the values between to the final value to that data look nice.

data['Shear Displacement'] = lc.remove_offset(data['Shear Displacement'],
                                              18593, 19058, set_between=True)
data['Shear Displacement'] = lc.remove_offset(data['Shear Displacement'],
                                              66262, 67830, set_between=True)

##############################
# For the normal displacement we assume that half of it is in each of the two layers of a
# double direct setup. We are going to change the sign such that compaction shows a thinner
# layer and dialation shows a thicker layer. On the bench the blocks were 89.2 mm thick with
# a 4 mm gouge layer. Notice that because of the units awareness we can just add 4 mm and the
# math works!

data['Normal Displacement'] = data['Normal Displacement'] * (-0.5 * units('dimensionless'))
data['Normal Displacement'] = lc.zero(data['Normal Displacement'], 42, mode='before')
data['Normal Displacement'] = data['Normal Displacement'] + 4 * units('mm')

##############################
# Let's calculate simple friction (shear stress / normal stress). We have a function in pylook
# that does this intelligently handling divide by zeros when there is no shear stress on the
# sample

data['Friction'] = lc.friction(data['Shear Stress'], data['Normal Stress'])

##############################
# ## Quick Look
# We'll use Bokeh to take a quick look at the data. Matplotlib is the best choice for your
# publication plots, but the speed and interactivity of Bokeh in the notebook is hard to beat.
# We'll be adding helpers to pylook to make this process easier in the future as well.

# This is a handy function that will be integrated into pylook in a more advanced way soon,
# but demonstrates how to make a flexible plotting function instead of copying and pasting a
# bunch of code over and over again.


def make_runplot(data, x_var='Time', y_vars=None,
                 tools='pan,wheel_zoom,box_zoom,reset,save,box_select,hover'):
    plots = []
    for col_name in list(data):
        if col_name == x_var:
            continue
        if y_vars and (col_name not in y_vars):
            continue

        # First plot is simple, the rest we share the x range with the first
        if plots == []:
            p = figure(title=col_name, tools=tools)
        else:
            p = figure(title=col_name, tools=tools, x_range=plots[0].x_range)

        # Plot the data and set the labels
        p.xaxis.axis_label = str(data[x_var].units)
        p.yaxis.axis_label = str(data[col_name].units)
        p.line(data[x_var].m, data[col_name].m)

        plots.append(p)
    show(gridplot(plots, ncols=1, plot_width=600, plot_height=175))

##############################
# By default make_runplot would plot all of the variables, let's just plot a couple of basic
# ones. Hover over the graph to see the values! That can be turned off by clicking the message
# bubble icon in the plot toolbar. If we don't specify, data are plotted with respect to time.


make_runplot(data, y_vars=['Shear Stress', 'Normal Stress'])


##############################
# We can specify to plot relative to another x variable though - with load point displacement
# probably being the most common.

make_runplot(data, x_var='Shear Displacement', y_vars=['Shear Stress', 'Normal Stress'])

##############################
# Easy right? We'll be adding more features to reduce this code even further, but it moves us
# even further towards the goal of easy to understand and portable reductions that require a
# minimum of installation and learning pain. Being in Python also means we can seamlessly
# transfer these data into machine learning tools or just about any other analysis library
# you're interested in!
