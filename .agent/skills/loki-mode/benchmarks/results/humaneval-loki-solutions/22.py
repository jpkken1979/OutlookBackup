# HumanEval/22
# Loki Mode Multi-Agent Solution
# Attempts: 1
# Passed: True

from typing import Any


def filter_integers(values: list[Any]) -> list[int]:
    """Filter given list of any python values only for integers
    >>> filter_integers(['a', 3.14, 5])
    [5]
    >>> filter_integers([1, 2, 3, 'abc', {}, []])
    [1, 2, 3]
    """
    return [x for x in values if isinstance(x, int) and not isinstance(x, bool)]
