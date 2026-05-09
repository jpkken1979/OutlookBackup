---
name: tauri-security-patterns
description: Tauri security guidance for IPC validation, permissions, data protection, secure frontend/backend boundaries, and desktop-app hardening. Use when auditing or designing security for a Tauri app, reviewing command boundaries, handling secrets or local storage, or hardening a Rust-plus-web desktop application against common abuse paths.
type: feature
---

# Tauri Security Patterns

## Purpose

Provide practical security guidance for Tauri applications, especially around frontend/Rust boundaries, permissions, IPC, and local system access.

## When to Use

- Auditing a Tauri app for security issues
- Designing safe Tauri command boundaries
- Hardening file system, shell, or OS-level capabilities
- Handling secrets, local storage, or sensitive data in desktop apps
- Reviewing frontend/backend trust boundaries in Tauri

## Workflow

1. Identify the sensitive capabilities exposed by the app
2. Review the JS/Rust boundary and command validation
3. Check permission surface and plugin usage
4. Harden storage, crypto, and logging behavior
5. Validate the app against realistic abuse paths

## Critical Patterns

- Validate input on both sides of the JS/Rust boundary
- Minimize exposed capabilities and plugin permissions
- Treat IPC as a security boundary, not just a convenience layer
- Avoid unsafe logging and careless storage of sensitive values

## Examples

### Security review inputs

```json
{
  "project_path": "/path/to/project",
  "auto_scan": true
}
```

### Pattern generation inputs

```json
{
  "pattern_type": "ipc_security",
  "framework": "react",
  "threat_level": "high",
  "include_examples": true
}
```

### Expected findings shape

```json
{
  "status": "warning",
  "vulnerabilities": [
    {
      "severity": "high",
      "description": "Unsafe command input validation",
      "location": "src-tauri/src/commands/*.rs",
      "recommendation": "Validate and constrain command inputs explicitly"
    }
  ]
}
```

## Resources

- IPC validation patterns
- Permission minimization and plugin hardening
- Secure storage and crypto concerns in desktop apps
- Tauri-specific threat modeling

## Validation

- Verify every sensitive command validates external input
- Confirm capability exposure is minimal
- Check storage/logging behavior for secrets and PII
- Test hardening assumptions against the real desktop threat surface
