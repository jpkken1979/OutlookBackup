/**
 * api.js - UNS Backup API wrapper
 * Wrapper tipado para window.pywebview.api
 */
const Api = (() => {
  /**
   * Llama al metodo del bridge Python
   * @param {string} method - Nombre del metodo
   * @param {*} args - Argumentos (se stringify para JSON)
   * @returns {Promise<*>}
   */
  async function call(method, args = null) {
    try {
      const api = window.pywebview?.api;
      if (!api) throw new Error('pywebview bridge not ready');

      const result = api[method](args);
      if (result && typeof result.then === 'function') {
        return await result;
      }
      return result;
    } catch (err) {
      console.error(`[Api] ${method}:`, err);
      throw err;
    }
  }

  // ===== Outlook =====
  const connect_outlook = () => call('connect_outlook'),
        detect_accounts = () => call('detect_accounts');

  // ===== Config =====
  const get_config = () => call('get_config'),
        update_config = (config) => call('update_config', config);

  // ===== Backup =====
  const estimate_backup_size = (smtp_list) => call('estimate_backup_size', smtp_list),
        start_backup = (params) => call('start_backup', params),
        get_backup_progress = () => call('get_backup_progress'),
        cancel_backup = () => call('cancel_backup');

  // ===== Import =====
  const search_pst_files = () => call('search_pst_files'),
        start_import = (params) => call('start_import', params),
        get_import_progress = () => call('get_import_progress'),
        preview_pst = (path) => call('preview_pst', path);

  // ===== Cache =====
  const scan_cache_files = () => call('scan_cache_files'),
        start_cache_backup = (params) => call('start_cache_backup', params),
        get_cache_progress = () => call('get_cache_progress');

  // ===== Schedule =====
  const get_schedule_info = () => call('get_schedule_info'),
        save_schedule = (schedule) => call('save_schedule', schedule),
        remove_schedule = () => call('remove_schedule'),
        test_schedule_now = () => call('test_schedule_now');

  // ===== Tools =====
  const open_extracted_folder = () => call('open_extracted_folder'),
        find_rar_files = () => call('find_rar_files'),
        extract_rar = (params) => call('extract_rar', params),
        run_migration = (params) => call('run_migration', params),
        get_tools_progress = () => call('get_tools_progress');

  // ===== Inventory =====
  const export_account_inventory = (params) => call('export_account_inventory', params),
        get_account_details = (email) => call('get_account_details', email),
        test_connection = (params) => call('test_connection', params);

  // ===== History =====
  const get_backup_history = () => call('get_backup_history'),
        delete_backup = (path) => call('delete_backup', path),
        open_backup_folder = (path) => call('open_backup_folder', path),
        search_backups = (params) => call('search_backups', params);

  // ===== Dialogs =====
  const select_folder = () => call('select_folder'),
        select_file = (filter) => call('select_file', filter);

  // ===== App =====
  const get_app_info = () => call('get_app_info'),
        get_i18n = (key) => call('get_i18n', key);

  return {
    // Outlook
    connect_outlook,
    detect_accounts,
    // Config
    get_config,
    update_config,
    // Backup
    estimate_backup_size,
    start_backup,
    get_backup_progress,
    cancel_backup,
    // Import
    search_pst_files,
    start_import,
    get_import_progress,
    preview_pst,
    // Cache
    scan_cache_files,
    start_cache_backup,
    get_cache_progress,
    // Schedule
    get_schedule_info,
    save_schedule,
    remove_schedule,
    test_schedule_now,
    // Tools
    open_extracted_folder,
    find_rar_files,
    extract_rar,
    run_migration,
    get_tools_progress,
    // Inventory
    export_account_inventory,
    get_account_details,
    test_connection,
    // History
    get_backup_history,
    delete_backup,
    open_backup_folder,
    search_backups,
    // Dialogs
    select_folder,
    select_file,
    // App
    get_app_info,
    get_i18n,
  };
})();

window.Api = Api;