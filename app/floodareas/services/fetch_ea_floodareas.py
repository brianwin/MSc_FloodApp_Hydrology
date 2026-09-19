import pandas as pd
import requests
import os
import json

from sqlalchemy import text
import time
from ...utils import get_geoms

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, shape  #, MultiPolygon
from shapely.geometry import box as shapely_box
from shapely.ops import transform
from pyproj import Transformer

from app import db
from ..models import (
    FloodareaMeta, FloodareaJson,
    Floodarea, FloodareaPolygon, FloodareaMetrics
)

import logging
logger = logging.getLogger('floodWatch3')

ea_root_url = 'http://environment.data.gov.uk/flood-monitoring'

def load_floodarea_data_from_ea(truncate_all=True, force_replace=False):
    url = f'{ea_root_url}/id/floodAreas?_limit=10000'
    save_folder: str = "readings_hydrology_tn/floodareas"
    filename = f'floodareas.json'

    os.makedirs(save_folder, exist_ok=True)  # Ensure the folder exists
    filepath = os.path.join(save_folder, filename)
    logger.info(f"filepath  : {filepath}")

    if os.path.exists(filepath):
        logger.info(f"filepath found")
        if force_replace:
            logger.info(f"force_replace=True, attempting to delete: {filepath}")
            try:
                logger.info(f"os.path.isfile({filepath!r}) = {os.path.isfile(filepath)}")
                os.remove(filepath)
            except FileNotFoundError:
                logger.warning(f"File disappeared before delete: {filepath}")
            except PermissionError as e:
                logger.error(f"Permission error deleting {filepath}: {e}")
            except IsADirectoryError as e:
                logger.error(f"Expected a file but {filepath} is a directory: {e}")
            except OSError as e:
                logger.error(f"OS error deleting {filepath}: {e}")
            else:
                logger.info(f"Successfully removed existing file: {filepath}")
        else:
            logger.info("force_replace=False, not deleting existing file here")
            if os.path.getsize(filepath) == 0:
                logger.warning(f"File exists, but is empty: {filepath}")
                os.remove(filepath)
                logger.info(f"Removed existing file: {filepath}")
            else:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if not data.get('items'):
                        logger.warning(f"File exists, but has no items: {filepath}")
                        os.remove(filepath)
                        logger.info(f"Removed existing file: {filepath}")
                    else:
                        logger.info(f"Using existing local file: {filepath}")
                        # Process from cached file
                        if truncate_all:
                            truncate_all_floodareas()
                        _process_floodarea_data(data)
                        return data
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Cached file is corrupt, removing: {filepath} ({e})")
                    os.remove(filepath)

    # Download if the file doesn't exist after optional deletion
    t0 = time.perf_counter()
    response = requests.get(url, timeout=60)
    t1 = time.perf_counter()

    if response.status_code == 200:
        logger.info(f'Fetching {url}')
        logger.info(f'Response {response.status_code}')

        data = response.json()

        # Save the JSON file to local os
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        t2 = time.perf_counter()
        nbytes = os.path.getsize(filepath)
        logger.info(f"Saved: {filepath}")
    else:
        logger.warning(f'Response {response.status_code}: Failed to fetch data from {url}')
        return None

    t3 = time.perf_counter()

    logger.info(f"GET (headers/conn): {t1 - t0:.3f}s")
    logger.info(f"WRITE {nbytes / 1e6:.1f} MB: {t2 - t1:.3f}s  -> {(nbytes / 1e6) / (t2 - t1):.1f} MB/s")
    logger.info(f"TOTAL: {t3 - t0:.3f}s, file size on disk: {nbytes / 1e6:.1f} MB")

    if truncate_all:
        truncate_all_floodareas()
    _process_floodarea_data(data)


def _process_floodarea_data(data):
    """Process the parsed JSON flood area data and save to database."""
    # save the "meta" table contents
    floodarea_meta_id = save_floodarea_meta(data.get('@context'), data['meta'])
    logger.info(f"meta data saved with floodarea_meta_id = {floodarea_meta_id}")

    count_items = 0
    start_time = time.time()
    for floodarea in data['items']:
        count_items += 1
        if count_items % 500 == 0:
            logger.info(f'Fetched {count_items} floodareas - elapsed= {int(time.time() - start_time)} seconds')

        # save the raw item data row to the "json" table
        floodarea_json_id = save_floodarea_json(floodarea_meta_id, floodarea)
        geom4326, geom27700 = get_geoms(floodarea.get('lat'), floodarea.get('long'))

        save_floodarea = Floodarea(
            # Remove explicit floodarea_id assignment to let DB handle it
            EnvAgy_id = floodarea.get('@id', '').replace(ea_root_url, '{root}'),
            county = floodarea.get('county'),
            description = floodarea.get('description'),
            eaAreaName = floodarea.get('eaAreaName'),
            eaRegionName = floodarea.get('eaRegionName'),
            floodWatchArea = floodarea.get('floodWatchArea'),
            fwdCode = floodarea.get('fwdCode'),
            label = floodarea.get('label'),
            lat=float(floodarea.get('lat') or 0),
            long=float(floodarea.get('long') or 0),
            notation = floodarea.get('notation'),
            polygon = (floodarea.get('polygon') or '').replace(ea_root_url, '{root}'),
            quickDialNumber = floodarea.get('quickDialNumber'),
            riverOrSea = floodarea.get('riverOrSea'),
            geom4326 = geom4326,
            geom27700 = geom27700
        )
        db.session.add(save_floodarea)
        db.session.flush() # Get the generated ID for save_floodarea
        floodarea_id = save_floodarea.floodarea_id

        url = floodarea.get('polygon')
        if url and count_items >4100 :
            try:
                poly_response = requests.get(url, timeout=30)
                logger.warning(f"        fetch polygon data for {url} - Status: {poly_response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed for polygon {url}: {e}")
                continue

            if poly_response.status_code != 200 or not poly_response.content:
                logger.warning(f"Could not fetch polygon data for {url} - Status: {poly_response.status_code}")
                continue

            try:
                poly = poly_response.json()
            except requests.exceptions.JSONDecodeError:
                logger.warning(f"Failed to decode JSON from {url}")
                continue

            poly = validate_polygon_json (poly)
            if not poly:
                continue

            geometry = poly['features'][0]['geometry']
            poly_geom = shape(geometry)  # Shapely geometry (Polygon or MultiPolygon)

            save_polygon = FloodareaPolygon(
                floodarea_id=floodarea_id,
                fwdCode=save_floodarea.fwdCode,
                lat=save_floodarea.lat,
                long=save_floodarea.long,
                geom4326=geom4326,
                geom27700=geom27700,
                polygon_json=poly,
                polygon_geom=from_shape(poly_geom, srid=4326)
            )
            db.session.add(save_polygon)

            #logger.info(floodarea_id)
            #logger.info(save_floodarea.fwdCode)
            #logger.info(poly)

            save_metrics = create_save_metrics_row(floodarea_id, save_floodarea.fwdCode, poly)
            if save_metrics:
                #logger.info(save_metrics.floodarea_id )
                db.session.add(save_metrics)

    db.session.commit()
    floodarea_count = db.session.query(Floodarea).count()
    floodarea_polygons_count = db.session.query(FloodareaPolygon).count()
    floodarea_metrics_count = db.session.query(FloodareaMetrics).count()
    logger.info(f'Floodarea data loaded successfully - {floodarea_count} floodareas, {floodarea_polygons_count} polygons {floodarea_metrics_count} metrics')
    logger.info(f'Elapsed= {int(time.time() - start_time)} seconds')


def truncate_all_floodareas():
    # Truncate *meta - all other tables will cascade delete
    count_before = db.session.query(Floodarea).count()
    logger.info(f'floodareas - row count before truncate: {count_before}')
    
    # RESTART IDENTITY resets the sequences for the truncated tables
    db.session.execute(text('TRUNCATE TABLE ea_source.floodarea_meta RESTART IDENTITY CASCADE'))
    logger.info(f'floodarea_meta truncated (and seq reset)')
    # Also truncate the production table if it's not being caught by the cascade
    db.session.execute(text('TRUNCATE TABLE production.floodarea RESTART IDENTITY CASCADE'))
    logger.info(f'floodarea main table truncated (and seq reset)')

    db.session.commit()
    db.session.expire_all()
    
    #logger.info(f'ea_source.floodarea_meta and production.floodarea truncated and sequences reset')
    count_after = db.session.query(Floodarea).count()
    logger.info(f'floodareas - row count after truncate: {count_after}')


def save_floodarea_meta(context: str, meta: dict) -> int:
    # Insert meta
    floodarea_meta = FloodareaMeta(
        context = context,
        publisher = meta.get('publisher'),
        license = meta.get('license'),
        documentation = meta.get('documentation'),
        version = float(meta.get('version')),
        comment = meta.get('comment'),
        hasFormat = meta.get('hasFormat')
    )
    db.session.add(floodarea_meta)
    db.session.flush()  # To get floodarea_meta.id
    return floodarea_meta.floodarea_meta_id


def save_floodarea_json(floodarea_meta_id: int, floodarea: dict) -> int:
        # Save full JSON
        floodarea_json = FloodareaJson(
            floodarea_meta_id=floodarea_meta_id,
            floodarea_data=floodarea
        )
        db.session.add(floodarea_json)
        return floodarea_json.floodarea_id


def validate_polygon_json(p_geojson: str | dict) -> dict|None:
    """ Validate a polygon json (either str or dict) and return a dist if valid, None if not valid.
    :param p_geojson: a str or dict
    :return: a dict or None
    """
    # Ensure we have a parsed JSON dict
    if isinstance(p_geojson, str):
        try:
            return_geojson = json.loads(p_geojson)
        except json.JSONDecodeError as e:
            logger.error("Invalid GeoJSON string:", e)
            return None
    elif isinstance(p_geojson, dict):
        try:
            return_geojson = p_geojson
        except json.JSONDecodeError as e:
            logger.error("Invalid GeoJSON dict:", e)
            return None
    else:
        logger.error("Invalid input type. Expected GeoJSON str or dict.")
        return None
    return return_geojson

def create_save_metrics_row(floodarea_id: int, fwdcode: str, polygon: dict) -> pd.DataFrame|None:
    try:
        df_wgs84 = get_wgs84_metrics(polygon)
        #logger.info('1==========')
        #logger.info(f"df_wgs84 : {df_wgs84['bounding_box_wgs84'][0]}  {df_wgs84['bound_centre_wgs84'][0]}  {df_wgs84['mpoly_centroid_wgs84'][0]}")
        #logger.info('2==========')
        df_bng = get_bng_metrics(polygon)
        #logger.info('3==========')
        #logger.info(f"df_bng : {df_bng['bounding_box_bng'][0]}  {df_bng['bound_centre_bng'][0]}  {df_bng['mpoly_centroid_bng'][0]}")
        #logger.info('4==========')

        if df_wgs84 is None or df_bng is None:
            logging.warning(f"Could not compute metrics for floodarea_id={floodarea_id}")
            return None

        # Shapely geometries from metrics
        bbox_wgs84 = df_wgs84['bounding_box_wgs84'][0]
        bcen_wgs84 = df_wgs84['bound_centre_wgs84'][0]
        mpoly_cent_wgs84 = df_wgs84['mpoly_centroid_wgs84'][0]

        bbox_bng = df_bng['bounding_box_bng'][0]
        bcen_bng = df_bng['bound_centre_bng'][0]
        mpoly_cent_bng = df_bng['mpoly_centroid_bng'][0]

        area_km2 = df_bng['area_km2'][0]
        area_m2 = df_bng['area_m2'][0]

        # Create Polygon bounding boxes
        bbox_poly_wgs84 = shapely_box(
            bbox_wgs84[0][1], bbox_wgs84[0][0],  # min long, min lat
            bbox_wgs84[1][1], bbox_wgs84[1][0],  # max long, max lat
        )
        bbox_poly_bng = shapely_box(
            bbox_bng[0][0], bbox_bng[0][1],  # min x, min y
            bbox_bng[1][0], bbox_bng[1][1],  # max x, max y
        )

        # Create row
        metrics = FloodareaMetrics(
            floodarea_id=floodarea_id,
            fwdCode=fwdcode,

            bbox_wgs84_min_lat=bbox_wgs84[0][0],
            bbox_wgs84_min_long=bbox_wgs84[0][1],
            bbox_wgs84_max_lat=bbox_wgs84[1][0],
            bbox_wgs84_max_long=bbox_wgs84[1][1],

            bcen_wgs84_lat=bcen_wgs84[0],
            bcen_wgs84_long=bcen_wgs84[1],
            mpoly_cent_wgs84_lat=mpoly_cent_wgs84[0],
            mpoly_cent_wgs84_long=mpoly_cent_wgs84[1],

            geom_bbox_wgs84=from_shape(bbox_poly_wgs84, srid=4326),
            geom_bcen_wgs84=from_shape(shape({'type': 'Point', 'coordinates': bcen_wgs84[::-1]}), srid=4326),
            geom_mpoly_cent_wgs84=from_shape(shape({'type': 'Point', 'coordinates': mpoly_cent_wgs84[::-1]}), srid=4326),

            bbox_bng_min_lat=bbox_bng[0][1],
            bbox_bng_min_long=bbox_bng[0][0],
            bbox_bng_max_lat=bbox_bng[1][1],
            bbox_bng_max_long=bbox_bng[1][0],

            bcen_bng_lat=bcen_bng[1],
            bcen_bng_long=bcen_bng[0],
            mpoly_cent_bng_lat=mpoly_cent_bng[1],
            mpoly_cent_bng_long=mpoly_cent_bng[0],

            geom_bbox_bng=from_shape(bbox_poly_bng, srid=27700),
            geom_bcen_bng=from_shape(shape({'type': 'Point', 'coordinates': bcen_bng}), srid=27700),
            geom_mpoly_cent_bng=from_shape(shape({'type': 'Point', 'coordinates': mpoly_cent_bng}), srid=27700),

            area_km2=area_km2,
            area_m2=area_m2
        )
        return metrics
    except Exception as e:
        logging.exception(f"Failed to insert FloodareaMetrics for ID {floodarea_id}: {e}")
        return None


def get_wgs84_metrics(p_geojson: dict) -> pd.DataFrame|None:
    """ Returns a one row dataframe of wgs84 metrics.
    :param p_geojson: A dict - polygon json
    :return: a dataframe of wgs84 metrics
    """
    try:
        # In web mapping APIs like Google Maps, spatial coordinates are often in order of latitude then longitude.
        # In spatial databases like PostGIS and SQL Server, spatial coordinates are in longitude and then latitude.

        # Folium maps use WGS84 grid for positioning, feature plotting, feedback end so on, and all of these have
        # coordinates in (latitude (GetY(), N +ve, S -ve), longitude (GetX(), W -ve, E +ve)).

        # We use that convention throughout this application
        geometry = p_geojson['features'][0]['geometry']
        poly = shape(geometry)  # Shapely geometry (Polygon or MultiPolygon)

        # Bounding box and centroid in WGS84
        min_long, min_lat, max_long, max_lat = poly.bounds
        bounding_box_wgs84 = [[min_lat, min_long], [max_lat, max_long]]
        bound_centre_wgs84 = [round((max_lat + min_lat) / 2, 6), round((max_long + min_long) / 2, 6)]
        mpoly_centroid_wgs84 = [round(poly.centroid.y, 6), round(poly.centroid.x, 6)]

        row = {
            'bounding_box_wgs84': bounding_box_wgs84,
            'bound_centre_wgs84': bound_centre_wgs84,
            'mpoly_centroid_wgs84': mpoly_centroid_wgs84
        }
        return pd.DataFrame([row])  # single-row DataFrame
    except Exception as e:
        logger.critical("Error in getPolygonMetricsRow:", e)
        return None

def get_bng_metrics(p_geojson: dict) -> pd.DataFrame|None:
    """ Returns a one row dataframe of bng metrics.

    :param p_geojson: A dict - polygon json
    :return: a dataframe of wgs84 metrics
    """
    try:
        geometry = p_geojson['features'][0]['geometry']
        poly = shape(geometry)  # Shapely geometry (Polygon or MultiPolygon)

        transformer = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
        poly_bng = transform(transformer.transform, poly)

        # Bounding box and centroid in BNG
        min_x, min_y, max_x, max_y = poly_bng.bounds
        bounding_box_bng = [[round(min_x, 6), round(min_y, 6)], [round(max_x, 6), round(max_y, 6)]]
        bound_centre_bng = [round((max_x + min_x) / 2, 6), round((max_y + min_y) / 2, 6)]
        mpoly_centroid_bng = [round(poly_bng.centroid.x, 6), round(poly_bng.centroid.y, 6)]
        area = poly_bng.area  # in square meters

        row = {
            'bounding_box_bng':     bounding_box_bng,
            'bound_centre_bng':     bound_centre_bng,
            'mpoly_centroid_bng':   mpoly_centroid_bng,
            'area_km2': area / 1e6,
            'area_m2': area
        }
        return pd.DataFrame([row])  # single-row DataFrame
    except Exception as e:
        logging.critical("Error in getPolygonMetricsRow:", {e})
        return None
