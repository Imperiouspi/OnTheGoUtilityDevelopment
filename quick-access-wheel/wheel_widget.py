import math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QPoint, QRectF, pyqtSignal, QTimer
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QFont, QFontMetrics, QPainterPath, QCursor
)


WHEEL_RADIUS = 180
INNER_RADIUS = 50
NUM_SLOTS = 8
SEGMENT_ANGLE = 360 / NUM_SLOTS
# Offset so slot 0 (right) is centered on the 0-degree axis
ANGLE_OFFSET = -SEGMENT_ANGLE / 2

# Colors
BG_COLOR = QColor(30, 30, 30, 220)
SEGMENT_COLOR = QColor(50, 50, 55, 200)
HOVER_COLOR = QColor(80, 120, 200, 200)
BORDER_COLOR = QColor(100, 100, 110, 180)
TEXT_COLOR = QColor(220, 220, 220)
BACK_COLOR = QColor(90, 60, 60, 200)
UNSET_TEXT_COLOR = QColor(140, 140, 140)


class WheelWidget(QWidget):
    """A radial 8-segment wheel overlay."""

    slot_selected = pyqtSignal(int)  # emitted with the slot index on release
    slot_clicked = pyqtSignal(int)  # emitted on mouse button click (for editing)
    folder_hovered = pyqtSignal(int)  # emitted when a folder slot is hovered

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        size = WHEEL_RADIUS * 2 + 40
        self.setFixedSize(size, size)

        self._center = QPoint(size // 2, size // 2)
        self._hovered_slot = -1
        self._slots = [{"label": "Select to add action", "type": None}] * NUM_SLOTS
        self._mouse_tracking_timer = QTimer(self)
        self._mouse_tracking_timer.timeout.connect(self._track_mouse)
        self._mouse_tracking_timer.setInterval(16)  # ~60fps

        # Folder hover dwell timer — auto-expands after 400ms
        self._folder_dwell_timer = QTimer(self)
        self._folder_dwell_timer.setSingleShot(True)
        self._folder_dwell_timer.setInterval(400)
        self._folder_dwell_timer.timeout.connect(self._on_folder_dwell)

    def show_at_cursor(self):
        pos = QCursor.pos()
        self.move(pos.x() - self.width() // 2, pos.y() - self.height() // 2)
        self.show()
        self.raise_()
        self._mouse_tracking_timer.start()

    def hide(self):
        self._mouse_tracking_timer.stop()
        self._folder_dwell_timer.stop()
        selected = self._hovered_slot
        self._hovered_slot = -1
        super().hide()
        if 0 <= selected < NUM_SLOTS:
            self.slot_selected.emit(selected)

    def mousePressEvent(self, event):
        """Click on a segment to edit it."""
        if event.button() == Qt.LeftButton and 0 <= self._hovered_slot < NUM_SLOTS:
            self.slot_clicked.emit(self._hovered_slot)

    def set_slots(self, slots):
        self._slots = slots

    def _track_mouse(self):
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        dx = local_pos.x() - self._center.x()
        dy = local_pos.y() - self._center.y()
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < INNER_RADIUS or dist > WHEEL_RADIUS:
            if self._hovered_slot != -1:
                self._hovered_slot = -1
                self._folder_dwell_timer.stop()
                self.update()
            return

        angle = math.degrees(math.atan2(dy, dx)) - ANGLE_OFFSET
        if angle < 0:
            angle += 360

        slot = int(angle / SEGMENT_ANGLE) % NUM_SLOTS
        if slot != self._hovered_slot:
            self._hovered_slot = slot
            self._folder_dwell_timer.stop()
            # Start dwell timer if hovering a folder slot
            if slot < len(self._slots):
                slot_data = self._slots[slot]
                if slot_data.get("type") == "folder":
                    self._folder_dwell_timer.start()
            self.update()

    def _on_folder_dwell(self):
        """Called when the mouse has hovered over a folder slot long enough."""
        if 0 <= self._hovered_slot < NUM_SLOTS:
            slot_data = self._slots[self._hovered_slot]
            if slot_data.get("type") == "folder":
                self.folder_hovered.emit(self._hovered_slot)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw each segment
        for i in range(NUM_SLOTS):
            self._draw_segment(painter, i)

        # Draw inner circle (dead zone)
        painter.setBrush(QColor(20, 20, 20, 240))
        painter.setPen(QPen(BORDER_COLOR, 1.5))
        painter.drawEllipse(self._center, int(INNER_RADIUS), int(INNER_RADIUS))

        painter.end()

    def _draw_segment(self, painter, index):
        start_angle = ANGLE_OFFSET + index * SEGMENT_ANGLE
        slot_data = self._slots[index] if index < len(self._slots) else {}
        slot_type = slot_data.get("type")
        is_hovered = index == self._hovered_slot

        # Build the segment path
        path = QPainterPath()
        rect_outer = QRectF(
            self._center.x() - WHEEL_RADIUS,
            self._center.y() - WHEEL_RADIUS,
            WHEEL_RADIUS * 2,
            WHEEL_RADIUS * 2
        )
        rect_inner = QRectF(
            self._center.x() - INNER_RADIUS,
            self._center.y() - INNER_RADIUS,
            INNER_RADIUS * 2,
            INNER_RADIUS * 2
        )

        # Qt uses 1/16th degree units, counter-clockwise from 3 o'clock
        qt_start = int(-start_angle * 16)
        qt_span = int(-SEGMENT_ANGLE * 16)

        path.arcMoveTo(rect_outer, -start_angle)
        path.arcTo(rect_outer, -start_angle, -SEGMENT_ANGLE)
        path.arcTo(rect_inner, -(start_angle + SEGMENT_ANGLE), SEGMENT_ANGLE)
        path.closeSubpath()

        # Fill
        if is_hovered:
            painter.setBrush(HOVER_COLOR)
        elif slot_type == "back":
            painter.setBrush(BACK_COLOR)
        else:
            painter.setBrush(SEGMENT_COLOR)

        painter.setPen(QPen(BORDER_COLOR, 1.5))
        painter.drawPath(path)

        # Draw label
        mid_angle_deg = start_angle + SEGMENT_ANGLE / 2
        mid_angle = math.radians(mid_angle_deg)
        label_radius = (WHEEL_RADIUS + INNER_RADIUS) / 2
        lx = self._center.x() + label_radius * math.cos(mid_angle)
        ly = self._center.y() + label_radius * math.sin(mid_angle)

        label = slot_data.get("label", "")
        font = QFont("Sans", 9)
        font.setBold(is_hovered)
        painter.setFont(font)

        if slot_type is None:
            painter.setPen(UNSET_TEXT_COLOR)
        else:
            painter.setPen(TEXT_COLOR)

        fm = QFontMetrics(font)
        # Word wrap into at most 2 lines
        words = label.split()
        lines = []
        current = ""
        max_width = int((WHEEL_RADIUS - INNER_RADIUS) * 0.75)
        for w in words:
            test = (current + " " + w).strip()
            if fm.horizontalAdvance(test) > max_width and current:
                lines.append(current)
                current = w
            else:
                current = test
        if current:
            lines.append(current)
        lines = lines[:2]

        total_height = len(lines) * fm.height()
        ty = ly - total_height / 2

        for line in lines:
            tw = fm.horizontalAdvance(line)
            painter.drawText(int(lx - tw / 2), int(ty + fm.ascent()), line)
            ty += fm.height()
