_LIGHT_STYLESHEET = """
    QWidget {
        background: #eef1f6;
        color: #0f172a;
        font-family: "Segoe UI", Arial;
        font-size: 14px;
    }
    /* Terminal side panes are dark — global QWidget color would hide labels on dark chrome */
    QWidget#MobaLeftPane,
    QWidget#MobaRightPane {
        color: #e6edf3;
    }
    QWidget#MobaLeftPane QLabel,
    QWidget#MobaRightPane QLabel {
        color: #e6edf3;
        /* Global QWidget sets a light panel bg; without this, labels stay light-on-light (invisible). */
        background-color: transparent;
    }
    QLabel#LogPanelLabel {
        color: #0f172a;
        font-weight: 600;
        font-size: 15px;
    }
    QMainWindow {
        background: #eef1f6;
    }
    QMenuBar#AppMenuBar {
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
        padding: 2px 4px;
        spacing: 6px;
        color: #0f172a;
    }
    QMenuBar#AppMenuBar::item {
        padding: 5px 12px;
        background: transparent;
        border-radius: 4px;
        color: #0f172a;
    }
    QMenuBar#AppMenuBar::item:selected {
        background: #e2e8f0;
    }
    QMenuBar#AppMenuBar::item:pressed {
        background: #cbd5e1;
    }
    QMenu {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        padding: 4px 0;
    }
    QMenu::item {
        padding: 6px 28px 6px 16px;
    }
    QMenu::item:selected {
        background: #e0edff;
    }
    /* Styled QFileDialog fallback (native dialogs use OS chrome and may ignore these rules) */
    QFileDialog {
        background: #ffffff;
        color: #0f172a;
    }
    QFileDialog QLabel {
        color: #0f172a;
        background: transparent;
        font-size: 13px;
    }
    QFileDialog QLineEdit,
    QFileDialog QComboBox,
    QFileDialog QSpinBox {
        background: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 6px;
        min-height: 22px;
        selection-background-color: #dbeafe;
        selection-color: #0f172a;
    }
    QFileDialog QListView,
    QFileDialog QTreeView {
        background: #ffffff;
        color: #0f172a;
        selection-background-color: #dbeafe;
        selection-color: #0f172a;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
    }
    QFileDialog QPushButton {
        background: #eef2ff;
        border: 1px solid #c7d2fe;
        color: #1e3a8a;
        padding: 8px 14px;
        border-radius: 8px;
        font-weight: 600;
    }
    QFileDialog QPushButton:hover {
        background: #e0e7ff;
    }
    QFileDialog QDialogButtonBox QPushButton {
        min-width: 88px;
    }
    QMessageBox {
        background: #ffffff;
        color: #0f172a;
    }
    QMessageBox QLabel {
        color: #0f172a;
        background: transparent;
        min-width: 280px;
        font-size: 14px;
    }
    QMessageBox QPushButton {
        background: #eef2ff;
        border: 1px solid #c7d2fe;
        color: #1e3a8a;
        padding: 8px 18px;
        border-radius: 8px;
        font-weight: 600;
        min-width: 72px;
    }
    QMessageBox QPushButton:hover {
        background: #e0e7ff;
    }
    QMessageBox QLabel#qt_msgbox_label,
    QMessageBox QLabel#qt_msgboxex_label {
        color: #0f172a;
        background: transparent;
    }
    QMessageBox QLabel#qt_msgbox_informativelabel {
        color: #334155;
        background: transparent;
        font-size: 13px;
    }
    QFrame#TopCard {
        background: #fcfdff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
    }
    QLabel#appTitle {
        font-size: 22px;
        font-weight: 700;
        color: #0b1324;
        padding: 8px 2px 4px 2px;
    }
    QTabWidget::pane {
        background: #f6f8fb;
        border: 1px solid #dde3eb;
        border-radius: 14px;
        margin-top: 10px;
    }
    QTabWidget#MainTabs::pane {
        margin-top: 2px;
        border-radius: 8px;
        border: 1px solid #c9d4e3;
        background: #f6f8fb;
    }
    QTabWidget#MainTabs > QStackedWidget {
        background: #f6f8fb;
    }
    QTabWidget#MainTabs > QStackedWidget > QWidget {
        background-color: #f6f8fb;
    }
    QTabWidget#MainTabs QTabBar::tab {
        background-color: #e2e8f0;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-bottom: none;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        min-height: 24px;
        min-width: 96px;
        padding: 4px 12px;
        margin-right: 4px;
        font-weight: 600;
        font-size: 13px;
    }
    QTabWidget#MainTabs QTabBar::tab:selected {
        background-color: #ffffff;
        color: #0f172a;
        border-color: #94a3b8;
        border-bottom: 2px solid #2563eb;
        font-weight: 700;
    }
    QTabWidget#MainTabs QTabBar::tab:hover {
        background-color: #f1f5f9;
        color: #0f172a;
    }
    QTabWidget#ExplorerSessionTabs QTabBar::tab {
        background-color: #e2e8f0;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        min-height: 22px;
        min-width: 92px;
        padding: 3px 10px;
        margin-right: 2px;
        font-weight: 600;
        font-size: 12px;
    }
    QTabWidget#ExplorerSessionTabs QTabBar::tab:selected {
        background-color: #ffffff;
        border-color: #94a3b8;
        border-bottom: 2px solid #2563eb;
    }
    QTabWidget#ExplorerSessionTabs QTabBar::tab:hover {
        background-color: #f1f5f9;
    }
    QTabWidget#ExplorerSessionTabs::pane {
        background: #ffffff;
    }
    QTabWidget#ExplorerSessionTabs QStackedWidget {
        background: #ffffff;
    }
    QTabWidget#MobaTabs QStackedWidget {
        background: #0f131a;
    }
    QTabWidget#MainTabs QTabBar::close-button,
    QTabWidget#ExplorerSessionTabs QTabBar::close-button {
        subcontrol-position: right;
        width: 18px;
        height: 18px;
        border-radius: 4px;
        background: #64748b;
        margin: 3px;
    }
    QTabWidget#MainTabs QTabBar::close-button:hover,
    QTabWidget#ExplorerSessionTabs QTabBar::close-button:hover {
        background: #dc2626;
    }
    /* Terminal session tabs: default close control reads as a normal red close button */
    QTabWidget#MobaTabs QTabBar::close-button {
        subcontrol-position: right;
        width: 18px;
        height: 18px;
        border-radius: 4px;
        background: #dc2626;
        margin: 3px;
    }
    QTabWidget#MobaTabs QTabBar::close-button:hover {
        background: #b91c1c;
    }
    QFrame#ExplorerTransferStrip {
        background: #eef2ff;
        border: 1px solid #c7d2fe;
        border-radius: 10px;
        min-width: 80px;
        max-width: 110px;
    }
    QToolButton#ExplorerTransferBtn {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 7px 5px;
        min-width: 78px;
        font-size: 11px;
        font-weight: 600;
        color: #0f172a;
        icon-size: 18px;
    }
    QToolButton#ExplorerTransferBtn:hover {
        background: #e8f1ff;
        border-color: #2563eb;
    }
    QToolButton#ExplorerNewFileBtn {
        background: #ecfdf5;
        border: 1px solid #6ee7b7;
        color: #065f46;
    }
    QToolButton#ExplorerNewFileBtn:hover {
        background: #d1fae5;
        border-color: #10b981;
    }
    QToolButton#ExplorerEditBtn {
        background: #eff6ff;
        border: 1px solid #93c5fd;
        color: #1e3a8a;
    }
    QToolButton#ExplorerEditBtn:hover {
        background: #dbeafe;
        border-color: #2563eb;
    }
    QTabBar::tab {
        background: #e9eef7;
        border: 1px solid transparent;
        border-radius: 10px;
        color: #334155;
        padding: 9px 16px;
        margin-right: 6px;
    }
    QTabBar::tab:selected {
        background: #1f6feb;
        color: #ffffff;
        border-color: #1f6feb;
        font-weight: 600;
    }
    QTabBar::tab:hover {
        background: #dce6f8;
    }
    QGroupBox {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        margin-top: 12px;
        padding-top: 15px;
        font-weight: 600;
        background: #ffffff;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px;
        color: #475569;
    }
    QPushButton {
        background: #eef2ff;
        border: 1px solid #c7d2fe;
        border-radius: 8px;
        padding: 8px 12px;
        color: #1e3a8a;
        font-weight: 500;
    }
    QPushButton:hover {
        background: #e0e7ff;
    }
    QPushButton:pressed {
        background: #c7d2fe;
    }
    QLineEdit, QComboBox, QTreeWidget {
        background: #ffffff;
        border: 1px solid #d8e0ea;
        border-radius: 8px;
        padding: 8px;
        color: #1f2937;
        selection-background-color: #dbeafe;
    }
    QComboBox {
        padding-right: 26px;
        min-height: 24px;
        border-top-right-radius: 8px;
        border-bottom-right-radius: 8px;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px;
        border-left: 1px solid #d8e0ea;
        background: #f8fafc;
    }
    QComboBox QAbstractItemView {
        background: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-radius: 0px;
        selection-background-color: #dbeafe;
        selection-color: #0f172a;
        margin: 0px;
        padding: 0px;
        outline: 0;
    }
    QComboBox QAbstractItemView::viewport {
        background: #ffffff;
        margin: 0px;
        padding: 0px;
    }
    QComboBox QAbstractItemView::item {
        min-height: 24px;
        padding: 2px 6px;
        border: 0px;
    }
    QComboBox QAbstractItemView::item:selected {
        background: #cfe3ff;
        color: #0b1728;
    }
    QPlainTextEdit {
        background: #ffffff;
        border: 1px solid #d8e0ea;
        border-radius: 8px;
        padding: 8px;
        color: #1f2937;
        selection-background-color: #dbeafe;
    }
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTreeWidget:focus {
        border: 1px solid #60a5fa;
    }
    QTreeWidget::item:selected {
        background: #dbeafe;
        color: #0b3a82;
    }
    QTreeWidget::item {
        height: 26px;
    }
    QHeaderView::section {
        background: #f8fafc;
        color: #334155;
        border: 1px solid #e2e8f0;
        padding: 7px;
        font-weight: 600;
    }
    QSplitter::handle {
        background: #edf1f6;
        width: 2px;
    }
    /* WinSCP-style file explorer tab */
    QFrame#WinScpPane {
        background: #ffffff;
        border: 1px solid #c9d2de;
        border-radius: 2px;
    }
    QLineEdit#WinScpAddress {
        background: #ffffff;
        border: 1px solid #b8c2cf;
        border-radius: 1px;
        padding: 5px 7px;
        font-size: 13px;
    }
    QPushButton#WinScpToolBtn {
        background: #f8fafc;
        border: 1px solid #b7c2d2;
        border-radius: 1px;
        padding: 2px 8px;
        color: #0f172a;
        font-size: 11px;
        min-height: 20px;
    }
    QPushButton#WinScpToolBtn:hover {
        background: #e9eff7;
        border-color: #8fa4c3;
    }
    QTableWidget#WinScpTable {
        background: #ffffff;
        border: 1px solid #bcc8d9;
        gridline-color: #eef2f7;
        font-size: 13px;
        icon-size: 24px;
        alternate-background-color: #f8fafc;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
    }
    QTableWidget#WinScpTable QHeaderView::section {
        background: #eef2f7;
        color: #0f172a;
        padding: 7px 10px;
        min-height: 26px;
        border: 1px solid #c5d0e0;
        font-weight: 600;
        font-size: 13px;
    }
    QTableWidget#WinScpTable::item:selected {
        background: #2563eb;
        color: #ffffff;
    }
    QTableWidget#WinScpTable::item:selected:active {
        background: #1d4ed8;
        color: #ffffff;
    }
    QTableWidget#WinScpTable::item:focus {
        outline: none;
    }
    QFrame#WinScpStatusBar {
        background: #eceff3;
        border: 1px solid #c5d0e0;
        border-radius: 0px;
        min-height: 22px;
    }
    QLabel#WinScpStatusText {
        color: #334155;
        font-size: 12px;
    }
    QLabel#WinScpMenuText {
        color: #0f172a;
        font-size: 12px;
        font-weight: 500;
    }
    QToolButton#WinScpIconBtn {
        background: #ffffff;
        border: 1px solid #bcc8d9;
        border-radius: 4px;
        padding: 1px;
        min-width: 22px;
        min-height: 22px;
        icon-size: 16px;
    }
    QToolButton#WinScpIconBtn:hover {
        background: #ebf2fa;
        border-color: #8fa4c3;
    }
    QToolButton#WinScpIconBtn:disabled {
        background: #e2e8f0;
        border: 1px solid #cbd5e1;
        color: #64748b;
    }
    QMenuBar#WinScpMenuBar {
        background: #f5f7fa;
        border-bottom: 1px solid #c5d0e0;
        spacing: 4px;
        padding: 2px 4px;
        font-size: 12px;
    }
    QMenuBar#WinScpMenuBar::item {
        padding: 4px 10px;
        background: transparent;
    }
    QMenuBar#WinScpMenuBar::item:selected {
        background: #e2ecf7;
        border: 1px solid #b7c7db;
    }
    QToolButton#WinScpMainToolBtn {
        background: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 2px 6px;
        color: #0f172a;
        font-size: 11px;
        icon-size: 16px;
    }
    QToolButton#WinScpMainToolBtn:hover {
        background: #eef4fb;
        border-color: #b7c7db;
    }
    QPushButton#ExplorerReconnectBtn {
        font-size: 12px;
        font-weight: 600;
        min-height: 26px;
        padding: 4px 10px;
    }
    QLabel#WinScpProtoBadge {
        background: #eef4fb;
        border: 1px solid #b7c7db;
        padding: 2px 8px;
        font-size: 11px;
        color: #334155;
    }
    QLabel#WinScpSessionTab {
        background: #e8f1ff;
        border: 1px solid #9fbfe8;
        border-bottom: none;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 600;
        color: #0b3a82;
    }
    QFrame#WinScpVSep {
        min-width: 2px;
        max-width: 2px;
        background: #d5dde8;
    }
    /* MobaXterm-style terminal tab */
    QFrame#MobaLeftPane, QWidget#MobaLeftPane {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
    }
    QWidget#MobaRightPane {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
    }
    QTreeWidget#MobaSessionTree {
        background: #252b38;
        border: 1px solid #3b4355;
        color: #dbe5f5;
        font-size: 12px;
    }
    QTreeWidget#MobaSessionTree::item:selected {
        background: #2f6fed;
        color: white;
    }
    QTabWidget#MobaTabs::pane {
        border: 1px solid #2f3848;
        background: #0f131a;
        border-radius: 2px;
        margin-top: 4px;
    }
    QTabWidget#MobaTabs QTabBar::tab {
        background: #21262d;
        color: #f0f3f6;
        border: 1px solid #30363d;
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 2px 10px;
        margin-right: 2px;
        min-height: 18px;
        min-width: 108px;
        font-size: 11px;
        font-weight: 600;
    }
    QTabWidget#MobaTabs QTabBar::tab:selected {
        background: #0d1117;
        color: #f0f3f6;
        border-color: #58a6ff;
        border-bottom: 2px solid #58a6ff;
        font-weight: 700;
    }
    QTabWidget#MobaTabs QTabBar::tab:hover {
        background: #30363d;
        color: #f0f3f6;
    }
    QPushButton#MobaToolBtn {
        background: #2a3040;
        border: 1px solid #46526a;
        border-radius: 3px;
        color: #dbe5f5;
        padding: 4px 8px;
        min-height: 20px;
        font-size: 12px;
    }
    QPushButton#MobaToolBtn:hover {
        background: #34405a;
    }
    QPlainTextEdit#MobaTerminalOutput,
    QTextEdit#MobaTerminalOutput {
        background-color: #1a1e27;
        color: #f8fafc;
        border: 1px solid #3d4450;
        border-radius: 4px;
        padding: 10px 12px;
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 14px;
        font-weight: normal;
        selection-background-color: #1f6feb;
        selection-color: #ffffff;
    }
    QPlainTextEdit#MobaTerminalOutput:focus,
    QTextEdit#MobaTerminalOutput:focus {
        border: 1px solid #6e8cff;
    }
    QLabel#TerminalSessionFooter {
        background-color: #161b22;
        color: #8b949e;
        border: 1px solid #30363d;
        border-top: none;
        border-radius: 0 0 4px 4px;
        padding: 6px 12px;
        font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
        font-size: 12px;
    }
    QListWidget#MobaBookmarkList {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 4px;
        color: #e6edf3;
        font-size: 13px;
        padding: 6px;
        outline: none;
    }
    QListWidget#SessionBookmarkList {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 4px;
        color: #e6edf3;
        font-size: 13px;
        padding: 6px;
        outline: none;
    }
    QListWidget#MobaBookmarkList::item, QListWidget#SessionBookmarkList::item {
        padding: 8px 10px;
        border-radius: 4px;
        color: #e6edf3;
        min-height: 22px;
    }
    QListWidget#MobaBookmarkList::item:selected, QListWidget#SessionBookmarkList::item:selected {
        background-color: #21262d;
        color: #f0f3f6;
        border: 1px solid #388bfd;
    }
    QListWidget#MobaBookmarkList::item:hover, QListWidget#SessionBookmarkList::item:hover {
        background-color: #21262d;
    }
    QLineEdit#MobaQuickConnect {
        background: #252b38;
        border: 1px solid #3b4355;
        color: #dbe5f5;
        border-radius: 2px;
        padding: 4px 8px;
        font-size: 12px;
    }
    QLabel#MobaStatus {
        background: #1b2230;
        border: 1px solid #2f3848;
        color: #b9c5dd;
        padding: 4px 9px;
        font-size: 12px;
    }
    QLabel#MobaSidebarHeading {
        color: #d0d7de;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    QLabel#MobaMenuText {
        color: #f0f3f6;
        background-color: transparent;
        font-size: 13px;
        font-weight: 500;
    }
    QLabel#MobaTabCtrlLabel {
        color: #8b949e;
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton#MobaCloseTabBtn {
        background: #dc2626;
        border: 1px solid #b91c1c;
        color: #ffffff;
        padding: 4px 12px;
        min-height: 22px;
        font-weight: 700;
        border-radius: 4px;
    }
    QPushButton#MobaCloseTabBtn:hover {
        background: #b91c1c;
    }
    QTextEdit#AppLogView {
        background: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 8px 10px;
        font-size: 14px;
    }
    QPushButton#HeaderMiniBtn {
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        padding: 2px 6px;
        color: #334155;
        font-weight: 600;
    }
    QPushButton#HeaderSaveBtn {
        background: #2563eb;
        border: 1px solid #1d4ed8;
        color: #ffffff;
        padding: 4px 14px;
        border-radius: 4px;
        font-weight: 600;
    }
    QPushButton#HeaderSaveBtn:hover {
        background: #3b82f6;
    }
    QPushButton#ScrcpyStartBtn,
    QPushButton#ScrcpyStopBtn {
        icon-size: 16px;
        min-height: 28px;
        font-weight: 600;
    }
    QLabel#WinScpPaneTitle {
        font-size: 11px;
        font-weight: 600;
        color: #475569;
        padding: 0 2px;
    }
    QWidget#SessionStrip {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
    }
    QFrame#SessionStripVSep {
        color: #cbd5e1;
        max-width: 1px;
    }
    QPushButton#SessionStripBtn {
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        padding: 4px 12px;
        color: #334155;
        font-weight: 600;
    }
    QPushButton#SessionStripBtn:hover {
        background: #e2e8f0;
    }
    QComboBox#SessionWorkspaceCombo, QComboBox#SessionDeviceCombo,
    QComboBox#SessionProtocolCombo {
        padding: 4px 8px;
        min-height: 22px;
    }
    QLabel#SessionHint {
        color: #64748b;
        font-size: 12px;
    }
    QLabel#SessionConnStatus {
        color: #475569;
        font-weight: 600;
        font-size: 12px;
    }
    QLineEdit#SessionHostEdit {
        min-width: 180px;
    }
    QWidget#MainBody {
        background: #f6f8fb;
    }
    QLabel#ScrcpyHintLabel {
        color: #64748b;
        font-size: 12px;
    }
    QWidget#ScrcpyLeftPanel {
        background: transparent;
    }
    QWidget#ScrcpyEmbedHost {
        background: #0f1419;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
    }
    QSplitter#MainBodySplit::handle { background: #cbd5e1; height: 4px; }
    QSplitter#ScrcpyMainSplit::handle { background: #cbd5e1; width: 4px; }
    QWidget#ExplorerChrome {
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
    }
    QLabel#ExplorerSessionHint {
        font-size: 12px;
        color: #64748b;
        padding: 0px;
        margin: 0px;
    }
    """

# Appended after light stylesheet when dark=True. No global QWidget rule (breaks layout & terminal panes).
_DARK_APPEND = """
    QWidget { background: #12151c; color: #e6edf3; }
    QLabel { color: #e6edf3; background: transparent; }
    QLabel#LogPanelLabel {
        color: #e6edf3;
        font-weight: 600;
        font-size: 15px;
    }
    QMainWindow { background: #12151c; }
    QMenuBar#AppMenuBar { background: #161b22; border-bottom: 1px solid #30363d; color: #e6edf3; }
    QMenuBar#AppMenuBar::item { color: #e6edf3; }
    QMenuBar#AppMenuBar::item:selected { background: #21262d; }
    QMenu { background: #161b22; border: 1px solid #30363d; color: #e6edf3; }
    QMenu::item:selected { background: #21262d; color: #f0f6fc; }
    QTabWidget::pane { background: #161922; border: 1px solid #2d333b; }
    QTabWidget#MainTabs::pane { background: #161922; border: 1px solid #2d333b; }
    QTabWidget#MainTabs QTabBar::tab {
        background-color: #21262d;
        color: #f0f6fc;
        border: 1px solid #30363d;
        min-height: 24px;
        padding: 4px 12px;
        font-size: 13px;
    }
    QTabWidget#MainTabs QTabBar::tab:selected {
        background-color: #161922;
        color: #f0f6fc;
        border-color: #6e8cff;
        border-bottom: 2px solid #6e8cff;
    }
    QTabWidget#MainTabs QTabBar::tab:hover { background-color: #30363d; color: #f0f6fc; }
    QTabWidget#ExplorerSessionTabs QTabBar::tab {
        background-color: #21262d;
        color: #f0f6fc;
        border: 1px solid #30363d;
        min-height: 22px;
        padding: 3px 10px;
        font-size: 12px;
    }
    QTabWidget#ExplorerSessionTabs QTabBar::tab:selected {
        background-color: #0d1117;
        color: #f0f6fc;
        border-color: #58a6ff;
        border-bottom: 2px solid #58a6ff;
    }
    QTabWidget#ExplorerSessionTabs QTabBar::tab:hover { background-color: #30363d; color: #f0f6fc; }
    QTabWidget#ExplorerSessionTabs::pane { background: #0f172a; border: 1px solid #334155; }
    QTabWidget#ExplorerSessionTabs QStackedWidget { background: #0f172a; }
    QTabWidget#MobaTabs QStackedWidget { background: #0f172a; }
    QTabWidget#MainTabs > QStackedWidget {
        background: #161922;
    }
    QTabWidget#MainTabs > QStackedWidget > QWidget {
        background-color: #161922;
    }
    QTabWidget#ExplorerSessionTabs QWidget { background: #0f172a; }
    QTabWidget#MobaTabs QWidget { background: #0f172a; }
    QTabWidget#MainTabs QTabBar::close-button,
    QTabWidget#ExplorerSessionTabs QTabBar::close-button {
        subcontrol-position: right;
        width: 18px;
        height: 18px;
        border-radius: 4px;
        background: #484f58;
        margin: 3px;
    }
    QTabWidget#MainTabs QTabBar::close-button:hover,
    QTabWidget#ExplorerSessionTabs QTabBar::close-button:hover {
        background: #da3633;
    }
    QTabWidget#MobaTabs QTabBar::close-button {
        subcontrol-position: right;
        width: 18px;
        height: 18px;
        border-radius: 4px;
        background: #da3633;
        margin: 3px;
    }
    QTabWidget#MobaTabs QTabBar::close-button:hover {
        background: #f85149;
    }
    QTabWidget#MobaTabs QTabBar::tab {
        min-height: 22px;
        padding: 3px 11px;
        font-size: 13px;
        min-width: 112px;
    }
    QGroupBox { background: #111827; border: 1px solid #334155; color: #f1f5f9; }
    QGroupBox::title { color: #8b949e; }
    QPushButton { background: #1e293b; border: 1px solid #334155; color: #f1f5f9; }
    QPushButton:hover { background: #334155; }
    QPushButton:pressed { background: #475569; }
    QLineEdit, QComboBox, QTreeWidget {
        background: #0f172a;
        border: 1px solid #334155;
        color: #f1f5f9;
        selection-background-color: #1d4ed8;
        selection-color: #ffffff;
    }
    QComboBox {
        padding-right: 26px;
        min-height: 24px;
        border-top-right-radius: 8px;
        border-bottom-right-radius: 8px;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px;
        border-left: 1px solid #334155;
        background: #111827;
    }
    QComboBox QAbstractItemView {
        background: #0b1220;
        color: #f8fafc;
        border: 1px solid #475569;
        border-radius: 0px;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
        margin: 0px;
        padding: 0px;
        outline: 0;
    }
    QComboBox QAbstractItemView::viewport {
        background: #0b1220;
        margin: 0px;
        padding: 0px;
    }
    QComboBox QAbstractItemView::item {
        min-height: 24px;
        padding: 2px 6px;
        border: 0px;
    }
    QComboBox QAbstractItemView::item:selected {
        background: #2563eb;
        color: #ffffff;
    }
    QPlainTextEdit {
        background: #0f172a;
        border: 1px solid #334155;
        color: #f1f5f9;
        selection-background-color: #1d4ed8;
    }
    QHeaderView::section { background: #334155; color: #e2e8f0; border: 1px solid #475569; }
    QSplitter::handle { background: #475569; }
    QFrame#WinScpPane { background: #111827; border: 1px solid #334155; }
    QLineEdit#WinScpAddress { background: #0f172a; border: 1px solid #334155; color: #f8fafc; }
    QTableWidget#WinScpTable {
        background: #0f172a;
        border: 1px solid #334155;
        alternate-background-color: #111827;
        color: #f8fafc;
        gridline-color: #334155;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
    }
    QTableWidget#WinScpTable QHeaderView::section {
        background: #334155;
        color: #e2e8f0;
        border: 1px solid #475569;
    }
    QFrame#ExplorerTransferStrip {
        background: #1e293b;
        border: 1px solid #475569;
        border-radius: 10px;
    }
    QToolButton#ExplorerTransferBtn {
        background: #0f172a;
        border: 1px solid #475569;
        border-radius: 8px;
        color: #f8fafc;
        icon-size: 18px;
    }
    QToolButton#ExplorerTransferBtn:hover { background: #475569; border-color: #38bdf8; }
    QToolButton#ExplorerNewFileBtn {
        background: #064e3b;
        border: 1px solid #34d399;
        color: #d1fae5;
    }
    QToolButton#ExplorerNewFileBtn:hover { background: #065f46; border-color: #6ee7b7; }
    QToolButton#ExplorerEditBtn {
        background: #1e3a8a;
        border: 1px solid #60a5fa;
        color: #dbeafe;
    }
    QToolButton#ExplorerEditBtn:hover { background: #1d4ed8; border-color: #93c5fd; }
    QPushButton#ExplorerReconnectBtn {
        font-size: 12px;
        font-weight: 600;
        min-height: 26px;
        padding: 4px 11px;
    }
    QToolButton#WinScpIconBtn {
        background: #1e293b;
        border: 1px solid #475569;
        color: #f8fafc;
        border-radius: 4px;
        icon-size: 16px;
    }
    QToolButton#WinScpIconBtn:hover { background: #30363d; }
    QToolButton#WinScpIconBtn:disabled {
        background: #161b22;
        border: 1px solid #21262d;
        color: #8b949e;
    }
    QFrame#WinScpStatusBar { background: #252b3a; border: 1px solid #475569; }
    QLabel#WinScpStatusText { color: #94a3b8; }
    QLabel#WinScpStatusConn { color: #94a3b8; }
    QTextEdit#AppLogView {
        background: #0d1117;
        color: #e6edf3;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 8px 10px;
        font-size: 14px;
    }
    QPushButton#HeaderMiniBtn { background: #334155; border: 1px solid #475569; color: #e2e8f0; }
    QWidget#MainBody { background: #161922; }
    QWidget#ExplorerChrome { background: #111827; border: 1px solid #334155; }
    QLabel#ExplorerSessionHint { color: #8b949e; }
    QLabel#MobaTabCtrlLabel { color: #8b949e; }
    QPushButton#MobaCloseTabBtn {
        background: #da3633;
        border: 1px solid #f85149;
        color: #ffffff;
    }
    QPushButton#MobaCloseTabBtn:hover { background: #f85149; }
    QPushButton#ScrcpyStartBtn,
    QPushButton#ScrcpyStopBtn {
        icon-size: 16px;
        min-height: 28px;
        font-weight: 600;
        border: 1px solid #475569;
    }
    QLabel#ScrcpyConfigTitle { color: #e2e8f0; }
    QLabel#ScrcpyStatusLabel { color: #c9d1d9; }
    QLabel#ScrcpyHintLabel { color: #8b949e; font-size: 12px; }
    QWidget#ScrcpyLeftPanel { background: #0d1117; }
    QWidget#ScrcpyLeftInner { background: #0d1117; }
    QWidget#ScrcpyEmbedHost {
        background: #010409;
        border: 1px solid #30363d;
        border-radius: 8px;
    }
    QGroupBox#ScrcpyOptionsGroup QLabel, QGroupBox#ScrcpyAdbGroup QLabel { color: #e6edf3; }
    QGroupBox#ScrcpyOptionsGroup QComboBox {
        margin-bottom: 2px;
    }
    QGroupBox#ScrcpyOptionsGroup QComboBox::drop-down {
        background: transparent;
    }
    QCheckBox { color: #e6edf3; }
    QGroupBox#ScrcpyAdbGroup {
        font-size: 12px;
        font-weight: 600;
    }
    QGroupBox#ScrcpyAdbGroup QToolButton {
        background: #1e293b;
        border: 1px solid #475569;
        border-radius: 6px;
        color: #f8fafc;
        padding: 6px 8px;
        font-size: 11px;
        icon-size: 16px;
    }
    QGroupBox#ScrcpyAdbGroup QToolButton:hover { background: #334155; border-color: #58a6ff; }
    QComboBox QAbstractItemView {
        background: #0f172a;
        color: #f8fafc;
        selection-background-color: #1d4ed8;
        selection-color: #ffffff;
    }
    QToolTip { background: #161b22; color: #e6edf3; border: 1px solid #30363d; padding: 6px; }
    QDialog QLabel { color: #e6edf3; }
    QSplitter#MainBodySplit::handle { background: #30363d; height: 4px; }
    QSplitter#ScrcpyMainSplit::handle { background: #30363d; width: 4px; }
    QPushButton#SessionStripBtn { background: #334155; border: 1px solid #475569; color: #e2e8f0; }
    QFileDialog {
        background: #111827;
        color: #f1f5f9;
    }
    QFileDialog QLabel { color: #e2e8f0; background: transparent; }
    QFileDialog QLineEdit, QFileDialog QComboBox, QFileDialog QListView, QFileDialog QTreeView {
        background: #0f172a;
        color: #f1f5f9;
        border: 1px solid #334155;
        selection-background-color: #1d4ed8;
        selection-color: #ffffff;
    }
    QFileDialog QPushButton {
        background: #334155;
        border: 1px solid #475569;
        color: #f8fafc;
        padding: 8px 14px;
        border-radius: 8px;
        font-weight: 600;
    }
    QMessageBox {
        background: #111827;
        color: #f1f5f9;
    }
    QMessageBox QLabel {
        color: #e6edf3;
        background: transparent;
        min-width: 280px;
        font-size: 14px;
    }
    QMessageBox QPushButton {
        background: #334155;
        border: 1px solid #475569;
        color: #f8fafc;
        padding: 8px 18px;
        border-radius: 8px;
        font-weight: 600;
        min-width: 72px;
    }
    QMessageBox QPushButton:hover {
        background: #475569;
    }
    QMessageBox QLabel#qt_msgbox_label,
    QMessageBox QLabel#qt_msgboxex_label {
        color: #e6edf3;
        background: transparent;
    }
    QMessageBox QLabel#qt_msgbox_informativelabel {
        color: #cbd5e1;
        background: transparent;
        font-size: 13px;
    }
    QDialog { background: #111827; color: #f1f5f9; }
    QDialog QWidget { background: #111827; color: #f1f5f9; }
    QDialog QTableWidget#WinScpTable {
        background: #1e293b;
        color: #e2e8f0;
        gridline-color: #334155;
    }
    QDialog QTableWidget#WinScpTable QHeaderView::section {
        background: #334155;
        color: #e2e8f0;
    }
    QDialog QListWidget::item:selected {
        background: #1d4ed8;
        color: #ffffff;
    }
    QCheckBox { spacing: 6px; color: #f8fafc; }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 1px solid #64748b;
        border-radius: 3px;
        background: #0f172a;
    }
    QCheckBox::indicator:checked {
        background: #2563eb;
        border: 1px solid #93c5fd;
        image: url(:/qt-project.org/styles/commonstyle/images/checkbox_checked.png);
    }
    QCheckBox::indicator:unchecked {
        image: url(:/qt-project.org/styles/commonstyle/images/checkbox_unchecked.png);
    }
"""


def get_stylesheet(dark: bool = False) -> str:
    if dark:
        return _LIGHT_STYLESHEET + "\n" + _DARK_APPEND
    return _LIGHT_STYLESHEET
