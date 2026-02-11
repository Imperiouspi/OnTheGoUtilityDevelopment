import math
import os
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QPoint, QRectF, pyqtSignal, QTimer
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QFont, QFontMetrics, QPainterPath, QCursor,
    QPixmap
)


NUM_SLOTS = 8
SEGMENT_ANGLE = 360 / NUM_SLOTS
# Offset so slot 0 (right) is centered on the 0-degree axis
ANGLE_OFFSET = -SEGMENT_ANGLE / 2

# Settings button
SETTINGS_BTN_RADIUS = 16
SETTINGS_GEAR = "\u2699"  # gear emoji


class WheelWidget(QWidget):
    """A radial 8-segment wheel overlay."""

    slot_selected = pyqtSignal(int)  # emitted with the slot index on release
    slot_clicked = pyqtSignal(int)  # emitted on mouse button click (for editing)
    folder_hovered = pyqtSignal(int)  # emitted when a folder slot is hovered
    settings_selected = pyqtSignal()  # emitted when settings button released

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

        # Configurable style values (defaults)
        self._wheel_radius = 180
        self._inner_radius = 50
        self._bg_opacity = 220
        self._font_size = 9
        self._segment_color = QColor(50, 50, 55, 200)
        self._hover_color = QColor(80, 120, 200, 200)
        self._text_color = QColor(220, 220, 220)
        self._border_color = QColor(100, 100, 110, 180)
        self._back_color = QColor(90, 60, 60, 200)
        self._unset_text_color = QColor(140, 140, 140)

        self._recalc_geometry()

        self._hovered_slot = -1
        self._settings_hovered = False
        self._centre_slot = None  # folder slot data when inside a folder (label, icon, show_label)
        self._slots = [{"label": "Select to add action", "type": None}] * NUM_SLOTS
        self._suppress_selection = False
        self._mouse_tracking_timer = QTimer(self)
        self._mouse_tracking_timer.timeout.connect(self._track_mouse)
        self._mouse_tracking_timer.setInterval(16)  # ~60fps

        # Folder hover dwell timer
        self._folder_dwell_timer = QTimer(self)
        self._folder_dwell_timer.setSingleShot(True)
        self._folder_dwell_timer.setInterval(400)
        self._folder_dwell_timer.timeout.connect(self._on_folder_dwell)
        self._dwell_ms = 400
        self._auto_continue_extra_ms = 200
        # After folder navigation, suppress dwell for the slot type
        # that would cause an unwanted immediate reversal.
        self._suppress_back_dwell = False   # set after entering a folder
        self._suppress_folder_dwell = False  # set after going back

    def _recalc_geometry(self):
        """Recalculate widget size and key positions based on current settings."""
        size = self._wheel_radius * 2 + 60  # extra room for settings button
        self.setFixedSize(size, size)
        self._center = QPoint(size // 2, size // 2)
        # Settings button in the bottom-right corner, outside the wheel
        offset = self._wheel_radius + 22
        diag = offset * math.cos(math.radians(45))
        self._settings_btn_center = QPoint(
            int(self._center.x() + diag),
            int(self._center.y() + diag)
        )

    def apply_settings(self, settings):
        """Apply settings from config to the widget."""
        self._wheel_radius = settings.get("wheel_radius", 180)
        self._inner_radius = settings.get("inner_radius", 50)
        self._bg_opacity = settings.get("bg_opacity", 220)
        self._font_size = settings.get("font_size", 9)

        sc = settings.get("segment_color", [50, 50, 55, 200])
        self._segment_color = QColor(*sc)
        hc = settings.get("hover_color", [80, 120, 200, 200])
        self._hover_color = QColor(*hc)
        tc = settings.get("text_color", [220, 220, 220, 255])
        self._text_color = QColor(*tc)
        bc = settings.get("border_color", [100, 100, 110, 180])
        self._border_color = QColor(*bc)

        self._dwell_ms = settings.get("folder_dwell_ms", 400)
        self._auto_continue_extra_ms = settings.get("auto_continue_extra_ms", 200)
        self._folder_dwell_timer.setInterval(self._dwell_ms)

        self._recalc_geometry()
        self.update()

    def show_at_cursor(self):
        pos = QCursor.pos()
        x = pos.x() - self.width() // 2
        y = pos.y() - self.height() // 2
        # Clamp to the screen that contains the cursor (fixes multi-display)
        desktop = QApplication.desktop()
        screen_no = desktop.screenNumber(pos)
        geom = desktop.availableGeometry(screen_no)
        x = max(geom.left(), min(x, geom.right() - self.width()))
        y = max(geom.top(), min(y, geom.bottom() - self.height()))
        self.move(x, y)
        self.show()
        self.raise_()
        self._settings_hovered = False
        self._mouse_tracking_timer.start()

    def hide(self):
        self._mouse_tracking_timer.stop()
        self._folder_dwell_timer.stop()
        selected = self._hovered_slot
        was_settings = self._settings_hovered
        self._hovered_slot = -1
        self._settings_hovered = False
        super().hide()
        if self._suppress_selection:
            self._suppress_selection = False
            return
        if was_settings:
            self.settings_selected.emit()
        elif 0 <= selected < NUM_SLOTS:
            self.slot_selected.emit(selected)

    def mousePressEvent(self, event):
        """Right-click to edit a slot; left-click to activate the action and close."""
        if 0 <= self._hovered_slot < NUM_SLOTS:
            if event.button() == Qt.RightButton:
                self._suppress_selection = True
                self.slot_clicked.emit(self._hovered_slot)
            elif event.button() == Qt.LeftButton:
                # Activate the hovered action and close the wheel
                self.hide()

    def reset_hover(self, direction="enter"):
        """Reset hover state so the next mouse-track tick re-evaluates the current position.

        Call this after changing folder contents so that if the mouse is already
        over a folder slot in the new view, the dwell timer starts immediately
        without requiring the user to move the mouse away and back.

        direction:
            "enter" — just entered a folder; suppress back-dwell so we don't
                      immediately bounce back, and use extended dwell for
                      auto-continuing into nested folders.
            "back"  — just went back; suppress folder-dwell so a folder
                      that happens to be under the back-button position
                      doesn't auto-activate.
        """
        self._hovered_slot = -1
        self._folder_dwell_timer.stop()
        if direction == "enter":
            self._suppress_back_dwell = True
            self._suppress_folder_dwell = False
        else:  # "back"
            self._suppress_back_dwell = False
            self._suppress_folder_dwell = True

    def set_slots(self, slots):
        self._slots = slots

    def set_centre_slot(self, slot_data):
        """Set the slot data shown in the centre (e.g. current folder). None to hide. Uses same icon/label rules as segments."""
        self._centre_slot = slot_data

    def _track_mouse(self):
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        dx = local_pos.x() - self._center.x()
        dy = local_pos.y() - self._center.y()
        dist = math.sqrt(dx * dx + dy * dy)

        # Check if hovering settings button
        sdx = local_pos.x() - self._settings_btn_center.x()
        sdy = local_pos.y() - self._settings_btn_center.y()
        sdist = math.sqrt(sdx * sdx + sdy * sdy)
        new_settings_hovered = sdist <= SETTINGS_BTN_RADIUS

        if new_settings_hovered:
            if not self._settings_hovered or self._hovered_slot != -1:
                self._settings_hovered = True
                self._hovered_slot = -1
                self._folder_dwell_timer.stop()
                self.update()
            return

        if self._settings_hovered:
            self._settings_hovered = False
            self.update()

        if dist < self._inner_radius or dist > self._wheel_radius:
            if self._hovered_slot != -1:
                self._hovered_slot = -1
                self._folder_dwell_timer.stop()
                # Returning to the centre (or leaving the wheel) counts as
                # moving away — clear navigation suppression flags so the
                # next slot hover behaves normally.
                self._suppress_back_dwell = False
                self._suppress_folder_dwell = False
                self.update()
            return

        angle = math.degrees(math.atan2(dy, dx)) - ANGLE_OFFSET
        if angle < 0:
            angle += 360

        slot = int(angle / SEGMENT_ANGLE) % NUM_SLOTS
        if slot != self._hovered_slot:
            prev = self._hovered_slot
            self._hovered_slot = slot
            self._folder_dwell_timer.stop()
            # Clear suppression flags once the user moves to a genuinely
            # different slot (not the first re-evaluation after reset_hover
            # where prev == -1).
            if prev != -1:
                self._suppress_back_dwell = False
                self._suppress_folder_dwell = False
            # Start dwell timer if hovering a folder or back slot
            if slot < len(self._slots):
                slot_data = self._slots[slot]
                slot_type = slot_data.get("type")
                if slot_type == "folder" and not self._suppress_folder_dwell:
                    # Use extended dwell for auto-continuation (prev == -1
                    # means this is the first evaluation after a folder
                    # transition via reset_hover).
                    if prev == -1 and self._auto_continue_extra_ms > 0:
                        self._folder_dwell_timer.setInterval(
                            self._dwell_ms + self._auto_continue_extra_ms)
                    else:
                        self._folder_dwell_timer.setInterval(self._dwell_ms)
                    self._folder_dwell_timer.start()
                elif slot_type == "back" and not self._suppress_back_dwell:
                    self._folder_dwell_timer.setInterval(self._dwell_ms)
                    self._folder_dwell_timer.start()
            self.update()

    def _on_folder_dwell(self):
        """Called when the mouse has hovered over a folder or back slot long enough."""
        if 0 <= self._hovered_slot < NUM_SLOTS:
            slot_data = self._slots[self._hovered_slot]
            if slot_data.get("type") in ("folder", "back"):
                self.folder_hovered.emit(self._hovered_slot)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw each segment
        for i in range(NUM_SLOTS):
            self._draw_segment(painter, i)

        # Draw inner circle (dead zone)
        painter.setBrush(QColor(20, 20, 20, 240))
        painter.setPen(QPen(self._border_color, 1.5))
        painter.drawEllipse(self._center, int(self._inner_radius), int(self._inner_radius))

        # Centre content (current folder: same icon/label rules as segments)
        if self._centre_slot:
            self._draw_centre_content(painter)

        # Draw settings button
        self._draw_settings_button(painter)

        painter.end()

    def _draw_settings_button(self, painter):
        cx = self._settings_btn_center.x()
        cy = self._settings_btn_center.y()

        # Fill
        if self._settings_hovered:
            painter.setBrush(self._hover_color)
        else:
            painter.setBrush(QColor(60, 60, 65, 200))
        painter.setPen(QPen(self._border_color, 1.5))
        painter.drawEllipse(
            QPoint(cx, cy), SETTINGS_BTN_RADIUS, SETTINGS_BTN_RADIUS
        )

        # Gear icon
        painter.setPen(self._text_color)
        gear_font = QFont("Sans", 14)
        painter.setFont(gear_font)
        fm = QFontMetrics(gear_font)
        tw = fm.horizontalAdvance(SETTINGS_GEAR)
        painter.drawText(int(cx - tw / 2), int(cy + fm.ascent() / 2 - 1), SETTINGS_GEAR)

    def _draw_centre_content(self, painter):
        """Draw centre content (current folder) using same icon/label rules as segments."""
        slot_data = self._centre_slot
        icon = slot_data.get("icon")
        icon_type = slot_data.get("icon_type")
        show_label = slot_data.get("show_label", True)
        label = slot_data.get("label", "")
        has_icon = icon and icon_type

        lx = self._center.x()
        ly = self._center.y()
        icon_size = 20
        font = QFont("Sans", max(7, self._font_size - 1))
        font.setBold(True)
        painter.setFont(font)
        fm = QFontMetrics(font)
        max_width = int((self._inner_radius - 8) * 2)

        lines = []
        if show_label and label:
            words = label.split()
            current = ""
            for w in words:
                test = (current + " " + w).strip() if current else w
                if fm.horizontalAdvance(test) > max_width and current:
                    lines.append(current)
                    current = w
                else:
                    current = test
            if current:
                lines.append(current)
            lines = lines[:2]

        text_height = len(lines) * fm.height() if lines else 0
        spacing = 2 if (has_icon and lines) else 0
        total_height = (icon_size if has_icon else 0) + spacing + text_height
        top_y = ly - total_height / 2

        if has_icon:
            if icon_type == "emoji":
                emoji_font = QFont("Sans", 14)
                painter.setFont(emoji_font)
                efm = QFontMetrics(emoji_font)
                ew = efm.horizontalAdvance(icon)
                painter.setPen(self._text_color)
                painter.drawText(int(lx - ew / 2), int(top_y + efm.ascent()), icon)
                painter.setFont(font)
            elif icon_type == "image" and os.path.exists(icon):
                pixmap = QPixmap(icon).scaled(
                    icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                painter.drawPixmap(
                    int(lx - pixmap.width() / 2),
                    int(top_y),
                    pixmap
                )
            top_y += icon_size + spacing

        if lines:
            painter.setPen(self._text_color)
            ty = top_y
            for line in lines:
                tw = fm.horizontalAdvance(line)
                painter.drawText(int(lx - tw / 2), int(ty + fm.ascent()), line)
                ty += fm.height()

    def _draw_segment(self, painter, index):
        start_angle = ANGLE_OFFSET + index * SEGMENT_ANGLE
        slot_data = self._slots[index] if index < len(self._slots) else {}
        slot_type = slot_data.get("type")
        is_hovered = index == self._hovered_slot

        # Build the segment path
        path = QPainterPath()
        rect_outer = QRectF(
            self._center.x() - self._wheel_radius,
            self._center.y() - self._wheel_radius,
            self._wheel_radius * 2,
            self._wheel_radius * 2
        )
        rect_inner = QRectF(
            self._center.x() - self._inner_radius,
            self._center.y() - self._inner_radius,
            self._inner_radius * 2,
            self._inner_radius * 2
        )

        path.arcMoveTo(rect_outer, -start_angle)
        path.arcTo(rect_outer, -start_angle, -SEGMENT_ANGLE)
        path.arcTo(rect_inner, -(start_angle + SEGMENT_ANGLE), SEGMENT_ANGLE)
        path.closeSubpath()

        # Fill
        if is_hovered:
            painter.setBrush(self._hover_color)
        elif slot_type == "back":
            painter.setBrush(self._back_color)
        else:
            painter.setBrush(self._segment_color)

        painter.setPen(QPen(self._border_color, 1.5))
        painter.drawPath(path)

        # Tabbed effect for folder and back segments: extra arcs at the outer edge
        if slot_type in ("folder", "back"):
            painter.setBrush(Qt.NoBrush)
            step = 5
            for i in (1, 2):
                r = self._wheel_radius - i * step
                rect_tab = QRectF(
                    self._center.x() - r, self._center.y() - r, r * 2, r * 2
                )
                painter.drawArc(
                    rect_tab,
                    int(-start_angle * 16),
                    int(-SEGMENT_ANGLE * 16),
                )

        # Draw icon and/or label
        mid_angle_deg = start_angle + SEGMENT_ANGLE / 2
        mid_angle = math.radians(mid_angle_deg)
        label_radius = (self._wheel_radius + self._inner_radius) / 2
        lx = self._center.x() + label_radius * math.cos(mid_angle)
        ly = self._center.y() + label_radius * math.sin(mid_angle)

        icon = slot_data.get("icon")
        icon_type = slot_data.get("icon_type")
        show_label = slot_data.get("show_label", True)
        label = slot_data.get("label", "")
        has_icon = icon and icon_type

        # Calculate content dimensions
        icon_size = 24
        font = QFont("Sans", self._font_size)
        font.setBold(is_hovered)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Prepare label lines
        lines = []
        if show_label and label:
            words = label.split()
            current = ""
            max_width = int((self._wheel_radius - self._inner_radius) * 0.75)
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

        text_height = len(lines) * fm.height() if lines else 0
        spacing = 2 if (has_icon and lines) else 0
        total_height = (icon_size if has_icon else 0) + spacing + text_height
        top_y = ly - total_height / 2

        # Draw icon
        if has_icon:
            if icon_type == "emoji":
                emoji_font = QFont("Sans", 16)
                painter.setFont(emoji_font)
                efm = QFontMetrics(emoji_font)
                ew = efm.horizontalAdvance(icon)
                painter.setPen(self._text_color)
                painter.drawText(int(lx - ew / 2), int(top_y + efm.ascent()), icon)
                painter.setFont(font)
            elif icon_type == "image" and os.path.exists(icon):
                pixmap = QPixmap(icon).scaled(
                    icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                painter.drawPixmap(
                    int(lx - pixmap.width() / 2),
                    int(top_y),
                    pixmap
                )
            top_y += icon_size + spacing

        # Draw label text
        if lines:
            if slot_type is None:
                painter.setPen(self._unset_text_color)
            else:
                painter.setPen(self._text_color)

            ty = top_y
            for line in lines:
                tw = fm.horizontalAdvance(line)
                painter.drawText(int(lx - tw / 2), int(ty + fm.ascent()), line)
                ty += fm.height()
        elif not has_icon:
            # No icon and no label — show default unset text
            if slot_type is None:
                painter.setPen(self._unset_text_color)
                default_text = "Select to add action"
                words = default_text.split()
                current = ""
                max_width = int((self._wheel_radius - self._inner_radius) * 0.75)
                fallback_lines = []
                for w in words:
                    test = (current + " " + w).strip()
                    if fm.horizontalAdvance(test) > max_width and current:
                        fallback_lines.append(current)
                        current = w
                    else:
                        current = test
                if current:
                    fallback_lines.append(current)
                fallback_lines = fallback_lines[:2]
                fh = len(fallback_lines) * fm.height()
                fty = ly - fh / 2
                for line in fallback_lines:
                    tw = fm.horizontalAdvance(line)
                    painter.drawText(int(lx - tw / 2), int(fty + fm.ascent()), line)
                    fty += fm.height()
