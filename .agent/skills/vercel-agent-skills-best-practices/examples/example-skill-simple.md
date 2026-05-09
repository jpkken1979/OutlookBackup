---
name: api-error-response
description: "Generate consistent error responses for REST APIs following organizational standards"
version: 1.0.0
tags: [api, error-handling, backend]
author: Example Organization
---

# API Error Response Generator

Generate consistent, informative error responses for REST APIs.

[Extended thinking: Consistent error responses improve developer experience, enable better error handling on clients, and facilitate debugging. This skill ensures all API errors follow RFC 7807 (Problem Details) with organizational extensions.]

## Use this skill when

- Creating error responses in API endpoints
- Standardizing error handling across services
- Implementing error middleware or interceptors

## Do not use this skill when

- Generating success responses (use api-success-response)
- Logging errors (use logging-best-practices)
- Client-side error handling (use client-error-handling)

## Instructions

### 1. Identify Error Category

Classify the error:
- **Client errors (4xx)**: Invalid input, authentication, authorization
- **Server errors (5xx)**: System failures, dependencies down, bugs

### 2. Generate Error Response

Use this JSON structure:

```json
{
  "type": "https://api.example.com/problems/[error-type]",
  "title": "Brief, human-readable summary",
  "status": 400,
  "detail": "Detailed explanation of what went wrong",
  "instance": "/api/v1/users/123",
  "timestamp": "2024-01-15T10:30:00Z",
  "traceId": "abc-123-def-456"
}
```

### 3. Add Context Fields

Include relevant context:

```json
{
  // ... standard fields ...
  "errors": [
    {
      "field": "email",
      "message": "Invalid email format",
      "code": "INVALID_FORMAT"
    }
  ]
}
```

## Safety

- Never expose internal error details (stack traces, database queries)
- Sanitize user input in error messages
- Log full details server-side, return safe summary to client

## Examples

### Example 1: Validation Error

**Input**: User submits invalid email

**Output**:
```json
{
  "type": "https://api.example.com/problems/validation-error",
  "title": "Validation Failed",
  "status": 400,
  "detail": "The request contains invalid data",
  "instance": "/api/v1/users",
  "timestamp": "2024-01-15T10:30:00Z",
  "traceId": "req-abc-123",
  "errors": [
    {
      "field": "email",
      "message": "Must be a valid email address",
      "code": "INVALID_EMAIL"
    }
  ]
}
```

### Example 2: Not Found

**Input**: Resource doesn't exist

**Output**:
```json
{
  "type": "https://api.example.com/problems/not-found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "The requested user does not exist",
  "instance": "/api/v1/users/999",
  "timestamp": "2024-01-15T10:31:00Z",
  "traceId": "req-def-456"
}
```

### Example 3: Server Error

**Input**: Database connection fails

**Output**:
```json
{
  "type": "https://api.example.com/problems/internal-error",
  "title": "Internal Server Error",
  "status": 500,
  "detail": "An unexpected error occurred. Please try again later.",
  "instance": "/api/v1/orders",
  "timestamp": "2024-01-15T10:32:00Z",
  "traceId": "req-ghi-789"
}
```

**Note**: Full stack trace logged server-side with traceId for debugging.

## Validation Checklist

- [ ] Status code matches error category
- [ ] Type URL is valid and documented
- [ ] Title is concise and clear
- [ ] Detail provides actionable information
- [ ] Timestamp is ISO 8601 format
- [ ] TraceId included for debugging
- [ ] No sensitive data exposed
