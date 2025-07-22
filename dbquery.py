from pandas import DataFrame, read_csv, read_sql_query

from sqlalchemy.engine import Engine
from sqlalchemy import text

# Create the SQL query to get floodarea polygon data (select area of interest here)

## ===================================================
def get_flood_areas_csv(
        eaareaname: str = '.*'
        , county: str = '.*'
        , description: str = '.*'
        , label: str = '.*'
        , riverorsea: str = '.*'
        , fwdcode: str = '.*'
) -> DataFrame:
    # Load the dataset from CSV file
    df_source = read_csv('EA_floodarea_source_data.csv')

    # Apply filters similar to the SQL query using pandas with regex patterns
    df = df_source[
        (df_source['eaareaname'].str.contains(eaareaname, regex=True, na=False)) &
        (df_source['county'].str.contains(county, regex=True, na=False)) &
        (df_source['description'].str.contains(description, regex=True, na=False)) &
        (df_source['label'].str.contains(label, regex=True, na=False)) &
        (df_source['riverorsea'].str.contains(riverorsea, regex=True, na=False)) &
        (df_source['fwdcode'].str.contains(fwdcode, regex=True, na=False))
        ]
    return df


## ===================================================
def get_flood_areas(engine: Engine, **kwargs) -> DataFrame:
    """
    Purpose: Retrieve a df of flood areas from Postgres (originally from Environment Agency)
    Params : engine: An sqlalchemy database engine
             **kwargs: see below
    Returns: A pandas DataFrame

    kwargs may include (with examples)
        eaareaname='East Anglia'
        county='Cam'
        description='Thames'
        label='tributaries'
        riverorsea='English Channel'
    Note that wildcard % is added to both ends of the strings before query submission
    If provided, these attribute statements must all be true to contribute to the returned df(ie "and" functionality)
    """

    # The plan is that later this will be called from a gui which has selector drop-downs to set these kwargs
    query = text('''
        select 
            *
        from v_floodarea f
        where f.eaareaname  ilike :eaareaname
          and f.county      ilike :county
          and f.description ilike :description
          and f.label       ilike :label
          and f.riverorsea  ilike :riverorsea
          and f.fwdcode     ilike :fwdcode
        ;
        ''')

    # Create query params using kwargs values if provided (surrounded with %), or '%' wildcard if not
    params = { key:
               f"%{kwargs[key]}%" if kwargs.get(key) else '%'
               for key in ['eaareaname', 'county', 'description', 'label', 'riverorsea', 'fwdcode']
             }

    # Execute the query with the updated parameters. Load data into the dataframe
    df = read_sql_query(query, engine, params=params)
    return df
