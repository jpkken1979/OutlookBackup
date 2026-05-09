# HumanEval/14
# Loki Mode Multi-Agent Solution
# Attempts: 1
# Passed: True


def all_prefixes(string: str) -> list[str]:
    """Return list of all prefixes from shortest to longest of the input string
    >>> all_prefixes('abc')
    ['a', 'ab', 'abc']
    """
    return [string[:i] for i in range(1, len(string) + 1)]
