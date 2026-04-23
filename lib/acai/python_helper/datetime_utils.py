from datetime import datetime


def datetime_to_yyyymmdd_hhmmss(datetime_stamp: datetime) -> str:
    """
    Description:
    Convert a datetime object to a string in the format YYYYMMDD_hhmmss.

    Parameters:
    - datetime_stamp (datetime): The datetime object to be converted.

    Returns:
    - str: The datetime represented as a string in the format YYYYMMDD_hhmmss.
    """
    return datetime_stamp.strftime("%Y%m%d_%H%M%S")


def aws_timestamp_to_yyyymmdd_hhmmss(timestamp: str) -> str:
    """
    Description:
    Convert an AWS timestamp of the format "2019-12-20T11:47:26Z" to a string in the format YYYYMMDD_hhmmss.
    The AWS timestamp can be in the format "2019-12-18T13:17:42.866+0000" or "2019-12-20T11:47:26Z".

    Parameters:
    - timestamp (str): The AWS timestamp string.

    Returns:
    - str: The timestamp represented as a string in the format YYYYMMDD_hhmmss.
    """
    dt_obj = datetime.fromisoformat(
        timestamp.rstrip("Z").split(".")[0].replace("T", " ")
    )
    return dt_obj.strftime("%Y%m%d_%H%M%S")


def aws_timestamp_to_datetime(timestamp: str) -> datetime:
    """
    Description:
    Convert an AWS timestamp of the format "2019-12-20T11:47:26Z" to a datetime object.
    The AWS timestamp can be in the format "2019-12-18T13:17:42.866+0000" or "2019-12-20T11:47:26Z".

    Parameters:
    - timestamp (str): The AWS timestamp string.

    Returns:
    - datetime: A datetime object representing the timestamp.
    """
    return datetime.fromisoformat(timestamp.rstrip("Z").split(".")[0].replace("T", " "))
