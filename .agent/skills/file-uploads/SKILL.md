---
name: file-uploads
description: "Expert at handling file uploads and cloud storage with security-first approach. Implements S3 and Cloudflare R2 uploads, presigned URLs, multipart uploads for large files, and image optimization without blocking requests. Validates magic bytes, sanitizes filenames, enforces size limits. Use when: file uploads, cloud storage, S3 bucket integration, R2 uploads, presigned URLs, multipart uploads, large file handling, image optimization, or building secure file management systems."
type: feature
source: vibeship-spawner-skills (Apache 2.0)
user-invocable: true
---

# File Uploads & Cloud Storage

Build secure, performant file upload systems that handle large files without blocking, validate security constraints, and integrate with S3 or Cloudflare R2.

## Architecture Decision: Where to Upload

| Approach | Use Case | Pros | Cons |
|----------|----------|------|------|
| **Server-side proxy** | Small files (< 5MB), controlled sources | Simple, centralized control | Blocks request, scales poorly |
| **Presigned URLs** (recommended) | Large files, untrusted sources | Non-blocking, delegated to cloud | URL leakage risk if shared |
| **Multipart upload** | Files > 100MB | Resume capability, faster | Complex client logic |
| **Direct browser upload** | Client-managed responsibility | Simplest | No server validation |

**Rule of thumb**: Use presigned URLs for 90% of cases. Use multipart only for > 100MB. Never proxy large files.

## 🔒 Critical Security Checklist

### 1. File Type Validation (Magic Bytes)

**Never trust extensions.**

```
Client uploads: "resume.pdf"
Check magic bytes (file signature):
- PDF: %PDF at hex offset 0
- PNG: 89 50 4E 47 at offset 0
- JPEG: FF D8 FF at offset 0
- ZIP: 50 4B 03 04 at offset 0

If extension doesn't match magic bytes → REJECT
```

### 2. Filename Sanitization

**Never use client-provided filenames directly.**

```
Dangerous: /uploads/${req.body.filename}
→ /uploads/../../../etc/passwd (PATH TRAVERSAL)

Safe approach:
1. Generate UUID: abc123-def456
2. Keep extension only: abc123-def456.pdf
3. Store in hash: /uploads/ab/c1/23def456.pdf (shard by hash)
4. Map UUID → original filename in database
```

### 3. File Size Limits

Set hard limits at multiple layers:

```
1. Client-side (UX): Warn if > 100MB
2. Server presigned URL generation: Reject if > 1GB
3. Cloud provider bucket policy: Enforce max size
4. Rate limiting: Max 10 uploads per IP per hour
```

### 4. Presigned URL Safety

```
✓ Set expiration: 15 minutes for security, 1 hour for large uploads
✗ Don't cache presigned URLs (they expire)
✓ Use one-time URLs when possible
✗ Don't log or expose URLs in error messages
✓ Verify request comes from expected IP/user before generating
```

## Workflows by Scenario

### Scenario 1: Small Files (< 5MB)
→ Use presigned URL, validation on server

```
1. Client: POST /upload/presigned with size, type
2. Server: Validate size < 5MB, whitelist type
3. Server: Generate presigned URL (15 min expiry)
4. Client: Upload directly to S3/R2 via URL
5. Server: Webhook confirmation when uploaded
6. Server: Run final validation (scan for viruses, re-check magic bytes)
```

### Scenario 2: Large Files (5MB-100MB)
→ Use presigned URL + resumable upload

```
1. Client: Request presigned URL for 50MB file
2. Server: Split into 10MB chunks client-side
3. Client: Upload chunks in parallel (up to 3 concurrent)
4. Each chunk: Validated at S3 level
5. Server: Complete multipart upload when all chunks received
6. Server: Verify file integrity (ETag matching)
```

### Scenario 3: Huge Files (> 100MB)
→ Use multipart upload with resumability

```
1. Create multipart upload session in S3
2. Upload parts (5MB min, 5GB max each)
3. If interrupted: Resume from last completed part
4. Complete multipart when all parts uploaded
5. Log upload duration and throughput for monitoring
```

## Performance Patterns

### Image Optimization

```
Before upload:
- Client-side: Compress with imagemin (max 2MB)
- WebP format for modern browsers, JPEG fallback

After upload to S3:
- Lambda trigger on new upload
- Generate thumbnails: 150x150, 400x400, 1200x1200
- Create WebP variants
- Store metadata: dimensions, size, format
```

### Avoiding Blocking

```
❌ Bad: await S3.putObject().promise() during request
✓ Good: S3.putObject() in background, webhook notifies client
✓ Better: Let client upload directly via presigned URL, no backend wait
```

## Implementation Checklist

- [ ] All files validated by magic bytes, never by extension
- [ ] Filenames sanitized: UUID + extension only, no user input
- [ ] Size limits enforced: client warn, server reject, bucket policy
- [ ] Presigned URLs: 15 min expiry, generated per-request, not cached
- [ ] Security headers: Content-Disposition, no-cache on uploads
- [ ] Error messages don't reveal paths or credentials
- [ ] Monitoring: Log all upload attempts, sizes, rejections
- [ ] Tests include edge cases: oversized files, suspicious magic bytes, path traversal attempts
- [ ] Rate limiting per IP and per user

## Common Failure Modes

| Problem | Cause | Fix |
|---------|-------|-----|
| Uploads work locally, fail in production | Security policy difference | Check CloudFront/WAF rules |
| "CORS error" on presigned URL | Domain not whitelisted | Add Origin to bucket CORS policy |
| File appears corrupt after upload | Incomplete multipart | Implement part ETag verification |
| Presigned URL works then fails | Expired | Reduce expiry time in generation |

See vibeship-spawner-skills for templates and complete code examples.
