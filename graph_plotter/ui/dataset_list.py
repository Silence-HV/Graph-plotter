"""Liste der Datensätze (linke Seitenleiste)."""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QEvent, QModelIndex, QRect, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QColorDialog, QListView, QStyle,
                               QStyledItemDelegate, QStyleOptionViewItem)

from ..model import DEFAULT_COLORS, Dataset
from . import icons, theme

ROW_HEIGHT = 46
EYE_SIZE = 18


def _count(n: int) -> str:
    return f"{n:,}".replace(",", ".")


class DatasetModel(QAbstractListModel):
    """Listenmodell über die (vom Hauptfenster gehaltene) Liste der Datensätze."""

    DatasetRole = Qt.ItemDataRole.UserRole + 1
    edited = Signal()  # Sichtbarkeit oder Farbe in der Liste geändert

    def __init__(self, datasets: list[Dataset], parent=None):
        super().__init__(parent)
        self.datasets = datasets

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.datasets)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.datasets):
            return None
        ds = self.datasets[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return ds.display_label
        if role == self.DatasetRole:
            return ds
        if role == Qt.ItemDataRole.ToolTipRole:
            lines = []
            if ds.spec is not None:
                lines.append(ds.spec.path)
                if ds.spec.sheet:
                    lines.append(f"Tabellenblatt: {ds.spec.sheet}")
            lines.append(f"{_count(ds.n_points)} Punkte")
            if ds.is_combined:
                lines.append(f"Zusammengefasst aus {len(ds.members)} Datensätzen:")
                lines += [f"  {m.path}" for m in ds.members]
            elif ds.is_statistics:
                lines.append(f"Statistik über {ds.n_repeats} Messwiederholungen")
            return "\n".join(lines)
        return None

    def color_of(self, row: int) -> str:
        ds = self.datasets[row]
        return ds.color or DEFAULT_COLORS[row % len(DEFAULT_COLORS)]

    def refresh(self) -> None:
        self.beginResetModel()
        self.endResetModel()

    def row_changed(self, row: int) -> None:
        index = self.index(row)
        self.dataChanged.emit(index, index)

    def toggle_visible(self, row: int) -> None:
        self.datasets[row].visible = not self.datasets[row].visible
        self.row_changed(row)
        self.edited.emit()

    def set_color(self, row: int, color: str) -> None:
        self.datasets[row].color = color
        self.row_changed(row)
        self.edited.emit()


class DatasetDelegate(QStyledItemDelegate):
    """Zeichnet eine Zeile: [Auge] [Farbpunkt] Name / Infozeile."""

    colorClicked = Signal(int)

    @staticmethod
    def _eye_rect(rect: QRect) -> QRect:
        return QRect(rect.left() + 10, rect.center().y() - EYE_SIZE // 2, EYE_SIZE, EYE_SIZE)

    @staticmethod
    def _dot_rect(rect: QRect) -> QRect:
        return QRect(rect.left() + 38, rect.center().y() - 7, 14, 14)

    def sizeHint(self, option, index) -> QSize:
        return QSize(200, ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        c = theme.colors()
        model: DatasetModel = index.model()
        ds: Dataset = index.data(DatasetModel.DatasetRole)
        rect = option.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(c["selection"] if selected else c["hover"]))
            painter.drawRoundedRect(rect.adjusted(4, 2, -4, -2), 6, 6)

        # Auge (Sichtbarkeit)
        eye = icons.icon("eye" if ds.visible else "eye_off", c["text"] if ds.visible else c["muted"])
        eye.paint(painter, self._eye_rect(rect))

        # Farbpunkt
        painter.setPen(QPen(QColor(0, 0, 0, 60), 1))
        color = QColor(model.color_of(index.row()))
        if not ds.visible:
            color.setAlpha(90)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(self._dot_rect(rect))

        # Texte
        text_left = rect.left() + 62
        text_width = rect.width() - 62 - 10
        name_font = QFont(option.font)
        name_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(name_font)
        painter.setPen(QColor(c["text"] if ds.visible else c["muted"]))
        name_rect = QRect(text_left, rect.top() + 5, text_width, rect.height() // 2)
        name = painter.fontMetrics().elidedText(ds.display_label, Qt.TextElideMode.ElideMiddle, text_width)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        info = [f"{_count(ds.n_points)} Punkte"]
        if ds.is_combined:
            info.append(f"zusammengefasst, n = {ds.n_repeats}")
        elif ds.is_statistics:
            info.append(f"n = {ds.n_repeats}")
        if ds.axis == "Y2":
            info.append("Y2")
        if ds.fit and ds.fit != "none":
            info.append("Fit")
        if not ds.visible:
            info.append("ausgeblendet")
        small = QFont(option.font)
        small.setPointSizeF(max(7.0, option.font.pointSizeF() - 1))
        painter.setFont(small)
        painter.setPen(QColor(c["muted"]))
        info_rect = QRect(text_left, rect.top() + rect.height() // 2, text_width, rect.height() // 2 - 5)
        painter.drawText(info_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, " · ".join(info))
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            if self._eye_rect(option.rect).adjusted(-4, -4, 4, 4).contains(pos):
                model.toggle_visible(index.row())
                return True
            if self._dot_rect(option.rect).adjusted(-4, -4, 4, 4).contains(pos):
                self.colorClicked.emit(index.row())
                return True
        return super().editorEvent(event, model, option, index)


class DatasetListView(QListView):
    """Listenansicht mit Hinweis, solange keine Daten geladen sind."""

    def __init__(self, model: DatasetModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.delegate = DatasetDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.delegate.colorClicked.connect(self._choose_color)

    def _choose_color(self, row: int) -> None:
        model: DatasetModel = self.model()
        color = QColorDialog.getColor(QColor(model.color_of(row)), self, "Farbe auswählen")
        if color.isValid():
            model.set_color(row, color.name())

    def selected_rows(self) -> list[int]:
        return sorted(index.row() for index in self.selectionModel().selectedRows())

    def select_rows(self, rows: list[int]) -> None:
        selection = self.selectionModel()
        selection.clearSelection()
        for row in rows:
            index = self.model().index(row)
            selection.select(index, selection.SelectionFlag.Select | selection.SelectionFlag.Rows)
        if rows:
            selection.setCurrentIndex(self.model().index(rows[0]), selection.SelectionFlag.NoUpdate)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.model().rowCount() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(QColor(theme.colors()["muted"]))
            painter.drawText(self.viewport().rect().adjusted(16, 16, -16, -16),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             "Noch keine Daten.\n\nCSV- oder Excel-Dateien hierher ziehen "
                             "oder über „+“ laden.")
            painter.end()
