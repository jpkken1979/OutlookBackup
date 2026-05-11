"""Constantes COM de Outlook usadas por la app.

Estas constantes vienen del modelo de objetos de Outlook. Se duplican aca
para no depender de la enum dinamica que genera pywin32 (que solo existe
post-EnsureDispatch).
"""

# olDefaultFolders
FOLDER_INBOX = 6
FOLDER_SENT_MAIL = 5
FOLDER_DRAFTS = 16
FOLDER_DELETED = 3
FOLDER_OUTBOX = 4

# olItemType / Item.Class
MAIL_ITEM = 43

# olStoreType (para AddStoreEx)
STORE_DEFAULT = 1  # Outlook decide formato
STORE_UNICODE = 3  # PST Unicode (post-Outlook 2003)
STORE_ANSI = 2  # PST ANSI legacy

# olSaveAsType
SAVE_AS_MSG = 3  # .msg (Outlook native)
SAVE_AS_TXT = 0  # .txt
SAVE_AS_HTML = 5  # .html

# Account.AccountType
ACCOUNT_TYPE_EXCHANGE = 0
ACCOUNT_TYPE_IMAP = 1
ACCOUNT_TYPE_POP3 = 2
ACCOUNT_TYPE_HTTP = 3
ACCOUNT_TYPE_EAS = 4
ACCOUNT_TYPE_OTHER = 5

ACCOUNT_TYPE_NAMES = {
    ACCOUNT_TYPE_EXCHANGE: "Exchange",
    ACCOUNT_TYPE_IMAP: "IMAP",
    ACCOUNT_TYPE_POP3: "POP3",
    ACCOUNT_TYPE_HTTP: "HTTP",
    ACCOUNT_TYPE_EAS: "EAS",
    ACCOUNT_TYPE_OTHER: "Other",
}
