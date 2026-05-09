"""mcp_injector package — modularizado desde mcp_injector.py.

Este paquete contiene las funciones extradas del archivo original.
El archivo mcp_injector.py sigue existiendo como entry point standalone.

Para usar como paquete:
    from mcp_injector.constants import REPO_ROOT, ECOSYSTEM_VERSION
    from mcp_injector.path_utils import detect_project_type
    from mcp_injector.io_utils import merge_tree, emit_json
    from mcp_injector.mcp_config import get_mcp_servers
    from mcp_injector.skills_install import install_skills_as_commands
    from mcp_injector.markdown_update import update_claude_md
    from mcp_injector.injection import inject_workspace

Para usar como script:
    python .agent/scripts/mcp_injector.py --help
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Modulos base (utilidades)
# ---------------------------------------------------------------------------
from .constants import (  # noqa: F401
    CODE_EXTENSIONS,
    CONFIG_EXTENSIONS,
    DOC_EXTENSIONS,
    SKIP_TREE_NAMES,
    ROOT_RULE_FILES,
    PORTABLE_AGENT_DIRS,
    CLAUDE_DIRS,
    RULES_EXCLUDE,
    ANTIGRAVITY_FILES,
    LEGACY_CLAUDE_DIRS,
    REMOTE_GATEWAY_PLACEHOLDER,
    REMOTE_TOKEN_PLACEHOLDER,
    HOOK_RUNTIME_FILES,
    NON_PORTABLE_CLAUDE_MARKERS,
    REPO_ROOT,
    REPO_ROOT_POSIX,
    ECOSYSTEM_VERSION,
    DEFAULT_GATEWAY_URL,
    DEFAULT_MEMORY_BACKEND,
    DEFAULT_REGISTRY_MODE,
    DEFAULT_REGISTRY_CACHE_TTL_SECONDS,
    DEFAULT_ORCHESTRATOR_MODE,
    _read_ecosystem_version,
)

from .io_utils import (  # noqa: F401
    emit_json,
    read_json_file,
    write_json_file,
    deep_merge,
    copy_file,
    merge_tree,
    backup_path,
    safe_remove_legacy,
    remove_legacy_claude_dirs,
    get_claude_desktop_config_path,
    get_claude_code_global_dir,
    hash_file,
    hash_tree,
    compare_named_directories,
    compare_paths,
    get_runtime_path_pairs,
)

from .path_utils import (  # noqa: F401
    normalize_path,
    ensure_dir,
    iter_content_files,
    build_path_profile,
    _is_absolute_local_path,
    detect_project_type,
    runtime_roots,
    is_remote_gateway_url,
    find_legacy_claude_entries,
)

from .mcp_config import (  # noqa: F401
    force_utf8_python_command,
    normalize_hook_python_commands,
    sanitize_claude_settings,
    prune_invalid_local_mcp_servers,
    maybe_add_remote_server,
    get_mcp_servers,
    safe_merge_json,
    safe_merge_zed_settings,
    safe_merge_continue_json,
    install_antigravity_config,
    install_claude_settings,
    collect_runtime_fingerprint,
    install_ai_manifest,
    install_gemini_config,
    install_aider_config,
    get_agent_version,
    show_injection_diff,
    check_blocking_processes,
)

from .sdk_install import (  # noqa: F401
    install_sdk_python,
    install_sdk_js,
)

from .skills_install import (  # noqa: F401
    install_project_memory,
    install_skills_as_commands,
    install_codex_skills,
    install_minimax_skills,
    install_superpowers,
    install_brainstorming_planning,
    install_oh_my_claudecode,
    install_external_skill_bundle,
    audit_vendored_external_skills,
    install_antigravity_codex_assets,
)

from .markdown_update import (  # noqa: F401
    update_markdown_section,
    update_claude_md,
    update_agents_md,
    generate_ide_rules,
    install_copilot_instructions,
    parse_markdown_sections,
    parse_yaml_frontmatter,
)

from .injection import (  # noqa: F401
    inspect_installation,
    apply_injection_improvements,
    import_target_extras_to_repo,
    import_all_target_changes_to_repo,
    smart_merge,
    detect_real_conflicts,
    apply_conflict_resolution,
    inject_workspace,
    run_post_injection_smoke,
    update_hooks_only,
    _run_post_inject_hook,
    classify_entry_change,
    build_change_detail,
    import_named_entries_with_backup,
    _collect_out_of_scope_items,
)

# ---------------------------------------------------------------------------
# Funciones CLI de alto nivel (siguen en mcp_injector.py)
# ---------------------------------------------------------------------------
# deploy_rules, install_full, inject_direct, inject_global,
# sync_global_claude_assets -> usar mcp_injector.py como script
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Patch io_utils stubs con implementaciones reales de injection
# ---------------------------------------------------------------------------
try:
    from . import io_utils as _io_utils_module

    _io_utils_module.build_change_detail = build_change_detail
    _io_utils_module.classify_entry_change = classify_entry_change
except (NameError, AttributeError, ModuleNotFoundError):
    pass
