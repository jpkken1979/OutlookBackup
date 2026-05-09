# HumanEval/29
# Loki Mode Multi-Agent Solution
# Attempts: 1
# Passed: True


def filter_by_prefix(strings: list[str], prefix: str) -> list[str]:
    """Filter an input list of strings only for ones that start with a given prefix.
    >>> filter_by_prefix([], 'a')
    []
    >>> filter_by_prefix(['abc', 'bcd', 'cde', 'array'], 'a')
    ['abc', 'array']
    """
    return [s for s in strings if s.startswith(prefix)]
