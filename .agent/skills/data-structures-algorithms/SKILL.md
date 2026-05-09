---
name: data-structures-algorithms
description: "- Optimizando performance de código"
type: feature
---

# Data Structures & Algorithms

> Estructuras de datos y algoritmos esenciales para programación eficiente.

## Cuándo Usar Esta Skill

- Optimizando performance de código
- Resolviendo problemas algorítmicos
- Entrevistas técnicas
- Diseñando estructuras de datos custom

---

## Complejidad (Big-O)

### Tabla de Referencia Rápida

| Complejidad | Nombre | Ejemplo | 1K items | 1M items |
|-------------|--------|---------|----------|----------|
| O(1) | Constante | Hash lookup | 1 op | 1 op |
| O(log n) | Logarítmica | Binary search | 10 ops | 20 ops |
| O(n) | Lineal | Linear search | 1K ops | 1M ops |
| O(n log n) | Linearítmica | Merge sort | 10K ops | 20M ops |
| O(n²) | Cuadrática | Bubble sort | 1M ops | 1T ops |
| O(2ⁿ) | Exponencial | Fibonacci naive | ∞ | ∞ |

### Reglas para Análisis

```python
# O(1) - Constante
def get_first(arr):
    return arr[0]  # Siempre 1 operación

# O(n) - Lineal
def find_max(arr):
    max_val = arr[0]
    for x in arr:  # n iteraciones
        if x > max_val:
            max_val = x
    return max_val

# O(n²) - Cuadrática
def find_pairs(arr):
    pairs = []
    for i in range(len(arr)):      # n
        for j in range(len(arr)):  # × n = n²
            pairs.append((arr[i], arr[j]))
    return pairs

# O(log n) - Logarítmica
def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1  # Divide by 2 each time
        else:
            right = mid - 1
    return -1
```

---

## Estructuras de Datos

### 1. Arrays / Lists

```python
# Operaciones y complejidad
arr = [1, 2, 3, 4, 5]

arr[0]          # O(1) - Access by index
arr.append(6)   # O(1) amortized - Add to end
arr.insert(0,0) # O(n) - Insert at beginning
arr.pop()       # O(1) - Remove from end
arr.pop(0)      # O(n) - Remove from beginning
x in arr        # O(n) - Search
```

### 2. Hash Tables (Dictionaries)

```python
# Operaciones y complejidad
d = {}

d["key"] = "value"  # O(1) average - Insert
d["key"]            # O(1) average - Access
del d["key"]        # O(1) average - Delete
"key" in d          # O(1) average - Search

# Manejo de colisiones: Chaining vs Open Addressing
# Python usa Open Addressing con perturbación
```

**Cuándo usar:**
- Lookup rápido por clave
- Contar frecuencias
- Eliminar duplicados
- Caching

### 3. Sets

```python
s = {1, 2, 3}

s.add(4)        # O(1) average
s.remove(1)     # O(1) average
3 in s          # O(1) average
s1 & s2         # O(min(len(s1), len(s2))) - Intersection
s1 | s2         # O(len(s1) + len(s2)) - Union
```

### 4. Stacks (LIFO)

```python
class Stack:
    def __init__(self):
        self.items = []
    
    def push(self, item):    # O(1)
        self.items.append(item)
    
    def pop(self):           # O(1)
        return self.items.pop()
    
    def peek(self):          # O(1)
        return self.items[-1]
    
    def is_empty(self):      # O(1)
        return len(self.items) == 0

# Uso: Undo/redo, parsing, DFS, call stack
```

### 5. Queues (FIFO)

```python
from collections import deque

class Queue:
    def __init__(self):
        self.items = deque()
    
    def enqueue(self, item):  # O(1)
        self.items.append(item)
    
    def dequeue(self):        # O(1)
        return self.items.popleft()
    
    def is_empty(self):       # O(1)
        return len(self.items) == 0

# Uso: BFS, scheduling, buffers
```

### 6. Linked Lists

```python
class Node:
    def __init__(self, val):
        self.val = val
        self.next = None

class LinkedList:
    def __init__(self):
        self.head = None
    
    def insert_front(self, val):  # O(1)
        node = Node(val)
        node.next = self.head
        self.head = node
    
    def insert_end(self, val):    # O(n)
        if not self.head:
            self.head = Node(val)
            return
        curr = self.head
        while curr.next:
            curr = curr.next
        curr.next = Node(val)
    
    def delete(self, val):        # O(n)
        if self.head and self.head.val == val:
            self.head = self.head.next
            return
        curr = self.head
        while curr and curr.next:
            if curr.next.val == val:
                curr.next = curr.next.next
                return
            curr = curr.next

# Uso: Cuando inserciones/eliminaciones frecuentes al inicio
```

### 7. Trees

```python
class TreeNode:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

# Binary Search Tree (BST)
class BST:
    def __init__(self):
        self.root = None
    
    def insert(self, val):           # O(log n) average, O(n) worst
        if not self.root:
            self.root = TreeNode(val)
            return
        self._insert(self.root, val)
    
    def _insert(self, node, val):
        if val < node.val:
            if node.left:
                self._insert(node.left, val)
            else:
                node.left = TreeNode(val)
        else:
            if node.right:
                self._insert(node.right, val)
            else:
                node.right = TreeNode(val)
    
    def search(self, val):           # O(log n) average, O(n) worst
        return self._search(self.root, val)
    
    def _search(self, node, val):
        if not node or node.val == val:
            return node
        if val < node.val:
            return self._search(node.left, val)
        return self._search(node.right, val)

# Tree Traversals
def inorder(node):    # Left, Root, Right (sorted for BST)
    if node:
        inorder(node.left)
        print(node.val)
        inorder(node.right)

def preorder(node):   # Root, Left, Right
    if node:
        print(node.val)
        preorder(node.left)
        preorder(node.right)

def postorder(node):  # Left, Right, Root
    if node:
        postorder(node.left)
        postorder(node.right)
        print(node.val)

def levelorder(root):  # BFS
    if not root:
        return
    queue = deque([root])
    while queue:
        node = queue.popleft()
        print(node.val)
        if node.left:
            queue.append(node.left)
        if node.right:
            queue.append(node.right)
```

### 8. Heaps (Priority Queue)

```python
import heapq

# Min Heap (default in Python)
heap = []
heapq.heappush(heap, 3)   # O(log n)
heapq.heappush(heap, 1)
heapq.heappush(heap, 2)
min_val = heapq.heappop(heap)  # O(log n) - Returns 1

# Max Heap (negate values)
max_heap = []
heapq.heappush(max_heap, -3)
heapq.heappush(max_heap, -1)
max_val = -heapq.heappop(max_heap)  # Returns 3

# Heapify existing list
arr = [3, 1, 4, 1, 5, 9]
heapq.heapify(arr)  # O(n)

# Top K elements
def top_k(arr, k):
    return heapq.nlargest(k, arr)  # O(n log k)

# Uso: Priority queues, scheduling, top K, median finding
```

### 9. Graphs

```python
from collections import defaultdict, deque

class Graph:
    def __init__(self):
        self.adj = defaultdict(list)
    
    def add_edge(self, u, v, directed=False):
        self.adj[u].append(v)
        if not directed:
            self.adj[v].append(u)
    
    def bfs(self, start):
        """Breadth-First Search - O(V + E)"""
        visited = set([start])
        queue = deque([start])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            
            for neighbor in self.adj[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return result
    
    def dfs(self, start):
        """Depth-First Search - O(V + E)"""
        visited = set()
        result = []
        
        def _dfs(node):
            visited.add(node)
            result.append(node)
            for neighbor in self.adj[node]:
                if neighbor not in visited:
                    _dfs(neighbor)
        
        _dfs(start)
        return result
    
    def has_cycle(self):
        """Detect cycle in directed graph"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = defaultdict(int)
        
        def dfs(node):
            color[node] = GRAY
            for neighbor in self.adj[node]:
                if color[neighbor] == GRAY:
                    return True
                if color[neighbor] == WHITE and dfs(neighbor):
                    return True
            color[node] = BLACK
            return False
        
        for node in self.adj:
            if color[node] == WHITE:
                if dfs(node):
                    return True
        return False
```

### 10. Trie (Prefix Tree)

```python
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()
    
    def insert(self, word):      # O(m) where m = len(word)
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end = True
    
    def search(self, word):      # O(m)
        node = self.root
        for char in word:
            if char not in node.children:
                return False
            node = node.children[char]
        return node.is_end
    
    def starts_with(self, prefix):  # O(m)
        node = self.root
        for char in prefix:
            if char not in node.children:
                return False
            node = node.children[char]
        return True

# Uso: Autocomplete, spell checker, IP routing
```

---

## Algoritmos de Ordenamiento

### Comparison-based Sorts

```python
# Quick Sort - O(n log n) average, O(n²) worst
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

# Merge Sort - O(n log n) always, stable
def mergesort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = mergesort(arr[:mid])
    right = mergesort(arr[mid:])
    return merge(left, right)

def merge(left, right):
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

# Heap Sort - O(n log n), in-place
def heapsort(arr):
    heapq.heapify(arr)
    return [heapq.heappop(arr) for _ in range(len(arr))]
```

### Cuándo Usar Cada Uno

| Algoritmo | Mejor Para |
|-----------|------------|
| Quick Sort | General purpose, in-place |
| Merge Sort | Estabilidad requerida, linked lists |
| Heap Sort | Memory constrained |
| Counting Sort | Integers en rango pequeño |
| Radix Sort | Integers/strings de longitud fija |

---

## Patrones de Algoritmos

### 1. Two Pointers

```python
# Encontrar par que suma target en array ordenado
def two_sum_sorted(arr, target):
    left, right = 0, len(arr) - 1
    while left < right:
        curr_sum = arr[left] + arr[right]
        if curr_sum == target:
            return [left, right]
        elif curr_sum < target:
            left += 1
        else:
            right -= 1
    return []

# Remover duplicados in-place
def remove_duplicates(arr):
    if not arr:
        return 0
    write = 1
    for read in range(1, len(arr)):
        if arr[read] != arr[read - 1]:
            arr[write] = arr[read]
            write += 1
    return write
```

### 2. Sliding Window

```python
# Maximum sum subarray de tamaño k
def max_sum_subarray(arr, k):
    window_sum = sum(arr[:k])
    max_sum = window_sum
    
    for i in range(k, len(arr)):
        window_sum += arr[i] - arr[i - k]
        max_sum = max(max_sum, window_sum)
    
    return max_sum

# Longest substring sin caracteres repetidos
def longest_unique_substring(s):
    char_index = {}
    max_len = start = 0
    
    for i, char in enumerate(s):
        if char in char_index and char_index[char] >= start:
            start = char_index[char] + 1
        else:
            max_len = max(max_len, i - start + 1)
        char_index[char] = i
    
    return max_len
```

### 3. Binary Search Variations

```python
# Find first occurrence
def first_occurrence(arr, target):
    left, right = 0, len(arr) - 1
    result = -1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            result = mid
            right = mid - 1  # Continue searching left
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return result

# Search in rotated sorted array
def search_rotated(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        
        # Left half is sorted
        if arr[left] <= arr[mid]:
            if arr[left] <= target < arr[mid]:
                right = mid - 1
            else:
                left = mid + 1
        # Right half is sorted
        else:
            if arr[mid] < target <= arr[right]:
                left = mid + 1
            else:
                right = mid - 1
    return -1
```

### 4. Dynamic Programming

```python
# Fibonacci con memoization
def fib(n, memo={}):
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fib(n-1, memo) + fib(n-2, memo)
    return memo[n]

# Longest Common Subsequence
def lcs(s1, s2):
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    
    return dp[m][n]

# 0/1 Knapsack
def knapsack(weights, values, capacity):
    n = len(weights)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    
    for i in range(1, n + 1):
        for w in range(capacity + 1):
            if weights[i-1] <= w:
                dp[i][w] = max(
                    dp[i-1][w],
                    values[i-1] + dp[i-1][w - weights[i-1]]
                )
            else:
                dp[i][w] = dp[i-1][w]
    
    return dp[n][capacity]
```

### 5. Backtracking

```python
# Generar todas las permutaciones
def permutations(nums):
    result = []
    
    def backtrack(path, remaining):
        if not remaining:
            result.append(path[:])
            return
        
        for i in range(len(remaining)):
            path.append(remaining[i])
            backtrack(path, remaining[:i] + remaining[i+1:])
            path.pop()
    
    backtrack([], nums)
    return result

# N-Queens
def solve_n_queens(n):
    result = []
    board = [['.'] * n for _ in range(n)]
    
    def is_safe(row, col):
        # Check column
        for i in range(row):
            if board[i][col] == 'Q':
                return False
        # Check diagonals
        for i, j in zip(range(row-1, -1, -1), range(col-1, -1, -1)):
            if board[i][j] == 'Q':
                return False
        for i, j in zip(range(row-1, -1, -1), range(col+1, n)):
            if board[i][j] == 'Q':
                return False
        return True
    
    def backtrack(row):
        if row == n:
            result.append([''.join(r) for r in board])
            return
        
        for col in range(n):
            if is_safe(row, col):
                board[row][col] = 'Q'
                backtrack(row + 1)
                board[row][col] = '.'
    
    backtrack(0)
    return result
```

---

## Cheat Sheet de Selección

| Problema | Estructura/Algoritmo |
|----------|---------------------|
| Lookup rápido | Hash Table |
| Ordenado + búsqueda | BST o Binary Search |
| Min/Max frecuente | Heap |
| FIFO | Queue |
| LIFO / Undo | Stack |
| Prefijos | Trie |
| Relaciones | Graph |
| Subproblemas repetidos | Dynamic Programming |
| Todas las combinaciones | Backtracking |
| Array ordenado | Two Pointers |
| Subarray/substring | Sliding Window |

---

*Skill: data-structures-algorithms v1.0*
