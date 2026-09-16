import sys
import os
import sqlite3
import subprocess
import re
import time
import secrets
import shutil
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.serving import make_server
from PySide6.QtCore import QThread, Signal, QTimer, Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QAction, QPainter, QColor, QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QMessageBox, QTabWidget, QListWidget, 
                             QListWidgetItem, QMenu, QDialog, QFormLayout, QComboBox,
                             QProgressBar, QFrame, QGraphicsDropShadowEffect)

DB_NAME = "server_library.db"
LOG_FILE = "server_activity.log"
BACKUP_DIR = "backups"

# --- PERSISTENT LOGGING SETUP ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def log_event(message):
    logging.info(message)

# --- STYLESHEET (Dark Dashboard Theme) ---
MODERN_STYLE = """
QMainWindow {
    background-color: #0F172A;
}
QWidget {
    color: #F8FAFC;
    font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
}
QFrame#DashboardCard {
    background-color: #1E293B;
    border-radius: 12px;
    border: 1px solid #334155;
    padding: 12px;
}
QLabel {
    color: #94A3B8;
    font-weight: 500;
}
QLabel#CardTitle {
    color: #F8FAFC;
    font-size: 15px;
    font-weight: bold;
}
QLineEdit {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 12px;
    color: #F8FAFC;
    selection-background-color: #3B82F6;
}
QLineEdit:focus {
    border: 1px solid #3B82F6;
}
QLineEdit:read-only {
    background-color: #1E293B;
    color: #10B981;
}
QPushButton {
    background-color: #3B82F6;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #2563EB;
}
QPushButton:pressed {
    background-color: #1D4ED8;
}
QPushButton:disabled {
    background-color: #334155;
    color: #64748B;
}
QPushButton#StopBtn {
    background-color: #EF4444;
}
QPushButton#StopBtn:hover {
    background-color: #DC2626;
}
QTabWidget::pane {
    border: 1px solid #334155;
    background-color: #1E293B;
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
}
QTabBar::tab {
    background-color: #0F172A;
    color: #94A3B8;
    padding: 10px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background-color: #1E293B;
    color: #3B82F6;
    border-top: 2px solid #3B82F6;
}
QListWidget {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px;
}
QListWidget::item {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 8px;
    margin: 4px;
    padding: 8px;
    color: #F8FAFC;
}
QListWidget::item:hover {
    border: 1px solid #3B82F6;
    background-color: #26334D;
}
QListWidget::item:selected {
    background-color: #1D4ED8;
    border: 1px solid #60A5FA;
}
QTextEdit {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #10B981;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}
QMenu {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #3B82F6;
    color: #FFFFFF;
}
QDialog {
    background-color: #1E293B;
}
QComboBox {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px;
    color: #F8FAFC;
}
"""

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shared_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            item_type TEXT NOT NULL,
            is_public INTEGER NOT NULL,
            parent_path TEXT DEFAULT '/'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            role TEXT CHECK(role IN ('user', 'moderator')) DEFAULT 'user',
            can_write INTEGER DEFAULT 1,
            session_token TEXT,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- FEATURE: AUTOMATED SQLITE BACKUPS ---
def perform_sqlite_backup():
    if not os.path.exists(DB_NAME):
        return
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")
    
    try:
        # SQLite Online Backup API mechanism
        src = sqlite3.connect(DB_NAME)
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        log_event(f"Automated SQLite backup successfully created: {backup_path}")
    except Exception as e:
        log_event(f"Failed to perform automated SQLite backup: {e}")

flask_app = Flask(__name__)
CURRENT_SERVER_KEY = secrets.token_hex(8).upper()

# --- FEATURE: API RATE LIMITING STATE ---
CLIENT_REQUEST_TIMES = {}
RATE_LIMIT_MAX_REQUESTS = 30  # requests
RATE_LIMIT_WINDOW = 60       # seconds

@flask_app.before_request
def apply_rate_limit():
    if request.method == 'OPTIONS':
        return
    client_ip = request.remote_addr or "127.0.0.1"
    client_id = request.headers.get('X-Client-ID') or client_ip
    
    now = time.time()
    history = CLIENT_REQUEST_TIMES.get(client_id, [])
    # Filter out requests older than the sliding window
    history = [t for t in history if now - t < RATE_LIMIT_WINDOW]
    
    if len(history) >= RATE_LIMIT_MAX_REQUESTS:
        log_event(f"Rate limit exceeded for client: {client_id}")
        return jsonify({"error": "Rate limit exceeded. Try again later."}), 429
    
    history.append(now)
    CLIENT_REQUEST_TIMES[client_id] = history

@flask_app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        response = flask_app.make_default_options_response()
        headers = response.headers
        headers['Access-Control-Allow-Origin'] = '*'
        headers['Access-Control-Allow-Headers'] = 'Content-Type, bypass-tunnel-reminder, X-Client-ID, X-Server-Key, X-Session-Token, User-Agent'
        headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        return response, 200

@flask_app.after_request
def add_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, bypass-tunnel-reminder, X-Client-ID, X-Server-Key, X-Session-Token, User-Agent'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['bypass-tunnel-reminder'] = 'true'
    return response

def verify_client_access(req):
    client_id = req.headers.get('X-Client-ID') or req.args.get('user_id')
    provided_key = req.headers.get('X-Server-Key')
    session_token = req.headers.get('X-Session-Token')

    if not client_id:
        return False, "Missing Client ID", None

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, role, can_write, session_token FROM users WHERE user_id = ?', (client_id,))
    user = cursor.fetchone()

    if user and session_token and user[3] == session_token:
        cursor.execute('UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = ?', (client_id,))
        conn.commit()
        conn.close()
        return True, session_token, user

    if provided_key == CURRENT_SERVER_KEY:
        new_token = secrets.token_hex(16)
        cursor.execute('''
            INSERT INTO users (user_id, role, can_write, session_token, last_seen) 
            VALUES (?, 'user', 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET session_token=?, last_seen=CURRENT_TIMESTAMP
        ''', (client_id, new_token, new_token))
        conn.commit()
        cursor.execute('SELECT user_id, role, can_write, session_token FROM users WHERE user_id = ?', (client_id,))
        user = cursor.fetchone()
        conn.close()
        return True, new_token, user

    conn.close()
    return False, "Invalid Server Key or Session Expired", None

@flask_app.route('/api/auth/connect', methods=['POST', 'OPTIONS'])
def auth_connect():
    auth_ok, message_or_token, user_data = verify_client_access(request)
    if not auth_ok:
        return jsonify({"error": message_or_token}), 401
    
    data = request.json or {}
    custom_username = data.get('username')
    if custom_username:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET username = ? WHERE user_id = ?', (custom_username, user_data[0]))
        conn.commit()
        conn.close()

    log_event(f"User connected: {user_data[0] if user_data else 'Unknown'}")
    return jsonify({
        "status": "connected",
        "session_token": message_or_token,
        "role": user_data[1] if user_data else "user",
        "can_write": bool(user_data[2]) if user_data else True
    }), 200

@flask_app.route('/api/user/profile', methods=['GET', 'POST', 'OPTIONS'])
def user_profile():
    auth_ok, token_or_err, user_data = verify_client_access(request)
    if not auth_ok:
        return jsonify({"error": token_or_err}), 401
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.json or {}
        new_username = data.get('username', '')
        cursor.execute('UPDATE users SET username = ? WHERE user_id = ?', (new_username, user_data[0]))
        conn.commit()

    cursor.execute('SELECT user_id, username, role, can_write FROM users WHERE user_id = ?', (user_data[0],))
    u = cursor.fetchone()
    conn.close()

    return jsonify({
        "user_id": u[0],
        "username": u[1] or u[0],
        "role": u[2],
        "can_write": bool(u[3]),
        "session_token": token_or_err
    }), 200

@flask_app.route('/api/links', methods=['GET', 'OPTIONS'])
def get_links():
    auth_ok, err_or_token, user_data = verify_client_access(request)
    if not auth_ok:
        return jsonify({"error": err_or_token}), 401

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check if user is a moderator
    user_role = user_data[1] if user_data else 'user'
    
    if user_role == 'moderator':
        cursor.execute('''
            SELECT l.id, l.user_id, COALESCE(u.username, l.user_id), l.title, l.url, l.item_type, l.is_public, l.parent_path 
            FROM shared_links l
            LEFT JOIN users u ON l.user_id = u.user_id
        ''')
    else:
        cursor.execute('''
            SELECT l.id, l.user_id, COALESCE(u.username, l.user_id), l.title, l.url, l.item_type, l.is_public, l.parent_path 
            FROM shared_links l
            LEFT JOIN users u ON l.user_id = u.user_id
            WHERE l.is_public = 1 OR l.user_id = ?
        ''', (user_data[0],))
        
    rows = cursor.fetchall()
    conn.close()
    
    links = [{
        "id": row[0],
        "user_id": row[1],
        "username": row[2],
        "title": row[3],
        "url": row[4],
        "item_type": row[5],
        "is_public": bool(row[6]),
        "parent_path": row[7],
        "session_token": err_or_token
    } for row in rows]
    
    return jsonify(links), 200

@flask_app.route('/api/links', methods=['POST', 'PUT', 'DELETE', 'OPTIONS'])
def manage_links():
    auth_ok, err_or_token, user_data = verify_client_access(request)
    if not auth_ok:
        return jsonify({"error": err_or_token}), 401

    if not user_data[2] and user_data[1] != 'moderator':
        return jsonify({"error": "Write access revoked by moderator"}), 403

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.json or {}
        url = data.get('url', '')
        if not url:
            conn.close()
            return jsonify({"error": "URL cannot be empty"}), 400
        
        cursor.execute('''
            INSERT INTO shared_links (user_id, title, url, item_type, is_public, parent_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_data[0], data['title'], url, data.get('item_type', 'file'), int(data.get('is_public', 1)), data.get('parent_path', '/')))
        conn.commit()
        conn.close()
        log_event(f"Link added by {user_data[0]}: {data.get('title')}")
        return jsonify({"message": "Link added successfully", "session_token": err_or_token}), 201

    elif request.method == 'PUT':
        data = request.json or {}
        link_id = data.get('id')
        cursor.execute('''
            UPDATE shared_links SET title = ?, url = ?, item_type = ?, is_public = ? WHERE id = ?
        ''', (data['title'], data['url'], data.get('item_type', 'file'), int(data.get('is_public', 1)), link_id))
        conn.commit()
        conn.close()
        log_event(f"Link {link_id} updated by {user_data[0]}")
        return jsonify({"message": "Link updated successfully", "session_token": err_or_token}), 200

    elif request.method == 'DELETE':
        link_id = request.args.get('id')
        cursor.execute('DELETE FROM shared_links WHERE id = ?', (link_id,))
        conn.commit()
        conn.close()
        log_event(f"Link {link_id} deleted by {user_data[0]}")
        return jsonify({"message": "Link deleted successfully", "session_token": err_or_token}), 200

class FlaskThread(QThread):
    def __init__(self):
        super().__init__()
        self.server = None

    def run(self):
        self.server = make_server('0.0.0.0', 5000, flask_app, threaded=True)
        self.server.serve_forever()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server = None

class TunnelThread(QThread):
    url_found = Signal(str)
    log_signal = Signal(str)

    def __init__(self, subdomain=None):
        super().__init__()
        self.process = None
        self.subdomain = subdomain
        self.running = True

    def run(self):
        cmd = ["lt", "--port", "5000"]
        if self.subdomain:
            cmd.extend(["--subdomain", self.subdomain])

        while self.running:
            self.log_signal.emit("Launching Localtunnel process...")
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=(sys.platform == 'win32')
            )
            while self.running and self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    stripped = line.strip()
                    self.log_signal.emit(stripped)
                    match = re.search(r'https://[a-zA-Z0-9-]+\.loca\.lt', stripped)
                    if match:
                        self.url_found.emit(match.group(0))

            if self.running:
                self.log_signal.emit("Connection dropped. Auto-reconnecting in 3s...")
                time.sleep(3)

    def stop(self):
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.kill()
            except Exception:
                pass
            self.process = None

class ConnectionMeterDialog(QDialog):
    def __init__(self, user_data, target_url="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Connection Quality - {user_data['username']}")
        self.resize(380, 260)
        self.user_data = user_data
        self.target_url = target_url.strip() if target_url else "http://127.0.0.1:5000"

        layout = QVBoxLayout()
        
        info_lbl = QLabel(f"Checking connection status for <b>{user_data['username']}</b>...")
        info_lbl.setStyleSheet("color: #F8FAFC; font-size: 14px;")
        layout.addWidget(info_lbl)

        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setValue(0)
        self.meter.setTextVisible(True)
        self.meter.setFormat("Testing connection... %p%")
        self.meter.setStyleSheet("""
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 6px;
                text-align: center;
                background-color: #0F172A;
                color: #F8FAFC;
                font-weight: bold;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: #10B981;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.meter)

        self.network_info_lbl = QLabel("Target Endpoint: Initializing...")
        self.network_info_lbl.setStyleSheet("color: #3B82F6; font-size: 12px; font-weight: bold;")
        layout.addWidget(self.network_info_lbl)

        self.status_details = QLabel("Ping: -- ms | Status: Querying")
        self.status_details.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(self.status_details)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)

        self.sim_step = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_meter)
        self.timer.start(80)

    def update_meter(self):
        self.sim_step += 10
        if self.sim_step < 90:
            self.meter.setValue(self.sim_step)
        elif self.sim_step == 90:
            self.meter.setValue(90)
            self.timer.stop()
            self.perform_network_check()

    def perform_network_check(self):
        parsed = urllib.parse.urlparse(self.target_url)
        domain = parsed.netloc or "127.0.0.1:5000"
        scheme = parsed.scheme.upper() if parsed.scheme else "HTTP"
        
        self.network_info_lbl.setText(f"Target Endpoint: {scheme} -> {domain}")

        start_time = time.time()
        connected = False
        status_code = 0

        try:
            req = urllib.request.Request(self.target_url, headers={'bypass-tunnel-reminder': 'true', 'User-Agent': 'ConnectionMeter/1.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                status_code = resp.getcode()
                connected = (status_code == 200 or status_code == 404 or status_code == 401)
        except urllib.error.HTTPError as e:
            connected = True
            status_code = e.code
        except Exception:
            connected = False

        latency = int((time.time() - start_time) * 1000)

        if connected:
            self.meter.setValue(100)
            self.meter.setFormat("Signal: Connected & Active (100%)")
            self.status_details.setText(f"Latency: {latency} ms | Protocol: {scheme} | Status: Active (HTTP {status_code if status_code else 200})")
        else:
            self.meter.setValue(30)
            self.meter.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #334155;
                    border-radius: 6px;
                    text-align: center;
                    background-color: #0F172A;
                    color: #F8FAFC;
                    font-weight: bold;
                    height: 24px;
                }
                QProgressBar::chunk {
                    background-color: #EF4444;
                    border-radius: 4px;
                }
            """)
            self.meter.setFormat("Signal: Disconnected")
            self.status_details.setText(f"Target: {domain} | Status: Offline / Unreachable")

class UserInfoDialog(QDialog):
    def __init__(self, user_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"User Properties - {user_data['username']}")
        self.resize(350, 220)
        self.user_data = user_data
        
        layout = QFormLayout()
        layout.addRow("User ID:", QLabel(user_data['user_id']))
        layout.addRow("Username:", QLabel(user_data['username']))
        
        self.role_box = QComboBox()
        self.role_box.addItems(["user", "moderator"])
        self.role_box.setCurrentText(user_data['role'])
        layout.addRow("Role:", self.role_box)
        
        self.write_box = QComboBox()
        self.write_box.addItems(["Allowed", "Revoked"])
        self.write_box.setCurrentText("Allowed" if user_data['can_write'] else "Revoked")
        layout.addRow("Write Permission:", self.write_box)
        
        save_btn = QPushButton("Apply Changes")
        save_btn.clicked.connect(self.save_changes)
        layout.addRow(save_btn)
        self.setLayout(layout)

    def save_changes(self):
        new_role = self.role_box.currentText()
        new_write = 1 if self.write_box.currentText() == "Allowed" else 0
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = ?, can_write = ? WHERE user_id = ?", 
                       (new_role, new_write, self.user_data['user_id']))
        conn.commit()
        conn.close()
        log_event(f"Updated properties for user: {self.user_data['user_id']}")
        self.accept()

class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drive Central Library - Dashboard Console")
        self.resize(1000, 750)
        
        self.flask_thread = None
        self.tunnel_thread = None
        
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # --- Gateway Controls Frame ---
        self.control_card = QFrame()
        self.control_card.setObjectName("DashboardCard")
        card_layout = QVBoxLayout(self.control_card)

        title_lbl = QLabel("Server Control & Gateway Settings")
        title_lbl.setObjectName("CardTitle")
        card_layout.addWidget(title_lbl)

        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("Current Server Key:"))
        self.key_display = QLineEdit(CURRENT_SERVER_KEY)
        self.key_display.setReadOnly(True)
        key_layout.addWidget(self.key_display)
        card_layout.addLayout(key_layout)

        subdomain_layout = QHBoxLayout()
        subdomain_layout.addWidget(QLabel("Server Subdomain:"))
        self.subdomain_input = QLineEdit()
        self.subdomain_input.setPlaceholderText("e.g. my-drive-hub")
        subdomain_layout.addWidget(self.subdomain_input)
        subdomain_layout.addWidget(QLabel(".loca.lt"))
        card_layout.addLayout(subdomain_layout)
        
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel("Localtunnel Endpoint:"))
        self.url_input = QLineEdit()
        self.url_input.setReadOnly(True)
        info_layout.addWidget(self.url_input)
        card_layout.addLayout(info_layout)
        
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Server & Tunnel")
        self.start_btn.clicked.connect(self.start_server)
        btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Disconnect Tunnel")
        self.stop_btn.setObjectName("StopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_tunnel)
        btn_layout.addWidget(self.stop_btn)
        card_layout.addLayout(btn_layout)

        # --- Tab Container ---
        self.tabs = QTabWidget()
        
        # 1. Dashboard Overview Tab (Enhanced UI)
        self.dashboard_tab = QWidget()
        dash_layout = QVBoxLayout(self.dashboard_tab)
        dash_layout.setSpacing(12)

        metrics_layout_1 = QHBoxLayout()
        
        # Stat Card 1: Users
        card_users = QFrame()
        card_users.setObjectName("DashboardCard")
        cu_layout = QVBoxLayout(card_users)
        cu_layout.addWidget(QLabel("REGISTERED USERS"))
        self.lbl_user_count = QLabel("0")
        self.lbl_user_count.setStyleSheet("font-size: 24px; font-weight: bold; color: #3B82F6;")
        cu_layout.addWidget(self.lbl_user_count)
        metrics_layout_1.addWidget(card_users)

        # Stat Card 2: Links
        card_links = QFrame()
        card_links.setObjectName("DashboardCard")
        cl_layout = QVBoxLayout(card_links)
        cl_layout.addWidget(QLabel("SHARED LINKS"))
        self.lbl_link_count = QLabel("0")
        self.lbl_link_count.setStyleSheet("font-size: 24px; font-weight: bold; color: #10B981;")
        cl_layout.addWidget(self.lbl_link_count)
        metrics_layout_1.addWidget(card_links)

        # Stat Card 3: Gateway Status
        card_status = QFrame()
        card_status.setObjectName("DashboardCard")
        cs_layout = QVBoxLayout(card_status)
        cs_layout.addWidget(QLabel("GATEWAY STATUS"))
        self.lbl_gateway_status = QLabel("Offline")
        self.lbl_gateway_status.setStyleSheet("font-size: 20px; font-weight: bold; color: #EF4444;")
        cs_layout.addWidget(self.lbl_gateway_status)
        metrics_layout_1.addWidget(card_status)

        dash_layout.addLayout(metrics_layout_1)

        # Secondary Metric Row (Added Dashboard Info)
        metrics_layout_2 = QHBoxLayout()

        card_mods = QFrame()
        card_mods.setObjectName("DashboardCard")
        cm_layout = QVBoxLayout(card_mods)
        cm_layout.addWidget(QLabel("MODERATORS"))
        self.lbl_mod_count = QLabel("0")
        self.lbl_mod_count.setStyleSheet("font-size: 20px; font-weight: bold; color: #8B5CF6;")
        cm_layout.addWidget(self.lbl_mod_count)
        metrics_layout_2.addWidget(card_mods)

        # FEATURE: LIVE USER TELEMETRY METRIC
        card_active_users = QFrame()
        card_active_users.setObjectName("DashboardCard")
        cau_layout = QVBoxLayout(card_active_users)
        cau_layout.addWidget(QLabel("ACTIVE USERS (60s)"))
        self.lbl_active_users = QLabel("0")
        self.lbl_active_users.setStyleSheet("font-size: 20px; font-weight: bold; color: #EC4899;")
        cau_layout.addWidget(self.lbl_active_users)
        metrics_layout_2.addWidget(card_active_users)

        card_db_size = QFrame()
        card_db_size.setObjectName("DashboardCard")
        cd_layout = QVBoxLayout(card_db_size)
        cd_layout.addWidget(QLabel("DATABASE SIZE"))
        self.lbl_db_size = QLabel("0 KB")
        self.lbl_db_size.setStyleSheet("font-size: 20px; font-weight: bold; color: #F59E0B;")
        cd_layout.addWidget(self.lbl_db_size)
        metrics_layout_2.addWidget(card_db_size)

        card_port = QFrame()
        card_port.setObjectName("DashboardCard")
        cp_layout = QVBoxLayout(card_port)
        cp_layout.addWidget(QLabel("SERVER PORT"))
        lbl_port = QLabel("5000 (HTTP)")
        lbl_port.setStyleSheet("font-size: 20px; font-weight: bold; color: #06B6D4;")
        cp_layout.addWidget(lbl_port)
        metrics_layout_2.addWidget(card_port)

        dash_layout.addLayout(metrics_layout_2)

        # Quick Summary Card
        quick_card = QFrame()
        quick_card.setObjectName("DashboardCard")
        qc_layout = QVBoxLayout(quick_card)
        qc_title = QLabel("System Summary & Telemetry Overview")
        qc_title.setObjectName("CardTitle")
        qc_layout.addWidget(qc_title)

        self.dash_summary_lbl = QLabel("Server active on local port 5000. Start localtunnel from the Gateway tab to connect publicly.")
        self.dash_summary_lbl.setWordWrap(True)
        self.dash_summary_lbl.setStyleSheet("color: #94A3B8; font-size: 13px;")
        qc_layout.addWidget(self.dash_summary_lbl)

        dash_layout.addWidget(quick_card)
        dash_layout.addStretch()

        self.tabs.addTab(self.dashboard_tab, "Dashboard")

        # 2. Gateway Controls Tab
        self.gateway_tab = QWidget()
        gw_layout = QVBoxLayout(self.gateway_tab)
        gw_layout.addWidget(self.control_card)
        gw_layout.addStretch()
        self.tabs.addTab(self.gateway_tab, "Gateway Controls")

        # 3. Files List Tab with Dynamic Search Engine
        self.files_tab = QWidget()
        files_layout = QVBoxLayout(self.files_tab)
        
        # Search Bar Controls
        search_card = QFrame()
        search_card.setObjectName("DashboardCard")
        sc_layout = QHBoxLayout(search_card)
        sc_layout.setContentsMargins(8, 8, 8, 8)

        sc_layout.addWidget(QLabel("Search:"))
        self.file_search_input = QLineEdit()
        self.file_search_input.setPlaceholderText("Type name, user, or file type...")
        self.file_search_input.textChanged.connect(self.filter_files)
        sc_layout.addWidget(self.file_search_input)

        sc_layout.addWidget(QLabel("Filter By:"))
        self.file_type_filter = QComboBox()
        self.file_type_filter.addItems([
            "All Types", "folder", "file", "word", "excel", 
            "powerpoint", "image", "audio", "video", "txt document"
        ])
        self.file_type_filter.currentIndexChanged.connect(self.filter_files)
        sc_layout.addWidget(self.file_type_filter)

        files_layout.addWidget(search_card)

        self.files_list = QListWidget()
        self.files_list.setViewMode(QListWidget.IconMode)
        self.files_list.setIconSize(QSize(64, 64))
        self.files_list.setGridSize(QSize(140, 110))
        self.files_list.setMovement(QListWidget.Static)
        self.files_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_list.customContextMenuRequested.connect(self.show_file_context_menu)
        files_layout.addWidget(self.files_list)
        self.tabs.addTab(self.files_tab, "Managed Links (Explorer)")
        
        # 4. Users Tab with Dynamic Search Engine
        self.users_tab = QWidget()
        users_layout = QVBoxLayout(self.users_tab)

        # User Search Bar Controls
        user_search_card = QFrame()
        user_search_card.setObjectName("DashboardCard")
        usc_layout = QHBoxLayout(user_search_card)
        usc_layout.setContentsMargins(8, 8, 8, 8)

        usc_layout.addWidget(QLabel("Search Users:"))
        self.user_search_input = QLineEdit()
        self.user_search_input.setPlaceholderText("Search by User ID, Username, Role, or Write Permissions...")
        self.user_search_input.textChanged.connect(self.filter_users)
        usc_layout.addWidget(self.user_search_input)

        usc_layout.addWidget(QLabel("Filter By:"))
        self.user_filter_combo = QComboBox()
        self.user_filter_combo.addItems([
            "All Users", "Moderators", "Regular Users", "Write Allowed", "Write Revoked"
        ])
        self.user_filter_combo.currentIndexChanged.connect(self.filter_users)
        usc_layout.addWidget(self.user_filter_combo)

        users_layout.addWidget(user_search_card)

        self.users_list = QListWidget()
        self.users_list.setViewMode(QListWidget.IconMode)
        self.users_list.setIconSize(QSize(64, 64))
        self.users_list.setGridSize(QSize(140, 110))
        self.users_list.setMovement(QListWidget.Static)
        self.users_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.users_list.customContextMenuRequested.connect(self.show_user_context_menu)
        users_layout.addWidget(self.users_list)
        self.tabs.addTab(self.users_tab, "Users & Permissions")
        
        # 5. Logs Tab
        self.logs_tab = QWidget()
        logs_layout = QVBoxLayout(self.logs_tab)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        logs_layout.addWidget(self.log_box)
        self.tabs.addTab(self.logs_tab, "System Logs")
        
        main_layout.addWidget(self.tabs)
        self.setCentralWidget(central_widget)

        # Initial loading of persistent logs into the UI text box
        self.load_persistent_logs()

        # Data Refresh Timer (4s)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all_data)
        self.timer.start(4000)

        # FEATURE: BACKUP TIMER (Runs every 10 minutes)
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(perform_sqlite_backup)
        self.backup_timer.start(600000)

    # FEATURE: PERSISTENT LOG FILE LOADER
    def load_persistent_logs(self):
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r') as f:
                    content = f.read()
                    self.log_box.setText(content)
            except Exception as e:
                self.append_log(f"Error reading persistent log file: {e}")

    def append_log(self, message):
        self.log_box.append(message)
        log_event(message)

    def start_server(self):
        if not self.flask_thread:
            self.flask_thread = FlaskThread()
            self.flask_thread.start()
            self.append_log("Flask server listening on port 5000...")
        
        subdomain = self.subdomain_input.text().strip().lower()
        subdomain = re.sub(r'[^a-z0-9-]', '', subdomain)
        
        if subdomain:
            self.subdomain_input.setText(subdomain)
            self.append_log(f"Requesting custom server name: {subdomain}")
            self.tunnel_thread = TunnelThread(subdomain=subdomain)
        else:
            self.tunnel_thread = TunnelThread()

        self.tunnel_thread.url_found.connect(self.on_url_found)
        self.tunnel_thread.log_signal.connect(self.append_log)
        self.tunnel_thread.start()
        
        self.start_btn.setEnabled(False)
        self.subdomain_input.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.lbl_gateway_status.setText("Connecting...")
        self.lbl_gateway_status.setStyleSheet("font-size: 20px; font-weight: bold; color: #F59E0B;")

    def stop_tunnel(self):
        if self.tunnel_thread:
            self.tunnel_thread.stop()
            self.tunnel_thread.quit()
            self.tunnel_thread = None
            self.url_input.clear()
            self.append_log("Localtunnel disconnected.")
            self.start_btn.setEnabled(True)
            self.subdomain_input.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.lbl_gateway_status.setText("Offline")
            self.lbl_gateway_status.setStyleSheet("font-size: 20px; font-weight: bold; color: #EF4444;")

    def on_url_found(self, url):
        self.url_input.setText(url)
        self.append_log(f"Public Tunnel Active: {url}")
        self.lbl_gateway_status.setText("Online")
        self.lbl_gateway_status.setStyleSheet("font-size: 20px; font-weight: bold; color: #10B981;")

    def refresh_all_data(self):
        self.load_users()
        self.load_files()
        self.update_dashboard_metrics()

    def update_dashboard_metrics(self):
        user_count = self.users_list.count()
        link_count = self.files_list.count()
        self.lbl_user_count.setText(str(user_count))
        self.lbl_link_count.setText(str(link_count))

        # Query Database file size, moderator count, and telemetry for active users
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'moderator'")
        mod_count = cursor.fetchone()[0]
        self.lbl_mod_count.setText(str(mod_count))

        # FEATURE: LIVE USER TELEMETRY QUERY (active within last 60s)
        cursor.execute("SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-60 seconds')")
        active_count = cursor.fetchone()[0]
        self.lbl_active_users.setText(str(active_count))

        conn.close()

        if os.path.exists(DB_NAME):
            size_bytes = os.path.getsize(DB_NAME)
            size_kb = round(size_bytes / 1024, 1)
            self.lbl_db_size.setText(f"{size_kb} KB")

        url = self.url_input.text().strip()
        if url:
            self.dash_summary_lbl.setText(f"Active public endpoint: {url}\nServer Key: {CURRENT_SERVER_KEY}\nTelemetry: {active_count} active client(s) online.")
        else:
            self.dash_summary_lbl.setText(f"Server Key: {CURRENT_SERVER_KEY}\nNo public tunnel currently established.\nTelemetry: {active_count} active client(s) online.")

    def create_user_icon(self, role, can_write):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        color = QColor("#3B82F6") if role == 'moderator' else QColor("#64748B")
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(12, 4, 40, 40)
        
        painter.setBrush(QColor("#10B981") if can_write else QColor("#EF4444"))
        painter.drawEllipse(42, 42, 18, 18)
        painter.end()
        return QIcon(pixmap)

    def create_link_icon(self, item_type, is_public):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        type_colors = {
            'folder': "#F59E0B",
            'word': "#2563EB",
            'excel': "#059669",
            'powerpoint': "#EA580C",
            'image': "#9333EA",
            'audio': "#D97706",
            'video': "#DB2777",
            'txt document': "#475569",
            'unknown file': "#64748B",
            'file': "#0288D1"
        }
        type_labels = {
            'word': 'DOC', 'excel': 'XLS', 'powerpoint': 'PPT',
            'image': 'IMG', 'audio': 'AUD', 'video': 'VID',
            'txt document': 'TXT', 'unknown file': '?', 'file': 'FILE'
        }
        
        base_color = QColor(type_colors.get(item_type, "#0288D1"))
        
        if item_type == 'folder':
            painter.setBrush(base_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(8, 16, 48, 36, 4, 4)
            painter.drawRoundedRect(8, 10, 20, 8, 2, 2)
        else:
            painter.setBrush(base_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(12, 8, 40, 48, 4, 4)
            painter.setPen(QColor("#FFFFFF"))
            font = QFont("Arial", 8, QFont.Bold)
            painter.setFont(font)
            text = type_labels.get(item_type, 'FILE')
            painter.drawText(12, 20, 40, 24, Qt.AlignCenter, text)
            
        badge_color = QColor("#10B981") if is_public else QColor("#EF4444")
        painter.setPen(Qt.NoPen)
        painter.setBrush(badge_color)
        painter.drawEllipse(42, 42, 18, 18)
        painter.end()
        return QIcon(pixmap)

    def load_users(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, COALESCE(username, user_id), role, can_write FROM users")
        rows = cursor.fetchall()
        conn.close()
        
        self.users_list.clear()
        for uid, uname, role, can_write in rows:
            icon = self.create_user_icon(role, can_write)
            item = QListWidgetItem(icon, f"{uname}\n[{role.upper()}]")
            item.setData(Qt.UserRole, {
                "user_id": uid, "username": uname, 
                "role": role, "can_write": can_write
            })
            self.users_list.addItem(item)
            
        # Re-apply any active search filter
        self.filter_users()

    def filter_users(self):
        query = self.user_search_input.text().strip().lower()
        selected_filter = self.user_filter_combo.currentText().lower()

        for i in range(self.users_list.count()):
            item = self.users_list.item(i)
            data = item.data(Qt.UserRole)
            
            user_id = str(data.get("user_id", "")).lower()
            username = str(data.get("username", "")).lower()
            role = str(data.get("role", "")).lower()
            can_write = bool(data.get("can_write", True))

            write_str = "write allowed" if can_write else "write revoked"
            write_short_str = "allowed" if can_write else "revoked"

            # Check search match across User ID, Username, Role, and Write Permissions
            matches_query = (
                not query 
                or query in user_id 
                or query in username 
                or query in role 
                or query in write_str
                or query in write_short_str
            )

            # Check dropdown filter match
            matches_filter = True
            if selected_filter == "moderators":
                matches_filter = (role == "moderator")
            elif selected_filter == "regular users":
                matches_filter = (role == "user")
            elif selected_filter == "write allowed":
                matches_filter = can_write
            elif selected_filter == "write revoked":
                matches_filter = not can_write

            item.setHidden(not (matches_query and matches_filter))

    def load_files(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.id, l.title, l.item_type, l.is_public, l.user_id, l.url, COALESCE(u.username, l.user_id)
            FROM shared_links l
            LEFT JOIN users u ON l.user_id = u.user_id
        """)
        rows = cursor.fetchall()
        conn.close()
        
        self.files_list.clear()
        for lid, title, itype, is_pub, uid, url, uname in rows:
            icon = self.create_link_icon(itype, is_pub)
            privacy_label = "Public" if is_pub else "Private"
            item = QListWidgetItem(icon, f"{title}\nBy: {uname}\n({privacy_label})")
            item.setData(Qt.UserRole, {
                "id": lid, "title": title, "item_type": itype, 
                "is_public": is_pub, "user_id": uid, "username": uname, "url": url
            })
            self.files_list.addItem(item)
            
        # Re-apply any active search filter
        self.filter_files()

    def filter_files(self):
        query = self.file_search_input.text().strip().lower()
        selected_type = self.file_type_filter.currentText().lower()

        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            data = item.data(Qt.UserRole)
            
            title = str(data.get("title", "")).lower()
            username = str(data.get("username", "")).lower()
            user_id = str(data.get("user_id", "")).lower()
            item_type = str(data.get("item_type", "")).lower()

            # Check search match across Name, Username, User ID, and Item Type
            matches_query = (
                not query 
                or query in title 
                or query in username 
                or query in user_id 
                or query in item_type
            )
            
            # Check type filter
            matches_type = (selected_type == "all types" or selected_type == item_type)

            item.setHidden(not (matches_query and matches_type))

    def show_user_context_menu(self, pos):
        item = self.users_list.itemAt(pos)
        if not item:
            return
            
        data = item.data(Qt.UserRole)
        menu = QMenu(self)

        meter_action = QAction("Test Connection Quality...", self)
        meter_action.triggered.connect(lambda: self.show_connection_meter(data))
        menu.addAction(meter_action)

        menu.addSeparator()

        info_action = QAction("View Info & Permissions", self)
        info_action.triggered.connect(lambda: self.open_user_info(data))
        menu.addAction(info_action)
        
        mod_label = "Revoke Moderator" if data['role'] == 'moderator' else "Grant Moderator"
        mod_action = QAction(mod_label, self)
        mod_action.triggered.connect(lambda: self.toggle_user_role(data))
        menu.addAction(mod_action)
        
        write_label = "Revoke Write Access" if data['can_write'] else "Grant Write Access"
        write_action = QAction(write_label, self)
        write_action.triggered.connect(lambda: self.toggle_user_write(data))
        menu.addAction(write_action)
        
        menu.exec(self.users_list.mapToGlobal(pos))

    def show_connection_meter(self, user_data):
        current_endpoint = self.url_input.text().strip()
        dlg = ConnectionMeterDialog(user_data, target_url=current_endpoint, parent=self)
        dlg.exec()

    def open_user_info(self, user_data):
        dlg = UserInfoDialog(user_data, self)
        if dlg.exec():
            self.refresh_all_data()

    def toggle_user_role(self, data):
        new_role = 'user' if data['role'] == 'moderator' else 'moderator'
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (new_role, data['user_id']))
        conn.commit()
        conn.close()
        log_event(f"Toggled role for user {data['user_id']} to {new_role}")
        self.refresh_all_data()

    def toggle_user_write(self, data):
        new_write = 0 if data['can_write'] else 1
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET can_write = ? WHERE user_id = ?", (new_write, data['user_id']))
        conn.commit()
        conn.close()
        log_event(f"Toggled write permissions for user {data['user_id']} to {new_write}")
        self.refresh_all_data()

    def show_file_context_menu(self, pos):
        item = self.files_list.itemAt(pos)
        if not item:
            return
            
        data = item.data(Qt.UserRole)
        menu = QMenu(self)
        
        del_action = QAction("Delete Link", self)
        del_action.triggered.connect(lambda: self.delete_link(data['id']))
        menu.addAction(del_action)
        
        menu.exec(self.files_list.mapToGlobal(pos))

    def delete_link(self, link_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shared_links WHERE id = ?", (link_id,))
        conn.commit()
        conn.close()
        log_event(f"Deleted link ID: {link_id}")
        self.refresh_all_data()

    def closeEvent(self, event):
        self.stop_tunnel()
        if self.flask_thread:
            self.flask_thread.stop()
            self.flask_thread.quit()
        log_event("Server GUI application shutting down.")
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(MODERN_STYLE)
    gui = ServerGUI()
    gui.show()
    sys.exit(app.exec())