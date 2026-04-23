import copy
from typing import Any


def dict_lower_all_keys(in_dict: Any) -> Any:
    """
    Description:
    The dict_lower_all_keys function is a recursive utility designed to convert all dictionary keys in the input dictionary (in_dict) to lowercase.
    If the input dictionary contains nested dictionaries or lists with dictionaries, it will process them as well to ensure all dictionary keys at all nested levels are transformed to lowercase.
    For any other data types encountered within the dictionary, they are returned as-is without modification.

    Parameters:
    in_dict: A dictionary that can contain other nested dictionaries, lists, or other data types.

    Returns:
    A new dictionary with all keys converted to lowercase. If nested dictionaries or lists with dictionaries are encountered, they are transformed recursively.
    Behavior:
    """
    if isinstance(in_dict, dict):
        return {key.lower(): dict_lower_all_keys(item) for key, item in in_dict.items()}
    elif isinstance(in_dict, list):
        return [dict_lower_all_keys(obj) for obj in in_dict]
    else:
        return in_dict


def dict_lower_toplevel_keys(in_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Description:
    The dict_lower_toplevel_keys function transforms the keys of a dictionary to lowercase but only at the top-level.
    Nested dictionaries within the input remain unchanged.
    The function iterates through the key-value pairs of the given dictionary, converting each key to lowercase, and returns a new dictionary with these transformed keys.

    Parameters:
    in_dict: A dictionary with keys that need to be converted to lowercase. The dictionary can contain nested dictionaries, but the keys within these nested dictionaries won't be affected.

    Returns:
    A new dictionary where only the top-level keys have been converted to lowercase. Nested dictionaries or lists remain unchanged.
    """
    return {x.lower(): y for x, y in in_dict.items()}


def get_value_from_path(json_dict: dict[str, Any], path: str) -> Any:
    """
    Description:
    This function is designed to retrieve a value from a nested dictionary using a dot-separated path string.
    It navigates through the nested dictionary layers according to the provided path and returns the value at the end of the path.
    If the path does not exist in the dictionary, it will return None.

    Parameters:
    json_dict: A nested dictionary (can be a result of parsed JSON) from which the value needs to be extracted.

    path: A dot-separated string that represents the path through the nested dictionary to the desired value. For example, "a.b.c" represents a path that would retrieve the value in dict["a"]["b"]["c"].

    Returns:
    The value from the nested dictionary located at the specified path.
    If the path doesn't exist in the dictionary, it returns None.
    """
    path_elements = path.split(".")
    json_dict_copy = copy.deepcopy(json_dict)

    for element in path_elements:
        if element in json_dict_copy:
            if isinstance(json_dict_copy[element], dict):
                json_dict_copy = json_dict_copy[element]
            else:
                return json_dict_copy[element]
        else:
            return None

    return None
