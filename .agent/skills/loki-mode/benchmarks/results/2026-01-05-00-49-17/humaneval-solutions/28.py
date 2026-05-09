def concatenate(strings: list[str]) -> str:
    """Concatenate list of strings into a single string
    >>> concatenate([])
    ''
    >>> concatenate(['a', 'b', 'c'])
    'abc'
    """
    return "".join(strings)
