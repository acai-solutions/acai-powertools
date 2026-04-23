from hashlib import blake2b


def get_16_bytes_hash(input_string: str) -> str:
    """
    Description:
    Generates a 16-byte hash of the given input string using the BLAKE2b cryptographic hash algorithm.

    Parameters:
    - input_string (str): The string to be hashed.

    Returns:
    - str: The 16-byte hash in hexadecimal format.
    """
    return blake2b(input_string.encode("utf-8"), digest_size=8).hexdigest()
