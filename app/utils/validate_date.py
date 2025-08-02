import click
import datetime

def validate_date(_ctx, _param, value):
    """
    Click callback to validate YYYY-MM-DD dates.
    `_ctx` and `_param` are required by Click but intentionally unused.
    """
    # 1) Already a date? just return it.
    if isinstance(value, datetime.date):
        return value

    #if value is None or (isinstance(value, str) and value.strip() == ""):
    if not value:
        #print ('help me here')  #Interesting - this is called twice?
        return None

    # Ensure it’s a string (CLI always gives strings)
    val = value.strip()
    try:
        return datetime.datetime.strptime(val, '%Y-%m-%d').date()
    except ValueError:
        raise click.BadParameter("Date must be in format YYYY-MM-DD")


