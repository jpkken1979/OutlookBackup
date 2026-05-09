#!/usr/bin/env python3
"""
Data Structures & Algorithms - Implementaciones Ejecutables
Estructuras de datos y algoritmos fundamentales con ejemplos.
"""

import logging
from dataclasses import dataclass
from typing import Optional, TypeVar, Generic
from collections import deque

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# DATA STRUCTURES
# =============================================================================


# --- Stack (LIFO) ---
class Stack(Generic[T]):
    """Pila - Last In First Out."""

    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        if self.is_empty():
            raise IndexError("Stack is empty")
        return self._items.pop()

    def peek(self) -> T:
        if self.is_empty():
            raise IndexError("Stack is empty")
        return self._items[-1]

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def size(self) -> int:
        return len(self._items)


# --- Queue (FIFO) ---
class Queue(Generic[T]):
    """Cola - First In First Out."""

    def __init__(self) -> None:
        self._items: deque[T] = deque()

    def enqueue(self, item: T) -> None:
        self._items.append(item)

    def dequeue(self) -> T:
        if self.is_empty():
            raise IndexError("Queue is empty")
        return self._items.popleft()

    def front(self) -> T:
        if self.is_empty():
            raise IndexError("Queue is empty")
        return self._items[0]

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def size(self) -> int:
        return len(self._items)


# --- Linked List ---
@dataclass
class ListNode(Generic[T]):
    value: T
    next: Optional["ListNode[T]"] = None


class LinkedList(Generic[T]):
    """Lista enlazada simple."""

    def __init__(self) -> None:
        self.head: ListNode[T] | None = None
        self._size = 0

    def append(self, value: T) -> None:
        new_node = ListNode(value)
        if not self.head:
            self.head = new_node
        else:
            current = self.head
            while current.next:
                current = current.next
            current.next = new_node
        self._size += 1

    def prepend(self, value: T) -> None:
        new_node = ListNode(value, self.head)
        self.head = new_node
        self._size += 1

    def delete(self, value: T) -> bool:
        if not self.head:
            return False
        if self.head.value == value:
            self.head = self.head.next
            self._size -= 1
            return True
        current = self.head
        while current.next:
            if current.next.value == value:
                current.next = current.next.next
                self._size -= 1
                return True
            current = current.next
        return False

    def to_list(self) -> list[T]:
        result = []
        current = self.head
        while current:
            result.append(current.value)
            current = current.next
        return result

    def size(self) -> int:
        return self._size


# --- Binary Search Tree ---
@dataclass
class TreeNode(Generic[T]):
    value: T
    left: Optional["TreeNode[T]"] = None
    right: Optional["TreeNode[T]"] = None


class BinarySearchTree(Generic[T]):
    """Árbol binario de búsqueda."""

    def __init__(self) -> None:
        self.root: TreeNode[T] | None = None

    def insert(self, value: T) -> None:
        if not self.root:
            self.root = TreeNode(value)
        else:
            self._insert_recursive(self.root, value)

    def _insert_recursive(self, node: TreeNode[T], value: T) -> None:
        if value < node.value:
            if node.left:
                self._insert_recursive(node.left, value)
            else:
                node.left = TreeNode(value)
        else:
            if node.right:
                self._insert_recursive(node.right, value)
            else:
                node.right = TreeNode(value)

    def search(self, value: T) -> bool:
        return self._search_recursive(self.root, value)

    def _search_recursive(self, node: TreeNode[T] | None, value: T) -> bool:
        if not node:
            return False
        if value == node.value:
            return True
        if value < node.value:
            return self._search_recursive(node.left, value)
        return self._search_recursive(node.right, value)

    def inorder(self) -> list[T]:
        result: list[T] = []
        self._inorder_recursive(self.root, result)
        return result

    def _inorder_recursive(self, node: TreeNode[T] | None, result: list[T]) -> None:
        if node:
            self._inorder_recursive(node.left, result)
            result.append(node.value)
            self._inorder_recursive(node.right, result)


# --- Hash Map (simplified) ---
class HashMap(Generic[T]):
    """Tabla hash simple."""

    def __init__(self, capacity: int = 16) -> None:
        self._capacity = capacity
        self._buckets: list[list[tuple[str, T]]] = [[] for _ in range(capacity)]
        self._size = 0

    def _hash(self, key: str) -> int:
        return hash(key) % self._capacity

    def put(self, key: str, value: T) -> None:
        index = self._hash(key)
        bucket = self._buckets[index]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)
                return
        bucket.append((key, value))
        self._size += 1

    def get(self, key: str) -> T | None:
        index = self._hash(key)
        for k, v in self._buckets[index]:
            if k == key:
                return v
        return None

    def delete(self, key: str) -> bool:
        index = self._hash(key)
        bucket = self._buckets[index]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket.pop(i)
                self._size -= 1
                return True
        return False

    def size(self) -> int:
        return self._size


# =============================================================================
# ALGORITHMS
# =============================================================================


# --- Sorting ---
def quicksort(arr: list[int]) -> list[int]:
    """QuickSort - O(n log n) average."""
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)


def mergesort(arr: list[int]) -> list[int]:
    """MergeSort - O(n log n) guaranteed."""
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = mergesort(arr[:mid])
    right = mergesort(arr[mid:])
    return merge(left, right)


def merge(left: list[int], right: list[int]) -> list[int]:
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


# --- Searching ---
def binary_search(arr: list[int], target: int) -> int:
    """Binary Search - O(log n)."""
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1


# --- Graph Algorithms ---
def bfs(graph: dict[str, list[str]], start: str) -> list[str]:
    """Breadth-First Search."""
    visited = set()
    queue = deque([start])
    result = []

    while queue:
        node = queue.popleft()
        if node not in visited:
            visited.add(node)
            result.append(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)
    return result


def dfs(graph: dict[str, list[str]], start: str) -> list[str]:
    """Depth-First Search."""
    visited = set()
    result = []

    def dfs_recursive(node: str) -> None:
        if node in visited:
            return
        visited.add(node)
        result.append(node)
        for neighbor in graph.get(node, []):
            dfs_recursive(neighbor)

    dfs_recursive(start)
    return result


# --- Dynamic Programming ---
def fibonacci_dp(n: int) -> int:
    """Fibonacci con memoization - O(n)."""
    if n <= 1:
        return n
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i - 1] + dp[i - 2]
    return dp[n]


def longest_common_subsequence(s1: str, s2: str) -> int:
    """LCS - O(m*n)."""
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    return dp[m][n]


# =============================================================================
# DEMO
# =============================================================================


def main() -> None:
    """Demostración de estructuras de datos y algoritmos."""
    print("\n" + "=" * 60)
    print("DATA STRUCTURES & ALGORITHMS - Ejemplos Ejecutables")
    print("=" * 60)

    # Stack
    print("\n--- STACK ---")
    stack: Stack[int] = Stack()
    for i in [1, 2, 3]:
        stack.push(i)
    print(f"Stack: pop={stack.pop()}, peek={stack.peek()}, size={stack.size()}")

    # Queue
    print("\n--- QUEUE ---")
    queue: Queue[str] = Queue()
    for item in ["A", "B", "C"]:
        queue.enqueue(item)
    print(f"Queue: dequeue={queue.dequeue()}, front={queue.front()}")

    # Linked List
    print("\n--- LINKED LIST ---")
    ll: LinkedList[int] = LinkedList()
    for i in [1, 2, 3]:
        ll.append(i)
    ll.prepend(0)
    print(f"LinkedList: {ll.to_list()}")

    # BST
    print("\n--- BINARY SEARCH TREE ---")
    bst: BinarySearchTree[int] = BinarySearchTree()
    for val in [5, 3, 7, 1, 4, 6, 8]:
        bst.insert(val)
    print(f"BST inorder: {bst.inorder()}")
    print(f"BST search(4): {bst.search(4)}, search(9): {bst.search(9)}")

    # HashMap
    print("\n--- HASH MAP ---")
    hm: HashMap[int] = HashMap()
    hm.put("one", 1)
    hm.put("two", 2)
    hm.put("three", 3)
    print(f"HashMap: get('two')={hm.get('two')}, size={hm.size()}")

    # Sorting
    print("\n--- SORTING ---")
    arr = [64, 34, 25, 12, 22, 11, 90]
    print(f"Original: {arr}")
    print(f"QuickSort: {quicksort(arr.copy())}")
    print(f"MergeSort: {mergesort(arr.copy())}")

    # Binary Search
    print("\n--- BINARY SEARCH ---")
    sorted_arr = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    print(f"Array: {sorted_arr}")
    print(f"Search 5: index={binary_search(sorted_arr, 5)}")
    print(f"Search 10: index={binary_search(sorted_arr, 10)}")

    # Graph Algorithms
    print("\n--- GRAPH ALGORITHMS ---")
    graph = {"A": ["B", "C"], "B": ["D", "E"], "C": ["F"], "D": [], "E": ["F"], "F": []}
    print(f"BFS from A: {bfs(graph, 'A')}")
    print(f"DFS from A: {dfs(graph, 'A')}")

    # Dynamic Programming
    print("\n--- DYNAMIC PROGRAMMING ---")
    print(f"Fibonacci(10): {fibonacci_dp(10)}")
    print(f"LCS('ABCBDAB', 'BDCAB'): {longest_common_subsequence('ABCBDAB', 'BDCAB')}")

    print("\n" + "=" * 60)
    print("Todos los algoritmos ejecutados exitosamente")
    print("=" * 60)


if __name__ == "__main__":
    main()
