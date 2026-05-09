---
name: tauri
description: >-
type: feature
---
  Use when building cross-platform desktop/mobile apps, implementing native
  integrations, or managing Rust/Web IPC. Triggers: tauri, rust backend, window
  management, system tray, sidecar, IPC, code signing, cross-platform.
type: feature
metadata:
  category: framework
  author: ozy
  triggers: tauri, rust, desktop, mobile, IPC, sidecar, capabilities, distribution
  references: Rules.md, AGENTS.md

# Tauri Desktop Mastery (God Mode) 🦀

Expert principles for building secure, lightweight, and high-performance cross-platform applications.

## 💎 Core Principles (Axioms)
1. **The Core Process is Sacred**: Never perform UI logic in Rust. Keep the Rust core for heavy lifting, OS access, and state management.
2. **Principle of Least Privilege**: Use Tauri v2 Capabilities to expose only the minimal necessary APIs to the frontend.
3. **IPC is the Bottleneck**: Minimize high-frequency message passing. Batch data instead of sending thousands of small events.
4. **Safety by Design**: Never use `eval()` or expose raw shell access. Always prefer specialized commands with strict argument validation.
5. **Small is Beautiful**: Optimize binaries by excluding unused plugins and using the system WebView (no Chromium bundling).

## 🛠️ Step-by-Step implementation
1. **The Core Phase**: Set up the Rust backend in `src-tauri`. Define your State and common Commands.
2. **The IPC Phase**: Implement `invoke` handlers for request-response and `emit` for async event-driven signals.
3. **The Capability Phase**: (v2) Define permissions in `src-tauri/capabilities`. Grant access to FS, Shell, or Dialogs explicitly.
4. **The Distribution Phase**: Configure code signing (Windows/macOS) and set up GitHub Actions for automated releases.

## 🛡️ Security & Quality Checklist
- [ ] **Capabilities Check**: Are all frontend permissions strictly defined (no `"*"` in permissions)?
- [ ] **Command Validation**: Are all Rust command arguments typed and validated?
- [ ] **CSP Policy**: Is the Content Security Policy strict enough to prevent XSS?
- [ ] **Sidecar Security**: Are sidecar binaries (like Python) correctly signed and restricted in config?
- [ ] **Binary Size**: Are unnecessary features disabled in `Cargo.toml` to keep the binary small?

## 📚 Examples (Few-shot)

### Example: Secure Tauri Command (Rust)
```rust
// ✅ God Mode: Strongly typed, validated, and uses State
#[tauri::command]
async fn save_config(
  state: tauri::State<'_, AppState>, 
  data: ConfigData
) -> Result<(), String> {
  // Validate data before processing
  if data.version < 1 { return Err("Invalid version".into()); }
  let mut current = state.config.lock().map_err(|e| e.to_string())?;
  *current = data;
  Ok(())
}
```

### Example: Capability Management (v2 JSON)
```json
// ✅ God Mode: Explicit permission for a specific sidecar
{
  "identifier": "python-sidecar-allow",
  "permissions": [
    {
      "identifier": "shell:allow-execute",
      "allow": [{ "name": "binaries/python", "sidecar": true }]
    }
  ]
}
```

---
*Skill: tauri v2.1 (Bibek Poudel Edition)*
