"""
UNS Backup v2.0 - Strings en japonés
======================================
Todos los textos visibles para el usuario.
Si en el futuro se necesita multi-idioma, basta agregar más diccionarios.
"""

JA = {
    # ===== App general =====
    "app_title": "UNS メールバックアップ",
    "app_subtitle": "Outlookの安全なメール保存と復元",
    "company_name": "ユニバーサル企画株式会社",
    "version_label": "バージョン",
    "help": "❓ ヘルプ",
    "settings": "⚙️ 設定",
    "close": "閉じる",
    "cancel": "キャンセル",
    "ok": "OK",
    "yes": "はい",
    "no": "いいえ",
    "save": "保存",
    "loading": "読み込み中...",
    "ready": "✓ 準備完了",
    # ===== Tabs =====
    "tab_backup": "📤 バックアップ",
    "tab_restore": "📥 復元・インポート",
    "tab_history": "📊 履歴",
    "tab_settings": "⚙️ 自動バックアップ",
    # ===== Backup tab =====
    "backup_section_config": "1️⃣  設定",
    "backup_section_accounts": "2️⃣  検出されたアカウント",
    "backup_section_log": "📋 ログ",
    "domain_filter": "フィルタするドメイン:",
    "all_accounts": "全Outlookアカウントをバックアップ",
    "backup_folder": "バックアップ先:",
    "backup_format": "形式:",
    "format_pst": "⦿ PST(推奨・単一ファイル)",
    "format_msg": "○ MSG(個別ファイル)",
    "btn_detect": "🔍 Outlookアカウントを検出",
    "btn_select_domain": "✓ ドメインのみ選択",
    "btn_select_all": "☑ 全選択",
    "btn_select_none": "☐ 全解除",
    "btn_choose_folder": "📁 選択...",
    "btn_start_backup": "🚀 バックアップ開始",
    "btn_cancel_backup": "⛔ キャンセル",
    "btn_open_folder": "📂 バックアップフォルダを開く",
    "col_check": "✓",
    "col_email": "メールアドレス",
    "col_type": "種類",
    "col_name": "名前",
    "col_emails": "メール数",
    "status_connecting": "📡 Outlookに接続中...",
    "status_connected": "✓ Outlookに接続済み",
    "status_disconnected": "❌ Outlookに接続できません",
    "status_backing_up": "⏳ バックアップ中...",
    "status_backup_done": "✓ バックアップ完了",
    "status_backup_failed": "❌ バックアップ失敗",
    # ===== Restore tab =====
    "restore_warning": (
        "⚠️ 復元機能について\n"
        "この機能はバックアップしたPSTファイルをOutlookにインポートします。\n"
        "移行後の新しいPCや、過去のメールを復元したい時に使用してください。"
    ),
    "restore_section_select": "1️⃣  PSTファイルを選択",
    "restore_section_files": "2️⃣  検出されたPSTファイル",
    "restore_section_method": "3️⃣  インポート方法",
    "restore_folder_label": "バックアップフォルダ:",
    "btn_search_pst": "🔍 PSTを検索",
    "btn_browse_pst": "📁 PSTファイル直接選択...",
    "method_separate_folder": "📁 別フォルダとして開く",
    "method_separate_desc": "Outlookのサイドバーに「UNS Backup」として表示。元のメールと混ざりません。",
    "method_merge": "📂 既存のアカウントに統合",
    "method_merge_desc": "新しいOutlookアカウントの受信トレイに直接マージされます。検索可能。",
    "method_new_files": "🗂️ 各PSTを別データファイルに",
    "method_new_files_desc": "各PSTを別々のデータファイルとして開く",
    "btn_preview_pst": "🔍 PSTの中身をプレビュー",
    "btn_start_import": "📥 インポート開始",
    "btn_target_account": "復元先アカウント:",
    "col_filename": "ファイル名",
    "col_account": "アカウント",
    "col_size": "サイズ",
    "col_created": "作成日",
    "status_searching_pst": "🔍 PSTファイルを検索中...",
    "status_no_pst_found": "PSTファイルが見つかりませんでした",
    "status_importing": "⏳ インポート中...",
    "status_import_done": "✓ インポート完了",
    # ===== History tab =====
    "history_title": "📊 過去のバックアップ履歴",
    "history_empty": "まだバックアップ履歴がありません。\nバックアップタブから初回バックアップを実行してください。",
    "btn_refresh_history": "🔄 更新",
    "btn_view_report": "📋 レポートを開く",
    "btn_open_backup": "📂 フォルダを開く",
    "btn_delete_backup": "🗑️ 削除",
    "history_col_date": "日時",
    "history_col_accounts": "アカウント数",
    "history_col_emails": "メール数",
    "history_col_size": "サイズ",
    "history_col_status": "状態",
    "history_status_ok": "✅ 成功",
    "history_status_partial": "⚠️ 一部失敗",
    "history_status_failed": "❌ 失敗",
    # ===== Scheduler / Auto backup =====
    "auto_title": "⏰ 自動バックアップ設定",
    "auto_enabled": "自動バックアップを有効にする",
    "auto_frequency": "頻度:",
    "freq_daily": "毎日",
    "freq_weekly": "毎週",
    "freq_biweekly": "隔週(2週間ごと)",
    "freq_monthly": "毎月",
    "freq_custom": "カスタム(N日ごと)",
    "auto_day_of_week": "曜日:",
    "day_mon": "月",
    "day_tue": "火",
    "day_wed": "水",
    "day_thu": "木",
    "day_fri": "金",
    "day_sat": "土",
    "day_sun": "日",
    "auto_time": "時刻:",
    "auto_save_to": "保存先:",
    "auto_accounts_scope": "対象:",
    "scope_uns_only": "@uns-kikaku.com のみ",
    "scope_all": "全Outlookアカウント",
    "scope_custom": "選択したアカウントのみ",
    "auto_keep_last": "保持する世代数:",
    "auto_keep_desc": "古いバックアップを自動で削除します(0=削除しない)",
    "btn_save_schedule": "💾 スケジュール保存",
    "btn_remove_schedule": "🗑️ スケジュール削除",
    "btn_test_now": "🧪 今すぐテスト実行",
    "auto_status_active": "✅ 自動バックアップ有効",
    "auto_status_inactive": "⏸️ 自動バックアップ無効",
    "auto_next_run": "次回実行予定:",
    "auto_last_run": "前回実行:",
    # ===== Confirmaciones / mensajes =====
    "confirm_backup_title": "バックアップ確認",
    "confirm_backup_msg": "{count}個のアカウントをバックアップします。\n\n保存先: {dir}\n\n続行しますか?",
    "msg_no_accounts": "少なくとも1つのアカウントを選択してください。",
    "msg_folder_required": "バックアップ先を指定してください。",
    "msg_outlook_not_found": "Outlookに接続できませんでした。\n\nOutlookがインストールされ設定されているか確認してください。",
    "msg_backup_complete": "✅ バックアップが完了しました。\n\n保存先:\n{dir}\n\nフォルダを開きますか?",
    "confirm_import_title": "インポート確認",
    "confirm_import_msg": "{count}個のPSTファイルをインポートします。\n\n方法: {method}\n\n続行しますか?",
    "msg_no_pst": "インポートするPSTファイルを選択してください。",
    "msg_import_complete": "✅ インポートが完了しました。\n\nOutlookで確認してください。",
    "confirm_delete_backup": "このバックアップを削除しますか?\n\n{path}\n\nこの操作は元に戻せません。",
    "confirm_delete_schedule": "自動バックアップのスケジュールを削除しますか?",
    # ===== Footer =====
    "footer_help_text": "問題が発生した場合は、システム管理者にスクリーンショットを送ってください。",
    # ===== Account Inventory (v2.1) =====
    "inventory_section_title": "📋 アカウント情報エクスポート",
    "inventory_enable": "アカウント情報をJSONにエクスポート(バックアップと一緒に保存)",
    "inventory_include_servers": "サーバー設定を含める(IMAP/SMTP情報)",
    "inventory_include_passwords": "🔐 パスワードも含める(暗号化必須)",
    "inventory_warning_pwd": (
        "⚠️ パスワードを含めると非常にセンシティブなファイルになります。\n"
        "AES-256-GCMで暗号化されますが、絶対に第三者と共有しないでください。"
    ),
    "inventory_pwd_btn": "🔑 マスターパスワードを設定...",
    "inventory_pwd_set": "✓ マスターパスワード設定済み",
    "inventory_pwd_not_set": "❌ マスターパスワード未設定",
    "inventory_what_includes": "含まれる情報:",
    "inventory_export_done": "✅ アカウント情報を保存しました: {path}",
    # Master password dialog
    "master_password_title": "マスターパスワード",
    "master_password_warning": (
        "このパスワードはアカウント情報の暗号化に使用されます。\n"
        "忘れるとファイルを開けなくなります。安全な場所にメモしてください。\n"
        "8文字以上、できれば大文字・小文字・数字・記号を混ぜることを推奨します。"
    ),
    "master_password_label": "マスターパスワード:",
    "master_password_confirm": "確認のため再入力:",
    "master_password_show": "表示",
    "master_password_strength": "強度:",
    "master_password_match": "✓ 一致",
    "master_password_mismatch_label": "✗ 一致しません",
    "master_password_empty": "パスワードを入力してください",
    "master_password_too_short": "8文字以上にしてください",
    "master_password_mismatch": "2つのパスワードが一致しません",
    # Decrypt viewer
    "decrypt_btn": "🔓 アカウント情報を復号",
    "decrypt_select_file": "暗号化されたJSONを選択",
    "decrypt_password_prompt": "マスターパスワードを入力してください",
    "decrypt_failed_title": "復号失敗",
    "decrypt_success_title": "復号成功",
    "decrypt_show_passwords": "パスワードを表示する",
    "decrypt_save_plain": "💾 平文JSONとして保存(危険)",
    # Status messages
    "inventory_processing": "📋 アカウント情報を生成中...",
    "inventory_no_accounts": "アカウントが見つかりません",
    "inventory_credentials_warning": "⚠️ 認証情報の読み取りに失敗しました(権限不足の可能性)",
}


def t(key: str, **kwargs) -> str:
    """Obtiene un string traducido. Soporta formato con kwargs."""
    text = JA.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
