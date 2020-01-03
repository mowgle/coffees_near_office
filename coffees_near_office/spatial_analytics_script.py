'''
* NOTE: there is a music component in this code which requires the pyglet library to run. It can be downloaded by entering ‘pip install pyglet’
* on Terminal. Alternatively, you can remove the component by removing code lines 21, 142 & 143. This component has no purpose other than attempted humour. 
'''

'''
* STEP 1:
* Import all the necessary libraries
*
* fiona:        used to read and write spatial data files.
* mapnik:       used to convert spatial data files into visual maps.
* networkx:     used to conduct graph/network-based analysis. 
* osm2nx:       Jonny's code used to convert an xml file into a graph and an rtree index. 
* PIL:          Python Imaging Library. Adds image processing capabilities to this code. Used here to add a North arrow, scale bar and text.
* pyproj:       used to calculate ellipsoidal distances, transform coordinates from projected to geographical.
* scalebar:     Jonny's code used to quickly add a scalebar to the map.
'''

import fiona, mapnik, networkx, time
import pyglet
from osm2nx import read_osm
from pyproj import Proj, Geod, transform
from PIL import Image, ImageDraw, ImageFont
from scalebar import addScaleBar
from shapely.geometry import mapping, point, shape, LineString

# start a timer, to track how long the program takes to run
start_time = time.time()

print "Let's begin..."



'''
* STEP 2:
* Get the geographical coordinates of Jonny's office from the OSM shapefile provided
'''

with fiona.open('data/jonnysoffice.shp') as GISHQ:
    jonnysLocation = GISHQ[0]['geometry']['coordinates']



'''
* STEP 3:
* Make a bounding box that captures the area ~30 minutes walk around Jonny's office
* Then, filter the OSM shapefiles to show the cafes within this radius
*
* I have assumed a very basic 2.5km "as the crow flies" radius, according to Naismith's rule (no elevation accounted for)
* I will narrow this down in Step 4
'''

## first, set the function and variables needed to carry out the bounding box and filter calculations
# create a function that filters out the 'cafe' objects in the OSM shapefiles
def findCafes(feat):
    return feat[1]['properties']['amenity'] == 'cafe'

# create a 'max distance' variable, which sets the walking distance radius around Jonny's office
maxDist = 2500

# create an 'offset distance variable', which multiplies this max distance by sqrt(2), thus capturing the entire area of the bounding box
offsetDist = maxDist * (2**0.5)

# set the ellipsoid (in this instance, British National Grid) on which to do the Forward Vincenty bounding box calculation
g = Geod(ellps='airy')


## now, apply the calculations to the polygons shapefile
# open the Manchester 'osm_polygons' shapefile
with fiona.open('data/osm_polygons.shp') as poly:
    
    # use the Forward Vincenty method to get the edge points of the bounding box (bottom-left, top-right)
    blX, blY, bAz = g.fwd(jonnysLocation[0], jonnysLocation[1], 225, offsetDist)
    trX, trY, bAz = g.fwd(jonnysLocation[0], jonnysLocation[1], 45, offsetDist)
    
    # now, put all the points of interest within a bounding box using the above two points
    walkablePolys = list(poly.items(bbox=(blX, blY, trX, trY)))

    # filter to focus only on the cafes within the bounding box
    walkableCafePolys = filter(findCafes, walkablePolys)

    # print the result (to test the outcome)
    print "...there are", len(walkableCafePolys), "cafes Jonny potentially can walk to in 30 minutes, from the 'osm_polygons' file..."

    # save the results to a shapefile
    with fiona.open('shapefiles/cafe_polys.shp', 'w', driver='ESRI Shapefile', crs=poly.crs, schema={'geometry': 'Polygon', 'properties': {}}) as cafePolys:
        for feat in walkableCafePolys:
            cafePolys.write({'geometry': feat[1]['geometry'], "properties":{}})

# now, convert the polygons in the this file to centroid points (using a solution I found on GIS Stack Exchange)
'''
* Doing this makes it easier to measure the distance between Jonny's office and these cafes,
* and it also makes it easier to 'draw' the cafes on the map using an icon.
'''

# change the shapefile schema from 'Polygon' to 'Point'
with fiona.open('shapefiles/cafe_polys.shp') as src:
    meta = src.meta
    meta['schema']['geometry'] = 'Point'

    # re-write each cafe node from a polygon to a centroid point
    with fiona.open('shapefiles/cafe_polys.shp', 'w', **meta) as dst:
        for f in src:
            centroid = shape(f['geometry']).centroid
            f['geometry'] = mapping(centroid)
            dst.write(f)


## do the same calculations (bounding box and filter) for the points shapefile
with fiona.open('data/osm_points.shp') as point:

    blX, blY, bAz = g.fwd(jonnysLocation[0], jonnysLocation[1], 225, offsetDist)
    trX, trY, bAz = g.fwd(jonnysLocation[0], jonnysLocation[1], 45, offsetDist)
    
    walkablePoints = list(point.items(bbox=(blX, blY, trX, trY)))

    walkableCafePoints = filter(findCafes, walkablePoints)

    # print the result to test the outcome
    print "...and", len(walkableCafePoints), "cafes Jonny can potentially walk to in 30 minutes, from the 'osm_points' file..."

    # save the results to a shapefile
    with fiona.open('shapefiles/cafe_points.shp', 'w', driver='ESRI Shapefile', crs=point.crs, schema={'geometry': 'Point', 'properties': {}}) as cafePoints:
        for feat in walkableCafePoints:
            cafePoints.write({'geometry': feat[1]['geometry'], "properties":{}})



'''
* STEP 4:
* Calculate which of these cafes are actually within a 30 minute walk
*
* The bounding box is a rough measurement, designed to narrow down the cafes that I need to analyse in this step.
* Now, the distance between Jonny's office and each cafe will be measured. First, the shortest path between Jonny's
* office and each cafe will be calculated by creating a networkx graph and an rtree index from 'manchester.xml', and
* then using the A* algorithm (in networkx) to find the path. Then the path's length will be found using the Forward
* Vincenty method, and if the total distance is less than 2.5km (which, according to Naismith's Rule, will take 30
* minutes on a flat elevation), then it will be mapped. Otherwise, it will be discarded as Jonny cannot walk to it
* in 30 minutes. 
'''

# print some context to inform the person who is running the code of the next step
print '...now, to figure out which ones are ACTUALLY <30 minutes walk. This can take a few seconds. Here is some elevator music while you wait...'

# play some beautiful, relaxing music while they wait
song = pyglet.resource.media('data/elevator_music.wav', streaming=False)
song.play()


## first, store all the cafe nodes into a single shapefile for analysis
# initialise a list variable to store the cafe nodes
cafeCoordinates = []

# open the 'cafe_polys' shapefile just created, and append each cafe node to the list
with fiona.open('shapefiles/cafe_polys.shp') as polys:
    for feat in polys:
        cafeCoordinates.append(feat)

# do the same for the 'cafe_points' shapefile
with fiona.open('shapefiles/cafe_points.shp') as points:
    for feat in points:
        cafeCoordinates.append(feat)


## now, calculate the distance from Jonny's office to each of these cafes 
# open the 'manchester.xml' file using Jonny's osm2nx code, to make a networkx graph and an rtree index 
G, idx = read_osm('data/manchester.xml')

# initialise a list variable to store all the cafes that are <30 minutes walk
walkableCafes = []

# for the Inverse Vincenty distance calculation, set the 'from node' as Jonny's office (drawn as a 0m2 box, so rtree can understand)
office = str(list(idx.nearest((jonnysLocation[0], jonnysLocation[1], jonnysLocation[0], jonnysLocation[1]), 1))[0])

# to set the 'to node', loop through each of the cafe nodes in 'cafeCoordinates'...
for i in cafeCoordinates:

    # ...and pull the coordinates (drawn as a 0m2 box, so rtree can understand)
    cafe = str(list(idx.nearest((i['geometry']['coordinates'][0], i['geometry']['coordinates'][1], i['geometry']['coordinates'][0], i['geometry']['coordinates'][1]), 1))[0])

    # create an 'if' statement that only calculates the path if a path is possible 
    if networkx.has_path(G, source=office, target=cafe):

        # use the A* algorithm in networkx to calculate the nodes that comprise the shortest path from Jonny's office to each cafe, and store them a list ('path')
        path = networkx.astar_path(G, source=office, target=cafe, weight='distance')

        # initialise a list to store all of these node's coordinates
        pathLine = []

        # take each node in 'path', pull their coordinates from the networkx graph and append these coordinates to the 'pathLine' list
        for co in path:
            node = G.subgraph(co).nodes(data=True)
            pathLine.append([node[0][1]['lon'], node[0][1]['lat']])

        # convert 'pathLine' to a fiona linestring, so its length can be calculated using the Inverse Vincenty method 
        pathLineStr = mapping(LineString(pathLine))

        # set the ellipsoid for the Inverse Vincenty distance calculation (British National Grid)
        g = Geod(ellps='airy')

        # initialise a cumulative distance variable to store the path distance
        cumulativeDistance = 0

        # now, use the Inverse Vincenty method to calculate the length of each line segment in the path (using a format that recognises that 'pathLineStr' = LineString)
        for lineSeg in range(len(pathLineStr['coordinates'])-1):
            azF, azB, distance = g.inv(pathLineStr['coordinates'][lineSeg][0], pathLineStr['coordinates'][lineSeg][1], pathLineStr['coordinates'][lineSeg+1][0], pathLineStr['coordinates'][lineSeg+1][1])

            # add the distance of each line segment to the cumulativeDistance variable,
            cumulativeDistance += distance

        # if the cumulative distance is less than 2500 (2.5km), store the cafe's coordinates in the 'walkableCafes' variable
        if cumulativeDistance < 2500:
            walkableCafes.append(i)


## finally, save the walkableCafe list to a point shapefile
with fiona.open('shapefiles/cafes.shp', 'w', driver='ESRI Shapefile', crs=point.crs, schema={'geometry': 'Point', 'properties': {}}) as dst:
    for feat in walkableCafes:
            dst.write({'geometry': feat['geometry'], "properties":{}})

# print the results
print "...calculated! There are", len(walkableCafes), "cafes that Jonny can ACTUALLY walk to within 30 minutes. Now, to calculate the routes to my 3 favourite cafes: Anchor, Grindsmith and Takk..."



'''
* STEP 5:
* Calculate the distances between Jonny's office and 3 of my favourite cafes: Anchor, Grindmsith and Takk,
* and store them as a shapefile so they can be mapped.
*
* This is a simple process, using the same A* algorithm to calculate the route, then pulling the coordinates of the nodes
* in the route, and then storing it as a fiona linestring before saving into a shapefile. This will allow the rotues to be
* mapped on my map.
'''

## first, Anchor Coffee
# set the 'to node' to Anchor Coffee House's coordinates (taken from Google Maps) 
anchor = str(list(idx.nearest((-2.227269, 53.457689, -2.227269, 53.457689), 1))[0])

# calculate the route between Jonny's office and the Anchor Coffee House
anchorPath = networkx.astar_path(G, source=office, target=anchor, weight='distance')

# initialise a list to store the coordinates of each node in the path just calculated
anchorPathLine = []

# pull the coordinates of each node from the 'Manchester.xml' networkx graph, and store in this list
for i in anchorPath:
    node = G.subgraph(i).nodes(data=True)
    anchorPathLine.append([node[0][1]['lon'], node[0][1]['lat']])

# convert the list into a fiona linestring
anchorPathLineStr = mapping(LineString(anchorPathLine))

# write the results to a shapefile
with fiona.open('shapefiles/anchor_path.shp', 'w', driver='ESRI Shapefile', crs=point.crs, schema={'geometry': 'LineString', 'properties': {}}) as o:
            o.write({'geometry': anchorPathLineStr, "properties":{}})


## second, Grindsmith
# set the 'to node' (coordinates taken from Google Maps)
grindsmith = str(list(idx.nearest((-2.2497469, 53.4776638, -2.2497469, 53.4776638), 1))[0])

# calculate the route using A* algorithm in networkx
grindsmithPath = networkx.astar_path(G, source=office, target=grindsmith, weight='distance')

# initialise a list to store the coordinates for each node in the route
grindsmithPathLine = []

# pull the coordinates from each node and store in this list
for i in grindsmithPath:
    node = G.subgraph(i).nodes(data=True)
    grindsmithPathLine.append([node[0][1]['lon'], node[0][1]['lat']])

# convert the list into a fiona linestring
grindsmithPathLineStr = mapping(LineString(grindsmithPathLine))

# write the results to a shapefile
with fiona.open('shapefiles/grindsmith_path.shp', 'w', driver='ESRI Shapefile', crs=point.crs, schema={'geometry': 'LineString', 'properties': {}}) as o:
            o.write({'geometry': grindsmithPathLineStr, "properties":{}})


## third, Takk
# set the 'to node' (coordinates taken from Google Maps)
takk = str(list(idx.nearest((-2.2324669, 53.481079, -2.2324669, 53.481079), 1))[0])

# calculate the route using A* algorithm in networkx
takkPath = networkx.astar_path(G, source=office, target=takk, weight='distance')

# initialise a list to store the coordinates for each node in the route
takkPathLine = []

# pull the coordinates from each node and store in this list
for i in takkPath:
    node = G.subgraph(i).nodes(data=True)
    takkPathLine.append([node[0][1]['lon'], node[0][1]['lat']])

# convert the list into a fiona linestring
takkPathLineStr = mapping(LineString(takkPathLine))

# write the results to a shapefile
with fiona.open('shapefiles/takk_path.shp', 'w', driver='ESRI Shapefile', crs=point.crs, schema={'geometry': 'LineString', 'properties': {}}) as o:
            o.write({'geometry':takkPathLineStr, "properties":{}})


## Finally, store the coordinates of each cafe into a shapefile (for styling their icons) 
# initialise a favCafes list to store each node
favCafes= []

# look in the 'cafes' shapefile for each of these nodes, by searching for their coordinates
'''
* The coordinates were initially taken from Google Maps, but have been cross-referenced with
* the actual coordinates in the 'cafes' shapefile (by printing the coordinates of each
* geometry and checking).
'''
with fiona.open('shapefiles/cafes.shp') as cafes:
    for i in cafes:
        if i['geometry']['coordinates'] == (-2.227279074525657, 53.45767292805476):
            favCafes.append(i)
        if i['geometry']['coordinates'] == (-2.2324591, 53.481118):
            favCafes.append(i)
        if i['geometry']['coordinates'] == (-2.2497128, 53.4776521):
            favCafes.append(i)

# append the 'favCafes' list to a shapefile
with fiona.open('shapefiles/fav_cafes.shp', 'w', driver='ESRI Shapefile', crs=point.crs, schema={'geometry': 'Point', 'properties': {}}) as dst:
    for feat in favCafes:
        dst.write({'geometry': feat['geometry'], "properties":{}})

print "done! now, to put all of this onto a map..."



'''
* STEP 6:
* Make a map of the background of Manchester
*
* The OSM schema is odd and mixed, so I have made as good-looking a map as I think I can from it
'''

# make the map, give it a white background color, and project it according to the British National Grid coordinate reference system
m = mapnik.Map(1600,1600)
m.background = mapnik.Color('white')
m.srs = '+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy +datum=OSGB36 +units=m +no_defs'


## first, style layers in the 'osm_polygons' shapefile
## make style to append all the rules that style the 'osm_polygons' shapefile, which will style the map
mancPoly_s = mapnik.Style()

# make a filtered rule to apply to buildings, parking lots and schools and append it to the style
build_r = mapnik.Rule()
build_f = mapnik.Filter("[building] != ''")
build_r.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#c1c1c1')))
build_r.filter = build_f
build_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#c1c1c1'), 1))
mancPoly_s.rules.append(build_r)

# make a filtered rule to apply to parking lots and append it to the 'mancPoly_s' style
park_r = mapnik.Rule()
park_f = mapnik.Filter("[amenity] = 'parking'")
park_r.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#c1c1c1')))
park_r.filter = park_f
park_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#c1c1c1'), 1))
mancPoly_s.rules.append(park_r)

# make a filtered rule to apply to schools and append it to the style
school_r = mapnik.Rule()
school_f = mapnik.Filter("[amenity] = 'school'")
school_r.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#c1c1c1')))
school_r.filter = school_f
school_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#c1c1c1'), 1))
mancPoly_s.rules.append(school_r)

# make a filtered rule for residential areas and append it to the style
res_r = mapnik.Rule()
res_f = mapnik.Filter("[landuse] = 'residential'")
res_r.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#e0e0e0')))
res_r.filter = res_f
res_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#e0e0e0'), 1))
mancPoly_s.rules.append(res_r)

# make a filtered rule for industrial areas and append it to the style
ind_r = mapnik.Rule()
ind_f = mapnik.Filter("[landuse] = 'industrial'")
ind_r.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#a5a0a0')))
ind_r.filter = ind_f
ind_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#a5a0a0'), 1))
mancPoly_s.rules.append(ind_r)

# make a filtered rule for brownfield areas and append it to the style
brown_r = mapnik.Rule()
brown_f = mapnik.Filter("[landuse] = 'brownfield'")
brown_r.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#dbbfa2')))
brown_r.filter = brown_f
brown_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#dbbfa2'), 1))
mancPoly_s.rules.append(brown_r)

# make a filtered rule for construction areas and append it to the style
const_r = mapnik.Rule()
const_f = mapnik.Filter("[landuse] = 'construction'")
const_r.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#dbbfa2')))
const_r.filter = const_f
const_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#dbbfa2'), 1))
mancPoly_s.rules.append(const_r)

# make filtered rules for each of the five greenspace area types, and append it to the 'mancPoly_s' style
green_r1 = mapnik.Rule()
green_f1 = mapnik.Filter("[natural] != ''")
green_r1.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#caf0d6')))
green_r1.filter = green_f1
green_r1.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#caf0d6'), 1))
mancPoly_s.rules.append(green_r1)

green_r2 = mapnik.Rule()
green_f2 = mapnik.Filter("[leisure] = 'park'")
green_r2.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#caf0d6')))
green_r2.filter = green_f2
green_r2.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#caf0d6'), 1))
mancPoly_s.rules.append(green_r2)

green_r3 = mapnik.Rule()
green_f3 = mapnik.Filter("[leisure] = 'pitch'")
green_r3.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#caf0d6')))
green_r3.filter = green_f3
green_r3.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#caf0d6'), 1))
mancPoly_s.rules.append(green_r3)

green_r4 = mapnik.Rule()
green_f4 = mapnik.Filter("[landuse] = 'grass'")
green_r4.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#caf0d6')))
green_r4.filter = green_f4
green_r4.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#caf0d6'), 1))
mancPoly_s.rules.append(green_r4)

green_r5 = mapnik.Rule()
green_f5 = mapnik.Filter("[landuse] = 'meadow'")
green_r5.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#caf0d6')))
green_r5.filter = green_f5
green_r5.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#caf0d6'), 1))
mancPoly_s.rules.append(green_r5)

# append the 'manc_poly_s' style, containing all of these filtered rules, to the map
m.append_style('Manc_Poly_Style', mancPoly_s)


## second, style layers in the 'osm_lines' shapefile
# make style to append all the rules that style the 'osm_lines' shapefile, which will style the map
mancLine_s = mapnik.Style()

# make a filtered rule for rivers (waterways) and append it to the 'mancLine_s' style
water_r = mapnik.Rule()
water_f = mapnik.Filter("[waterway] != ''")
water_r.filter = water_f
water_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#87bdff'), 7))
mancLine_s.rules.append(water_r)

# make a filtered rule for roads and append it to the style
road_r = mapnik.Rule()
road_f = mapnik.Filter("[highway] != ''")
road_r.filter = road_f
road_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#FFEBAF'), 5))
mancLine_s.rules.append(road_r)

# make a filtered rule for motorways and append it to the style
mway_r = mapnik.Rule()
mway_f = mapnik.Filter("[highway] = 'motorway'")
mway_r.filter = mway_f
mway_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#f2d074'), 5))
mancLine_s.rules.append(mway_r)

### make a filtered rule for railway tracks and append it to the style
rail_r = mapnik.Rule()
rail_f = mapnik.Filter("[railway] != ''")
rail_r.filter = rail_f
rail_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('#ffafaf'), 5))
mancLine_s.rules.append(rail_r)

# append the 'manc_line_s' style, with all of these filtered rules, to the map
m.append_style('Manc_Line_Style', mancLine_s)

# add the 'osm_polygons' shapefile layer to the map, append the style made for it ('Manc_Poly_Style') and append the layer to the map
mancPoly_l = mapnik.Layer('Manc_Poly_Layer')
mancPoly_l.datasource = mapnik.Shapefile(file='data/osm_polygons.shp')
mancPoly_l.styles.append('Manc_Poly_Style')
m.layers.append(mancPoly_l)

# add the 'osm_lines' shapefile layer to the map, append the style made for it ('Manc_Line_Style') and append the layer to the map
mancLine_l = mapnik.Layer('Manc_Line_Layer')
mancLine_l.datasource = mapnik.Shapefile(file='data/osm_lines.shp')
mancLine_l.styles.append('Manc_Line_Style')
m.layers.append(mancLine_l)



'''
* STEP 7:
* Add the routes to my 3 favourite cafes
*
* These will all be styled using the same red line
'''

# create the style and rule for the 3 favourite routes
fav_s = mapnik.Style()
fav_r = mapnik.Rule()

# create a line symbolizer, append it to the rule, and append the rule to the style
fav_r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('red'), 5))
fav_s.rules.append(fav_r)
m.append_style('Fav_Style', fav_s)

# create layers from the route shapefiles for Anchor, Grindmsith and Takk, and append 'Fav_Style'
anchor_l = mapnik.Layer('Anchor_Layer')
anchor_l.datasource = mapnik.Shapefile(file='shapefiles/anchor_path.shp')
anchor_l.styles.append('Fav_Style')

grindsmith_l = mapnik.Layer('Grindsmith_Layer')
grindsmith_l.datasource = mapnik.Shapefile(file='shapefiles/grindsmith_path.shp')
grindsmith_l.styles.append('Fav_Style')

takk_l = mapnik.Layer('Takk_Layer')
takk_l.datasource = mapnik.Shapefile(file='shapefiles/takk_path.shp')
takk_l.styles.append('Fav_Style')

# append all the layers to the map
m.layers.append(takk_l)
m.layers.append(anchor_l)
m.layers.append(grindsmith_l)



'''
* STEP 8:
* Add Jonny's location and the cafes to the map
*
* For visual appeal, these locations have been mapped as icons.
* My 3 favourite cafes have also been given different-coloured cafe icons to distinguish them
'''

## first, Jonny's office
# make a style and rule for Jonny's Office location
jonny_r = mapnik.Rule()
jonny_s = mapnik.Style()

# make a point symbolizer for the office, which marks the office with a reasonably-sized location pin icon
jonny_ps = mapnik.PointSymbolizer()
jonny_ps.filename = "data/icons/office.png"
jonny_ps.allow_overlap = True
jonny_ps.transform = 'scale(0.125)'

# append the point symbolizer to the rule, and append the rule to the style, and append the rule to the map
jonny_r.symbols.append(jonny_ps)
jonny_s.rules.append(jonny_r)
m.append_style('Jonny_Style', jonny_s)

# create a layer for Jonny's office (using 'jonnysoffice.shp'), append the style just made, and append the layer to the map
jonny_l = mapnik.Layer('Jonny_Layer')
jonny_l.datasource = mapnik.Shapefile(file='data/jonnysoffice.shp')
jonny_l.styles.append('Jonny_Style')
m.layers.append(jonny_l)


## second, cafes within walking distance
# make a style and rule for the cafes
cafe_r = mapnik.Rule()
cafe_s = mapnik.Style()

# make a point symbolizer for cafes, which marks them with a reasonably-sized coffee cup icon
cafe_ps = mapnik.PointSymbolizer()
cafe_ps.filename = "data/icons/cafe.svg"
cafe_ps.allow_overlap = True
cafe_ps.transform = 'scale(0.4)'

# append the point symbolizer to the rule, and append the rule to the style, and append the rule to the map
cafe_r.symbols.append(cafe_ps)
cafe_s.rules.append(cafe_r)
m.append_style('Cafe_Style', cafe_s)

# create a layer for the cafes (using 'cafes.shp'), append the style just made, and append the layer to the map
cafe_l = mapnik.Layer('Cafe_Layer')
cafe_l.datasource = mapnik.Shapefile(file='shapefiles/cafes.shp')
cafe_l.styles.append('Cafe_Style')
m.layers.append(cafe_l)


## finally, my three favourite cafes
# make a style and rule for the favourite cafes
favCafe_r = mapnik.Rule()
favCafe_s = mapnik.Style()

# make a point symbolizer for cafes, which marks them with a reasonably-sized coffee cup icon
favCafe_ps = mapnik.PointSymbolizer()
favCafe_ps.filename = "data/icons/fav_cafe.svg"
favCafe_ps.allow_overlap = True
favCafe_ps.transform = 'scale(0.4)'

# append the point symbolizer to the rule, and append the rule to the style, and append the rule to the map
favCafe_r.symbols.append(favCafe_ps)
favCafe_s.rules.append(favCafe_r)
m.append_style('Fav_Cafe_Style', favCafe_s)

# create a layer for the cafes (using 'cafes.shp'), append the style just made, and append the layer to the map
favCafe_l = mapnik.Layer('Fav_Cafe_Layer')
favCafe_l.datasource = mapnik.Shapefile(file='shapefiles/fav_cafes.shp')
favCafe_l.styles.append('Fav_Cafe_Style')
m.layers.append(favCafe_l)



'''
* STEP 9:
* Zoom the map to a reasonable size
*
* As the cafes within a 30 minute walking distance are what we are interested in, it makes sense
* to zoom to the bounds of these cafes. As the cafes shapefile will be opened with fiona, the coordinates
* pulled are geographical, and need to be converted to projected coordinates (which mapnik needs to project
* the map image). The 'transform' function within pyproj will be used to achieve this. 
'''

# open the 'cafes' shapefile, which contains all of the cafes Jonny can walk to in <30 minutes
with fiona.open('shapefiles/cafes.shp') as cafes:

	# get the bounds of the cafes
	b = cafes.bounds
	
# create a 'Proj' object for the WGS84 (geographical, fiona) coordinates
p1 = Proj(init='epsg:4326')

# create a 'Proj' object for the British National Grid (projected, mapnik) coordinates
p2 = Proj(init='epsg:27700')

# transform the bottom left corner of the cafe bounding box
x1, y1 = transform(p1,p2,b[0],b[1])

# transform the top right corner of the cafe bounding box
x2, y2 = transform(p1,p2,b[2],b[3])

# zoom the map to these cafe bounds, and place a 100m buffer around it
buffer = 200
m.zoom_to_box(mapnik.Box2d(x1-buffer,y1-buffer,x2+buffer,y2+buffer))

# then, render the map to an image file
mapnik.render_to_file(m, 'output/cafes_pre-edit.png', 'png')



'''
* STEP 10:
* Add a North arrow, a key, some copyright attribution text, a title and a scale bar
*
* PIL will be used to do this.
* The scale bar will be created using Jonny's 'scalebar' code.
'''

# open the rendered file using PIL
mapImg = Image.open('output/cafes_pre-edit.png')

## First, add a North arrow
# open and resize a north arrow image (by adjusting its pixel size) to fit the map and add an ANTIALIAS command to prevent image pixelation
northArrow = Image.open('data/icons/north.png').resize((75,75), Image.ANTIALIAS)

# paste the arrow onto the map, positioning it 20 pixels away from the top-left of the map, and add a 'mask' to make the background transparent
mapImg.paste(northArrow, (20, 20), northArrow)


## Second, add a Key
# open and resize a key (by adjusting its pixel size) to fit the map and add an ANTIALIAS command to prevent image pixelation
key = Image.open('data/icons/key.png').resize((343,480), Image.ANTIALIAS)

# paste the key onto the map and position it on the botom=right of the map
mapImg.paste(key, (9, m.height-530))


## Third, add some copyright attribution text
# use the PIL ImageDraw function to draw text on the map
draw = ImageDraw.Draw(mapImg)

# create an 'attribution' variable that contains the text to write
attribution = 'Data Copyright OpenStreetMap Contributors'

# measure the width (tw) and height (th) of this text using 'draw.textsize' in PIL
aw, ah = draw.textsize(attribution)

# make a 'font' variable to store the text font, and set the font size
font = ImageFont.truetype('data/helvetica.ttf', 14)

# add the 'attribution' variable text to the map, position it on the bottom-right of the map, set the text colour and append the font
draw.text((m.width-43-aw, m.height-10-ah), attribution, fill=(0,0,0), font=font)


## Fourth, add a title
# create an 'title' variable that contains the title text
title = 'A map of all the cafes within a 30-minute walking distance of Jonnys office'

# measure the width (tw) and height (th) of this text using 'draw.textsize' in PIL
tw, th = draw.textsize(title)

# make a 'font' variable to store the text font (bold this time)
font_bold = ImageFont.truetype('data/helvetica_bold.ttf', 35)

# add the 'title' variable text to the map, position it on the top-centre of the map, set the text colour and append the font
draw.text((m.width/2-tw-170, 30-th), title, fill=(0,0,0), font=font_bold)


## Finally, add a scale bar
# Use Jonny's 'scalebar' code to add a scale bar to the map
addScaleBar(m, mapImg, True)

# save the map with the north arrow, the key, the copyright attribution text, the title and the scale bar added
mapImg.save('output/cafes_final.png', "PNG")



'''
* STEP 11:
* Show the final map
'''

# print a final statement, and display the total time the program took to run
print "All done! This program took", ("%s seconds" % (time.time() - start_time)), "to run."

time.sleep(3)

# open an image of the Success Kid, because, why not
img = Image.open('data/icons/kid.jpg')
img.show()

time.sleep(1) 

# open the map
img = Image.open('output/cafes_final.png')
img.show()
