import pandas as pd
from pandas import DataFrame

import json

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

from app import db
from ..models import FloodareaMetrics

import logging
# 🔥 Get the same logger as used in main
logger = logging.getLogger('__name__')

def get_transforms() -> tuple[Transformer, Transformer]:
    """Creates transformation objects for converting
        WGS84 coords (EPSG:4326) to British National Grid (BNG) coords (EPSG:27700) and vice versa.

    Returns: A tuple of
                - wgs84_to_bng: Converts wgs84 to BNG
                - bng_to_wgs84: Converts BNG to wgs84
    Usage:
        - lon, lat = -0.1278, 51.5074  # London
        - x, y = wgs84_to_bng.transform(lon, lat)
        - print(f"BNG: {x:.2f}, {y:.2f}")
        -
        - x, y = 530000, 180000  # approximate BNG for London
        - lon, lat = bng_to_wgs84.transform(x, y)
        - print(f"WGS84: {lat:.6f}, {lon:.6f}")
    """
    logger.debug('>')
    # Source: EPSG:4326 is WGS84 projection (lat/long in degrees)
    # Target: EPSG:27700 is British National Grid projection (x/y metres from a datum point)
    # Note: EPSG:5243 is used by OpenStreetMap (metres from a datum point)

    # Define the transformer (bidirectional)
    wgs84_to_bng = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
    bng_to_wgs84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    return wgs84_to_bng, bng_to_wgs84


def get_polygon_metrics_row(p_geojson: str | dict) -> None | DataFrame:
    """Validate and convert GeoJSON polygon to Shapely geometry. Compute bounding boxes, centroids and area (in m² and km²) in both WGS84 and BNG.

    :param p_geojson: str or dict.
        A GeoJSON of a polygon or multipolygon

    :return: A single row pd.DataFrame with the following columns:
            bounding_box_wgs84   : [[sw_lat, sw_long],[ne_lat, ne_long]]
            bound_centre_wgs84   : [[bc_lat, bc_long]]
            mpoly_centroid_wgs84 : [[centroid_lat, centroid_long]]
            bounding_box_bng     : [[sw_x, sw_y],[ne_x, ne_y]]
            bound_centre_bng     : [[bc_x, bc_y]]
            mpoly_centroid_bng   : [[centroid_x, centroid_y]]
            area                 : km²
            area                 : m²
    """
    #logger.debug(">")
    wgs84_to_bng, bng_to_wgs84 = get_transforms()

    # Ensure we have a parsed JSON dict
    if isinstance(p_geojson, str):
        try:
            l_geo_json = json.loads(p_geojson)
        except json.JSONDecodeError as e:
            logger.error("Invalid GeoJSON string:", e)
            return None
    elif isinstance(p_geojson, dict):
        try:
            l_geo_json = p_geojson
        except json.JSONDecodeError as e:
            logger.error("Invalid GeoJSON dict:", e)
            return None
    else:
        logger.error("Invalid input type. Expected GeoJSON str or dict.")
        return None

    try:
        # In web mapping APIs like Google Maps, spatial coordinates are often in order of latitude then longitude.
        # In spatial databases like PostGIS and SQL Server, spatial coordinates are in longitude and then latitude.

        # Folium maps use WGS84 grid for positioning, feature plotting, feedback end so on, and all of these have
        # coordinates in (latitude (GetY(), N +ve, S -ve), longitude (GetX(), W -ve, E +ve)).

        # We use that convention throughout this application
        geometry = l_geo_json['features'][0]['geometry']
        poly = shape(geometry)  # Shapely geometry (Polygon or MultiPolygon)

        # Bounding box and centroid in WGS84
        min_long, min_lat, max_long, max_lat = poly.bounds
        bounding_box_wgs84 = [[min_lat, min_long], [max_lat, max_long]]
        bound_centre_wgs84 = [round((max_lat + min_lat) / 2, 6), round((max_long + min_long) / 2, 6)]
        mpoly_centroid_wgs84 = [round(poly.centroid.y, 6), round(poly.centroid.x, 6)]

        # Transform geometry to BNG
        poly_bng = transform(wgs84_to_bng.transform, poly)

        # Bounding box and centroid in BNG
        min_x, min_y, max_x, max_y = poly_bng.bounds
        bounding_box_bng = [[round(min_x, 6), round(min_y, 6)], [round(max_x, 6), round(max_y, 6)]]
        bound_centre_bng = [round((max_x + min_x) / 2, 6), round((max_y + min_y) / 2, 6)]
        mpoly_centroid_bng = [round(poly_bng.centroid.x, 6), round(poly_bng.centroid.y, 6)]

        area = poly_bng.area  # in square meters

        row = {
            'bounding_box_wgs84':   bounding_box_wgs84,
            'bound_centre_wgs84':   bound_centre_wgs84,
            'mpoly_centroid_wgs84': mpoly_centroid_wgs84,

            'bounding_box_bng':     bounding_box_bng,
            'bound_centre_bng':     bound_centre_bng,
            'mpoly_centroid_bng':   mpoly_centroid_bng,

            'area_km2': area / 1e6,
            'area_m2': area
        }
        return pd.DataFrame([row])  # single-row DataFrame
    except Exception as e:
        logging.critical("Error in getPolygonMetricsRow:", e)
        #logger.debug('<')
        return None


def bulk_insert_metrics(df_metrics):
    metrics_objects = []

    for _, row in df_metrics.iterrows():
        fwdcode = row['fwdcode']

        metrics_objects.append(FloodareaMetrics(
            fwdcode=fwdcode,
            bbox_wgs84_min_lat=row['bounding_box_wgs84'][0][0],
            bbox_wgs84_min_long=row['bounding_box_wgs84'][0][1],
            bbox_wgs84_max_lat=row['bounding_box_wgs84'][1][0],
            bbox_wgs84_max_long=row['bounding_box_wgs84'][1][1],
            bcen_wgs84_lat=row['bound_centre_wgs84'][0],
            bcen_wgs84_lon=row['bound_centre_wgs84'][1],
            mpoly_cent_wgs84_lat=row['mpoly_centroid_wgs84'][0],
            mpoly_cent_wgs84_lon=row['mpoly_centroid_wgs84'][1],

            bbox_bng_min_lat=row['bounding_box_bng'][0][0],
            bbox_bng_min_long=row['bounding_box_bng'][0][1],
            bbox_bng_max_lat=row['bounding_box_bng'][1][0],
            bbox_bng_max_long=row['bounding_box_bng'][1][1],
            bcen_bng_lat=row['bound_centre_bng'][0],
            bcen_bng_lon=row['bound_centre_bng'][1],
            mpoly_cent_bng_lat=row['mpoly_centroid_bng'][0],
            mpoly_cent_bng_lon=row['mpoly_centroid_bng'][1],

            area_km2=row['area_km2'],
            area_m2=row['area_m2'],
            rank=row['rank']
        ))

    db.session.bulk_save_objects(metrics_objects)
    db.session.commit()
    print(f"Inserted {len(metrics_objects)} rows into floodarea_metrics.")







