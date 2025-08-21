from geoalchemy2 import WKBElement
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from shapely.ops import transform
from pyproj import Transformer

import logging
logger = logging.getLogger('floodWatch3')


def _transform_point(point: Point, from_crs: str, to_crs: str) -> Point:
    """
    Transforms a point from one coordinate reference system (CRS) to another.

    This function takes a geographic point defined in one CRS and transforms
    it to a new location in another CRS. The transformation is performed
    using a Transformer configured with the given source and target CRSs.

    :param point: The geographic point to transform.
    :type point: Point
    :param from_crs: The source coordinate reference system of the point,
        expressed as a string (e.g., EPSG code).
    :type from_crs: str
    :param to_crs: The target coordinate reference system to which the
        point will be transformed, expressed as a string (e.g., EPSG code).
    :type to_crs: str
    :return: A new Point transformed into the target CRS.
    :rtype: Point
    """
    transformer = Transformer.from_crs(from_crs, to_crs, always_xy=True)
    return transform(transformer.transform, point)

def _point_to_wkb(point: Point, srid: int) -> WKBElement:
    """
    Converts a given geometric point to a Well-Known Binary (WKB) representation.

    This function takes in a geometric point and a spatial reference identifier
    (SRID) and converts the point into its WKB representation, which is commonly
    used to store geometric objects in binary form in spatial databases.

    :param point: A geometric point to be converted.
    :type point: Point
    :param srid: The spatial reference identifier (SRID) of the point.
    :type srid: int
    :return: A Well-Known Binary representation of the point with SRID embedded.
    :rtype: WKBElement
    """
    return from_shape(point, srid=srid)

def get_geoms(lat: float, lon: float) -> tuple[WKBElement|None, WKBElement|None]:
    """
    Convert geospatial coordinates into Well-Known Binary (WKB) geometries for two different spatial
    reference systems (EPSG:4326 and EPSG:27700). If latitude and longitude values are valid, this
    function produces WKB representations of the original and transformed geometries. If the input
    parameters are invalid, it returns a tuple with None values.

    :param lat: The latitude value in decimal degrees
    :type lat: float
    :param lon: The longitude value in decimal degrees
    :type lon: float
    :return: A tuple containing WKB geometry in EPSG:4326 and WKB geometry in EPSG:27700. If the
        input is invalid, both elements of the tuple will be None.
    :rtype: tuple[WKBElement|None, WKBElement|None]
    """
    try:
        if lat is not None and lon is not None:
            lat = float(lat)
            lon = float(lon)

            point_4326 = Point(lon, lat)
            point_27700 = _transform_point(point_4326, "EPSG:4326", "EPSG:27700")
            geom4326 = _point_to_wkb(point_4326, 4326)
            geom27700 = _point_to_wkb(point_27700, 27700)
        else:
            geom4326 = None
            geom27700 = None
        return geom4326, geom27700
    except Exception as e:
        logger.error(f"Error getting geoms: {e}")
        logger.error(f"get_geoms parameters:> lat: {lat}, long: {lon}")
        return None, None
