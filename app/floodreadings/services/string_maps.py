import logging
logger = logging.getLogger('floodWatch2')

datumtype_map = {
    'mAOD' : '{root}/def/core/datumAOD',
    'mASD' : '{root}/def/core/datumASD',
    'mBDAT': '{root}/def/core/datumBDAT'
}
default_datumtype_map= None

period_map = {
    '5_min' : 300,
    '15_min': 900,
    '30_min': 1800,
    '1_h'   : 3600,
    'Unspecified': 0
}
default_period_map = 86400

valuetype_map = {
    'i': 'instantaneous',
    't': 'total',
    'Mean': 'mean',
    'Event': 'event',
    'Cumulative_Total': 'cumulative total'
}
#default_valuetype_map = just return original string

qualifier_map = {
    'crest_tapping':'Crest Tapping',
    'direction':'Direction',
    'downstage':'Downstream Stage',
    'dry_bulb':'Dry Bulb',
    'groundwater':'Groundwater',
    'height':'Height',
    'logged':'Logged',
    'reservoir_level':'Reservoir Level',
    'speed':'Speed',
    'stage':'Stage',
    'sump_level':'Sump Level',
    'tidal_level':'Tidal Level',
    'tipping_bucket_raingauge':'Tipping Bucket Raingauge',
    'water':'Water',
    'wet_bulb':'Wet Bulb'
}
#default_qualifier_map = just return original string

def get_datumtype_for_db(key:str) -> str:
    return datumtype_map.get(key, default_datumtype_map)

def get_period_for_db(key: str) -> int:
    return period_map.get(key, default_period_map)

def get_valuetype_for_db(key: str) -> str:
    return valuetype_map.get(key, key)

def get_qualifier_for_db(key: str) -> str:
    return qualifier_map.get(key, key)


FIELD_HANDLERS = {
    'datumtype': get_datumtype_for_db,
    'period'   : get_period_for_db,
    'valuetype': get_valuetype_for_db,
    'qualifier': get_qualifier_for_db
}

def get_fieldvalue_for_db(fieldname: str, raw_string: str) -> str | int | None:
    fieldname = fieldname.strip().lower()   # normalize input
    handler = FIELD_HANDLERS.get(fieldname)
    if handler:
        return handler(raw_string)
    logger.warning(f"Unknown fieldname: '{fieldname}' with key: '{raw_string}'")
    return None
