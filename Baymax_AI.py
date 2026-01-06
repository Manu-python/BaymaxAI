# app.py
import sys
import os
import base64
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QTextBrowser, QMessageBox, QLabel, QHBoxLayout)
from PyQt5.QtGui import QPalette, QBrush, QPixmap, QMovie, QFontDatabase, QFont, QTextCursor, QColor, QIcon as QICon
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QCoreApplication, QTimer
from PyQt5.QtWidgets import QScrollArea, QSizePolicy
from openai import OpenAI
from pathlib import Path

# IMPORTANT: Replace this with the actual path to your Baymax GIF.
# You can find the GIF online or create your own.
GIF_PATH = str(Path(__file__).parent / "Baymax_Eyes_FINAL_Animation.gif")

class OpenAIWorker(QThread):
    """
    Worker thread to handle the OpenAI API call to prevent the UI from freezing.
    """
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, client, messages):
        super().__init__()
        self.client = client
        self.messages = messages

    def run(self):
        """
        Makes the API call and emits the response or an error.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.messages
            )
            reply = response.choices[0].message.content
            self.response_received.emit(reply)
        except Exception as e:
            self.error_occurred.emit(f"Baymax encountered an error: {e}")


class MainWindow(QMainWindow):
    """
    The main application window for the Baymax chatbot.
    """
    def __init__(self):
        super().__init__()

        # --- 1. Load API Key and OpenAI Client ---
        api_key = api_key  # API key removed for safety
        if not api_key:
            QMessageBox.critical(self, "API Key Error", "OPENAI_API_KEY environment variable not set.")
            QCoreApplication.quit()
            return
        self.client = OpenAI(api_key=api_key)
        self.worker = None

        # --- 2. Initialize UI ---
        self.setWindowTitle("Baymax")
        self.setWindowIcon(QICon("Baymax_icon (40 x 40 px).svg"))
        self.resize(500, 700)
        self.setStyleSheet("""
            QWidget {
                color: black;
                font-family: 'Comfortaa', sans-serif;
            }
            QMainWindow {
                border-radius: 18px;
                background-color: rgba(255, 255, 255, 1);
            }
        """)

        # --- 3. Set Background GIF ---
        try:
            self.movie = QMovie(GIF_PATH)
            if not self.movie.isValid():
                raise FileNotFoundError
            
            self.movie_label = QLabel(self)
            self.movie_label.setMovie(self.movie)
            self.movie_label.setAlignment(Qt.AlignCenter) # Center the GIF
            
            # Connect the QMovie's frameChanged signal to a slot that scales the image
            self.movie.frameChanged.connect(self.update_movie_frame_scaled)
            self.movie.start()
            self.setCentralWidget(self.movie_label)

        except FileNotFoundError:
            QMessageBox.warning(self, "GIF Error", f"The GIF file was not found at: {GIF_PATH}\n"
                                                    "The application will run with a black background.")
            self.central_widget_container = QWidget()
            self.setCentralWidget(self.central_widget_container)
            self.central_widget_container.setStyleSheet("background-color: black;")


        # --- 4. Main Layout (Overlaying the GIF) ---
        self.central_widget_container = QWidget(self.centralWidget())
        self.central_widget_container.setAutoFillBackground(False)
        self.central_widget_container.setPalette(self.palette())
        self.central_widget_container.setGeometry(self.rect())
        self.main_layout = QVBoxLayout(self.central_widget_container)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)

        self.greeting_label = QLabel("Hello. I am Baymax.")
        greeting_font = QFont("Comfortaa", 32)  # Big font size
        self.greeting_label.setFont(greeting_font)
        self.greeting_label.setStyleSheet("color: black;")
        self.greeting_label.setAlignment(Qt.AlignCenter)

        self.description_label = QLabel("Your personal healthcare companion.")
        description_font = QFont("Comfortaa", 14)
        self.description_label.setFont(description_font)
        self.description_label.setStyleSheet("color: black; padding-bottom: 20px;")
        self.description_label.setAlignment(Qt.AlignCenter)

        self.main_layout.addWidget(self.greeting_label)
        self.main_layout.addWidget(self.description_label)

        # Add the 'Comfortaa' font from a URL
        QFontDatabase.addApplicationFont("https://fonts.googleapis.com/css2?family=Comfortaa&display=swap")
        # Fallback if the font doesn't load
        self.font = QFont("Comfortaa", 12)
        QApplication.setFont(self.font)

        # Chat display area with scroll area and widget container
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.main_layout.addWidget(self.scroll_area)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setSpacing(10)
        self.chat_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_area.setWidget(self.chat_container)



        # Input field
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("What is your medical query?")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.8);
                border: 2px solid rgba(255, 255, 255, 0.5);
                border-radius: 15px;
                padding: 10px;
            }
            QLineEdit:focus {
                background: rgba(255, 255, 255, 0.9);
                border: 2px solid rgba(200, 230, 255, 0.8);
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        self.main_layout.addWidget(self.input_field)

        # --- 5. Chat Logic ---
        self.messages = [
            {
                "role": "system",
                "content": (
                    "You are Baymax, the personal healthcare companion from Big Hero 6. "
                    "You are kind, gentle, and always put the patient first. You are focused on health and well-being. "
                    "Only introduce yourself once at the beginning of the conversation, saying 'Hello. I am Baymax.'"
                    "When the first message a user sends is a number, that means they are rating their pain level from 1 to 10. They don't necessarily have to input a number in their first message, but if they do, you should just respond with a follow-up question asking them to say if their pain is physical or emotional. Then continue the conversation normally."
                    "Don't say 'Hello. I am Baymax.' again after the first message. "
                )
            }
        ]

        QTimer.singleShot(500, lambda: self.append_message("assistant", "Hello. I am Baymax. Your personal healthcare companion.\n\nI was alerted to the presence of a medical query. On a scale of 1 to 10, how would you rate your pain?"))
        self.scroll_area.verticalScrollBar().setStyleSheet("""
                    QScrollBar:vertical {
                        background: transparent;
                        width: 8px;
                        margin: 0px 0px 0px 0px;
                        border-radius: 4px;
                    }
                    QScrollBar::handle:vertical {
                        background: rgba(100, 100, 100, 0.4);
                        min-height: 20px;
                        border-radius: 4px;
                    }
                    QScrollBar::handle:vertical:hover {
                        background: rgba(100, 100, 100, 0.7);
                    }
                    QScrollBar::add-line, QScrollBar::sub-line {
                        height: 0px;
                    }
                    QScrollBar::add-page, QScrollBar::sub-page {
                        background: none;
                    }
                """)
        
    def update_movie_frame_scaled(self):
        """
        Scales the current frame of the QMovie to fit the QLabel without distortion.
        This slot is connected to the QMovie's frameChanged signal.
        """
        if self.movie and self.movie_label:
            pixmap = self.movie.currentPixmap()
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.movie_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.movie_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """
        Handles window resizing.
        """
        super().resizeEvent(event)
        # Ensure the background and overlay resize correctly
        if self.movie_label:
            self.movie_label.setGeometry(self.rect())
            self.update_movie_frame_scaled() # Manually update the scaled frame on resize
        if self.central_widget_container:
            self.central_widget_container.setGeometry(self.rect())
        
    def append_message(self, role, content):
        is_user = (role == "user")
        bubble = ChatBubble(content, is_user)
        self.chat_layout.addWidget(bubble)

        # Scroll to bottom
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()))
        
        



    def send_message(self):
        """
        Handles sending the user's message and starting the API request.
        """
        user_prompt = self.input_field.text()
        if not user_prompt.strip():
            return

        self.append_message("user", user_prompt)
        self.messages.append({"role": "user", "content": user_prompt})
        self.input_field.clear()
        self.input_field.setEnabled(False) # Disable input while waiting for response

        # Start the worker thread for the API call
        self.worker = OpenAIWorker(self.client, self.messages)
        self.worker.response_received.connect(self.handle_response)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.start()

    def handle_response(self, reply):
        """
        Receives the API response and updates the UI.
        """
        # Add a polite follow-up if the user says "thank you"
        if "thank you" in self.messages[-1]["content"].lower():
            reply += "\n\nAre you satisfied with your care?"

        self.messages.append({"role": "assistant", "content": reply})
        self.append_message("assistant", reply)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        self.worker = None

    def handle_error(self, error_message):
        """
        Displays an error message if the API call fails.
        """
        QMessageBox.critical(self, "API Error", error_message)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        self.worker = None

class ChatBubble(QWidget):
    def __init__(self, text, is_user):
        super().__init__()
        rich_text = self.convert_markdown_to_html(text)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # no margins on container

        bubble = QLabel()
        bubble.setText(rich_text)  # ✅ Set the converted rich text here
        bubble.setTextFormat(Qt.RichText)  # ✅ Enable rich text
        bubble.setWordWrap(True)
        bubble.setStyleSheet(f"""
            background-color: {'rgba(102, 153, 255, 200)' if is_user else 'rgba(240, 240, 240, 215)'};
            color: {'white' if is_user else 'black'};
            border-radius: 20px;
            padding: 12px 18px;
            font-size: 14px;
            max-width: 300%;
        """)

        if is_user:
            layout.addStretch()
            layout.addWidget(bubble)
            layout.setSpacing(0)
            layout.setContentsMargins(50, 5, 10, 5)
        else:
            layout.addWidget(bubble)
            layout.addStretch()
            layout.setSpacing(0)
            layout.setContentsMargins(10, 5, 50, 5)

    def convert_markdown_to_html(self, text):
        import re

        # Escape HTML special characters first
        text = re.sub(r'&', '&amp;', text)
        text = re.sub(r'<', '&lt;', text)
        text = re.sub(r'>', '&gt;', text)

        # Bold: **text**
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        
        # Italic: *text*
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)

        # Inline code: `code`
        text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)

        # Line breaks
        text = text.replace('\n', '<br>')

        # Bullet points: lines starting with '- '
        lines = text.split('<br>')
        in_list = False
        new_lines = []

        for line in lines:
            if line.strip().startswith('- '):
                if not in_list:
                    new_lines.append('<ul>')
                    in_list = True
                item = line.strip()[2:]
                new_lines.append(f'<li>{item}</li>')
            else:
                if in_list:
                    new_lines.append('</ul>')
                    in_list = False
                new_lines.append(line)

        if in_list:
            new_lines.append('</ul>')

        return '<br>'.join(new_lines)




if __name__ == "__main__":
    # Fix for HiDPI displays
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # Optional fallback font if custom font fails to load:
    app.setFont(QFont("Arial", 12))  # <-- Add this line here temporarily

    from pathlib import Path
    font_path = Path(__file__).parent / "fonts" / "Comfortaa-VariableFont_wght.ttf"
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id == -1:
        print(f"Failed to load Comfortaa font from {font_path}")
    else:
        loaded_font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        app.setFont(QFont(loaded_font_family, 10))
        
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())