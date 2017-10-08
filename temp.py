import gmplot

gmap = gmplot.GoogleMapPlotter(37.428, -122.145, 16)

gmap.plot([37.86772, 32.1231], [31.4213,55.3213], 'blue', edge_width=10)


gmap.draw("mymap.html")