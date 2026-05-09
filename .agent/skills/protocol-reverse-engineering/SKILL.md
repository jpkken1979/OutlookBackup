---
name: protocol-reverse-engineering
description: "Master network protocol reverse engineering including packet capture/analysis, protocol dissection, state machine mapping, and custom protocol documentation. Covers tools (Wireshark, tcpdump, burp), techniques (packet inspection, traffic filtering, stateful analysis), binary protocol parsing, encryption detection, timing analysis, and generating protocol specifications. Includes patterns for API reverse engineering, proprietary protocol analysis, interoperability testing, and security testing (fuzzing, mutation). Use when analyzing network traffic, understanding proprietary/undocumented protocols, debugging network issues, implementing protocol clients, reverse engineering closed APIs, or security research on network communication."
type: feature
---

# Protocol Reverse Engineering

Systematically capture, analyze, and document network protocols from raw traffic and binary interactions.

---

## Protocol Analysis Workflow

```
┌─────────────────────────────────────────────────────┐
│ 1. CAPTURE: tcpdump, Wireshark, proxy (Burp/Fiddler)│
├─────────────────────────────────────────────────────┤
│ 2. FILTER: Isolate relevant traffic (IP, port)     │
├─────────────────────────────────────────────────────┤
│ 3. DECODE: Parse headers, payloads, encryption     │
├─────────────────────────────────────────────────────┤
│ 4. PATTERN: Identify state machine, message types  │
├─────────────────────────────────────────────────────┤
│ 5. DOCUMENT: Spec, code generator, interop tests   │
├─────────────────────────────────────────────────────┤
│ 6. VALIDATE: Implement client/server, fuzz test    │
└─────────────────────────────────────────────────────┘
```

---

## Pattern 1: Packet Capture & Filtering

### Capturing Network Traffic

```bash
# tcpdump: Capture to file
tcpdump -i eth0 -w traffic.pcap                       # All traffic
tcpdump -i eth0 -w api.pcap host 192.168.1.100       # Single host
tcpdump -i eth0 -w port_8080.pcap port 8080          # Specific port
tcpdump -i eth0 -w tcp_only.pcap tcp                 # TCP only
tcpdump -i eth0 -w filtered.pcap "tcp port 443 and host 192.168.1.50"

# Wireshark: GUI capture (Settings > Capture Options)
# Can apply real-time filters while capturing
```

### Filter Expressions (tcpdump/Wireshark)

```
tcp.port == 5000              # Specific TCP port
ip.src == 192.168.1.1         # Source IP
http.request.method == "POST" # HTTP POST requests
ssl.handshake.type == 1       # TLS Client Hello
frame.len > 1500              # Packets larger than 1500 bytes
tcp.flags.syn == 1            # SYN packets (connection setup)
```

---

## Pattern 2: Packet Structure Analysis

### Wireshark Deep Inspection

```
Frame:
  ├─ Link Layer (Ethernet)
  ├─ Network Layer (IP header)
  │   ├─ Source IP: 192.168.1.100
  │   ├─ Destination IP: 8.8.8.8
  │   └─ Protocol: TCP (6)
  ├─ Transport Layer (TCP)
  │   ├─ Source Port: 54321
  │   ├─ Destination Port: 443
  │   ├─ Sequence Number: 1234567890
  │   ├─ Acknowledgment: 9876543210
  │   ├─ Flags: SYN, ACK
  │   └─ Window Size: 65535
  └─ Application Layer (TLS/HTTP/Custom)
      ├─ Payload: [binary data]
      └─ Length: 256 bytes
```

### Manual Hex Dump Analysis

```python
import binascii

def analyze_packet_hex(data: bytes):
    """Analyze binary protocol structure."""
    hex_str = binascii.hexlify(data).decode()

    # Print in readable format
    for i in range(0, len(hex_str), 32):
        offset = i // 2
        hex_chunk = hex_str[i:i+32]
        ascii_chunk = ''.join(
            chr(b) if 32 <= b < 127 else '.'
            for b in data[offset:offset+16]
        )
        print(f"{offset:04x}: {hex_chunk:32} {ascii_chunk}")

# Example: Parse custom binary protocol
# Header: 4 bytes magic + 2 bytes length + payload
def parse_custom_message(data: bytes):
    magic = data[0:4]           # 4 bytes: protocol identifier
    length = int.from_bytes(data[4:6], 'big')  # 2 bytes big-endian
    payload = data[6:6+length]  # Remaining bytes

    return {
        "magic": magic.hex(),
        "message_length": length,
        "payload": payload.hex()
    }

# Example: Check for ASCII strings in binary data
def extract_ascii_strings(data: bytes, min_length: int = 4):
    """Find readable ASCII strings in binary data."""
    strings = []
    current = []

    for byte in data:
        if 32 <= byte < 127:  # Printable ASCII
            current.append(chr(byte))
        else:
            if len(current) >= min_length:
                strings.append(''.join(current))
            current = []

    return strings
```

---

## Pattern 3: Protocol State Machine Mapping

### Discovering Message Sequences

```python
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ProtocolMessage:
    direction: str  # "client->server" or "server->client"
    type: str       # Inferred message type
    hex_signature: str  # First 8 bytes (hex)
    length: int     # Message length
    payload_sample: str  # First 100 bytes

class ProtocolAnalyzer:
    """Map protocol state machine from traffic."""

    def __init__(self):
        self.messages: List[ProtocolMessage] = []
        self.state_machine: Dict[str, List[str]] = {}

    def add_message(self, direction: str, data: bytes):
        """Record a message in the protocol sequence."""
        msg = ProtocolMessage(
            direction=direction,
            type=self._guess_type(data),
            hex_signature=data[:8].hex(),
            length=len(data),
            payload_sample=data[:100].hex()
        )
        self.messages.append(msg)

    def _guess_type(self, data: bytes) -> str:
        """Infer message type from patterns."""
        # Common signatures
        if data.startswith(b'HTTP'):
            return "HTTP"
        if data[0] == 0x16:  # TLS Handshake
            return "TLS_Handshake"
        if data[0] == 0x14:  # TLS ChangeCipherSpec
            return "TLS_ChangeCipherSpec"
        if data[0] == 0x17:  # TLS Application Data
            return "TLS_AppData"
        return "Unknown"

    def build_state_machine(self):
        """Infer state transitions from message sequence."""
        states = {}
        current_state = "START"

        for i, msg in enumerate(self.messages):
            if current_state not in states:
                states[current_state] = []

            next_state = f"{msg.direction}_{msg.type}_{i}"
            states[current_state].append(next_state)
            current_state = next_state

        self.state_machine = states
        return states

    def print_state_diagram(self):
        """Print ASCII state diagram."""
        print("STATE MACHINE:")
        for state, transitions in self.state_machine.items():
            for next_state in transitions:
                print(f"  {state} -> {next_state}")
```

---

## Pattern 4: Encrypted Protocol Analysis (Without Keys)

### Timing & Pattern Analysis

```python
import time
from collections import defaultdict

class EncryptedProtocolAnalyzer:
    """Analyze encrypted traffic patterns."""

    def __init__(self):
        self.packet_sizes = []
        self.packet_timings = []
        self.size_patterns = defaultdict(int)

    def record_packet(self, size: int, timestamp: float):
        """Record packet metadata (doesn't need decryption)."""
        self.packet_sizes.append(size)
        self.packet_timings.append(timestamp)
        self.size_patterns[size] += 1

    def analyze_patterns(self):
        """Find patterns in encrypted traffic."""

        # Timing analysis: Identify fixed-duration operations
        intervals = [
            self.packet_timings[i] - self.packet_timings[i-1]
            for i in range(1, len(self.packet_timings))
        ]

        avg_interval = sum(intervals) / len(intervals) if intervals else 0

        # Size pattern analysis
        common_sizes = sorted(
            self.size_patterns.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            "total_packets": len(self.packet_sizes),
            "avg_packet_size": sum(self.packet_sizes) / len(self.packet_sizes),
            "avg_interval_ms": avg_interval * 1000,
            "common_sizes": common_sizes,
            "variance": self._calculate_variance(intervals),
        }

    def _calculate_variance(self, values: List[float]) -> float:
        if not values:
            return 0
        avg = sum(values) / len(values)
        return sum((x - avg) ** 2 for x in values) / len(values)
```

---

## Pattern 5: Binary Protocol Parser Generator

### Automatic Parsing from Structure

```python
from struct import unpack
from typing import Tuple, Any
import io

class BinaryProtocolParser:
    """Parse binary protocols with defined structure."""

    # Protocol definition: (format_string, field_name, size_bytes)
    PROTOCOL_STRUCTURE = [
        ('!H', 'magic', 2),           # Big-endian unsigned short
        ('!H', 'version', 2),
        ('!I', 'message_id', 4),      # Big-endian unsigned int
        ('!I', 'payload_length', 4),
        # Remaining is payload
    ]

    def parse_message(self, data: bytes) -> Dict[str, Any]:
        """Parse message according to protocol structure."""
        stream = io.BytesIO(data)
        result = {}
        offset = 0

        for fmt, name, size in self.PROTOCOL_STRUCTURE:
            chunk = stream.read(size)
            if len(chunk) < size:
                raise ValueError(f"Insufficient data for {name}")

            value = unpack(fmt, chunk)[0]
            result[name] = value
            offset += size

        # Read remaining as payload
        result['payload'] = stream.read()

        return result

    def generate_parser_code(self) -> str:
        """Generate Python code from protocol definition."""
        code = "def parse_message(data: bytes):\n"
        offset = 0

        for fmt, name, size in self.PROTOCOL_STRUCTURE:
            code += f"    {name} = unpack('!...', data[{offset}:{offset+size}])[0]\n"
            offset += size

        code += f"    payload = data[{offset}:]\n"
        code += "    return {...}\n"

        return code
```

---

## Pattern 6: API Reverse Engineering with Proxy

### Intercepting HTTPS with Burp/Fiddler

```python
# Example: Analyze HTTP requests/responses captured by proxy

def analyze_api_calls(pcap_file: str):
    """Analyze API patterns from proxy capture."""

    api_patterns = {
        "authentication": [],
        "data_retrieval": [],
        "mutations": [],
    }

    # Typical patterns
    # POST /api/login -> Response with token
    # GET /api/user -> Response with user data
    # POST /api/user/update -> Response with status

    return api_patterns

# Burp Suite Macro/Extension approach:
# 1. Capture traffic in Burp Proxy
# 2. Analyze in "Target" tab -> "Site map"
# 3. Identify URL patterns:
#    /api/v1/users     -> GET/POST
#    /api/v1/users/:id -> GET/PUT/DELETE
# 4. Map request/response types
# 5. Identify auth header format
# 6. Generate client library
```

---

## Best Practices Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Use correct capture point** | Avoid asymmetric routing | Capture at client or server |
| **Filter noise** | Focus on relevant traffic | Use tcp.port == X filters |
| **Document signatures** | Build protocol spec | Record hex signatures of message types |
| **Test state transitions** | Ensure understanding | Replay traffic, verify behavior matches |
| **Check encryption** | Know what you're seeing | TLS: encrypted, Custom: unknown |
| **Time sync for analysis** | Match client/server clocks | Use NTP, consistent timezone |
| **Keep original capture** | Preserve evidence | Archive pcap files |
| **Version your spec** | Track evolution | Semantic versioning of protocol docs |

---

## Tools Reference

| Tool | Purpose | Notes |
|------|---------|-------|
| **tcpdump** | Packet capture (CLI) | Lightweight, portable |
| **Wireshark** | Packet analysis (GUI) | Rich filters, dissectors |
| **Burp Suite** | HTTPS proxy | Application-level analysis |
| **Fiddler** | Web proxy (Windows) | Browser traffic inspection |
| **mitmproxy** | Python-based proxy | Scriptable, extensible |
| **scapy** | Packet crafting (Python) | Custom packet building/sending |
| **binwalk** | Binary analysis | Extract/analyze firmware |
| **Frida** | Runtime instrumentation | Hook function calls, trace execution |

---

## Implementation Checklist

- [ ] Set up packet capture (tcpdump or Wireshark)
- [ ] Filter traffic to relevant source/port
- [ ] Identify message boundaries
- [ ] Map protocol state machine
- [ ] Document message types and fields
- [ ] Create parser from structure
- [ ] Build test client
- [ ] Validate against live traffic
- [ ] Fuzz test protocol implementation
- [ ] Document protocol specification
- [ ] Create interop test suite
