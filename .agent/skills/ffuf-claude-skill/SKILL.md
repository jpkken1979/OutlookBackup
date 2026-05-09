---
name: ffuf-claude-skill
description: "Web fuzzing with ffuf tool for discovering hidden endpoints, parameters, virtual hosts, and security vulnerabilities through automated brute force. Supports wordlists, filtering, request customization, and output parsing for penetration testing and security research. Use when discovering hidden endpoints, fuzzing API parameters, finding subdomains, pentesting web applications, enumerating content paths, testing WAF bypasses, or building security reconnaissance tools."
type: feature
source: "https://github.com/jthack/ffuf_claude_skill"
risk: safe
user-invocable: true
---

# FFUF: Fast Web Fuzzer

High-speed, flexible HTTP brute force tool for discovering hidden resources, endpoints, and vulnerabilities in web applications.

## What FFUF Does

**FFUF** = HTTP request fuzzer with replaceable payloads (wordlists)

```
Input: Base URL + Wordlist + Fuzzing position
Process: Replace FUZZ marker with each wordlist item, make HTTP request
Output: Responses sorted by status code, size, time
```

Example:
```bash
ffuf -u http://target.com/FUZZ -w wordlist.txt
# Tries: /admin, /api, /backup, /config, /debug, /docs, ...
```

## Core Use Cases

### 1. Endpoint Discovery

Find hidden endpoints and routes:

```bash
ffuf -u http://target.com/FUZZ \
     -w endpoints.txt \
     -fc 404             # Filter out 404s
```

**Common endpoints to fuzz**: `/admin`, `/api`, `/backup`, `/config`, `/debug`, `/admin.php`, `/wp-admin`, `/cms`, `/phpmyadmin`

### 2. Parameter Fuzzing

Discover hidden parameters accepted by endpoints:

```bash
ffuf -u "http://target.com/search?q=test&FUZZ=value" \
     -w parameters.txt \
     -fc 400
```

**Common params**: `id`, `user`, `admin`, `debug`, `apikey`, `token`, `secret`, `key`

### 3. Virtual Host Discovery

Find subdomains and vhosts:

```bash
ffuf -u http://FUZZ.target.com \
     -w subdomains.txt \
     -H "Host: FUZZ.target.com"
```

### 4. File/Directory Discovery

Enumerate directory structure:

```bash
ffuf -u http://target.com/FUZZ \
     -w common-paths.txt \
     -e .php,.txt,.bak,.old
     # Also try: /file.php, /file.txt, /file.bak, /file.old
```

## Advanced Patterns

### Pattern 1: Multi-Position Fuzzing

```bash
ffuf -u "http://target.com/FUZZ1/FUZZ2" \
     -w words1.txt:FUZZ1 \
     -w words2.txt:FUZZ2
```

### Pattern 2: Rate Limiting & Delays

```bash
ffuf -u http://target.com/FUZZ \
     -w wordlist.txt \
     -t 1              # 1 thread (slow, avoids WAF)
     -p 0.2            # 200ms pause between requests
```

### Pattern 3: Custom Headers & Authentication

```bash
ffuf -u http://target.com/api/FUZZ \
     -w endpoints.txt \
     -H "Authorization: Bearer TOKEN" \
     -H "User-Agent: CustomAgent"
```

### Pattern 4: Response Filtering (Critical)

```bash
# Filter by status code
ffuf -u http://target.com/FUZZ -w wordlist.txt -fc 404,400,403

# Filter by response size
ffuf -u http://target.com/FUZZ -w wordlist.txt -fs 1234

# Filter by word count
ffuf -u http://target.com/FUZZ -w wordlist.txt -fw 20

# Combination filters
ffuf -u http://target.com/FUZZ -w wordlist.txt \
     -fc 404 -fs 5000-10000 -fw 100
```

## Wordlist Selection

| Wordlist | Use Case | Size | Quality |
|----------|----------|------|---------|
| `common.txt` | Quick scan | 1K items | High (frequent paths) |
| `raft-large` | Comprehensive | 100K items | Medium (brute-force heavy) |
| `directory-list-2.3` | Default standard | 220K items | Good (well-tested) |
| `subdomains-top-100` | Subdomain enum | 100 items | High (common subdomains) |
| Custom | Targeted attack | Variable | Depends on source |

Source: Wordlists available in `/usr/share/wordlists/` or SecLists GitHub repo.

## Performance & Optimization

| Problem | Solution | Trade-off |
|---------|----------|-----------|
| Too slow | Increase threads (`-t 200`) | More load on target, may trigger WAF |
| Too many 404s | Use `-fc 404` | May miss legitimate 404-returning endpoints |
| Timeouts | Increase timeout (`-timeout 30`) | Longer execution |
| WAF blocks requests | Reduce threads, add delay (`-p 0.5`) | Slower scan |

## Output & Parsing

### View Results

```bash
# Standard output
ffuf -u http://target.com/FUZZ -w wordlist.txt -v

# Save to file
ffuf -u http://target.com/FUZZ -w wordlist.txt -o results.txt

# JSON output (machine-readable)
ffuf -u http://target.com/FUZZ -w wordlist.txt -of json -o results.json
```

### Parse Results

```bash
# Show only successful (non-404) endpoints
ffuf -u http://target.com/FUZZ -w wordlist.txt -fc 404 | grep "200"

# Extract just the paths
ffuf -u http://target.com/FUZZ -w wordlist.txt -fc 404 | awk '{print $1}'
```

## Security & Responsible Use

### ✓ Authorized Testing
- You own/manage the target application
- Written authorization from system owner
- Bug bounty program rules followed
- Approved penetration test

### ✗ Do Not Use
- Unauthorized testing (illegal)
- Denial of Service (DoS) via fuzzing
- Public/production systems without permission

### Best Practices

1. **Start slow**: Begin with small wordlist, low thread count
2. **Identify signature**: Understand how 404s look (size, time, status)
3. **Filter properly**: Use `-fc`, `-fs`, `-fw` to isolate real results
4. **Respect rate limits**: Add delays if needed
5. **Ethical disclosure**: Report findings responsibly

## Troubleshooting

| Issue | Diagnostic | Solution |
|-------|-----------|----------|
| All 404s returned | Wrong URL format | Check base URL, FUZZ placement |
| Too many false positives | Poor filtering | Adjust `-fc`, `-fs`, `-fw` thresholds |
| Timeout/connection errors | Target unresponsive | Check URL, network connectivity, proxy settings |
| WAF/IPS blocks requests | Rate limiting or signature detection | Reduce `-t`, add `-p`, change User-Agent |

## Example Workflows

### Quick endpoint discovery
```bash
ffuf -u http://target.com/FUZZ -w /usr/share/wordlists/raft-large-directories.txt -fc 404,403
```

### Find admin panels
```bash
ffuf -u http://target.com/FUZZ -w admin-wordlist.txt -fc 404
```

### Enumerate subdomains
```bash
ffuf -u http://FUZZ.target.com -w subdomains.txt -H "Host: FUZZ.target.com" -fc 404
```

See [FFUF documentation](https://github.com/ffuf/ffuf) for complete reference and advanced options.
