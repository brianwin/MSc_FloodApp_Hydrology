from flask import request
import folium
from folium import GeoJson, FeatureGroup
from folium.plugins import Fullscreen
from markupsafe import Markup
from collections import defaultdict

import shapely.geometry
import json

# for map coordinate conversions
from osgeo import ogr
from osgeo import osr

import pandas as pd
import time
import math

from typing import Dict, List, Any

import logging

from osgeo.osr import CoordinateTransformation

# 🔥 Get the same logger
logger = logging.getLogger('floodWatch')

def get_area_colors(all_eaareanames):
    logger.debug(">")
    colors = [
        "#1f77b4",  # blue
        "#ff7f0e",  # orange
        "#d62728",  # red
        "#9467bd",  # purple
        "#8c564b",  # brown
        "#e377c2",  # pink
        "#7f7f7f",  # gray
        "#bcbd22",  # yellow-greenish (ok)
        "#17becf",  # cyan
        "#ff1493",  # deep pink
        "#ffa500",  # strong orange
        "#ff4500",  # orange-red
        "#6a5acd",  # slate blue
        "#ff00ff",  # magenta
        "#00ced1",  # dark turquoise
    ]
    # Assign a color to each eaareaname
    area_colors = {}
    for idx, eaname in enumerate(all_eaareanames):
        area_colors[eaname] = colors[idx % len(colors)]
    logger.info(f'Area colors assigned: {len(colors)} colours')
    #logger.debug('<')
    return area_colors

def build_checkboxes_old(df):
    """
    Build EA area checkboxes:
    - all_eaareanames: all possible names (checkbox list)
    - active_eaareanames: names matching current filters (checkboxes enabled)
    - filtered_eaareanames: dict of filter values used

    :param df: Full flood area DataFrame
    :return: active_eaareanames (enabled), filtered_eaareanames (used filters)
    """
    logger.debug(">")

    # Apply filters excluding 'eaareaname' for greying logic
    filters_for_greying = {k: v for k, v in request.args.items(multi=True) if v and k != 'eaareaname' and k!= 'apply_all_active'}
    logger.debug(f'filters_for_greying: {filters_for_greying}')

    # Get rows filtered by all filters except eaareaname
    filtered_for_greying = df.copy()
    for key, value in filters_for_greying.items():
        filtered_for_greying = filtered_for_greying[filtered_for_greying[key].str.contains(value, case=False, na=False)]
    logger.debug(f'filtered_for_greying: {len(filtered_for_greying)} rows')

    # Get set of area names that are "active" (i.e., should not be greyed out)
    active_eaareanames = set(filtered_for_greying['eaareaname'].dropna().unique())
    logger.debug(f'active_eaareanames: {active_eaareanames}')

    # Separate out eaareaname for form persistence, but don’t apply it yet
    filtered_eaareanames = request.args.getlist('eaareaname')  # might be multiple
    #filtered_eaareanames = active_eaareanames
    logger.debug(f'filtered_eaareanames: {filtered_eaareanames}')
    #logger.debug('<')
    return active_eaareanames, filtered_eaareanames


def get_row_filter_criteria() -> Dict[str, List[str]]:
    """Extracts query parameters from the Flask request, excluding specific control flags.

    Returns:
        A dictionary mapping each relevant query parameter (except 'eaareaname' and 'apply_all_active')
        to its list of values, as received in the GET request.
     """
    logger.debug(">")
    ignore_keys = {'eaareaname', 'apply_all_active', 'visible_checkbox'}
    row_filter_criteria = {}

    for key in request.args:
        if key in ignore_keys:
            continue

        raw_values = request.args.getlist(key)
        # Flatten comma-separated entries
        expanded_values = []
        for val in raw_values:
            expanded_values.extend([v.strip() for v in val.split(',') if v.strip()])

        if expanded_values:
            row_filter_criteria[key] = expanded_values

    #logger.info(f'criteria:  {dict(row_filter_criteria)}')
    # typically this returns (for text boxes with comma seperated values)
    # criteria:  {'county': ['ess', 'kent', 'suf'], 'riverorsea': ['thames', 'lark']}
    #logger.debug('<')
    return row_filter_criteria

def build_floodarea_table(df):
    """Creates an html table of flood areas

    Args:
        df: A dataframe of flood areas to be included in the table

    Returns:
        q_table_html: A markup object for the table. Includes a "Select" column of checkboxes
                        who's action must be incorporated in the html page. Each row is uniquely
                        identified by the contents of the "fwdcode" column
        q_num_rows; The number of rows in the table
    """
    logger.debug(">")
    df2=df.copy()
    q_num_rows = len(df2)
    df2.insert(0, 'Select', df2.apply(lambda row: f'<input type="checkbox" class="row-checkbox" name="row_select" value="{row["fwdcode"]}" checked>', axis=1))

    # Leaving this here in case later we want to restrict the columns shown in the table
    #df2 = df2[['fwdcode','eaareaname', 'county', 'description', 'label', 'riverorsea']]
    df2 = df2[['Select', 'eaareaname', 'county', 'riverorsea', 'description', 'label', 'fwdcode']]

    # Custom column headers
    column_labels = {
        'Select': '<input type="checkbox" id="select-all-checkbox" onclick="toggleAllCheckboxes(this)" checked>',
        'fwdcode': 'FWD Code',
        'eaareaname': 'Area',
        'county': 'County',
        'description': 'Description',
        'label': 'Label',
        'riverorsea': 'River/Sea'
    }
    df2.rename(columns=column_labels, inplace=True)

    table_html = df2.to_html(classes="table table-striped table-hover", index=False, escape=False)
    table_html += """
        <script>
        function toggleAllCheckboxes(master) {
            const checkboxes = document.querySelectorAll('.row-checkbox');
            checkboxes.forEach(cb => cb.checked = master.checked);
        }
        </script>
        """
    q_table_html = Markup(table_html)
    #logger.debug('<')
    return q_table_html, q_num_rows

def build_floodarea_map(df: pd.DataFrame, area_colors:  dict[Any, str]) -> Markup:
    """Creates a folium map positioned and zoomed to fit polygons for selected flood areas.

    Determines the rectangular boundary of the polygons included in the df. Centres and zooms the map to fit.
    Plots a group bounding box for the polygon set.

    Args:
        df: A dataframe of flood areas to be included on the map
        area_colors: the application color set for Environmental Agency areas
    Returns:
        A markup object for the map, with polygons and a group bounding box

    Raises:
        None
    """
    logger.debug(">")
    # Create Folium map if there’s geodata
    #folium_map = folium.Map(location=[52.5, -1.5]) #, tiles='cartodbpositron'

    logger.debug(f'df.shape (input)         : {df.shape}')
    df2 = df # filter_by_bounds(df)
    logger.debug(f'df2.shape (after bounding): {df2.shape}')
    #print(df2.columns)

    if not df2.empty:
        min_latitude  = df2['bounding_box_wsg84'].apply(lambda b: b[0][0]).min()
        max_latitude  = df2['bounding_box_wsg84'].apply(lambda b: b[1][0]).max()
        min_longitude = df2['bounding_box_wsg84'].apply(lambda b: b[0][1]).min()
        max_longitude = df2['bounding_box_wsg84'].apply(lambda b: b[1][1]).max()

        boundary_corners = [[min_latitude, min_longitude], [max_latitude, max_longitude]]   # se and nw corners

        # Whatever method we use to determine map scaling, here are some points worth noting:
        # 1. folium only does "integer" scaling so the map will never fit the frame perfectly
        # 2. the further from the equator you go in latitude the more the map is distorted so
        #       lat flat-page distances are not the same as long flat-page distances. BNG
        #       approximates to flat-page distances.
        # 3. From 2. it is appropriate to convert to BNG, add margins and convert back to wsg84
        #       for scaling. True for either "adding n metres" or "adding n%" margins
        # 4. folium (leaflet) adds its own margin of 10% when creating a map or using fit_bounds(tb)
        # For points 2,3,4: see function compute_tight_bounds()

        folium_map = folium.Map()
        draw_group_bounding_box(folium_map, boundary_corners)
        folium_map.fit_bounds(boundary_corners)

        #tight_bounds_corners=compute_tight_bounds(boundary_corners,0.02)
        #draw_group_bounding_box(folium_map, tight_bounds_corners)

        #logger.debug(tight_bounds_corners)
        #folium_map.fit_bounds(tight_bounds_corners)
    else:
        folium_map = folium.Map(location=[52.5, -1.5], zoom_start=6) #, tiles='cartodbpositron')

    # add the "fullscreen" feature top right
    Fullscreen(position="topright", title="Expand me", title_cancel="Exit me", force_separate_button=True).add_to(folium_map)


    polygon_count = len(df2)
    logger.debug(f'polygon_count: {polygon_count}')

    max_polygons_before_cluster = 500  # or something else?
    if polygon_count > max_polygons_before_cluster:
        simplified = True
    else:
        simplified = False


    # Initialize feature groups and counts for each area
    area_layer_groups = {}
    area_polygon_counts = defaultdict(lambda: [0, 0])  # [simplified_count, normal_count]
    out_of_area_count = 0

    selected_areas = request.args.getlist('eaareaname')
    logger.debug(f'selected_areas: {selected_areas}')

    for _, row in df2.iterrows():
        # Add Markers
        #if pd.notna(row['lat']) and pd.notna(row['long']):
        #    popup = f"{row['label']} ({row['fwdcode']})"
        #    folium.Marker(location=[row['lat'], row['long']], popup=popup).add_to(folium_map)

        if pd.notna(row.get('polygon_json')):
            area_name = row['eaareaname']
            label = row['label']

            # Create a unique feature group (layer) for each area, if it doesn't already exist
            if area_name not in area_layer_groups:
                area_layer_groups[area_name] = FeatureGroup(name=area_name)
            try:
                #if (table_build_rows >= 10000) or (area_name not in selected_areas):
                if area_name not in selected_areas:
                    out_of_area_count +=1
                    continue

                fg, poly_styles = generate_polygon_html(area_name,
                                                        label,
                                                        area_colors,
                                                        row.get('polygon_json'),
                                                        simplified
                                                       )
                area_layer_groups[area_name].add_child(fg)  # Add fg to the "area_name" area_layer_group
                area_polygon_counts[area_name][0] += poly_styles[0]
                area_polygon_counts[area_name][1] += poly_styles[1]
            except Exception:
                pass  # Ignore bad JSON

    logger.debug(f'out_of_area_count  = {out_of_area_count}')
    logger.debug(f'area_polygon_counts= {dict(area_polygon_counts)}')
    total_polygon_counts = [
        sum(counts[0] for counts in area_polygon_counts.values()),
        sum(counts[1] for counts in area_polygon_counts.values())
    ]

    logger.debug(f'Total polygon counts [simplified, normal]: {total_polygon_counts}')

    # Add all area layers to the map
    start_time = time.time()
    for area_name, layer_group in area_layer_groups.items():
        layer_group.add_to(folium_map)

    # Add LayerControl to toggle layers
    folium.LayerControl().add_to(folium_map)
    logger.debug(f'layer_group.add_to(folium_map) time = {time.time() - start_time:.6f} secs')
    logger.debug(f'layer_group.add_to(folium_map) count= {len(area_layer_groups)} areas')

    # Render Folium map as HTML
    map_html = Markup(folium_map._repr_html_())

    logger.debug(f'render folium_map: {len(area_layer_groups)} areas, {total_polygon_counts[0] + total_polygon_counts[1]} polygons, in {time.time() - start_time:.6f} seconds')
    #logger.debug('<')
    return map_html

def draw_group_bounding_box(m: folium.Map, corners: list[list] ):
    """Draws a bounding box using the corners specified.

    Args:
        m: A folium map
        corners: SE and NW corners of the format [[min_lat, min_long], [max_lat, max_long]]
    Returns:
        None
    """
    min_lat, min_long = corners[0][0], corners[0][1]
    max_lat, max_long = corners[1][0], corners[1][1]

    # latitudinal boundaries of selection
    for lat in [min_lat, max_lat]:
        folium.PolyLine(
            locations=[[lat, min_long],[lat, max_long]],
        color = 'green',
        weight = 2,
        dash_array = '5,5',
        tooltip = f"Lat = {lat}"
        ).add_to(m)

    # longitudinal boundaries of selection
    for long in [min_long, max_long]:
        folium.PolyLine(
            locations=[[min_lat, long],[max_lat, long]],
        color = 'green',
        weight = 2,
        dash_array = '5,5',
        tooltip = f"Lat = {long}"
        ).add_to(m)

def compute_tight_bounds(corners: list[list], padding_metres: int =0, padding_ratio: float =0.05) -> list[list]:
    """Calculates tight boundaries for the mpa determined by SE and NW corners provided.

    ** This does not provide any significant benefit to foliums scaling after .fit_bounds
       Its use has been discontinued 23/05/2025
    **

    Note: Folium adds its own 10% margins when creating a map or using "m.add_bounds" and
    this is not accessible in the folium api. This is what we are trying to circumvent here

    Args:
        corners: SE and NW corners - format [[min_lat, min_long], [max_lat, max_long]]
        padding_metres:  typically set to 1000.  If 0 then padding ratio is used
        padding_ratio:   typically 0.05 for 5% padding
    Returns:
        tight_corners: SE and NW corners to be used in creating a folium map (format as corners above)
    """
    min_lat, min_long = corners[0][0], corners[0][1]
    max_lat, max_long = corners[1][0], corners[1][1]

    to_bng, to_wsg84 = get_transforms()
    sw = to_bng.TransformPoint(min_long, min_lat)  # note: TransformPoint(long, lat) -> x,y
    ne = to_bng.TransformPoint(max_long, max_lat)
    logger.debug(f'sw =      {sw}, ne =      {ne}')  # note third item of tuple returned is elevation (=0.0)

    folium_margin_multiplier = 1.05  # half 10% padding - 5% each side ???
    lat_folium_padding  = (ne[1] - sw[1]) / folium_margin_multiplier
    long_folium_padding = (ne[0] - sw[0]) / folium_margin_multiplier

    logging.debug(f'padding_metres {padding_metres}')
    if padding_metres != 0:  #TODO - make this 0 - see params
        padding_metres = 1000 #TODO - remove this line

        sw_marg = (sw[0] + long_folium_padding + padding_metres, sw[1] + lat_folium_padding + padding_metres)
        ne_marg = (ne[0] - long_folium_padding - padding_metres, ne[1] - lat_folium_padding - padding_metres)
        logger.debug(f'padding_metres = {padding_metres}')
    else:
        lat_pad  = (ne[1] - sw[1]) * padding_ratio
        long_pad = (ne[0] - sw[0]) * padding_ratio

        sw_marg = (sw[0] + long_folium_padding + long_pad, sw[1] + lat_folium_padding + lat_pad)
        ne_marg = (ne[0] - long_folium_padding - long_pad, ne[1] - lat_folium_padding - lat_pad)
        logger.debug(f'padding_ratio = {padding_ratio}')
        logger.debug(f'lat/long pad =    {lat_pad:.6f}, {long_pad:.6f}')

    logger.debug(f'sw_marg = {sw_marg}, ne_marg = {ne_marg}')  # note third item of tuple returned is elevation (=0.0)

    tight_bounds_sw = to_wsg84.TransformPoint(sw_marg[0], sw_marg[1])  # note: TransformPoint(x, y) -> lat,long
    tight_bounds_ne = to_wsg84.TransformPoint(ne_marg[0], ne_marg[1])
    logger.debug(f'sw =      {tight_bounds_sw}, ne =      {tight_bounds_ne}')

    tight_bounds = [ [tight_bounds_sw[1], tight_bounds_sw[0]], [tight_bounds_ne[1], tight_bounds_ne[0]] ]

    # Note: debug to 6dp but the output has greater precision
    fmt = lambda p: f"[{p[0]:.6f}, {p[1]:.6f}]"
    logger.debug(f'input_bounds = [{fmt(corners[0])}, {fmt(corners[1])}]')
    logger.debug(f'tight_bounds = [{fmt(tight_bounds[0])}, {fmt(tight_bounds[1])}]')
    return tight_bounds

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Purpose: Filters df based on criteria passed.
    :param   df: usually the full flood area DataFrame
    :return: Filtered dataframe
    """
    logger.debug(">")
    criteria = get_row_filter_criteria()
    logger.info(f'criteria:  {criteria}')

    if not criteria:
        return df

    # Build a combined filter mask - start with all true
    mask = pd.Series(True, index=df.index)
    logger.debug(f'mask: {dict(mask.value_counts())}')

    for key, values in criteria.items():
        if key == 'eaareaname':
            mask &= df[key].isin(values)
        else:
            if key not in df.columns or not values:
                continue
            submask = pd.Series(False, index=df.index)
            for val in values:
                if df[key].dtype == 'object':
                    submask |= df[key].str.contains(val, case=False, na=False)
                else:
                    submask |= df[key] == val  # for fields that might not be text (like fwdcode)

            logger.debug(f"k={key} v={values} - submask: {dict(submask.value_counts().to_dict())}")

            # Align submask to df index and apply to mask
            submask = submask.reindex(df.index, fill_value=False)
            mask &= submask

        logger.debug(f"k={key} v={values} - mask:    {dict(mask.value_counts().to_dict())}")
    if df[mask].empty:
        logger.warning("No flood areas matched current filters.")
    #logger.debug('<')
    return df[mask]


def generate_polygon_html(eaareaname, label, area_colors, polygon_json=None, simplified=False):
    #logger.debug(">")
    fg = FeatureGroup(name=eaareaname)
    simplified_style = normal_style = 0
    area_color = area_colors.get(eaareaname, "#000000")  # fallback to black

    js = f"""function onEachFeature(feature, layer) {{
            layer.on('click', function (e) {{
                toggleSelection("{eaareaname}");
            }});
        }}"""

    if simplified:
        # Simplified style: Make outlines thinner, and fill transparent
        simplified_style += 1
        geojson = GeoJson(
            data=polygon_json,
            tooltip=folium.Tooltip(f"<b>{eaareaname}</b>", sticky=True),
            style_function=lambda feature, color=area_color: {
                'fillColor': 'transparent',
                'color': color,
                'weight': 1,
                'fillOpacity': 0.0,
            },
            highlight_function=lambda feature, color=area_color: {
                'fillColor': color,
                'color': 'black',  # Border becomes black on hover
                'weight': 2,  # Thicker border on hover
                'fillOpacity': 0.1,  # Slightly more opaque
            }
        )
    else:
        # Normal style
        normal_style += 1
        geojson = GeoJson(
            data=polygon_json,
            tooltip=folium.Tooltip(
                f"<div style='min-width: 150px; max-width: 300px; "
                f"white-space: normal; overflow-wrap: break-word; word-break: break-word;'>"
                f"<b>{eaareaname}</b><br>{label}</div>",
                sticky=True),
            style_function=lambda feature, color=area_color: {
                'fillColor': color,
                'color': color,
                'weight': 2,
                'fillOpacity': 0.5,
            },
            highlight_function=lambda feature, color=area_color: {
                'fillColor': color,
                'color': 'black',  # Border becomes black on hover
                'weight': 4,  # Thicker border on hover
                'fillOpacity': 0.7,  # Slightly more opaque
            }
        )
    geojson.add_child(folium.Element(f"<script>{js}</script>"))
    fg.add_child(geojson)
    poly_styles = (simplified_style, normal_style)
    #logger.debug('<')
    return fg, poly_styles


def get_transforms():
    """Creates objects to translate WGS84 coords to BNG (British National Grid) and vice versa.

    Returns: Transformation objects transform_wsg842bng and transform_bng2wsg84
    """
    logger.debug('>')
    # EPSG:4326 is WGS84 projection (degrees)
    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)

    # EPSG:27700 is British National Grid projection (metres from a datum point)
    # EPSG:5243 is used by OpenStreetMap (metres from a datum point)
    target = osr.SpatialReference()
    target.ImportFromEPSG(27700)
    # target.ImportFromEPSG(5243)

    # Transform coordinates from one projection to another
    transform_wsg842bng = osr.CoordinateTransformation(source, target)

    # .... and back again
    transform_bng2wsg84 = osr.CoordinateTransformation(target, source)
    #logger.debug('<')
    return transform_wsg842bng, transform_bng2wsg84


def get_polygon_metrics_row(p_geojson, transform_wsg842planar):
    """
    Purpose : Validate and convert GeoJSON to polygon geometry, compute bounding box and area
    Params  : p_geoJSON (str or dict) GeoJSON of the polygon
    Returns : A single row df with the following columns:
                bounding_box_wsg84   : [[sw_lat, sw_long],[ne_lat, ne_long]]
                bound_centre_wgs84   : [[bc_lat, bc_long]]
                mpoly_centroid_wsg84 : [[centroid_lat, centroid_long]]
                bounding_box_bng     : [[sw_x, sw_y],[ne_x, ne_y]]
                bound_centre_bng     : [[bc_x, bc_y]]
                mpoly_centroid_bng   : [[centroid_x, centroid_y]]
                area                 : m^2
    """
    #logger.debug(">")
    #transform_wsg842bng, transform_bng2wsg84 = get_transforms()

    # Ensure we have a parsed JSON dict
    if isinstance(p_geojson, str):
        try:
            l_geo_json = json.loads(p_geojson)
        except json.JSONDecodeError as e:
            print("Invalid GeoJSON string:", e)
            return None, None
    elif isinstance(p_geojson, dict):
        l_geo_json = p_geojson
    else:
        print("Invalid input type. Expected GeoJSON str or dict.")
        return None, None

    try:
        # In web mapping APIs like Google Maps, spatial coordinates are often in order of latitude then longitude.
        # In spatial databases like PostGIS and SQL Server, spatial coordinates are in longitude and then latitude.

        # Folium maps use WSG84 grid for positioning, feature plotting, feedback end so on, and all of these have
        # coordinates in (latitude (GetY(), N +ve, S -ve), longitude (GetX(), W -ve, E +ve)).
        # We use that convention throughout this application
        geometry = l_geo_json['features'][0]['geometry']
        poly = ogr.CreateGeometryFromJson(json.dumps(geometry))

        envelope_wsg84 = poly.GetEnvelope()  # (minX, maxX, minY, maxY) # This includes all parts of the MultiPolygon
        min_long, max_long, min_lat, max_lat = envelope_wsg84

        bounding_box_wsg84   = [[min_lat, min_long], [max_lat, max_long]]
        bound_centre_wgs84   = [round((max_lat + min_lat) / 2, 6), round((max_long + min_long) / 2, 6)]
        mpoly_centroid_wsg84 = [round(poly.Centroid().GetY(), 6), round(poly.Centroid().GetX(), 6)]


        # Transform to BNG (meters) for area and bounding box calculations
        poly.Transform(transform_wsg842planar)

        # Bounding rectangle in bng (for measuring distances in metres)
        envelope_bng = poly.GetEnvelope()  # (minX, maxX, minY, maxY) # This includes all parts of the MultiPolygon
        min_x, max_x, min_y, max_y = envelope_bng

        bounding_box_bng   = [[round(min_x,6), round(min_y,6)], [round(max_x,6), round(max_y,6)]]
        bound_centre_bng   = [round((max_x + min_x) / 2, 6), round((max_y + min_y) / 2, 6)]
        mpoly_centroid_bng = [round(poly.Centroid().GetX(), 6), round(poly.Centroid().GetY(), 6)]

        # Area in square meters
        if poly.GetGeometryType() == ogr.wkbMultiPolygon:
            area = sum(poly.GetGeometryRef(i).GetArea() for i in range(poly.GetGeometryCount()))
        else:
            area = poly.GetArea()

        row = {
            'bounding_box_wsg84':   bounding_box_wsg84,
            'bound_centre_wgs84':   bound_centre_wgs84,
            'mpoly_centroid_wsg84': mpoly_centroid_wsg84,

            'bounding_box_bng':     bounding_box_bng,
            'bound_centre_bng':     bound_centre_bng,
            'mpoly_centroid_bng':   mpoly_centroid_bng,

            'area_km2': area / 1e6,
            'area_m2': area
        }
        #logger.debug('<')
        return pd.DataFrame([row])  # single-row DataFrame
    except Exception as e:
        logging.critical("Error in getPolygonMetricsRow:", e)
        #logger.debug('<')
        return None, None


def add_floodarea_support_cols(df: pd.DataFrame,
                               transform_wsg842planar: CoordinateTransformation) -> pd.DataFrame:
    """
    Parameter:   df: a dataframe of (row-wise filtered) floodarea data from EA (may contain several flood areas)
                 transform_wsg842planar: a coordinate transformation from WSG84 to a xy (not polar) system of your choice
    Return:      df: a dataframe with the following additional columns related to floodarea
                'area_m2' : Area of a floodarea in square metres
                'area_km2': Area of a floodarea in square kilometres
                'min_lat' : minimum latitude of a floodarea
                'min_long': minimum longitude of a floodarea
                'max_lat' : maximum latitude of a floodarea
                'max_long': maximum longitude of a floodarea
                'rank'    : Rank of the area within this df by area (largest first)
    """
    logger.debug(">")
    df = df.copy()  # Avoid modifying the original DataFrame

    # drop target columns if they already exist.  If they don't then bypass silently with errors='ignore'
    df.drop(columns=['area_m2', 'area_km2', 'rank', 'min_lat', 'max_lat', 'min_long', 'max_long'], inplace=True,
            errors='ignore')

    df.drop(columns=['bounding_box_wsg84', 'bound_centre_wgs84', 'mpoly_centroid_wsg84'
        , 'bounding_box_bng', 'bound_centre_bng', 'mpoly_centroid_bng'
        , 'area'
                     ], inplace=True, errors='ignore'
            )

    # Get bounding box + area for each row
    # Note:
    #   bounding_box = [
    #      [sw_point.GetY(), sw_point.GetX()],  # [lat, lon] SW
    #      [ne_point.GetY(), ne_point.GetX()]   # [lat, lon] NE
    #   ]

    # Define helper to extract metrics and return as single-row DataFrame
    def extract_feature_row(polygon_json, transform_wsg842planar):
        return get_polygon_metrics_row(polygon_json, transform_wsg842planar)

    # Apply to each row and stack into a fresh DataFrame
    # feature_df = df['polygon_json'].apply(extract_features)
    start_time = time.time()
    feature_rows = df['polygon_json'].apply(lambda poly: extract_feature_row(poly, transform_wsg842planar))
    logger.debug(f'Add metric columns: time = {time.time() - start_time:.6f} secs   feature_rows.shape = {feature_rows.shape}')

    feature_df = pd.concat(feature_rows.values, ignore_index=True)
    # Add a rank (by descending area_km2) column to the dataFrame
#    feature_df['rank'] = feature_df['area_km2'].rank(ascending=False)
    #print(f'Add rank:           time = {time.time() - start_time:.6f} secs   feature_df.shape   = {feature_df.shape}')

    # Merge into the original df at column 6
    insert_at_col = 6
    # Split the original DataFrame into two parts
    df_left = df.iloc[:, :insert_at_col]
    df_right = df.iloc[:, insert_at_col:]
    # Concatenate: left + new columns + right
    df_final = pd.concat([df_left, feature_df, df_right], axis=1)

    # Sort the dataFrame by 'rank' (the biggest floodarea first)
#    df_sorted_by_rank = df_final.sort_values(by='rank', ascending=True)
    df_sorted_by_rank = df_final
    # print(df_sorted_by_rank.head())

    #logger.debug('<')
    return df_sorted_by_rank


def filter_by_bounds(df):
    logger.debug(">")
    logger.debug(df.columns)
    map_zoom = request.args.get('map_zoom', type=int)
    min_lat = request.args.get('map_min_lat', type=float)
    min_lon = request.args.get('map_min_lon', type=float)
    max_lat = request.args.get('map_max_lat', type=float)
    max_lon = request.args.get('map_max_lon', type=float)

    #map_zoom = 0
    #min_lat = df['lat'].min()
    #min_lon = df['long'].min()
    #max_lat = df['lat'].max()
    #max_lon = df['long'].max()


    logger.debug(f"filter_by_bounds:  map zoom: {map_zoom}, bounds: ({min_lat}, {min_lon}) to ({max_lat}, {max_lon})")

    if None in (min_lat, min_lon, max_lat, max_lon):
        return df  # No filtering if bounds missing

    print(df['bounding_box_wsg84'].head(5))
    filtered = df[
        (df['bounding_box_wsg84'].apply(lambda b: b[0][0]) >= min_lat) &
        (df['bounding_box_wsg84'].apply(lambda b: b[1][0]) <= max_lat) &
        (df['bounding_box_wsg84'].apply(lambda b: b[0][1]) >= min_lon) &
        (df['bounding_box_wsg84'].apply(lambda b: b[1][1]) <= max_lon)
    ]
    logger.debug(f'Polygons in view: {len(filtered)}')
    #logger.debug('<')
    return filtered


