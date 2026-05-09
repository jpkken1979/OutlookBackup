def intersperse(numbers: list[int], delimeter: int) -> list[int]:
    """Insert a number 'delimeter' between every two consecutive elements of input list `numbers'
    >>> intersperse([], 4)
    []
    >>> intersperse([1, 2, 3], 4)
    [1, 4, 2, 4, 3]
    """
    if not numbers:
        return []

    result = [numbers[0]]
    for num in numbers[1:]:
        result.append(delimeter)
        result.append(num)

    return result
