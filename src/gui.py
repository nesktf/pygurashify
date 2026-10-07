#!/usr/bin/env python3
import sys
from typing import Optional
from pathlib import Path
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QImage, QPixmap, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QSlider,
    QCheckBox,
    QFileDialog,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QSizePolicy,
    QMessageBox,
)

from higurashifier import (
    AspectMode,
    BlurOpts,
    EdgeOpts,
    EdgeMethod,
    ProcessOpts,
    preprocess_image,
    process_array,
)


class ImageProcessorThread(QThread):
    finished = Signal(int, QImage, object)
    error = Signal(int, str)
    generation_id: int
    pil_image: Image.Image
    opts: ProcessOpts

    def __init__(
        self, generation_id: int, pil_image: Image.Image, opts: ProcessOpts, parent=None
    ):
        super().__init__(parent)
        self.generation_id = generation_id
        self.pil_image = pil_image.copy()
        self.opts = opts

    def run(self):
        try:
            img = preprocess_image(
                self.pil_image.convert("RGB"),
                self.opts.aspect_mode,
                self.opts.max_height,
            )
            pixels = np.array(img, dtype=np.float64)
            result_array = process_array(pixels, self.opts)

            h, w, ch = result_array.shape
            bytes_per_line = ch * w
            qimg = QImage(
                result_array.data, w, h, bytes_per_line, QImage.Format_RGB888
            ).copy()
            out_pil = Image.fromarray(result_array, mode="RGB")

            self.finished.emit(self.generation_id, qimg, out_pil)
        except Exception as exc:
            self.error.emit(self.generation_id, str(exc))


class AspectImageLabel(QLabel):
    pixmap_source: Optional[QPixmap] = None
    placeholder_text: str

    def __init__(self, placeholder_text: str, parent=None):
        super().__init__(parent)
        self.placeholder_text = placeholder_text
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(240, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(
            "QLabel { background-color: #121212; color: #9e9e9e; "
            "border: 1px solid #333333; border-radius: 6px; font-size: 13px; }"
        )
        self.setText(self.placeholder_text)

    def _update_scaled_pixmap(self):
        if self.pixmap_source and not self.pixmap_source.isNull():
            scaled = self.pixmap_source.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            super().setPixmap(scaled)

    def set_display_pixmap(self, pixmap: Optional[QPixmap]):
        self.pixmap_source = pixmap
        if self.pixmap_source is None:
            self.setText(self.placeholder_text)
        else:
            self.setText("")
            self._update_scaled_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()


class ClickableImageLabel(AspectImageLabel):
    clicked = Signal()

    def __init__(self, placeholder_text: str, parent=None):
        super().__init__(placeholder_text, parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    current_pil_image: Optional[Image.Image] = None
    processed_pil_image: Optional[Image.Image] = None
    current_worker: Optional[ImageProcessorThread] = None
    generation_id: int = 0
    left_label: ClickableImageLabel
    right_label: AspectImageLabel
    debounce_timer: QTimer
    progress_bar: QProgressBar
    status_label: QLabel
    btn_save: QPushButton
    group_contrast: QGroupBox
    group_unsharp: QGroupBox
    group_posterize: QGroupBox
    group_blur: QGroupBox
    group_edge: QGroupBox
    spin_max_height: QSpinBox
    spin_posterize: QSpinBox
    spin_contrast: QDoubleSpinBox
    spin_blur_angle: QDoubleSpinBox
    spin_blur_radius: QSpinBox
    spin_blur_opacity: QDoubleSpinBox
    spin_edge_thresh: QDoubleSpinBox
    spin_edge_opacity: QDoubleSpinBox
    check_edge_invert: QCheckBox
    combo_edge_method: QComboBox

    def _on_param_changed(self):
        if self.current_pil_image is not None:
            self.progress_bar.show()
            self.debounce_timer.start()

    def _collect_process_opts(self) -> ProcessOpts:
        aspect_map = {
            "4:3": AspectMode.ASPECT_4_3,
            "16:9": AspectMode.ASPECT_16_9,
            "1:1": AspectMode.ASPECT_1_1,
            "original": AspectMode.ASPECT_ORIGINAL,
        }
        aspect_mode = aspect_map.get(
            self.combo_aspect.currentText(), AspectMode.ASPECT_ORIGINAL
        )
        max_height = self.spin_max_height.value() or None

        white_level = (
            self.spin_contrast.value() if self.group_contrast.isChecked() else None
        )
        unsharpening = (
            self.spin_unsharp.value() if self.group_unsharp.isChecked() else None
        )
        posterize_levels = (
            self.spin_posterize.value() if self.group_posterize.isChecked() else None
        )

        blur_opts = None
        if self.group_blur.isChecked():
            blur_opts = BlurOpts(
                radius=self.spin_blur_radius.value(),
                angle=self.spin_blur_angle.value(),
                opacity=self.spin_blur_opacity.value(),
            )

        edge_opts = None
        if self.group_edge.isChecked():
            method_map = {
                "prewitt": EdgeMethod.PREWITT,
                "laplacian": EdgeMethod.LAPLACIAN,
                "roberts": EdgeMethod.ROBERTS,
                "sobel": EdgeMethod.SOBEL,
            }
            edge_opts = EdgeOpts(
                method=method_map.get(
                    self.combo_edge_method.currentText(), EdgeMethod.SOBEL
                ),
                threshold=self.spin_edge_thresh.value(),
                opacity=self.spin_edge_opacity.value(),
                invert=self.check_edge_invert.isChecked(),
            )

        return ProcessOpts(
            aspect_mode=aspect_mode,
            max_height=max_height,
            white_level=white_level,
            unsharpening=unsharpening,
            posterize_levels=posterize_levels,
            blur=blur_opts,
            edges=edge_opts,
        )

    def _start_processing(self):
        if self.current_pil_image is None:
            return

        self.generation_id += 1
        opts = self._collect_process_opts()

        self.progress_bar.show()
        self.status_label.setText("Processing image...")

        def on_finish(gen_id: int, qimg: QImage, out_pil: Image.Image):
            if gen_id != self.generation_id:
                return

            self.processed_pil_image = out_pil
            pixmap = QPixmap.fromImage(qimg)
            self.right_label.set_display_pixmap(pixmap)
            self.progress_bar.hide()
            self.btn_save.setEnabled(True)
            self.status_label.setText(f"Ready ({out_pil.width}x{out_pil.height})")

        def on_error(gen_id: int, error_msg: str):
            if gen_id != self.generation_id:
                return

            self.progress_bar.hide()
            self.status_label.setText(f"Error: {error_msg}")
            QMessageBox.critical(self, "Processing Error", error_msg)

        self.current_worker = ImageProcessorThread(
            self.generation_id, self.current_pil_image, opts, parent=self
        )
        self.current_worker.finished.connect(on_finish)
        self.current_worker.error.connect(on_error)
        self.current_worker.start()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("pygurashify - Higurashi Style Filter")
        self.resize(1020, 800)
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 2px;
                margin-top: 10px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 0 4px;
            }
            QGroupBox:disabled, QGroupBox:unchecked {
                border-color: #444444;
                color: #555555;
            }
            QGroupBox::title:disabled, QGroupBox::title:unchecked {
                color: #555555;
            }
            """)

        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(300)
        self.debounce_timer.timeout.connect(self._start_processing)

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(12, 12, 12, 12)
        central_layout.setSpacing(8)

        main_splitter = QSplitter(Qt.Vertical)
        central_layout.addWidget(main_splitter, 1)

        # image view panel
        image_panel = QWidget()
        img_layout = QHBoxLayout(image_panel)
        img_layout.setContentsMargins(0, 0, 0, 0)
        img_layout.setSpacing(12)

        def select_input_image():
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Image",
                "",
                "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff);;All Files (*)",
            )
            if not path:
                return

            try:
                pil_img = Image.open(path)
                pil_img.load()
                self.current_pil_image = pil_img
                self.left_label.set_display_pixmap(QPixmap(path))
                self.status_label.setText(
                    f"Loaded: {Path(path).name} ({pil_img.width}x{pil_img.height})"
                )
                self._on_param_changed()
            except Exception as err:
                QMessageBox.critical(self, "Error opening image", str(err))

        # original image
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_header = QLabel("Original")
        left_header.setAlignment(Qt.AlignCenter)
        self.left_label = ClickableImageLabel("Click here to load an image")
        self.left_label.clicked.connect(select_input_image)
        left_layout.addWidget(left_header)
        left_layout.addWidget(self.left_label)

        # result image
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_header = QLabel("Processed Result")
        right_header.setAlignment(Qt.AlignCenter)
        self.right_label = AspectImageLabel("Processed image will appear here")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()

        right_layout.addWidget(right_header)
        right_layout.addWidget(self.right_label)
        right_layout.addWidget(self.progress_bar)

        img_layout.addWidget(left_container, 1)
        img_layout.addWidget(right_container, 1)
        main_splitter.addWidget(image_panel)

        # controls panel
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_container = QWidget()
        controls_grid = QGridLayout(controls_container)
        controls_grid.setContentsMargins(12, 8, 12, 8)
        controls_grid.setSpacing(6)

        # preprocessing
        group_prep = QGroupBox("Preprocessing")
        prep_layout = QGridLayout(group_prep)

        prep_layout.addWidget(QLabel("Aspect Ratio:"), 0, 0)
        self.combo_aspect = QComboBox()
        self.combo_aspect.addItems(["original", "4:3", "16:9", "1:1"])
        self.combo_aspect.currentIndexChanged.connect(self._on_param_changed)
        prep_layout.addWidget(self.combo_aspect, 0, 1, 1, 2)

        prep_layout.addWidget(QLabel("Max Height (0=off):"), 1, 0)
        self.spin_max_height = QSpinBox()
        self.spin_max_height.setRange(0, 4000)
        self.spin_max_height.setValue(1080)
        self.spin_max_height.setSingleStep(60)
        self.spin_max_height.valueChanged.connect(self._on_param_changed)
        btn_reset_height = QPushButton("R")
        btn_reset_height.setToolTip("Reset to default (1080)")
        btn_reset_height.setFixedWidth(24)
        btn_reset_height.clicked.connect(lambda: self.spin_max_height.setValue(1080))
        prep_layout.addWidget(self.spin_max_height, 1, 1)
        prep_layout.addWidget(btn_reset_height, 1, 2)

        def int_slider(min_val: int, max_val: int, default_val: int):
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default_val)

            spin = QSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(default_val)

            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            spin.valueChanged.connect(self._on_param_changed)

            btn = QPushButton("R")
            btn.setToolTip(f"Reset to default ({default_val})")
            btn.setFixedWidth(24)
            btn.clicked.connect(lambda: spin.setValue(default_val))

            return slider, spin, btn

        def float_slider(
            min_val: float,
            max_val: float,
            default_val: float,
            step: float,
            decimals: int,
            multiplier: int,
        ):
            slider = QSlider(Qt.Horizontal)
            slider.setRange(
                int(round(min_val * multiplier)), int(round(max_val * multiplier))
            )
            slider.setValue(int(round(default_val * multiplier)))

            spin = QDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setSingleStep(step)
            spin.setDecimals(decimals)
            spin.setValue(default_val)

            # connect synchronized changes without circular signal recursion
            slider.valueChanged.connect(lambda v: spin.setValue(v / multiplier))
            spin.valueChanged.connect(
                lambda v: slider.setValue(int(round(v * multiplier)))
            )
            spin.valueChanged.connect(self._on_param_changed)

            btn = QPushButton("R")
            btn.setToolTip(f"Reset to default ({default_val})")
            btn.setFixedWidth(24)
            btn.clicked.connect(lambda: spin.setValue(default_val))

            return slider, spin, btn

        # contrast
        self.group_contrast = QGroupBox("Contrast")
        self.group_contrast.setCheckable(True)
        self.group_contrast.setChecked(True)
        self.group_contrast.toggled.connect(self._on_param_changed)
        contrast_layout = QGridLayout(self.group_contrast)

        contrast_layout.addWidget(QLabel("White level (%):"), 0, 0)
        slider_contrast, self.spin_contrast, btn_reset_contrast = float_slider(
            50.1, 100.0, 85.0, step=0.5, decimals=1, multiplier=10
        )
        contrast_layout.addWidget(slider_contrast, 0, 1)
        contrast_layout.addWidget(self.spin_contrast, 0, 2)
        contrast_layout.addWidget(btn_reset_contrast, 0, 3)

        # blur
        self.group_blur = QGroupBox("Blur")
        self.group_blur.setCheckable(True)
        self.group_blur.setChecked(True)
        self.group_blur.toggled.connect(self._on_param_changed)
        blur_layout = QGridLayout(self.group_blur)

        blur_layout.addWidget(QLabel("Radius (px):"), 0, 0)
        slider_blur_radius, self.spin_blur_radius, btn_reset_blur_radius = int_slider(
            0, 30, 9
        )
        blur_layout.addWidget(slider_blur_radius, 0, 1)
        blur_layout.addWidget(self.spin_blur_radius, 0, 2)
        blur_layout.addWidget(btn_reset_blur_radius, 0, 3)

        blur_layout.addWidget(QLabel("Angle (deg):"), 1, 0)
        slider_blur_angle, self.spin_blur_angle, btn_reset_blur_angle = float_slider(
            -90.0, 90.0, -25.0, step=1.0, decimals=1, multiplier=10
        )
        blur_layout.addWidget(slider_blur_angle, 1, 1)
        blur_layout.addWidget(self.spin_blur_angle, 1, 2)
        blur_layout.addWidget(btn_reset_blur_angle, 1, 3)

        blur_layout.addWidget(QLabel("Opacity:"), 2, 0)
        slider_blur_opacity, self.spin_blur_opacity, btn_reset_blur_opacity = (
            float_slider(0.0, 1.0, 0.7, step=0.05, decimals=2, multiplier=100)
        )
        blur_layout.addWidget(slider_blur_opacity, 2, 1)
        blur_layout.addWidget(self.spin_blur_opacity, 2, 2)
        blur_layout.addWidget(btn_reset_blur_opacity, 2, 3)

        # edge detection
        self.group_edge = QGroupBox("Edge Detection")
        self.group_edge.setCheckable(True)
        self.group_edge.setChecked(True)
        self.group_edge.toggled.connect(self._on_param_changed)
        edge_layout = QGridLayout(self.group_edge)

        edge_layout.addWidget(QLabel("Algorithm:"), 0, 0)
        self.combo_edge_method = QComboBox()
        self.combo_edge_method.addItems(["sobel", "prewitt", "laplacian", "roberts"])
        self.combo_edge_method.currentIndexChanged.connect(self._on_param_changed)
        edge_layout.addWidget(self.combo_edge_method, 0, 1, 1, 3)

        edge_layout.addWidget(QLabel("Threshold:"), 1, 0)
        slider_edge_thresh, self.spin_edge_thresh, btn_reset_edge_thresh = float_slider(
            0.0, 255.0, 80.0, step=1.0, decimals=1, multiplier=10
        )
        edge_layout.addWidget(slider_edge_thresh, 1, 1)
        edge_layout.addWidget(self.spin_edge_thresh, 1, 2)
        edge_layout.addWidget(btn_reset_edge_thresh, 1, 3)

        edge_layout.addWidget(QLabel("Opacity:"), 2, 0)
        slider_edge_opacity, self.spin_edge_opacity, btn_reset_edge_opacity = (
            float_slider(0.0, 1.0, 0.5, step=0.05, decimals=2, multiplier=100)
        )
        edge_layout.addWidget(slider_edge_opacity, 2, 1)
        edge_layout.addWidget(self.spin_edge_opacity, 2, 2)
        edge_layout.addWidget(btn_reset_edge_opacity, 2, 3)

        self.check_edge_invert = QCheckBox("Invert edge color (white on black)")
        self.check_edge_invert.setChecked(False)
        self.check_edge_invert.toggled.connect(self._on_param_changed)
        edge_layout.addWidget(self.check_edge_invert, 3, 0, 1, 4)

        # unsharpening
        self.group_unsharp = QGroupBox("Unsharpening")
        self.group_unsharp.setCheckable(True)
        self.group_unsharp.setChecked(True)
        self.group_unsharp.toggled.connect(self._on_param_changed)
        unsharp_layout = QGridLayout(self.group_unsharp)

        unsharp_layout.addWidget(QLabel("Amount:"), 0, 0)
        self.slider_unsharp, self.spin_unsharp, btn_reset_unsharp = float_slider(
            0.0, 3.0, 1.0, step=0.1, decimals=2, multiplier=100
        )
        unsharp_layout.addWidget(self.slider_unsharp, 0, 1)
        unsharp_layout.addWidget(self.spin_unsharp, 0, 2)
        unsharp_layout.addWidget(btn_reset_unsharp, 0, 3)

        # posterization
        self.group_posterize = QGroupBox("Posterization")
        self.group_posterize.setCheckable(True)
        self.group_posterize.setChecked(True)
        self.group_posterize.toggled.connect(self._on_param_changed)
        posterize_layout = QGridLayout(self.group_posterize)

        posterize_layout.addWidget(QLabel("Levels:"), 0, 0)
        slider_posterize, self.spin_posterize, btn_reset_posterize = int_slider(
            2, 20, 9
        )
        posterize_layout.addWidget(slider_posterize, 0, 1)
        posterize_layout.addWidget(self.spin_posterize, 0, 2)
        posterize_layout.addWidget(btn_reset_posterize, 0, 3)

        controls_grid.addWidget(group_prep, 0, 0)
        controls_grid.addWidget(self.group_contrast, 0, 1)
        controls_grid.addWidget(self.group_blur, 1, 0)
        controls_grid.addWidget(self.group_edge, 1, 1)
        controls_grid.addWidget(self.group_unsharp, 2, 0)
        controls_grid.addWidget(self.group_posterize, 2, 1)

        controls_scroll.setWidget(controls_container)
        main_splitter.addWidget(controls_scroll)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 2)

        def save_processed_image():
            if self.processed_pil_image is None:
                return

            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Processed Image",
                "higurashified.png",
                "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;All Files (*)",
            )
            if not path:
                return

            try:
                self.processed_pil_image.save(path)
                self.status_label.setText(f"Saved: {Path(path).name}")
            except Exception as err:
                QMessageBox.critical(self, "Save Error", str(err))

        bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 2, 0, 0)
        self.status_label = QLabel("Click on the left image to open a file.")
        self.btn_save = QPushButton("Save Processed Image")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(save_processed_image)
        bottom_layout.addWidget(self.status_label, 1)
        bottom_layout.addWidget(self.btn_save, 0)
        central_layout.addWidget(bottom_bar, 0)

        self.setCentralWidget(central_widget)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
