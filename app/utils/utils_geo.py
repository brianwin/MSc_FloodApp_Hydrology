from geoalchemy2 import WKBElement
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from shapely.ops import transform
from pyproj import Transformer

def get_geoms(lat: float, long: float) -> (WKBElement, WKBElement):
    if lat is not None and long is not None:
        lat = float(lat)
        long = float(long)

        point_4326 = Point(long, lat)
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
        point_27700 = transform(transformer.transform, point_4326)

        geom4326 = from_shape(point_4326, srid=4326)
        geom27700 = from_shape(point_27700, srid=27700)
    else:
        geom4326 = None
        geom27700 = None
    return geom4326, geom27700
