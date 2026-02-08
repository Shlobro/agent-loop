"""Centralized UI theme and lightweight motion helpers."""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QPushButton, QWidget


def apply_app_theme(app: QApplication):
    """Apply a modern neutral theme to the entire application."""
    if app is None:
        return
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QWidget {
            color: #ece6de;
            background: #111315;
            font-family: "Segoe UI Variable Text";
            font-size: 15px;
        }
        QMainWindow, QDialog {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #101214, stop:0.5 #12161a, stop:1 #0f1317);
        }
        QLabel[role="muted"] { color: #9aa4b1; }
        QLabel[role="hero"] { color: #f3eee7; font-size: 26px; font-weight: 700; }
        QLabel[role="hero_subtitle"] { color: #a8b5c2; font-size: 15px; }
        QGroupBox {
            border: 1px solid #232a31;
            border-radius: 14px;
            margin-top: 12px;
            padding-top: 12px;
            background: #151a1f;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
            color: #c9d3dd;
            font-size: 16px;
        }
        QPlainTextEdit, QTextEdit, QTextBrowser, QLineEdit, QListWidget, QSpinBox, QComboBox {
            background: #0f1419;
            border: 1px solid #29313a;
            border-radius: 10px;
            font-size: 15px;
            padding: 8px 10px;
            selection-background-color: #2f6f9d;
        }
        QTextBrowser {
            line-height: 1.45;
        }
        QListWidget::item {
            padding: 10px 10px;
            margin: 2px 0;
            border-radius: 8px;
        }
        QListWidget::item:selected {
            background: #27577a;
        }
        QPlainTextEdit:focus, QTextEdit:focus, QTextBrowser:focus, QLineEdit:focus, QListWidget:focus,
        QSpinBox:focus, QComboBox:focus {
            border: 1px solid #4f95c7;
        }
        QComboBox::drop-down {
            border: none;
            width: 22px;
        }
        QProgressBar {
            border: 1px solid #2d3a47;
            border-radius: 9px;
            text-align: center;
            background: #10161d;
            color: #dbe4ee;
            min-height: 16px;
        }
        QProgressBar::chunk {
            border-radius: 8px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                        stop:0 #2a7cb5, stop:1 #53b8b2);
        }
        QSplitter::handle {
            background: #1d252d;
            width: 3px;
            margin: 2px;
            border-radius: 1px;
        }
        QMenuBar {
            background: #0f1419;
            border-bottom: 1px solid #202a34;
        }
        QMenuBar::item {
            background: transparent;
            font-size: 14px;
            padding: 7px 11px;
            border-radius: 6px;
        }
        QMenuBar::item:selected, QMenu::item:selected {
            background: #263442;
        }
        QMenu {
            background: #0f1419;
            border: 1px solid #27313b;
            padding: 4px;
        }
        QPushButton {
            background: #202a33;
            border: 1px solid #2f3e4d;
            border-radius: 10px;
            font-size: 15px;
            padding: 10px 16px;
            color: #e7edf4;
            font-weight: 600;
        }
        QPushButton:hover { background: #273644; border-color: #3f5366; }
        QPushButton:pressed { background: #1b252f; }
        QPushButton:disabled {
            background: #181d23;
            color: #77808a;
            border-color: #222a33;
        }
        QPushButton[variant="primary"] {
            background: #2b77ae;
            border: 1px solid #3d8fca;
            color: #f4fbff;
        }
        QPushButton[variant="primary"]:hover { background: #3388c7; }
        QPushButton[variant="danger"] {
            background: #7f2c34;
            border: 1px solid #a53f48;
            color: #fff5f6;
        }
        QPushButton[variant="danger"]:hover { background: #96404a; }
        """
    )


def polish_button(button: QPushButton, variant: str):
    """Set button style variant and refresh style."""
    button.setProperty("variant", variant)
    button.style().unpolish(button)
    button.style().polish(button)


def animate_fade_in(widget: QWidget, duration_ms: int = 360, delay_ms: int = 0):
    """Apply a simple fade-in animation to a widget."""
    if widget is None:
        return

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(max(120, duration_ms))
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutCubic)

    def _start():
        animation.start()

    widget._fade_animation = animation
    if delay_ms > 0:
        QTimer.singleShot(delay_ms, _start)
    else:
        _start()
