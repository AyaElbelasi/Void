import sys
import hashlib
import os
import time
import random
import math
import csv
import json
import shutil 
from datetime import datetime
import markdown

# PyQt Imports
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLineEdit,
                             QScrollArea, QLabel, QSplitter, QListWidget, QListWidgetItem, QFrame,
                             QDialog, QSlider, QCheckBox, QDialogButtonBox, 
                             QStackedWidget, QGridLayout, QComboBox, QGraphicsDropShadowEffect,
                             QMenu, QSizePolicy)
from PyQt6.QtCore import (Qt, QSize, pyqtSignal, QThread, QPoint, QPointF, QTimer, 
                          QPropertyAnimation, QEasingCurve, QEvent, QObject, QRect, QParallelAnimationGroup)
from PyQt6.QtGui import (QFont, QColor, QPalette, QPainter, QBrush, QPen, 
                         QRadialGradient, QCursor, QAction, QIcon, QFontMetrics)
from openpyxl import Workbook, load_workbook

# --- LANGCHAIN & AI IMPORTS ---
try:
    from langchain_community.document_loaders import CSVLoader
    from langchain_community.embeddings import HuggingFaceBgeEmbeddings
    from langchain_chroma import Chroma
    # CHANGED: Using LlamaCpp instead of ChatOpenAI
    from langchain_community.llms import LlamaCpp 
    AI_AVAILABLE = True
except ImportError:
    print("AI libraries not found. Run: pip install langchain-community langchain-chroma langchain-openai chromadb sentence-transformers llama-cpp-python")
    AI_AVAILABLE = False

# ==================== BACKEND SETUP ====================
vector_db = None
llm = None
if AI_AVAILABLE:
    print("--- Initializing AI Backend ---")
    try:
        db_path = "./chroma_db_aerospace_final" 
        csv_file_path = "final_dataset_no_scale.csv"
        if os.path.exists(db_path):
            print(f"Found existing database at {db_path}. Loading...")
            embeddings = HuggingFaceBgeEmbeddings(
                model_name="BAAI/bge-small-en-v1.5",
                model_kwargs={'device': 'cuda'}, 
                encode_kwargs={'normalize_embeddings': True}
            )
            vector_db = Chroma(
                persist_directory=db_path, 
                embedding_function=embeddings,
                collection_name="aerospace_csv_db"
            )
        else:
            embeddings = HuggingFaceBgeEmbeddings(
                model_name="BAAI/bge-small-en-v1.5",
                model_kwargs={'device': 'cuda'}, 
                encode_kwargs={'normalize_embeddings': True}
            )
            loader = CSVLoader(file_path=csv_file_path, encoding="utf-8")
            docs = loader.load()
            print("Creating Vector DB...")
            vector_db = Chroma.from_documents(
                documents=docs, 
                embedding=embeddings,
                collection_name="aerospace_csv_db",
                persist_directory=db_path
            )
        
        # --- CHANGED: Load Base Model AND Adapter ---
        print("Loading Local GGUF Model with Adapter...")
        llm = LlamaCpp(
            # 1. THE HEAVY BASE MODEL (e.g., Llama 3 8B)
            model_path="Meta-Llama-3-8B-Instruct.Q4_K_M.gguf", 
            
            # 2. YOUR TRAINED ADAPTER
            lora_path="my_lora_adapter.gguf", 
            
            n_gpu_layers=-1,       
            n_ctx=4096,           
            temperature=0.1,      # Low temp = Less creative, more strict
            verbose=True,
            f16_kv=True           
        )
        print("Backend Ready.")
    
    except Exception as e:
        print(f"CRITICAL BACKEND ERROR: {e}")
        print("Make sure both 'base_model.gguf' and 'my_lora_adapter.gguf' are in this folder.")
        print("The app will launch, but AI features will fail.")

# ==================== THEME ENGINE ====================
class ThemeManager:
    def __init__(self):
        self.is_dark = True
        self.font_size = 10
        self.font_family = "Segoe UI"
        
        self.dark_palette = {
            "BG_MAIN": "#0b0d1a",
            "BG_SIDEBAR": "#10132a",
            "BG_CARD": "#161a3a",
            "ACCENT_PRIMARY": "#5b5fd9",
            "ACCENT_HOVER": "#7b80ff",
            "TEXT_MAIN": "#f4f5ff",
            "TEXT_SUB": "#b4b7e5",
            "TEXT_SIDEBAR": "#d6d8ff",
            "INPUT_BG": "#0f1230",       
            "BORDER": "none",         
            "SCROLL_HANDLE": "#5b5fd9",
            "SCROLL_BG": "#10132a",
            "ORB_GRADIENT": "stop:0 #9aa0ff, stop:0.4 #5b5fd9, stop:0.75 #161a3a, stop:1 transparent"
        }
        
        self.light_palette = {
            "BG_MAIN": "#eef0f4",        
            "BG_SIDEBAR": "#ffffff",     
            "BG_CARD": "#f8f9fc",        
            "ACCENT_PRIMARY": "#4f54d1", 
            "ACCENT_HOVER": "#3e42a3",
            "TEXT_MAIN": "#0f172a",      
            "TEXT_SUB": "#475569",
            "TEXT_SIDEBAR": "#0f172a",
            "INPUT_BG": "#f8f9fc",       
            "BORDER": "none",
            "SCROLL_HANDLE": "#9aa0ff",
            "SCROLL_BG": "#e4e7ee",
            "ORB_GRADIENT": "stop:0 #cfd2ff, stop:0.4 #7b80ff, stop:0.75 #4f54d1, stop:1 transparent"
        }

    def get(self, key):
        palette = self.dark_palette if self.is_dark else self.light_palette
        return palette.get(key, "#000000")

    def toggle_theme(self, is_dark):
        self.is_dark = is_dark

    def set_font_size(self, size):
        self.font_size = size

theme = ThemeManager()

# ==================== HELPERS ====================
def adjust_input_height(line_edit, padding=24, min_height=44):
    """Calculates necessary height for input based on font size to prevent clipping."""
    font = QFont(theme.font_family, theme.font_size)
    line_edit.setFont(font)
    fm = QFontMetrics(font)
    text_height = fm.height()
    new_height = max(min_height, text_height + padding)
    line_edit.setFixedHeight(new_height)
    line_edit.setTextMargins(0, 0, 0, 1)

# ==================== VISUAL EFFECTS ====================
class StarfieldWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stars = []
        self.current_offset = QPointF(0, 0)
        
        for _ in range(200): 
            self.stars.append({
                'x': random.random(), 
                'y': random.random(),
                'size': random.uniform(0.5, 2.5), 
                'speed': random.uniform(0.05, 0.20), 
                'brightness': random.randint(40, 180) 
            })
            
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_parallax)
        self.timer.start(20) 

    def update_parallax(self):
        global_mouse = QCursor.pos()
        local_mouse = self.mapFromGlobal(global_mouse)
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        target_x = (local_mouse.x() - center_x) 
        target_y = (local_mouse.y() - center_y)
        
        self.current_offset += (QPointF(target_x, target_y) - self.current_offset) * 0.05
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(theme.get("BG_MAIN")))
        
        w = self.width()
        h = self.height()
        painter.setPen(Qt.PenStyle.NoPen)
        
        if theme.is_dark:
            base_color = QColor(255, 255, 255)
        else:
            base_color = QColor(theme.get("ACCENT_PRIMARY"))
        
        for star in self.stars:
            x = ((star['x'] * w) - self.current_offset.x() * star['speed']) % (w+50) - 25
            y = ((star['y'] * h) - self.current_offset.y() * star['speed']) % (h+50) - 25
            
            color = QColor(base_color)
            color.setAlpha(star['brightness'])
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x, y), star['size'], star['size'])

class VoidOrb(QFrame):
    def __init__(self, size=100):
        super().__init__()
        self.setFixedSize(size, size)
        self._phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(20)

    def animate(self):
        self._phase += 0.05
        self.update() 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        breath = (math.sin(self._phase) + 1) / 2
        scale = 0.85 + (breath * 0.15)
        radius = (self.width() / 2) * scale
        center = QPointF(self.rect().center())
        
        gradient = QRadialGradient(center, radius)
        c1 = QColor(theme.get("ACCENT_HOVER"))
        c2 = QColor(theme.get("ACCENT_PRIMARY")) 
        c3 = QColor(theme.get("BG_MAIN")) 
        c1.setAlpha(240); c2.setAlpha(180); c3.setAlpha(0)
        
        gradient.setColorAt(0.0, c1)
        gradient.setColorAt(0.5, c2)
        gradient.setColorAt(1.0, c3)
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius, radius)

# ==================== CUSTOM INPUTS ====================
class PasswordEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.setFixedHeight(50)
        
        self.toggle_btn = QPushButton(self)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus) 
        self.toggle_btn.setStyleSheet("background: transparent; border: none;")
        self.toggle_btn.clicked.connect(self.toggle_visibility)
        self.toggle_btn.installEventFilter(self)
        
        self.is_visible = False

    def resizeEvent(self, event):
        self.toggle_btn.move(self.width() - 35, (self.height() - 30) // 2)
        super().resizeEvent(event)

    def eventFilter(self, obj, event):
        if obj == self.toggle_btn and event.type() == QEvent.Type.Paint:
            painter = QPainter(self.toggle_btn)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            c = QColor("#b4b7e5")
            painter.setPen(QPen(c, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            w, h = self.toggle_btn.width(), self.toggle_btn.height()
            painter.drawEllipse(QPointF(w/2, h/2), 10, 6)
            painter.setBrush(QBrush(c))
            painter.drawEllipse(QPointF(w/2, h/2), 3, 3)
        
            if self.is_visible:
                painter.setPen(QPen(c, 2))
                painter.drawLine(int(w/2 - 8), int(h/2 - 8), int(w/2 + 8), int(h/2 + 8))
            
            return True
        return super().eventFilter(obj, event)

    def toggle_visibility(self):
        self.is_visible = not self.is_visible
        if self.is_visible: self.setEchoMode(QLineEdit.EchoMode.Normal)
        else: self.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_btn.update()

# ==================== DATA & HISTORY MANAGER ====================
class HistoryManager:
    def __init__(self, filename="chat_history.json"):
        self.filename = filename

    def load_all(self):
        if not os.path.exists(self.filename): return {}
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}

    def save_all(self, data):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except: pass

class AuthManager:
    def __init__(self, db_file="users.xlsx"):
        self.db_file = db_file
        self.users = {}
        self._init_db()
        self._load_users()

    def _init_db(self):
        if not os.path.exists(self.db_file):
            wb = Workbook()
            ws = wb.active; ws.title = "users"
            ws.append(["username", "password_hash"])
            wb.save(self.db_file)

    def _load_users(self):
        wb = load_workbook(self.db_file)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] and row[1]: self.users[row[0]] = row[1]

    def _save_user(self, username, password_hash):
        wb = load_workbook(self.db_file)
        ws = wb.active
        ws.append([username, password_hash])
        wb.save(self.db_file)

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def register(self, username, password):
        if username in self.users: return False, "Username exists"
        if len(username) < 3: return False, "Min 3 chars user"
        if len(password) < 6: return False, "Min 6 chars pass"
        
        hashed = self.hash_password(password)
        self.users[username] = hashed
        self._save_user(username, hashed)
        return True, "Success"

    def login(self, username, password):
        if username not in self.users: return False, "User not found"
        if self.users[username] == self.hash_password(password): return True, "Success"
        return False, "Wrong password"

# ==================== UI WIDGETS ====================
class ThemeSlider(QFrame):
    toggled = pyqtSignal(bool)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark = True
        self.setFixedSize(70, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border: none;")

    def mousePressEvent(self, event):
        self.is_dark = not self.is_dark
        self.toggled.emit(self.is_dark)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bg = QColor("#080912") if self.is_dark else QColor("#e5e7eb")
        
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 17, 17)
        
        handle_x = 40 if self.is_dark else 6 
        painter.setBrush(QColor(theme.get("ACCENT_PRIMARY")))
        painter.drawEllipse(handle_x, 5, 24, 24)
        
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 12))
        painter.drawText(QRect(handle_x, 5, 24, 24), Qt.AlignmentFlag.AlignCenter, "🌙" if self.is_dark else "☀️")

class GlowButton(QPushButton):
    def __init__(self, text, is_primary=True):
        super().__init__(text)
        self.is_primary = is_primary
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(45)
        self.update_style()
        
        if is_primary:
            self.shadow = QGraphicsDropShadowEffect(self)
            self.shadow.setBlurRadius(0) 
            self.shadow.setColor(QColor(theme.get("ACCENT_HOVER")))
            self.shadow.setOffset(0, 0)
            self.setGraphicsEffect(self.shadow)
            
            self.anim = QPropertyAnimation(self.shadow, b"blurRadius")
            self.anim.setDuration(150)

    def enterEvent(self, e):
        if self.is_primary: self.anim.setStartValue(0); self.anim.setEndValue(20); self.anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self.is_primary: self.anim.setStartValue(20); self.anim.setEndValue(0); self.anim.start()
        super().leaveEvent(e)

    def update_style(self):
        self.setFont(QFont(theme.font_family, theme.font_size, QFont.Weight.Bold))
        bg = theme.get("ACCENT_PRIMARY") if self.is_primary else "transparent"
        fg = "#ffffff" if self.is_primary else theme.get("TEXT_SUB")
        self.setStyleSheet(f"QPushButton {{ background-color: {bg}; color: {fg}; border-radius: 22px; padding: 0 22px; border: none; }} QPushButton:hover {{ background-color: {theme.get('ACCENT_HOVER') if self.is_primary else theme.get('BG_CARD')}; }}")

class SuggestionCard(QFrame):
    clicked = pyqtSignal(str)
    def __init__(self, icon, title, prompt):
        super().__init__()
        self.prompt = prompt
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(220, 140)
        self._pressed = False
        
        layout = QVBoxLayout(self)
        layout.addStretch()
        self.icon_label = QLabel(icon)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label); layout.addWidget(self.title_label); layout.addStretch()
        
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(0)
        self.shadow.setColor(QColor(theme.get("ACCENT_PRIMARY")))
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)
        self.anim = QPropertyAnimation(self.shadow, b"blurRadius")
        self.anim.setDuration(150)
        self.update_style()

    def enterEvent(self, e): self.anim.setStartValue(0); self.anim.setEndValue(25); self.anim.start(); super().enterEvent(e)
    def leaveEvent(self, e): self.anim.setStartValue(25); self.anim.setEndValue(0); self.anim.start(); super().leaveEvent(e)

    def update_style(self):
        self.setStyleSheet(f"QFrame {{ background-color: {theme.get('BG_CARD')}; border-radius: 16px; }} QFrame:hover {{ background-color: {theme.get('BG_SIDEBAR')}; }}")
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self.icon_label.setFont(QFont("Segoe UI Emoji", 24))
        self.title_label.setFont(QFont(theme.font_family, theme.font_size, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {theme.get('TEXT_MAIN')}; background: transparent; border: none;")

    def mousePressEvent(self, e): 
        if e.button() == Qt.MouseButton.LeftButton: self._pressed = True
    def mouseReleaseEvent(self, e): 
        if e.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            if self.rect().contains(e.position().toPoint()): self.clicked.emit(self.prompt)

# ==================== UPDATED CHAT BUBBLE (REALTIME MARKDOWN) ====================
class ChatBubble(QFrame):
    typing_finished = pyqtSignal()

    def __init__(self, text, is_user=True, animate=True):
        super().__init__()
        self.full_text = text
        self.is_user = is_user
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 12, 15, 12)
        
        self.lbl = QLabel("")
        self.lbl.setWordWrap(True)
        self.lbl.setTextFormat(Qt.TextFormat.RichText) 
        self.lbl.setOpenExternalLinks(True)
        self.lbl.setStyleSheet("background: transparent; border: none;")
        
        if not is_user:
            self.name_lbl = QLabel("VOID AI")
            self.name_lbl.setStyleSheet("background: transparent; border: none;")
            self.layout.addWidget(self.name_lbl)
            
        self.layout.addWidget(self.lbl)
        self.update_style()
        
        if not is_user and animate:
            self.start_typewriter()
        else:
            self.lbl.setText(self.render_to_html(text))

    def render_to_html(self, text):
        """Converts Markdown to HTML with inline CSS for theme colors."""
        try:
            html_content = markdown.markdown(text)
            text_color = "white" if self.is_user else theme.get("TEXT_MAIN")
            link_color = "#ffffff" if self.is_user else theme.get("ACCENT_HOVER")
            
            styled_html = f"""
            <html>
            <head>
            <style>
                body {{ 
                    font-family: '{theme.font_family}';
                    font-size: {theme.font_size}pt; 
                    color: {text_color};
                }}
                p {{ margin-bottom: 5px; }}
                code {{ 
                    background-color: {theme.get('BG_SIDEBAR')};
                    padding: 2px 4px; 
                    border-radius: 4px;
                }}
                a {{ color: {link_color}; font-weight: bold; text-decoration: none; }}
            </style>
            </head>
            <body>
            {html_content}
            </body>
            </html>
            """
            
            return styled_html
        except Exception as e:
            return text

    def start_typewriter(self):
        self.current_idx = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.type_chunk) 
        self.timer.start(10) # Fast updates

    def type_chunk(self):
        chunk_size = 2 
        if self.current_idx < len(self.full_text):
            self.current_idx += chunk_size
            partial_text = self.full_text[:self.current_idx]
            formatted_partial = self.render_to_html(partial_text)
            self.lbl.setText(formatted_partial) 
        else:
            self.timer.stop()
            self.lbl.setText(self.render_to_html(self.full_text))
            self.typing_finished.emit()

    def skip_typing(self):
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
            self.lbl.setText(self.render_to_html(self.full_text))
            self.typing_finished.emit()

    def update_style(self):
        if self.is_user:
            self.setStyleSheet(f"QFrame {{ background-color: {theme.get('ACCENT_PRIMARY')}; border-radius: 18px; border-bottom-right-radius: 4px; border: none; }}")
            self.lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            self.setStyleSheet(f"QFrame {{ background-color: {theme.get('BG_CARD')}; border: none; border-radius: 18px; border-bottom-left-radius: 4px; }}")
            self.lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            if hasattr(self, 'name_lbl'):
                self.name_lbl.setFont(QFont(theme.font_family, theme.font_size - 2, QFont.Weight.Bold))
                self.name_lbl.setStyleSheet(f"color: {theme.get('ACCENT_HOVER')}; margin-bottom: 4px; border: none;")
        
        current_text = self.full_text
        self.lbl.setText(self.render_to_html(current_text))

class ThinkingBubble(QFrame):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 12, 15, 12)
        self.name_lbl = QLabel("VOID AI")
        self.name_lbl.setStyleSheet("background: transparent; border: none;")
        self.layout.addWidget(self.name_lbl)
        self.lbl = QLabel("Thinking")
        self.lbl.setStyleSheet("background: transparent; border: none;")
        self.layout.addWidget(self.lbl)
        self.update_style()
        self.dots = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_dots)
        self.timer.start(500)

    def animate_dots(self):
        self.dots = (self.dots + 1) % 4
        self.lbl.setText("Thinking" + "." * self.dots)

    def update_style(self):
        self.lbl.setFont(QFont(theme.font_family, theme.font_size))
        self.name_lbl.setFont(QFont(theme.font_family, theme.font_size - 2, QFont.Weight.Bold))
        self.name_lbl.setStyleSheet(f"color: {theme.get('ACCENT_HOVER')}; margin-bottom: 4px; border: none;")
        self.setStyleSheet(f"QFrame {{ background-color: {theme.get('BG_CARD')}; color: {theme.get('TEXT_MAIN')}; border: none; border-radius: 18px; border-bottom-left-radius: 4px; }}")

# ==================== UPDATED MEMORY-AWARE WORKER ====================
# ==================== UPDATED MEMORY-AWARE WORKER ====================
class ModelWorker(QThread):
    finished = pyqtSignal(str)
    def __init__(self, prompt, conversation_history=None):
        super().__init__()
        self.prompt = prompt
        self.conversation_history = conversation_history or []

    def run(self):
        try:
            if not vector_db or not llm:
                time.sleep(1.5)
                self.finished.emit("Error: AI backend not ready.")
                return
            
            # Retrieve relevant context
            retriever = vector_db.as_retriever(search_kwargs={"k": 2})
            retrieved_docs = retriever.invoke(self.prompt)
            context_text = "\n\n".join([doc.page_content for doc in retrieved_docs])

            # Build history
            history_text = ""
            for role, msg in self.conversation_history[-6:]:
                if role == "user":
                    history_text += f"Student: {msg}\n"
                else:
                    history_text += f"Void: {msg}\n"
            
            # --- FINAL "STRICT TA" PROMPT ---
            full_prompt = f"""You are Void, an Aerospace Engineering idea generator. 

**CORE RULES:**

1. **GREETINGS ONLY:** If user says "Hi", "Hello", "Hey":
   - Reply: "Systems online! What engineering project are you working on?"
   - DO NOT suggest topics or use database unless asked a question

2. **STRICT SCOPE:** Only answer Aerospace Engineering questions
   - If question is off-topic (food, life advice, etc.):
   - Reply: "My guidance systems are locked to Aerospace Engineering only."
   - Do NOT answer off-topic questions

3. **USE PROVIDED DATA ONLY:**
   - Check CLASS_NOTES below
   - If answer is in notes: explain clearly and concisely
   - If answer is NOT in notes: say "I don't have that data in my notes."
   - NEVER invent information
   - If unsure, say "I don't have that data in my notes."

4. **FORMAT:**
   - Speak naturally 
   - Be casual but technical
   - Use **Bold** for key terms and headers. Use bullet points for lists when helpful.

---
CLASS_NOTES:
{context_text}

CHAT HISTORY:
{history_text}

STUDENT: {self.prompt}

VOID:"""
            
            # Generate response
            response = llm.invoke(full_prompt)
            raw_text = response.content if hasattr(response, "content") else str(response)
            
            # --- AGGRESSIVE CLEANER (Removes "VOID RESPONDS", etc.) ---
            clean_text = raw_text.strip()
            
            # 1. Kill entire first line if it looks like a header
            lines = clean_text.split('\n')
            if lines:
                # Normalize line to uppercase, remove stars/hashes/colons
                header_check = lines[0].upper().replace("*", "").replace("#", "").replace(":", "").strip()
                forbidden_headers = [
                    "RESPONSE", "ANSWER", "VOID", "VOID RESPONDS", 
                    "VOID RESPONSE", "VOID AI", "SYSTEM", "ASSISTANT"
                ]
                
                if header_check in forbidden_headers:
                    clean_text = "\n".join(lines[1:]).strip()
            
            # 2. Kill inline prefixes (e.g. "Void: Hello")
            prefixes = [
                "Response:", "Answer:", "Void:", "Void Responds:", 
                "Void Response:", "Assistant:", "Void AI:"
            ]
            for _ in range(2): 
                for p in prefixes:
                    if clean_text.lower().startswith(p.lower()):
                        clean_text = clean_text[len(p):].strip()
            
            # 3. Remove leading symbols
            if clean_text.startswith(":") or clean_text.startswith("-"):
                clean_text = clean_text[1:].strip()

            self.finished.emit(clean_text)

        except Exception as e:
            self.finished.emit(f"AI Error: {str(e)}")

# ==================== SETTINGS & MAIN WINDOW ====================
class SettingsDialog(QDialog):
    settings_changed = pyqtSignal()
    logout_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(400, 320) 
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(20, 20, 20, 20)
        
        self.container = QWidget()
        self.outer_layout.addWidget(self.container)
        
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20); self.shadow.setYOffset(5); self.shadow.setColor(QColor(0, 0, 0, 80))
        self.container.setGraphicsEffect(self.shadow)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(0,0,0,0)
        
        title_bar = QWidget(); title_bar.setFixedHeight(60)
        tb_layout = QHBoxLayout(title_bar); tb_layout.setContentsMargins(30,10,20,10)
        self.lbl_title = QLabel("Settings"); self.lbl_title.setFont(QFont(theme.font_family, theme.font_size + 10, QFont.Weight.Bold))
        
        self.btn_x = QPushButton("✕"); self.btn_x.setFlat(True); self.btn_x.setCursor(Qt.CursorShape.PointingHandCursor); self.btn_x.clicked.connect(self.reject)
        self.btn_x.setStyleSheet(f"color: {theme.get('TEXT_MAIN')}; font-size: 20px; font-weight: bold; border: none;")
        tb_layout.addWidget(self.lbl_title); tb_layout.addStretch(); tb_layout.addWidget(self.btn_x)
        layout.addWidget(title_bar)
        
        content = QWidget(); c_layout = QVBoxLayout(content); c_layout.setContentsMargins(40,20,40,40); c_layout.setSpacing(30)
        
        font_lbl = QLabel("Font Size")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(8); self.slider.setMaximum(18); self.slider.setValue(theme.font_size)
        self.slider.valueChanged.connect(self.on_font_change)
        
        toggle_row = QHBoxLayout()
        toggle_lbl = QLabel("Theme")
        self.theme_toggle = ThemeSlider()
        self.theme_toggle.is_dark = theme.is_dark 
        self.theme_toggle.toggled.connect(self.on_theme_change)
        toggle_row.addWidget(toggle_lbl); toggle_row.addStretch(); toggle_row.addWidget(self.theme_toggle)
        
        c_layout.addWidget(font_lbl); c_layout.addWidget(self.slider)
        c_layout.addLayout(toggle_row)
        c_layout.addStretch()
        
        self.btn_logout = GlowButton("Log Out", is_primary=False)
        self.btn_logout.setStyleSheet(f"color: #ef4444; border: 1px solid #ef4444; border-radius: 22px; background: transparent;")
        self.btn_logout.clicked.connect(self.request_logout)
        c_layout.addWidget(self.btn_logout)
        
        layout.addWidget(content)
        
        self.title_bar_widget = title_bar
        self.font_lbl = font_lbl; self.toggle_lbl = toggle_lbl
        
        self.update_internal_styles()
        self.update_style()
        
    def request_logout(self):
        self.logout_requested.emit()
        self.accept()

    def mousePressEvent(self, e): 
        if e.button() == Qt.MouseButton.LeftButton: self.drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft(); e.accept()
    def mouseMoveEvent(self, e): 
        if e.buttons() == Qt.MouseButton.LeftButton: self.move(e.globalPosition().toPoint() - self.drag_pos); e.accept()
    def on_font_change(self, v): theme.set_font_size(v); self.settings_changed.emit(); self.update_internal_styles()
    def on_theme_change(self, d): theme.toggle_theme(d); self.settings_changed.emit(); self.update_internal_styles(); self.update_style()
    def update_style(self):
        self.setStyleSheet("QDialog { background: transparent; }")
        self.container.setStyleSheet(f"QWidget {{ background-color: {theme.get('BG_CARD')}; border: {theme.get('BORDER')}; border-radius: 15px; }}")
    
    def update_internal_styles(self):
        self.lbl_title.setStyleSheet(f"color: {theme.get('TEXT_MAIN')}; border: none;")
        self.btn_x.setStyleSheet(f"color: {theme.get('TEXT_MAIN')}; font-size: 20px; font-weight: bold; border: none;")
        self.title_bar_widget.setStyleSheet(f"border-bottom: none;")
        self.font_lbl.setStyleSheet(f"color: {theme.get('TEXT_MAIN')}; font-size: {theme.font_size + 2}pt; border: none;")
        
        self.toggle_lbl.setStyleSheet(f"color: {theme.get('TEXT_MAIN')}; font-size: {theme.font_size + 2}pt; border: none;")
        
        slider_bg = "#e5e7eb" if not theme.is_dark else theme.get("INPUT_BG")
        handle_bg = theme.get("ACCENT_PRIMARY")
        self.slider.setStyleSheet(f"""
            QSlider {{ min-height: 30px; }}
            QSlider::groove:horizontal {{
                background: {slider_bg}; height: 8px;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {handle_bg}; width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}
        """)
        for lbl in [self.lbl_title, self.font_lbl, self.toggle_lbl]:
            lbl.setWordWrap(False)
            lbl.setMinimumHeight(lbl.fontMetrics().height() + 10)

class MainWindow(QMainWindow):
    logout_signal = pyqtSignal()
    def __init__(self, username="User"):
        super().__init__()
        self.username = username
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(1280, 800)
        
        self.history_manager = HistoryManager()
        self.conversations = {} 
        self.is_sidebar_open = True
        
        self.dragging = False; self.drag_pos = None
        self.current_chat_id = None; self.thinking_bubble = None
        self.worker = None; self.current_ai_bubble = None; self.is_typing = False
        self.starfield = StarfieldWidget(self)
        self.setCentralWidget(self.starfield)
        
        self.main_layout = QHBoxLayout(self.starfield); self.main_layout.setContentsMargins(0,0,0,0); self.main_layout.setSpacing(0)
        
        # Sidebar with QScrollArea Mask
        self.sidebar_container = QScrollArea()
        self.sidebar_container.setMaximumWidth(280) 
        self.sidebar_container.setMinimumWidth(0)
        self.sidebar_container.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_container.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_container.setWidgetResizable(True)
        self.sidebar_container.setFrameShape(QFrame.Shape.NoFrame)
        
        # Inner Sidebar
        self.sidebar = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar); self.sidebar_layout.setContentsMargins(20, 20, 20, 20); self.sidebar_layout.setSpacing(15)
        self.sidebar_container.setWidget(self.sidebar)
        
        self.btn_new = GlowButton("+ New Project")
        self.btn_new.clicked.connect(self.show_dashboard)
        
        self.lbl_history = QLabel("RECENT ACTIVITY")
        self.lbl_history.setFont(QFont(theme.font_family, 10, QFont.Weight.Bold))
        
        self.chat_list = QListWidget()
        self.chat_list.itemClicked.connect(self.load_chat)
        self.chat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self.show_context_menu)
        
        self.profile_frame = QFrame(); self.profile_frame.setMinimumHeight(80)
        p_layout = QHBoxLayout(self.profile_frame); p_layout.setContentsMargins(15, 10, 15, 10)
        self.avatar = QLabel(self.username[0].upper()); self.avatar.setFixedSize(40, 40); self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_info = QVBoxLayout(); p_info.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft); p_info.setSpacing(4)
        self.p_name = QLabel(self.username); self.p_name.setFont(QFont(theme.font_family, 12, QFont.Weight.Bold)); self.p_name.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.btn_settings = QPushButton("⚙ Settings"); self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor); self.btn_settings.clicked.connect(self.open_settings)
        p_info.addWidget(self.p_name); p_info.addWidget(self.btn_settings)
        p_layout.addWidget(self.avatar); p_layout.addLayout(p_info); p_layout.addStretch()
        
        self.sidebar_layout.addWidget(self.btn_new); self.sidebar_layout.addWidget(self.lbl_history); self.sidebar_layout.addWidget(self.chat_list)
        self.sidebar_layout.addWidget(self.profile_frame)
        
        self.content_wrapper = QWidget(); cw_layout = QVBoxLayout(self.content_wrapper); cw_layout.setContentsMargins(0,0,0,0); cw_layout.setSpacing(0)
        
        self.title_bar = QWidget(); self.title_bar.setFixedHeight(60)
        tb_layout = QHBoxLayout(self.title_bar); tb_layout.setContentsMargins(20, 0, 20, 0); tb_layout.setSpacing(10)
        self.btn_menu = QPushButton("☰"); self.btn_menu.setFixedSize(40, 40); self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor); self.btn_menu.clicked.connect(self.toggle_sidebar)
        self.brand_lbl = QLabel("VOID"); self.brand_lbl.setFont(QFont(theme.font_family, 22, QFont.Weight.Bold)); self.brand_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.win_btns = []
        for icon, func in [("🗕", self.showMinimized), ("🗖", self.toggle_max), ("✕", self.close)]:
            btn = QPushButton(icon); btn.setFixedSize(45, 45); btn.clicked.connect(func); self.win_btns.append(btn)
        tb_layout.addWidget(self.btn_menu); tb_layout.addSpacing(112); tb_layout.addStretch(); tb_layout.addWidget(self.brand_lbl); tb_layout.addStretch()
        for btn in self.win_btns: tb_layout.addWidget(btn)
        cw_layout.addWidget(self.title_bar)
        
        self.stack = QStackedWidget()
        self.dashboard = self.create_dashboard(); self.chat_view = self.create_chat_view()
        self.stack.addWidget(self.dashboard); self.stack.addWidget(self.chat_view)
        cw_layout.addWidget(self.stack)
        
        self.main_layout.addWidget(self.sidebar_container); self.main_layout.addWidget(self.content_wrapper)
        
        self.sidebar_anim = QPropertyAnimation(self.sidebar_container, b"maximumWidth")
        self.sidebar_anim.setDuration(300)
        self.sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        self.apply_theme() 
        self.load_history_from_disk()

    def resizeEvent(self, event):
        self.sidebar.setFixedHeight(self.height())
        super().resizeEvent(event)

    def show_context_menu(self, pos):
        item = self.chat_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            menu.setStyleSheet(f"""
                QMenu {{ background-color: {theme.get('BG_CARD')}; color: {theme.get('TEXT_MAIN')}; border: 1px solid {theme.get('ACCENT_PRIMARY')}; }}
                QMenu::item {{ padding: 8px 20px; }}
                QMenu::item:selected {{ background-color: {theme.get('ACCENT_HOVER')}; color: white; }}
            """)
            delete_action = QAction("Delete Chat", self)
            delete_action.triggered.connect(lambda: self.delete_chat(item))
            menu.addAction(delete_action)
            menu.exec(self.chat_list.mapToGlobal(pos))

    def delete_chat(self, item):
        chat_id = item.data(Qt.ItemDataRole.UserRole)
        self.chat_list.takeItem(self.chat_list.row(item))
        if chat_id in self.conversations:
            del self.conversations[chat_id]
        self.save_history_to_disk()
        if self.current_chat_id == chat_id:
            self.show_dashboard()

    def load_history_from_disk(self):
        full_data = self.history_manager.load_all()
        user_data = full_data.get(self.username, {})
        self.conversations = user_data
        for chat_id, chat_data in self.conversations.items():
            chat_name = chat_data.get("name", "New Chat")
            try:
                date_obj = datetime.strptime(chat_id, "%Y-%m-%d %H:%M:%S")
                short_time = date_obj.strftime("%m-%d %H:%M")
            except: short_time = chat_id
            display_text = f"{chat_name}\n{short_time}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, chat_id)
            self.chat_list.insertItem(0, item)

    def save_history_to_disk(self):
        full_data = self.history_manager.load_all()
        full_data[self.username] = self.conversations
        self.history_manager.save_all(full_data)

    def toggle_sidebar(self):
        width = self.sidebar_container.width()
        target = 0 if width > 0 else 280
        
        self.sidebar_anim.setStartValue(width)
        self.sidebar_anim.setEndValue(target)
        self.sidebar_anim.start()

    def create_dashboard(self):
        w = QWidget(); self.dash_layout = QVBoxLayout(w); self.dash_layout.setAlignment(Qt.AlignmentFlag.AlignCenter); self.dash_layout.setSpacing(30)
        self.greet_lbl = QLabel(f"Hello, {self.username}"); self.greet_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.orb = VoidOrb(120)
        self.sub_lbl = QLabel("What are we engineering today?"); self.sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_container = QFrame(); input_container.setFixedWidth(600); ic_layout = QHBoxLayout(input_container); ic_layout.setContentsMargins(10,10,10,10)
        self.dash_input = QLineEdit(); self.dash_input.setPlaceholderText("Type a prompt to start immediately..."); self.dash_input.setFixedHeight(50)
        self.dash_input.returnPressed.connect(lambda: self.start_chat_from_text(self.dash_input.text()))
        
        btn_go = QPushButton("➤"); btn_go.setFixedSize(50, 50); btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_go.clicked.connect(lambda: self.start_chat_from_text(self.dash_input.text()))
        ic_layout.addWidget(self.dash_input); ic_layout.addWidget(btn_go)
        self.dash_input_ref = input_container; self.dash_input_field = self.dash_input; self.dash_go_btn = btn_go
        
        grid_w = QWidget(); self.grid_layout = QGridLayout(grid_w); self.grid_layout.setSpacing(20)
        self.suggestion_cards = []
        suggestions = [("🚁", "Drone PID", "Help me tune the PID controller for a quadcopter"), ("🚀", "Rocket Staging", "Calculate delta-v for a two-stage rocket"), ("✈️", "Airfoil CFD", "Analyze lift properties of NACA 2412"), ("🛰️", "Orbit Calc", "Design a LEO orbit power budget")]
        for i, (icon, title, prompt) in enumerate(suggestions):
            card = SuggestionCard(icon, title, prompt); card.clicked.connect(self.start_chat_from_text)
            self.suggestion_cards.append(card); self.grid_layout.addWidget(card, i // 2, i % 2)
        
        self.dash_layout.addStretch(); self.dash_layout.addWidget(self.orb, 0, Qt.AlignmentFlag.AlignCenter)
        self.dash_layout.addWidget(self.greet_lbl); self.dash_layout.addWidget(self.sub_lbl); self.dash_layout.addSpacing(10)
        self.dash_layout.addWidget(grid_w, 0, Qt.AlignmentFlag.AlignCenter); self.dash_layout.addSpacing(20)
        self.dash_layout.addWidget(input_container, 0, Qt.AlignmentFlag.AlignCenter); self.dash_layout.addStretch()
        return w

    def create_chat_view(self):
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(40, 20, 40, 20)
        orb_container = QWidget(); orb_layout = QHBoxLayout(orb_container); self.chat_orb = VoidOrb(60)
        orb_layout.addStretch(); orb_layout.addWidget(self.chat_orb); orb_layout.addStretch(); layout.addWidget(orb_container)
        
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.chat_container = QWidget(); self.chat_layout = QVBoxLayout(self.chat_container); self.chat_layout.addStretch()
        self.scroll.setWidget(self.chat_container)
        
        input_frame = QFrame(); input_frame.setFixedHeight(80); il = QHBoxLayout(input_frame); il.setContentsMargins(10,10,10,10)
        
        self.chat_input = QLineEdit(); self.chat_input.setPlaceholderText("Ask follow up..."); self.chat_input.setFixedHeight(50)
        self.chat_input.returnPressed.connect(self.send_message)
        self.btn_send = GlowButton("➤"); self.btn_send.setFixedSize(50, 50); self.btn_send.clicked.connect(self.send_message)
        il.addWidget(self.chat_input); il.addWidget(self.btn_send)
        
        self.warning_lbl = QLabel("Void is an AI made by students. Double-check results."); self.warning_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.scroll); layout.addWidget(input_frame); layout.addWidget(self.warning_lbl)
        return w

    def show_dashboard(self):
        self.stack.setCurrentIndex(0); self.current_chat_id = None; self.dash_input.clear()

    def start_chat_from_text(self, text):
        text = text.strip()
        if not text: return
        self.start_chat_logic(text)

    def send_message(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate(); self.worker = None
            if self.thinking_bubble:
                p = self.thinking_bubble.parentWidget(); 
                if p: p.deleteLater()
                self.thinking_bubble = None
            self.btn_send.setText("➤"); self.chat_input.setDisabled(False); self.chat_input.setFocus(); self.is_typing = False
            return
        if self.is_typing and self.current_ai_bubble:
            self.current_ai_bubble.skip_typing(); return
        
        text = self.chat_input.text().strip()
        if not text: return
        self.start_chat_logic(text)

    # --- UPDATED LOGIC TO PASS HISTORY ---
    def start_chat_logic(self, text):
        if not self.current_chat_id:
            now = datetime.now()
            timestamp_id = now.strftime("%Y-%m-%d %H:%M:%S")
            short_time = now.strftime("%m-%d %H:%M")
            chat_name = (text[:20] + '...') if len(text) > 20 else text
            self.current_chat_id = timestamp_id
            self.conversations[self.current_chat_id] = {"name": chat_name, "msgs": []}
            display_text = f"{chat_name}\n{short_time}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, self.current_chat_id)
            self.chat_list.insertItem(0, item)
            self.stack.setCurrentIndex(1)
            self.clear_chat_area()
        
        # Add user message to UI
        self.add_bubble(text, True, animate=True)
        # Add to history
        self.conversations[self.current_chat_id]["msgs"].append(("user", text))
        self.save_history_to_disk()
        
        # Reset inputs
        self.chat_input.clear(); self.dash_input.clear(); self.chat_input.setDisabled(True)
        self.btn_send.setText("■")
        
        # Add thinking indicator
        self.thinking_bubble = ThinkingBubble()
        row = QWidget(); row_layout = QHBoxLayout(row); row_layout.setContentsMargins(0, 5, 0, 5)
        self.thinking_bubble.setMaximumWidth(600); row_layout.addWidget(self.thinking_bubble); row_layout.addStretch()
        self.chat_layout.insertWidget(self.chat_layout.count()-1, row)
        self.scroll_to_bottom()
        
        # --- PASS HISTORY TO WORKER HERE ---
        conversation_history = self.conversations[self.current_chat_id]["msgs"]
        self.worker = ModelWorker(text, conversation_history)
        self.worker.finished.connect(self.handle_ai_response)
        self.worker.start()

    def handle_ai_response(self, text):
        if self.thinking_bubble:
            parent_widget = self.thinking_bubble.parentWidget()
            if parent_widget: parent_widget.deleteLater()
            self.thinking_bubble = None
        
        self.is_typing = True
        self.current_ai_bubble = self.add_bubble(text, False, animate=True)
        self.current_ai_bubble.typing_finished.connect(self.on_typing_finished)
        
        self.conversations[self.current_chat_id]["msgs"].append(("ai", text))
        self.save_history_to_disk()
        self.chat_input.setDisabled(False); self.chat_input.setFocus(); self.btn_send.setText("■"); self.worker = None

    def on_typing_finished(self):
        self.is_typing = False; self.current_ai_bubble = None; self.btn_send.setText("➤")

    def add_bubble(self, text, is_user, animate=True):
        bubble = ChatBubble(text, is_user, animate); row = QWidget(); row_layout = QHBoxLayout(row); row_layout.setContentsMargins(0, 5, 0, 5)
        if is_user: row_layout.addStretch(); bubble.setMaximumWidth(600); row_layout.addWidget(bubble)
        else: bubble.setMaximumWidth(600); row_layout.addWidget(bubble); row_layout.addStretch()
        self.chat_layout.insertWidget(self.chat_layout.count()-1, row); self.scroll_to_bottom()
        return bubble

    def clear_chat_area(self):
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def load_chat(self, item):
        chat_id = item.data(Qt.ItemDataRole.UserRole)
        if chat_id in self.conversations:
            self.current_chat_id = chat_id; self.stack.setCurrentIndex(1); self.clear_chat_area()
            for role, text in self.conversations[chat_id]["msgs"]: self.add_bubble(text, role == "user", animate=False)

    def scroll_to_bottom(self):
        QApplication.processEvents(); self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.settings_changed.connect(self.apply_theme)
        dlg.logout_requested.connect(self.logout_signal.emit)
        dlg.exec()

    def toggle_max(self):
        if self.isMaximized(): self.showNormal()
        else: self.showMaximized()

    def apply_theme(self):
        # --- Window Controls ---
        self.title_bar.setStyleSheet(f"background-color: transparent; border: none;")
        self.brand_lbl.setStyleSheet(f"color: {theme.get('TEXT_MAIN')}; border: none;")
        self.btn_menu.setStyleSheet(f"color: {theme.get('TEXT_SUB')}; background: transparent; border: none; font-size: 20px;")
        for btn in self.win_btns: 
            btn.setStyleSheet(f"color: {theme.get('TEXT_SUB')}; border: none; background: transparent; font-size: 16px;")
        
        # --- Sidebar ---
        self.sidebar.setStyleSheet(f"background-color: {theme.get('BG_SIDEBAR')}; border: none;")
        self.sidebar_container.setStyleSheet(f"background-color: {theme.get('BG_SIDEBAR')}; border: none;")
        self.lbl_history.setStyleSheet(f"color: {theme.get('TEXT_SIDEBAR')}; font-size: {theme.font_size}pt; letter-spacing: 1px; border: none;")
        
        # --- Scrollbars ---
        scrollbar_qss = f"""
            QScrollBar:vertical {{ border: none; background: {theme.get("SCROLL_BG")}; width: 10px; margin: 0px; border-radius: 5px; }}
            QScrollBar::handle:vertical {{ background: {theme.get("SCROLL_HANDLE")}; min-height: 20px; border-radius: 5px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; background: none; border: none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            QScrollBar:horizontal {{ border: none; background: {theme.get("SCROLL_BG")}; height: 10px; margin: 0px; border-radius: 5px; }}
            QScrollBar::handle:horizontal {{ background: {theme.get("SCROLL_HANDLE")}; min-width: 20px; border-radius: 5px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; background: none; border: none; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
        """
        
        # --- List Widget ---
        self.chat_list.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none; color: {theme.get('TEXT_SIDEBAR')}; font-size: {theme.font_size}pt; }}
            QListWidget::item:hover {{ background: {theme.get('BG_CARD')}; }}
            QListWidget::item:selected {{ background: {theme.get('INPUT_BG')}; color: {theme.get('ACCENT_PRIMARY')}; border: none; }}
            {scrollbar_qss}
        """)
        self.chat_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # --- Profile & General ---
        self.btn_new.update_style()
        self.profile_frame.setStyleSheet(f"background: {theme.get('BG_CARD')}; border-radius: 12px; border: none;")
        self.avatar.setStyleSheet(f"background: {theme.get('ACCENT_PRIMARY')}; color: white; border-radius: 20px; font-weight: bold; border: none;")
        self.p_name.setStyleSheet(f"color: {theme.get('TEXT_MAIN')}; font-size: {theme.font_size+2}pt; border: none; background: transparent;")
        self.btn_settings.setStyleSheet(f"color: {theme.get('TEXT_SUB')}; text-align: left; background: transparent; border: none;")
        self.greet_lbl.setStyleSheet(f"color: {theme.get('TEXT_MAIN')}; font-size: {theme.font_size + 14}pt; font-weight: bold; border: none;")
        self.sub_lbl.setStyleSheet(f"color: {theme.get('TEXT_SUB')}; font-size: {theme.font_size + 2}pt; border: none;")
        
        # --- Resize Inputs First ---
        adjust_input_height(self.dash_input_field)
        adjust_input_height(self.chat_input)
        
        # --- Get New Height ---
        # We use a large radius to ensure pill shape regardless of height
        input_h = self.dash_input_field.height()
        
        # --- Inputs (Rounded Corners Fix) ---
        input_style = f"""
            QLineEdit {{ 
                background-color: {theme.get('INPUT_BG')}; 
                color: {theme.get('TEXT_MAIN')}; 
                border-radius: {input_h // 2}px; 
                padding: 0 20px;
                border: 1px solid transparent; 
                font-size: {theme.font_size}pt;
            }}
            QLineEdit:focus {{
                background-color: {theme.get('BG_CARD')}; border: 1px solid {theme.get('ACCENT_PRIMARY')};
            }}
        """
        self.dash_input_field.setStyleSheet(input_style)
        self.chat_input.setStyleSheet(input_style)
        
        # --- Send Buttons (Circular Alignment Fix) ---
        # Resize buttons to match input height
        self.dash_go_btn.setFixedSize(input_h, input_h)
        self.btn_send.setFixedSize(input_h, input_h)
        
        circular_btn_style = f"""
            QPushButton {{ 
                background-color: {theme.get('ACCENT_PRIMARY')}; color: white; 
                border-radius: {input_h // 2}px; 
                border: none; 
                padding: 0px; 
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ 
                background-color: {theme.get('ACCENT_HOVER')};
            }}
        """
        self.dash_go_btn.setStyleSheet(circular_btn_style)
        self.btn_send.setStyleSheet(circular_btn_style)
        
        # --- Chat Area ---
        self.content_wrapper.setStyleSheet("background: transparent;")
        self.chat_container.setStyleSheet("background: transparent;")
        self.scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }} {scrollbar_qss}")
        self.warning_lbl.setStyleSheet(f"color: {theme.get('TEXT_SUB')}; font-size: {theme.font_size-2}pt; border: none;")
        
        # Refresh existing bubbles
        for i in range(self.chat_layout.count()):
            row_item = self.chat_layout.itemAt(i)
            if row_item and row_item.widget():
                bubbles = row_item.widget().findChildren(ChatBubble)
                for b in bubbles: b.update_style()
                thinking = row_item.widget().findChildren(ThinkingBubble)
                for t in thinking: t.update_style()
        for card in self.suggestion_cards: card.update_style()

    def mousePressEvent(self, e): 
        if e.button() == Qt.MouseButton.LeftButton: 
            self.dragging = True
            self.drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()
    def mouseMoveEvent(self, e): 
        if self.dragging and not self.isMaximized(): 
            self.move(e.globalPosition().toPoint() - self.drag_pos)
            e.accept()
    def mouseReleaseEvent(self, e): 
        self.dragging = False

class AuthWidget(QWidget):
    login_successful = pyqtSignal(str) 
    def __init__(self, auth_manager):
        super().__init__()
        self.auth_manager = auth_manager
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(500, 650)
        
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        self.bg = StarfieldWidget(self); layout.addWidget(self.bg)
        
        self.container = QFrame(self.bg); self.container.setFixedSize(380, 480)
        cl = QVBoxLayout(self.container); cl.setSpacing(15); cl.setContentsMargins(30, 30, 30, 30)
        
        btn_close = QPushButton("✕", self.container);
        btn_close.setGeometry(340, 10, 30, 30); btn_close.setCursor(Qt.CursorShape.PointingHandCursor); btn_close.setFlat(True); btn_close.clicked.connect(self.close)
        
        self.orb = VoidOrb(70); cl.addWidget(self.orb, 0, Qt.AlignmentFlag.AlignCenter)
        self.title_lbl = QLabel("VOID"); self.title_lbl.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold)); self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); cl.addWidget(self.title_lbl)
        
        self.stack = QStackedWidget()
        self.login_page = self.create_login_page(); self.signup_page = self.create_signup_page()
        self.stack.addWidget(self.login_page); self.stack.addWidget(self.signup_page)
        
        self.msg_lbl = QLabel(""); self.msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.stack); cl.addWidget(self.msg_lbl)
        
        self.update_styles()
        btn_close.setStyleSheet("QPushButton { background: transparent; border: none; color: #a78bfa; font-weight: bold; font-size: 16px; } QPushButton:hover { color: white; }")
        QTimer.singleShot(100, self.start_anim)

    def start_anim(self):
        center_x = (self.width() - self.container.width()) // 2
        center_y = (self.height() - self.container.height()) // 2
        
        self.anim = QPropertyAnimation(self.container, b"geometry")
        self.anim.setDuration(800)
        start_rect = QRect(center_x, self.height(), self.container.width(), self.container.height())
        end_rect = QRect(center_x, center_y, self.container.width(), self.container.height())
        self.anim.setStartValue(start_rect); self.anim.setEndValue(end_rect); self.anim.setEasingCurve(QEasingCurve.Type.OutBack); self.anim.start()

    def create_login_page(self):
        page = QWidget(); l = QVBoxLayout(page); l.setContentsMargins(0,0,0,0); l.setSpacing(15)
        self.login_user = QLineEdit(); self.login_user.setPlaceholderText("Username"); self.login_user.returnPressed.connect(self.handle_login)
        self.login_pass = PasswordEdit(); self.login_pass.setPlaceholderText("Password"); self.login_pass.returnPressed.connect(self.handle_login)
        
        self.btn_login = GlowButton("Log In"); self.btn_login.clicked.connect(self.handle_login)
        switch_btn = QPushButton("Sign Up"); switch_btn.setFlat(True); switch_btn.setCursor(Qt.CursorShape.PointingHandCursor); switch_btn.clicked.connect(lambda: self.switch_view(1)); self.style_switch_btn(switch_btn)
        l.addWidget(self.login_user); l.addWidget(self.login_pass); l.addWidget(self.btn_login); l.addWidget(switch_btn)
        return page

    def create_signup_page(self):
        page = QWidget(); l = QVBoxLayout(page); l.setContentsMargins(0,0,0,0); l.setSpacing(15)
        self.signup_user = QLineEdit(); self.signup_user.setPlaceholderText("New Username"); self.signup_user.returnPressed.connect(self.handle_signup)
        self.signup_pass = PasswordEdit(); self.signup_pass.setPlaceholderText("New Password"); self.signup_pass.returnPressed.connect(self.handle_signup)
        self.signup_confirm = PasswordEdit(); self.signup_confirm.setPlaceholderText("Confirm Password"); self.signup_confirm.returnPressed.connect(self.handle_signup)
        
        btn = GlowButton("Sign Up"); btn.clicked.connect(self.handle_signup)
        switch_btn = QPushButton("Log In"); switch_btn.setFlat(True); switch_btn.setCursor(Qt.CursorShape.PointingHandCursor); switch_btn.clicked.connect(lambda: self.switch_view(0)); self.style_switch_btn(switch_btn)
        l.addWidget(self.signup_user); l.addWidget(self.signup_pass); l.addWidget(self.signup_confirm); l.addWidget(btn); l.addWidget(switch_btn)
        return page

    def style_switch_btn(self, btn): btn.setStyleSheet("color: #7b80ff; font-weight: bold; border: none; background: transparent;")
    def switch_view(self, index): self.stack.setCurrentIndex(index); self.msg_lbl.setText("")
    def update_styles(self):
        self.container.setStyleSheet(f"QFrame {{ background-color: {theme.get('BG_CARD')}; border-radius: 25px; border: none; }}")
        self.title_lbl.setStyleSheet(f"color: {theme.get('TEXT_MAIN')}; background: transparent; border: none;")
        self.msg_lbl.setStyleSheet("border: none; background: transparent; color: #ef4444;")
        inp_style = f"background-color: {theme.get('INPUT_BG')}; color: {theme.get('TEXT_MAIN')}; border: none; border-radius: 12px; padding: 0 40px 0 15px;"
        for inp in [self.login_user, self.login_pass, self.signup_user, self.signup_pass, self.signup_confirm]:
            inp.setStyleSheet(inp_style)
            adjust_input_height(inp)
    
    def handle_login(self):
        u = self.login_user.text().strip(); p = self.login_pass.text()
        success, msg = self.auth_manager.login(u, p)
        if success: self.login_successful.emit(u)
        else: self.msg_lbl.setText(msg)

    def handle_signup(self):
        u = self.signup_user.text().strip(); p = self.signup_pass.text(); c = self.signup_confirm.text()
        if p != c: self.msg_lbl.setText("Passwords do not match"); return
        success, msg = self.auth_manager.register(u, p)
        if success: self.login_successful.emit(u)
        else: self.msg_lbl.setText(msg)

    def resizeEvent(self, e): self.bg.resize(self.size()); self.container.move((self.width()-380)//2, (self.height()-480)//2)
    def clear_inputs(self):
        self.login_user.clear(); self.login_pass.clear()
        self.signup_user.clear(); self.signup_pass.clear(); self.signup_confirm.clear()
        self.msg_lbl.setText("")

if __name__ == "__main__":
    app = QApplication.instance()
    if not app: app = QApplication(sys.argv)
    
    font = QFont("Segoe UI", 10); app.setFont(font)
    auth_manager = AuthManager()
    
    auth_window = AuthWidget(auth_manager)
    main_window = None
    
    def start_app(username):
        global main_window
        auth_window.close()
        main_window = MainWindow(username)
        main_window.logout_signal.connect(handle_logout)
        main_window.show()

    def handle_logout():
        global main_window
        main_window.close()
    
        auth_window.clear_inputs()
        auth_window.update_styles()
        auth_window.show()

    auth_window.login_successful.connect(start_app)
    auth_window.show()
    app.exec()