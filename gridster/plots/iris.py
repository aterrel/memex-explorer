from bokeh.sampledata.iris import flowers
from bokeh.plotting import *
from bokeh import embed

output_server("iris")

colormap = {'setosa': 'red', 'versicolor': 'green', 'virginica': 'blue'}

flowers['color'] = flowers['species'].map(lambda x: colormap[x])

#setting the name kwarg will give this scatter plot a user
#friendly id, and the corresponding embed.js will have a nice name
#too

scatter(flowers["petal_length"], flowers["petal_width"],
        color=flowers["color"], fill_alpha=0.2, size=10, name="iris")
        
xax, yax = axis()
xax.axis_label = 'Petal Length'
yax.axis_label = 'Petal Width'

curplot().title = "Iris Morphology"

show()

tag = embed.autoload_server(curplot(), cursession())
