def all_prefixes(string: str) -> list[str]:
    """Return list of all prefixes from shortest to longest of the input string
    >>> all_prefixes('abc')
    ['a', 'ab', 'abc']
    """
    return [string[: i + 1] for i in range(len(string))]
