import sys
import sqlite3
import requests
import uuid
import webbrowser
from PySide6.QtCore import Qt, QTimer, QSize, QThread, Signal, QRectF
from PySide6.QtGui import QIcon, QPixmap, QAction, QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QDialog, QFormLayout, QMessageBox, QComboBox, 
                             QSplitter, QListWidget, QListWidgetItem, QMenu, QCheckBox,
                             QFrame, QTabWidget, QStyledItemDelegate, QStyle)

CLIENT_DB = "client_servers.db"

# ==========================================
# MODERN QSS STYLESHEET
# ==========================================
DARK_STYLESHEET = """
QMainWindow {
    background-color: #0F172A;
}

QWidget {
    color: #F8FAFC;
    font-family: 'Segoe UI', SF Pro Display, Helvetica, Arial, sans-serif;
    font-size: 13px;
}

/* --- Metric Cards --- */
QFrame#MetricCard {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 12px;
}

QLabel#MetricValue {
    font-size: 20px;
    font-weight: bold;
    color: #38BDF8;
}

QLabel#MetricLabel {
    font-size: 11px;
    color: #94A3B8;
    font-weight: 600;
}

/* --- Panel Frames --- */
QFrame#PanelFrame {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 12px;
}

QLabel#PanelHeader {
    font-size: 14px;
    font-weight: bold;
    color: #F8FAFC;
}

/* --- Inputs & Combos --- */
QLineEdit, QComboBox {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    color: #F8FAFC;
    selection-background-color: #0284C7;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #38BDF8;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #1E293B;
    border: 1px solid #334155;
    selection-background-color: #0284C7;
    color: #F8FAFC;
}

/* --- Buttons --- */
QPushButton {
    background-color: #0284C7;
    color: #FFFFFF;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
}

QPushButton:hover {
    background-color: #0369A1;
}

QPushButton:pressed {
    background-color: #075985;
}

QPushButton#SecondaryBtn {
    background-color: #334155;
    color: #F8FAFC;
}

QPushButton#SecondaryBtn:hover {
    background-color: #475569;
}

/* --- List Views --- */
QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget::item {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px;
    margin-bottom: 6px;
    color: #F8FAFC;
}

QListWidget::item:hover {
    background-color: #1E293B;
    border-color: #38BDF8;
}

QListWidget::item:selected {
    background-color: #0369A1;
    border-color: #38BDF8;
    color: #FFFFFF;
}

/* Icon Mode Specifics for Explorer */
QListWidget#ExplorerList::item, QListWidget#ModList::item, QListWidget#FavList::item {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 6px;
    margin: 4px;
}

QListWidget#ExplorerList::item:hover, QListWidget#ModList::item:hover, QListWidget#FavList::item:hover {
    background-color: #1E293B;
    border-color: #38BDF8;
}

/* --- Tabs --- */
QTabWidget::pane {
    border: 1px solid #334155;
    background-color: transparent;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #0F172A;
    color: #94A3B8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    font-weight: bold;
}

QTabBar::tab:selected {
    background-color: #1E293B;
    color: #38BDF8;
    border-bottom: 2px solid #38BDF8;
}

/* --- Splitter --- */
QSplitter::handle {
    background-color: transparent;
    width: 8px;
}

/* --- Context Menu --- */
QMenu {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 20px 6px 10px;
    border-radius: 4px;
    color: #F8FAFC;
}

QMenu::item:selected {
    background-color: #0284C7;
    color: #FFFFFF;
}

/* --- Dialogs --- */
QDialog {
    background-color: #1E293B;
}

QCheckBox {
    color: #F8FAFC;
}
"""

def init_client_db():
    conn = sqlite3.connect(CLIENT_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS connected_servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_name TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            server_key TEXT,
            session_token TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_config (
            client_id TEXT PRIMARY KEY,
            username TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorite_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_name TEXT NOT NULL,
            link_id INTEGER NOT NULL,
            title TEXT,
            url TEXT,
            item_type TEXT,
            UNIQUE(server_name, link_id)
        )
    ''')
    cursor.execute('SELECT client_id, username FROM client_config')
    row = cursor.fetchone()
    if not row:
        c_id = f"user_{uuid.uuid4().hex[:8]}"
        cursor.execute('INSERT INTO client_config VALUES (?, ?)', (c_id, f"Client_{c_id[5:]}"))
    conn.commit()
    conn.close()

init_client_db()

def get_client_info():
    conn = sqlite3.connect(CLIENT_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT client_id, username FROM client_config')
    row = cursor.fetchone()
    conn.close()
    return row[0], row[1]

def update_client_username(new_username):
    c_id, _ = get_client_info()
    conn = sqlite3.connect(CLIENT_DB)
    cursor = conn.cursor()
    cursor.execute('UPDATE client_config SET username = ? WHERE client_id = ?', (new_username, c_id))
    conn.commit()
    conn.close()

def update_server_token(server_name, new_token):
    if not new_token:
        return
    conn = sqlite3.connect(CLIENT_DB)
    cursor = conn.cursor()
    cursor.execute('UPDATE connected_servers SET session_token = ? WHERE server_name = ?', (new_token, server_name))
    conn.commit()
    conn.close()

def get_auth_headers(srv_data):
    client_id, _ = get_client_info()
    return {
        'X-Client-ID': client_id,
        'X-Session-Token': srv_data.get('session_token', '') or '',
        'X-Server-Key': srv_data.get('server_key', '') or '',
        'bypass-tunnel-reminder': 'true'
    }

def check_drive_privacy(url):
    if "sharing" in url or "usp=sharing" in url or "export=download" in url:
        return True
    if "/file/d/" in url or "/drive/folders/" in url:
        return True
    return False

# ==========================================
# FAVORITES DB HELPERS
# ==========================================
def add_favorite(server_name, link_id, title, url, item_type):
    conn = sqlite3.connect(CLIENT_DB)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO favorite_resources (server_name, link_id, title, url, item_type)
        VALUES (?, ?, ?, ?, ?)
    ''', (server_name, link_id, title, url, item_type))
    conn.commit()
    conn.close()

def remove_favorite(server_name, link_id):
    conn = sqlite3.connect(CLIENT_DB)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM favorite_resources WHERE server_name = ? AND link_id = ?', (server_name, link_id))
    conn.commit()
    conn.close()

def get_favorites():
    conn = sqlite3.connect(CLIENT_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT server_name, link_id, title, url, item_type FROM favorite_resources')
    rows = cursor.fetchall()
    conn.close()
    return set((r[0], r[1]) for r in rows)

# ==========================================
# WORKER THREAD FOR ASYNC FETCHING
# ==========================================
class LinkFetcherThread(QThread):
    links_fetched = Signal(list, dict)  # (fetched_links, server_statuses)

    def __init__(self, servers, selected_server="All Servers", parent=None):
        super().__init__(parent)
        self.servers = servers
        self.selected_server = selected_server

    def run(self):
        all_links = []
        statuses = {}

        for srv in self.servers:
            s_name = srv['server_name']
            if self.selected_server != "All Servers" and s_name != self.selected_server:
                continue

            headers = get_auth_headers(srv)
            try:
                res = requests.get(f"{srv['url']}/api/links", headers=headers, timeout=2.5)
                if res.status_code == 200:
                    statuses[s_name] = True
                    links = res.json()
                    for item in links:
                        item['origin_server'] = s_name
                        item['server_url'] = srv['url']
                        item['server_key'] = srv['server_key']
                        item['session_token'] = srv['session_token']
                        all_links.append(item)
                else:
                    statuses[s_name] = False
            except Exception:
                statuses[s_name] = False

        self.links_fetched.emit(all_links, statuses)

# ==========================================
# SERVER HEALTH LIST DELEGATE
# ==========================================
class ServerItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        srv_data = index.data(Qt.UserRole)
        is_online = index.data(Qt.UserRole + 1)
        selected = option.state & QStyle.State_Selected

        # Draw item background
        bg_color = QColor("#0369A1" if selected else "#0F172A")
        border_color = QColor("#38BDF8" if selected else "#334155")

        rect = option.rect.adjusted(2, 2, -2, -2)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, 8, 8)

        # Draw Server Health Indicator Badge
        status_color = QColor("#22C55E") if is_online else QColor("#EF4444")
        painter.setBrush(QBrush(status_color))
        painter.setPen(Qt.NoPen)
        badge_y = rect.center().y() - 5
        painter.drawEllipse(rect.left() + 10, badge_y, 10, 10)

        # Draw Server Name & Status Text
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold if selected else QFont.Normal))
        painter.setPen(QPen(QColor("#FFFFFF" if selected else "#F8FAFC")))
        
        server_text = index.data(Qt.DisplayRole) or (srv_data.get('server_name') if srv_data else '')
        text_rect = QRectF(rect.left() + 28, rect.top(), rect.width() - 85, rect.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, server_text)

        # Draw Online / Offline Text Badge
        status_str = "ONLINE" if is_online else "OFFLINE"
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QPen(status_color))
        status_rect = QRectF(rect.right() - 60, rect.top(), 52, rect.height())
        painter.drawText(status_rect, Qt.AlignVCenter | Qt.AlignRight, status_str)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 44)

# ==========================================
# CUSTOM UI COMPONENTS
# ==========================================
class MetricCard(QFrame):
    def __init__(self, title, value="0", parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        
        self.val_label = QLabel(value)
        self.val_label.setObjectName("MetricValue")
        
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("MetricLabel")
        
        layout.addWidget(self.val_label)
        layout.addWidget(self.title_label)
        self.setLayout(layout)

    def set_value(self, value):
        self.val_label.setText(str(value))

class LinkModal(QDialog):
    def __init__(self, parent=None, initial_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Resource Link" if initial_data else "Add Cloud / Drive Resource")
        self.resize(440, 300)
        self.initial_data = initial_data
        
        layout = QFormLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.title_input = QLineEdit()
        self.url_input = QLineEdit()
        
        self.provider_box = QComboBox()
        self.provider_box.addItems(["Google Drive", "Dropbox", "OneDrive", "Mega", "Direct/Other"])
        
        self.type_box = QComboBox()
        self.type_box.addItems([
            "folder", 
            "unknown file", 
            "audio", 
            "video", 
            "word", 
            "excel", 
            "powerpoint", 
            "image", 
            "txt document"
        ])
        
        self.public_check = QCheckBox("Public Link (Checked = Public, Unchecked = Private)")
        self.public_check.setChecked(True)
        
        self.url_input.textChanged.connect(self.auto_detect_privacy)
        self.url_input.textChanged.connect(self.auto_detect_provider)
        
        layout.addRow("Title:", self.title_input)
        layout.addRow("Resource URL:", self.url_input)
        layout.addRow("Link Provider:", self.provider_box)
        layout.addRow("Item Type:", self.type_box)
        layout.addRow("Privacy Status:", self.public_check)
        
        if initial_data:
            self.title_input.setText(initial_data.get('title', ''))
            self.url_input.setText(initial_data.get('url', ''))
            self.type_box.setCurrentText(initial_data.get('item_type', 'unknown file'))
            self.public_check.setChecked(bool(initial_data.get('is_public', 1)))

        save_btn = QPushButton("Save Link")
        save_btn.clicked.connect(self.accept)
        layout.addRow(save_btn)
        self.setLayout(layout)

    def auto_detect_provider(self, url):
        url_lower = url.lower()
        if "drive.google.com" in url_lower or "docs.google.com" in url_lower:
            self.provider_box.setCurrentText("Google Drive")
        elif "dropbox.com" in url_lower:
            self.provider_box.setCurrentText("Dropbox")
        elif "onedrive" in url_lower or "1drv.ms" in url_lower or "sharepoint" in url_lower:
            self.provider_box.setCurrentText("OneDrive")
        elif "mega.nz" in url_lower or "mega.io" in url_lower:
            self.provider_box.setCurrentText("Mega")
        elif url and self.provider_box.currentText() == "Google Drive":
            self.provider_box.setCurrentText("Direct/Other")

    def auto_detect_privacy(self, url):
        if not self.initial_data:
            if "drive.google.com" in url or "docs.google.com" in url:
                is_pub = check_drive_privacy(url)
                self.public_check.setChecked(is_pub)

    def get_data(self):
        selected_type = self.type_box.currentText()
        if self.provider_box.currentText() == "Direct/Other" and selected_type not in [
            "folder", "unknown file", "audio", "video", "word", "excel", "powerpoint", "image", "txt document"
        ]:
            selected_type = "unknown file"

        return {
            "title": self.title_input.text().strip(),
            "url": self.url_input.text().strip(),
            "item_type": selected_type,
            "is_public": 1 if self.public_check.isChecked() else 0
        }

class ServerModal(QDialog):
    def __init__(self, parent=None, server_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Server Details" if server_data else "Connect New Server")
        self.resize(400, 240)
        
        layout = QFormLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. xxx (without .loca.lt)")
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("16-character server key")
        
        self.url_display = QLineEdit()
        self.url_display.setReadOnly(True)
        
        layout.addRow("Server Name:", self.name_input)
        layout.addRow("Localtunnel Endpoint:", self.url_display)
        layout.addRow("Server Key:", self.key_input)
        
        if server_data:
            self.name_input.blockSignals(True)
            self.name_input.setText(server_data['server_name'])
            self.key_input.setText(server_data['server_key'])
            self.url_display.setText(server_data['url'])
            self.name_input.blockSignals(False)

        self.name_input.textChanged.connect(self.update_url)
            
        save_btn = QPushButton("Save & Connect")
        save_btn.clicked.connect(self.accept)
        layout.addRow(save_btn)
        self.setLayout(layout)

    def update_url(self, text):
        clean_name = text.strip().lower().replace("https://", "").replace(".loca.lt", "")
        self.url_display.setText(f"https://{clean_name}.loca.lt" if clean_name else "")

    def get_data(self):
        s_name = self.name_input.text().strip().lower().replace("https://", "").replace(".loca.lt", "")
        full_url = f"https://{s_name}.loca.lt"
        key = self.key_input.text().strip()
        return s_name, full_url, key

class ProfileDialog(QDialog):
    def __init__(self, active_servers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Profile")
        self.resize(480, 280)
        self.active_servers = active_servers
        client_id, username = get_client_info()
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        form = QFormLayout()
        form.setSpacing(10)
        
        cid_lbl = QLabel(client_id)
        cid_lbl.setStyleSheet("color: #38BDF8; font-weight: bold;")
        form.addRow("Client ID:", cid_lbl)
        
        self.uname_input = QLineEdit(username)
        form.addRow("Custom Username:", self.uname_input)
        
        save_btn = QPushButton("Update Profile")
        save_btn.clicked.connect(self.save_profile)
        form.addRow(save_btn)
        layout.addLayout(form)
        
        layout.addWidget(QLabel("<b>Server Access & Roles:</b>"))
        self.status_list = QListWidget()
        layout.addWidget(self.status_list)
        
        self.setLayout(layout)
        self.load_status()

    def load_status(self):
        self.status_list.clear()
        
        for srv in self.active_servers:
            headers = get_auth_headers(srv)
            try:
                res = requests.get(f"{srv['url']}/api/user/profile", headers=headers, timeout=2)
                if res.status_code == 200:
                    data = res.json()
                    role = data.get('role', 'user')
                    write = "Allowed" if data.get('can_write') else "Revoked"
                    if data.get('session_token'):
                        update_server_token(srv['server_name'], data['session_token'])
                    self.status_list.addItem(f"Server: {srv['server_name']} | Role: {role} | Write Permission: {write}")
                else:
                    self.status_list.addItem(f"Server: {srv['server_name']} | Status: Auth Error ({res.status_code})")
            except Exception:
                self.status_list.addItem(f"Server: {srv['server_name']} | Status: Server Offline / Unreachable")

    def save_profile(self):
        new_uname = self.uname_input.text().strip()
        if new_uname:
            update_client_username(new_uname)
            for srv in self.active_servers:
                headers = get_auth_headers(srv)
                try:
                    res = requests.post(f"{srv['url']}/api/user/profile", json={"username": new_uname}, headers=headers, timeout=2)
                    if res.status_code == 200 and res.json().get('session_token'):
                        update_server_token(srv['server_name'], res.json()['session_token'])
                except Exception:
                    pass
            QMessageBox.information(self, "Success", "Profile updated and synchronized.")

# ==========================================
# MAIN APPLICATION WINDOW
# ==========================================
class ClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi-Server Drive Explorer")
        self.resize(1150, 720)
        self.is_moderator = False
        self.fetch_thread = None
        
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # -----------------------------
        # TOP HEADER & PROFILE BAR
        # -----------------------------
        top_bar = QHBoxLayout()
        title_lbl = QLabel("Dashboard & Explorer")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #F8FAFC;")
        top_bar.addWidget(title_lbl)
        
        top_bar.addStretch()
        
        self.profile_btn = QPushButton("My Profile")
        self.profile_btn.setObjectName("SecondaryBtn")
        self.profile_btn.clicked.connect(self.open_profile)
        top_bar.addWidget(self.profile_btn)
        
        self.add_srv_btn = QPushButton("+ Add Server Connection")
        self.add_srv_btn.clicked.connect(self.add_server)
        top_bar.addWidget(self.add_srv_btn)
        
        main_layout.addLayout(top_bar)
        
        # -----------------------------
        # METRICS DASHBOARD
        # -----------------------------
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)
        
        self.card_servers = MetricCard("Connected Servers", "0")
        self.card_links = MetricCard("Total Link Resources", "0")
        self.card_public = MetricCard("Public Items", "0")
        self.card_private = MetricCard("Private Items", "0")
        
        metrics_layout.addWidget(self.card_servers)
        metrics_layout.addWidget(self.card_links)
        metrics_layout.addWidget(self.card_public)
        metrics_layout.addWidget(self.card_private)
        
        main_layout.addLayout(metrics_layout)
        
        # -----------------------------
        # SEARCH & FILTER BAR
        # -----------------------------
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        srv_filter_lbl = QLabel("Filter Server:")
        srv_filter_lbl.setStyleSheet("font-weight: 600; color: #94A3B8;")
        search_layout.addWidget(srv_filter_lbl)
        
        self.server_filter = QComboBox()
        self.server_filter.setFixedWidth(180)
        self.server_filter.currentIndexChanged.connect(self.load_all_links)
        search_layout.addWidget(self.server_filter)
        
        search_lbl = QLabel("Search Explorer:")
        search_lbl.setStyleSheet("font-weight: 600; color: #94A3B8;")
        search_layout.addWidget(search_lbl)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, owner username, or server...")
        self.search_input.textChanged.connect(self.filter_explorer)
        search_layout.addWidget(self.search_input)
        
        main_layout.addLayout(search_layout)
        
        # -----------------------------
        # SPLITTER: SIDEBAR & MAIN GRID
        # -----------------------------
        splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel: Connected Servers List with Health Visual Delegate
        left_widget = QFrame()
        left_widget.setObjectName("PanelFrame")
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(14, 14, 14, 14)
        
        left_hdr = QLabel("Server Connections")
        left_hdr.setObjectName("PanelHeader")
        left_layout.addWidget(left_hdr)
        
        self.server_list = QListWidget()
        self.server_list.setItemDelegate(ServerItemDelegate(self.server_list))
        self.server_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.server_list.customContextMenuRequested.connect(self.show_server_context_menu)
        left_layout.addWidget(self.server_list)
        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)
        
        # Right Panel: Main Tabbed View
        right_widget = QFrame()
        right_widget.setObjectName("PanelFrame")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(14, 14, 14, 14)
        
        self.tab_widget = QTabWidget()
        
        # Tab 1: General Explorer
        self.explorer_tab = QWidget()
        exp_tab_layout = QVBoxLayout(self.explorer_tab)
        exp_tab_layout.setContentsMargins(0, 10, 0, 0)
        
        hdr_layout = QHBoxLayout()
        right_hdr = QLabel("Explorer (Files & Folders)")
        right_hdr.setObjectName("PanelHeader")
        hdr_layout.addWidget(right_hdr)
        
        self.add_link_btn = QPushButton("+ Add Resource Link")
        self.add_link_btn.clicked.connect(self.add_drive_link)
        hdr_layout.addWidget(self.add_link_btn)
        exp_tab_layout.addLayout(hdr_layout)
        
        self.explorer_list = QListWidget()
        self.explorer_list.setObjectName("ExplorerList")
        self.explorer_list.setViewMode(QListWidget.IconMode)
        self.explorer_list.setIconSize(QSize(56, 56))
        self.explorer_list.setGridSize(QSize(150, 115))
        self.explorer_list.setMovement(QListWidget.Static)
        self.explorer_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.explorer_list.customContextMenuRequested.connect(self.show_explorer_context_menu)
        self.explorer_list.itemDoubleClicked.connect(self.open_link_in_browser)
        exp_tab_layout.addWidget(self.explorer_list)
        
        self.tab_widget.addTab(self.explorer_tab, "Explorer")

        # Tab 2: Favorites / Starred Grid View
        self.fav_tab = QWidget()
        fav_tab_layout = QVBoxLayout(self.fav_tab)
        fav_tab_layout.setContentsMargins(0, 10, 0, 0)

        fav_hdr = QLabel("Starred & Favorite Resources")
        fav_hdr.setObjectName("PanelHeader")
        fav_tab_layout.addWidget(fav_hdr)

        self.fav_list = QListWidget()
        self.fav_list.setObjectName("FavList")
        self.fav_list.setViewMode(QListWidget.IconMode)
        self.fav_list.setIconSize(QSize(56, 56))
        self.fav_list.setGridSize(QSize(150, 115))
        self.fav_list.setMovement(QListWidget.Static)
        self.fav_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fav_list.customContextMenuRequested.connect(self.show_explorer_context_menu)
        self.fav_list.itemDoubleClicked.connect(self.open_link_in_browser)
        fav_tab_layout.addWidget(self.fav_list)

        self.tab_widget.addTab(self.fav_tab, "Favorites")
        
        # Tab 3: Moderator Hub (Dynamic)
        self.mod_tab = QWidget()
        mod_tab_layout = QVBoxLayout(self.mod_tab)
        mod_tab_layout.setContentsMargins(0, 10, 0, 0)
        
        mod_hdr_layout = QHBoxLayout()
        mod_hdr = QLabel("Moderator Hub (All System Links)")
        mod_hdr.setObjectName("PanelHeader")
        mod_hdr_layout.addWidget(mod_hdr)
        mod_tab_layout.addLayout(mod_hdr_layout)

        # Dynamic Search Bar for Moderator Hub
        mod_search_card = QFrame()
        mod_search_card.setObjectName("MetricCard")
        mod_sc_layout = QHBoxLayout(mod_search_card)
        mod_sc_layout.setContentsMargins(8, 8, 8, 8)

        mod_sc_layout.addWidget(QLabel("Search:"))
        self.mod_search_input = QLineEdit()
        self.mod_search_input.setPlaceholderText("Type name, user, or file type...")
        self.mod_search_input.textChanged.connect(self.filter_mod_files)
        mod_sc_layout.addWidget(self.mod_search_input)

        mod_sc_layout.addWidget(QLabel("Filter By:"))
        self.mod_type_filter = QComboBox()
        self.mod_type_filter.addItems([
            "All Types", "folder", "unknown file", "word", "excel", 
            "powerpoint", "image", "audio", "video", "txt document"
        ])
        self.mod_type_filter.currentIndexChanged.connect(self.filter_mod_files)
        mod_sc_layout.addWidget(self.mod_type_filter)

        mod_tab_layout.addWidget(mod_search_card)

        self.mod_list = QListWidget()
        self.mod_list.setObjectName("ModList")
        self.mod_list.setViewMode(QListWidget.IconMode)
        self.mod_list.setIconSize(QSize(56, 56))
        self.mod_list.setGridSize(QSize(150, 115))
        self.mod_list.setMovement(QListWidget.Static)
        self.mod_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mod_list.customContextMenuRequested.connect(self.show_explorer_context_menu)
        self.mod_list.itemDoubleClicked.connect(self.open_link_in_browser)
        mod_tab_layout.addWidget(self.mod_list)
        
        right_layout.addWidget(self.tab_widget)
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)
        
        splitter.setSizes([260, 850])
        main_layout.addWidget(splitter)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        self.all_fetched_links = []
        self.server_statuses = {}
        self.refresh_servers()
        
        # Polling Timer for Async Link Refresh
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_all_links)
        self.timer.start(6000)

    def check_moderator_status(self, servers):
        selected_srv = self.server_filter.currentText()
        is_mod = False
        
        for srv in servers:
            if selected_srv != "All Servers" and srv['server_name'] != selected_srv:
                continue
            headers = get_auth_headers(srv)
            try:
                res = requests.get(f"{srv['url']}/api/user/profile", headers=headers, timeout=2)
                if res.status_code == 200:
                    data = res.json()
                    if data.get('role') == 'moderator':
                        is_mod = True
                        break
            except Exception:
                pass

        self.is_moderator = is_mod
        tab_idx = self.tab_widget.indexOf(self.mod_tab)
        
        if self.is_moderator and tab_idx == -1:
            self.tab_widget.addTab(self.mod_tab, "Manage Links (All)")
        elif not self.is_moderator and tab_idx != -1:
            self.tab_widget.removeTab(tab_idx)

    def get_servers_from_db(self):
        conn = sqlite3.connect(CLIENT_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT id, server_name, url, server_key, session_token FROM connected_servers")
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "server_name": r[1], "url": r[2], "server_key": r[3], "session_token": r[4]} for r in rows]

    def refresh_servers(self):
        servers = self.get_servers_from_db()
        self.server_list.clear()
        
        self.server_filter.blockSignals(True)
        self.server_filter.clear()
        self.server_filter.addItem("All Servers")
        
        for srv in servers:
            self.server_filter.addItem(srv['server_name'])
            is_online = self.server_statuses.get(srv['server_name'], False)
            
            item = QListWidgetItem(srv['server_name'])
            item.setData(Qt.UserRole, srv)
            item.setData(Qt.UserRole + 1, is_online)
            self.server_list.addItem(item)
            
        self.server_filter.blockSignals(False)
        self.card_servers.set_value(len(servers))
        self.load_all_links()

    def add_server(self):
        dialog = ServerModal(self)
        if dialog.exec():
            s_name, url, key = dialog.get_data()
            if not s_name:
                return
            
            client_id, username = get_client_info()
            headers = {
                'X-Client-ID': client_id,
                'X-Server-Key': key,
                'bypass-tunnel-reminder': 'true'
            }
            try:
                res = requests.post(f"{url}/api/auth/connect", json={"username": username}, headers=headers, timeout=3)
                if res.status_code == 200:
                    token = res.json().get('session_token')
                    conn = sqlite3.connect(CLIENT_DB)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO connected_servers (server_name, url, server_key, session_token)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(server_name) DO UPDATE SET url=?, server_key=?, session_token=?
                    ''', (s_name, url, key, token, url, key, token))
                    conn.commit()
                    conn.close()
                    QMessageBox.information(self, "Success", f"Connected to server '{s_name}'!")
                    self.refresh_servers()
                else:
                    QMessageBox.warning(self, "Auth Failed", res.json().get('error', 'Invalid Key'))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed connecting: {str(e)}")

    def edit_server(self, server_data):
        dialog = ServerModal(self, server_data)
        if dialog.exec():
            s_name, url, key = dialog.get_data()
            conn = sqlite3.connect(CLIENT_DB)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE connected_servers SET server_name = ?, url = ?, server_key = ? WHERE id = ?
            ''', (s_name, url, key, server_data['id']))
            conn.commit()
            conn.close()
            self.refresh_servers()

    def show_server_context_menu(self, pos):
        item = self.server_list.itemAt(pos)
        if not item:
            return
        srv_data = item.data(Qt.UserRole)
        
        menu = QMenu(self)
        edit_act = QAction("Edit Server Details", self)
        edit_act.triggered.connect(lambda: self.edit_server(srv_data))
        menu.addAction(edit_act)
        
        remove_act = QAction("Remove Server", self)
        remove_act.triggered.connect(lambda: self.remove_server(srv_data['id']))
        menu.addAction(remove_act)
        
        menu.exec(self.server_list.mapToGlobal(pos))

    def remove_server(self, server_id):
        conn = sqlite3.connect(CLIENT_DB)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM connected_servers WHERE id = ?", (server_id,))
        conn.commit()
        conn.close()
        self.refresh_servers()

    def create_explorer_icon(self, item_type, is_public, is_starred=False):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        type_colors = {
            'folder': "#F59E0B",
            'word': "#2563EB",
            'excel': "#16A34A",
            'powerpoint': "#EA580C",
            'image': "#9333EA",
            'audio': "#D97706",
            'video': "#E11D48",
            'txt document': "#475569",
            'unknown file': "#64748B",
            'file': "#0284C7"
        }
        type_labels = {
            'word': 'DOC', 'excel': 'XLS', 'powerpoint': 'PPT',
            'image': 'IMG', 'audio': 'AUD', 'video': 'VID',
            'txt document': 'TXT', 'unknown file': 'FILE', 'file': 'DOC'
        }
        
        base_color = QColor(type_colors.get(item_type, "#0284C7"))
        
        if item_type == 'folder':
            painter.setBrush(base_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(6, 16, 52, 38, 6, 6)
            painter.drawRoundedRect(6, 10, 22, 10, 4, 4)
        else:
            painter.setBrush(base_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(10, 6, 44, 52, 6, 6)
            
            painter.setPen(QColor("#FFFFFF"))
            font = QFont("Arial", 8, QFont.Bold)
            painter.setFont(font)
            text = type_labels.get(item_type, 'FILE')
            painter.drawText(10, 20, 44, 24, Qt.AlignCenter, text)
            
        badge_color = QColor("#22C55E") if is_public else QColor("#EF4444")
        painter.setBrush(badge_color)
        painter.setPen(QPen(QColor("#0F172A"), 2))
        painter.drawEllipse(42, 42, 16, 16)

        if is_starred:
            painter.setBrush(QColor("#F59E0B"))
            painter.setPen(QPen(QColor("#0F172A"), 1))
            painter.drawEllipse(6, 6, 14, 14)
        
        painter.end()
        return QIcon(pixmap)

    def load_all_links(self):
        """Asynchronous Link & Server Status Fetcher using QThread"""
        if self.fetch_thread and self.fetch_thread.isRunning():
            return

        servers = self.get_servers_from_db()
        self.check_moderator_status(servers)

        selected_srv = self.server_filter.currentText()
        self.fetch_thread = LinkFetcherThread(servers, selected_srv)
        self.fetch_thread.links_fetched.connect(self.on_links_fetched)
        self.fetch_thread.start()

    def on_links_fetched(self, links, statuses):
        self.all_fetched_links = links
        self.server_statuses = statuses

        # Update Server Health Badges in left list
        for i in range(self.server_list.count()):
            item = self.server_list.item(i)
            srv_data = item.data(Qt.UserRole)
            if srv_data:
                s_name = srv_data['server_name']
                item.setData(Qt.UserRole + 1, statuses.get(s_name, False))
        self.server_list.viewport().update()

        self.filter_explorer()

    def filter_explorer(self):
        query = self.search_input.text().strip().lower()
        self.explorer_list.clear()
        self.fav_list.clear()
        self.mod_list.clear()
        
        pub_count = 0
        priv_count = 0
        fav_set = get_favorites()
        
        for item in self.all_fetched_links:
            s_name = item.get('origin_server', '')
            link_id = item.get('id')
            is_fav = (s_name, link_id) in fav_set

            if item.get('is_public'):
                pub_count += 1
            else:
                priv_count += 1

            title = item.get('title', '').lower()
            owner = item.get('username', '').lower()
            s_name_lower = s_name.lower()

            if query and not (query in s_name_lower or query in title or query in owner):
                continue
                
            icon = self.create_explorer_icon(item.get('item_type'), item.get('is_public'), is_starred=is_fav)
            visibility = "Public" if item.get('is_public') else "Private"
            label = f"{item.get('title')}\n[{visibility}] ({s_name})"
            
            list_item = QListWidgetItem(icon, label)
            list_item.setData(Qt.UserRole, item)
            self.explorer_list.addItem(list_item)

            if is_fav:
                fav_item = QListWidgetItem(icon, f"{item.get('title')}\n[{visibility}] ({s_name})")
                fav_item.setData(Qt.UserRole, item)
                self.fav_list.addItem(fav_item)
            
            if self.is_moderator:
                mod_item = QListWidgetItem(icon, f"{item.get('title')}\nBy: {item.get('username')}\n[{visibility}]")
                mod_item.setData(Qt.UserRole, item)
                self.mod_list.addItem(mod_item)

        self.card_links.set_value(len(self.all_fetched_links))
        self.card_public.set_value(pub_count)
        self.card_private.set_value(priv_count)
        
        if self.is_moderator:
            self.filter_mod_files()

    def filter_mod_files(self):
        query = self.mod_search_input.text().strip().lower()
        selected_type = self.mod_type_filter.currentText().lower()

        for i in range(self.mod_list.count()):
            item = self.mod_list.item(i)
            data = item.data(Qt.UserRole)
            if not data:
                continue

            title = str(data.get("title", "")).lower()
            username = str(data.get("username", "")).lower()
            user_id = str(data.get("user_id", "")).lower()
            item_type = str(data.get("item_type", "")).lower()

            matches_query = (
                not query 
                or query in title 
                or query in username 
                or query in user_id 
                or query in item_type
            )
            
            matches_type = (selected_type == "all types" or selected_type == item_type)

            item.setHidden(not (matches_query and matches_type))

    def show_explorer_context_menu(self, pos):
        sender_list = self.sender()
        item = sender_list.itemAt(pos) if sender_list else None
        if not item:
            return
            
        data = item.data(Qt.UserRole)
        menu = QMenu(self)
        
        open_act = QAction("Open in Local Browser", self)
        open_act.triggered.connect(lambda: webbrowser.open(data['url']))
        menu.addAction(open_act)

        # Clipboard Actions
        copy_url_act = QAction("Copy Link URL", self)
        copy_url_act.triggered.connect(lambda: self.copy_to_clipboard(data['url'], "Link URL copied to clipboard!"))
        menu.addAction(copy_url_act)

        copy_full_act = QAction("Copy Title & Link", self)
        copy_full_act.triggered.connect(lambda: self.copy_to_clipboard(f"{data['title']} - {data['url']}", "Title & Link copied to clipboard!"))
        menu.addAction(copy_full_act)

        menu.addSeparator()

        # Favorite Pinning Actions
        fav_set = get_favorites()
        is_fav = (data['origin_server'], data['id']) in fav_set
        fav_act = QAction("★ Remove from Favorites" if is_fav else "☆ Pin to Favorites", self)
        fav_act.triggered.connect(lambda: self.toggle_favorite(data, is_fav))
        menu.addAction(fav_act)

        menu.addSeparator()

        edit_act = QAction("Edit Link", self)
        edit_act.triggered.connect(lambda: self.edit_link(data))
        menu.addAction(edit_act)
        
        info_act = QAction("View Properties", self)
        info_act.triggered.connect(lambda: self.view_link_info(data))
        menu.addAction(info_act)
        
        del_act = QAction("Remove Link", self)
        del_act.triggered.connect(lambda: self.delete_link(data))
        menu.addAction(del_act)
        
        menu.exec(sender_list.mapToGlobal(pos))

    def copy_to_clipboard(self, text, confirmation_msg="Copied to clipboard!"):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.statusBar().showMessage(confirmation_msg, 3000)

    def toggle_favorite(self, data, is_fav):
        if is_fav:
            remove_favorite(data['origin_server'], data['id'])
        else:
            add_favorite(data['origin_server'], data['id'], data['title'], data['url'], data['item_type'])
        self.filter_explorer()

    def open_link_in_browser(self, item):
        data = item.data(Qt.UserRole)
        if data and data.get('url'):
            webbrowser.open(data['url'])

    def add_drive_link(self):
        selected_srv_name = self.server_filter.currentText()
        if selected_srv_name == "All Servers":
            QMessageBox.warning(self, "Select Server", "Please select a specific server from the dropdown before adding a link.")
            return

        servers = [s for s in self.get_servers_from_db() if s['server_name'] == selected_srv_name]
        if not servers:
            return

        modal = LinkModal(self)
        if modal.exec():
            payload = modal.get_data()
            srv = servers[0]
            headers = get_auth_headers(srv)
            try:
                res = requests.post(f"{srv['url']}/api/links", json=payload, headers=headers, timeout=2)
                if res.status_code == 201:
                    new_token = res.json().get('session_token')
                    if new_token:
                        update_server_token(srv['server_name'], new_token)
                    QMessageBox.information(self, "Published", "Resource published successfully!")
                    self.load_all_links()
                else:
                    QMessageBox.warning(self, "Error", res.json().get('error', 'Failed to publish link.'))
            except Exception as e:
                QMessageBox.critical(self, "Connection Error", f"Server connection failed: {str(e)}")

    def edit_link(self, data):
        modal = LinkModal(self, initial_data=data)
        if modal.exec():
            updated_data = modal.get_data()
            updated_data['id'] = data['id']
            headers = get_auth_headers(data)
            try:
                res = requests.put(f"{data['server_url']}/api/links", json=updated_data, headers=headers, timeout=2)
                if res.status_code == 200:
                    new_token = res.json().get('session_token')
                    if new_token:
                        update_server_token(data['origin_server'], new_token)
                    self.load_all_links()
                else:
                    QMessageBox.warning(self, "Error", res.json().get('error', 'Failed updating link.'))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not sync changes: {str(e)}")

    def view_link_info(self, data):
        info_text = (
            f"Title: {data.get('title')}\n"
            f"Type: {data.get('item_type')}\n"
            f"Visibility: {'Public' if data.get('is_public') else 'Private'}\n"
            f"Owner User: {data.get('username')}\n"
            f"Server Name: {data.get('origin_server')}\n"
            f"URL: {data.get('url')}"
        )
        QMessageBox.information(self, "Resource Info", info_text)

    def delete_link(self, data):
        headers = get_auth_headers(data)
        try:
            res = requests.delete(f"{data['server_url']}/api/links?id={data['id']}", headers=headers, timeout=2)
            if res.status_code == 200:
                new_token = res.json().get('session_token')
                if new_token:
                    update_server_token(data['origin_server'], new_token)
                self.load_all_links()
            else:
                QMessageBox.warning(self, "Error", res.json().get('error', 'Failed deleting link.'))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not sync deletion: {str(e)}")

    def open_profile(self):
        active_servers = self.get_servers_from_db()
        dlg = ProfileDialog(active_servers, self)
        dlg.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    gui = ClientGUI()
    gui.show()
    sys.exit(app.exec())