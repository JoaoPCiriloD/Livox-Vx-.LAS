import shlex
import shutil
import json
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.core.tools import fastlio2_command, fastlio2_output_dir, pipeline_command
from ajr_desktop.settings import LOGO_PATH, PROJECT_ROOT

class CopyWorker(QObject):
    message = Signal(str)
    finished = Signal(bool, object)

    def __init__(self, session_paths, destination_path):
        super().__init__()
        self.session_paths = session_paths
        self.destination_path = destination_path

    def run(self):
        saved_paths = []
        try:
            for session_path in self.session_paths:
                saved_paths.append(self.copy_session_results(session_path))
        except OSError as exc:
            self.message.emit(f"Erro ao copiar resultados: {exc}")
            self.finished.emit(False, [])
            return

        self.finished.emit(True, saved_paths)

    def copy_session_results(self, session_path):
        target_path = self.destination_path / session_path.name
        target_path.mkdir(parents=True, exist_ok=True)

        copied_las_files = []
        map_files = self.fastlio_result_files(session_path)
        if map_files:
            for source_file in map_files:
                destination_file = target_path / source_file.name
                self.message.emit(f"Copiando: {source_file.name}")
                shutil.copy2(source_file, destination_file)
                if destination_file.suffix.lower() == ".las":
                    copied_las_files.append(destination_file)
            self.copy_fastlio_logs(session_path, target_path)
            self.message.emit(f"Resultados salvos em: {target_path}")
            return {
                "session_path": target_path,
                "las_files": copied_las_files,
            }

        output_path = session_path / "output"
        if output_path.exists():
            target_output = target_path / "output"
            target_output.mkdir(parents=True, exist_ok=True)

            for source_file in self.result_files(session_path, output_path):
                destination_file = target_output / source_file.name
                self.message.emit(f"Copiando: {source_file.name}")
                shutil.copy2(source_file, destination_file)
                if destination_file.suffix.lower() == ".las":
                    copied_las_files.append(destination_file)

        for filename in ("relatorio.md", "metrics.json"):
            source_file = session_path / filename
            if source_file.exists():
                shutil.copy2(source_file, target_path / filename)

        self.message.emit(f"Resultados salvos em: {target_path}")
        return {
            "session_path": target_path,
            "las_files": copied_las_files,
        }

    def fastlio_result_files(self, session_path):
        files = []
        files.extend(sorted(session_path.glob("*_fastlio2_map.las")))
        files.extend(sorted(session_path.glob("*_fastlio2_map.pcd")))
        return files

    def copy_fastlio_logs(self, session_path, target_path):
        logs_path = session_path / "logs"
        if logs_path.exists():
            shutil.copytree(logs_path, target_path / "logs", dirs_exist_ok=True)

    def result_files(self, session_path, output_path):
        files = []
        best_las = self.best_las_file(session_path, output_path)
        if best_las:
            files.append(best_las)

        files.extend(sorted(output_path.glob("*.csv")))
        files.extend(sorted(output_path.glob("*.ply")))
        return files

    def best_las_file(self, session_path, output_path):
        # The standard georeferenced LAS is the safest automatic preview.
        # LIO outputs can be visually misleading when IMU/timestamp quality is poor.
        priority_kinds = ("geo", "lio", "any")

        for kind in priority_kinds:
            matches = self.las_matches(output_path, kind)
            if matches:
                return matches[0]

        local_matches = sorted(output_path.glob("*.las"))
        return local_matches[0] if local_matches else None

    def las_matches(self, output_path, kind):
        if kind == "lio":
            pattern = "*_lio_geo.las"
        elif kind == "geo":
            pattern = "*_geo.las"
        else:
            pattern = "*.las"

        matches = []
        for path in sorted(output_path.glob(pattern)):
            stem = path.stem
            if "_local" in stem or "_deg" in stem:
                continue
            if kind == "geo" and "_lio" in stem:
                continue
            matches.append(path)
        return matches

    def lio_ready(self, session_path):
        metrics_path = session_path / "metrics.json"
        if not metrics_path.exists():
            return False

        try:
            metrics = json.loads(metrics_path.read_text())
        except (OSError, json.JSONDecodeError):
            return False

        values = metrics.get("metrics", metrics)
        return bool(values.get("lio_ready_inputs"))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.process = None
        self.copy_thread = None
        self.copy_worker = None
        self.last_output_paths = []

        self.setWindowTitle("AJR LiDAR Pipeline")
        self.setMinimumSize(1180, 760)

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Selecione ou cole o caminho da pasta do voo")

        self.browse_button = QPushButton("Selecionar")
        self.browse_button.clicked.connect(self.browse_folder)

        self.batch_checkbox = QCheckBox("Processar varias sessoes")
        self.batch_checkbox.setChecked(False)

        self.fastlio_checkbox = QCheckBox("Usar FAST-LIO2 Docker e gerar *_map.las")
        self.fastlio_checkbox.setChecked(True)

        self.run_button = QPushButton("Executar Pipeline")
        self.run_button.clicked.connect(self.run_pipeline)

        self.stop_button = QPushButton("Parar Pipeline")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_pipeline)

        self.clear_button = QPushButton("Limpar Log")
        self.clear_button.clicked.connect(self.clear_log)

        self.status_label = QLabel("Status: Pronto")
        self.status_label.setObjectName("statusLabel")

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("logOutput")

        self.setCentralWidget(self.build_layout())
        self.apply_styles()

    def build_layout(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("AJR LiDAR Pipeline")
        title.setObjectName("title")

        subtitle = QLabel("Reconstrucao FAST-LIO2, conversao LAS e abertura no CloudCompare")
        subtitle.setObjectName("subtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header_layout.addWidget(self.build_logo())
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self.build_config_panel(), 1)
        content.addWidget(self.build_log_panel(), 2)

        root_layout.addWidget(header)
        root_layout.addLayout(content)

        return root

    def build_logo(self):
        logo_label = QLabel()
        logo_label.setObjectName("logoLabel")
        logo_label.setFixedSize(82, 82)
        logo_label.setAlignment(Qt.AlignCenter)

        pixmap = QPixmap(str(LOGO_PATH))
        if not pixmap.isNull():
            logo_label.setPixmap(
                pixmap.scaled(
                    72,
                    72,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        else:
            logo_label.setText("RT")

        return logo_label

    def build_config_panel(self):
        panel = QGroupBox("Entrada e processamento")
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_input)
        folder_row.addWidget(self.browse_button)

        options_box = QGroupBox("Opcoes")
        options_layout = QVBoxLayout(options_box)
        options_layout.addWidget(self.fastlio_checkbox)
        options_layout.addWidget(self.batch_checkbox)

        info_box = QGroupBox("Saida")
        info_layout = QGridLayout(info_box)
        info_layout.addWidget(QLabel("FAST-LIO2:"), 0, 0)
        info_layout.addWidget(QLabel(str(PROJECT_ROOT / "fastlio2_output")), 0, 1)
        info_layout.addWidget(QLabel("Pipeline Python:"), 1, 0)
        info_layout.addWidget(QLabel(str(PROJECT_ROOT / "sessoes")), 1, 1)
        info_layout.addWidget(QLabel("CloudCompare:"), 2, 0)
        info_layout.addWidget(QLabel("Abrir automaticamente apos salvar"), 2, 1)

        actions = QHBoxLayout()
        actions.addWidget(self.run_button)
        actions.addWidget(self.stop_button)

        layout.addWidget(QLabel("Pasta de entrada"))
        layout.addLayout(folder_row)
        layout.addWidget(options_box)
        layout.addWidget(info_box)
        layout.addStretch()
        layout.addLayout(actions)
        layout.addWidget(self.clear_button, 0, Qt.AlignRight)

        return panel

    def build_log_panel(self):
        panel = QGroupBox("Log de execucao")
        layout = QVBoxLayout(panel)
        layout.addWidget(self.log_output)
        return panel

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta de entrada")
        if folder:
            self.folder_input.setText(folder)
            self.batch_checkbox.setChecked(self.detect_batch_mode(Path(folder)))

    def run_pipeline(self):
        folder = self.folder_input.text().strip()
        if not folder:
            self.log("Erro: selecione uma pasta antes de processar.")
            return

        folder_path = Path(folder)
        if not folder_path.exists():
            self.log(f"Erro: pasta nao encontrada: {folder}")
            return

        if not folder_path.is_dir():
            self.log(f"Erro: o caminho informado nao e uma pasta: {folder}")
            return

        if self.process and self.process.state() != QProcess.NotRunning:
            self.log("Erro: ja existe um processamento em andamento.")
            return

        use_fastlio = self.fastlio_checkbox.isChecked()
        if use_fastlio:
            lvx_file = self.find_lvx_file(folder_path)
            if not lvx_file:
                self.log(f"Erro: nenhum arquivo .lvx encontrado em {folder}")
                return
            if lvx_file.stat().st_size <= 0:
                self.log(f"Erro: arquivo .lvx vazio ou invalido: {lvx_file}")
                return
            if self.detect_batch_mode(folder_path):
                self.log("FAST-LIO2 no app processa uma sessao por vez. Selecione uma pasta de voo com um .lvx.")
                return

            session_name = self.session_name_for(folder_path)
            output_dir = fastlio2_output_dir(session_name)
            self.prepare_fastlio_output_dir(output_dir)
            command = fastlio2_command(lvx_file, output_dir)
            self.last_output_paths = [output_dir]
            batch_mode = False
        else:
            batch_mode = self.detect_batch_mode(folder_path)
            if batch_mode != self.batch_checkbox.isChecked():
                self.batch_checkbox.setChecked(batch_mode)

            command = pipeline_command(
                folder,
                batch=batch_mode,
                skip_cloudcompare=True,
            )
            self.last_output_paths = self.output_paths_for(folder_path, batch_mode)

        self.log_output.clear()
        if use_fastlio:
            self.log("Modo: FAST-LIO2 Docker")
            self.log("Saida esperada: *_fastlio2_map.las")
        elif batch_mode:
            self.log("Modo: varias sessoes (batch)")
        else:
            self.log("Modo: pipeline Python - sessao unica")
        self.log("Comando montado:")
        self.log(" ".join(shlex.quote(arg) for arg in command))
        self.log("")

        self.set_running_state(True)

        self.process = QProcess(self)
        self.process.setProgram(command[0])
        self.process.setArguments(command[1:])
        self.process.setWorkingDirectory(str(PROJECT_ROOT))

        self.process.readyReadStandardOutput.connect(self.read_stdout)
        self.process.readyReadStandardError.connect(self.read_stderr)
        self.process.finished.connect(self.process_finished)
        self.process.errorOccurred.connect(self.process_error)

        self.process.start()

    def read_stdout(self):
        data = self.process.readAllStandardOutput().data().decode(errors="replace")
        if data:
            self.log(data.rstrip())

    def read_stderr(self):
        data = self.process.readAllStandardError().data().decode(errors="replace")
        if data:
            self.log(data.rstrip())

    def process_finished(self, exit_code, exit_status):
        self.log("")
        self.log(f"Codigo da saida: {exit_code}")

        if exit_code == 0:
            self.status_label.setText("Status: Finalizado com sucesso")
            self.set_running_state(False)
            self.prompt_save_results()
        else:
            self.status_label.setText("Status: Finalizado com erro")
            self.set_running_state(False)
 
    def process_error(self, error):
        self.log("")
        self.log(f"Erro ao executar processo: {error}")
        self.status_label.setText("Status: Erro ao iniciar")
        self.set_running_state(False)

    def stop_pipeline(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            self.log("")
            self.log("Parando processamento...")
            self.process.terminate()

            if not self.process.waitForFinished(3000):
                self.log("Processo nao encerrou normalmente. Forcando parada.")
                self.process.kill()

    def clear_log(self):
        self.log_output.clear()

    def session_name_for(self, folder_path):
        if folder_path.name.lower() == "input" and folder_path.parent.name:
            return folder_path.parent.name
        return folder_path.name

    def prepare_fastlio_output_dir(self, output_dir):
        if not output_dir.exists():
            return

        for pattern in ("*_fastlio2_map.las", "*_fastlio2_map.pcd"):
            for path in output_dir.glob(pattern):
                path.unlink(missing_ok=True)

    def output_paths_for(self, folder_path, batch_mode):
        sessions_dir = PROJECT_ROOT / "sessoes"
        if not batch_mode:
            return [sessions_dir / folder_path.name]

        session_paths = []
        for child in sorted(folder_path.iterdir()):
            if child.is_dir() and self.has_lvx_files(child):
                session_paths.append(sessions_dir / child.name)
        return session_paths

    def prompt_save_results(self):
        existing_outputs = [path for path in self.last_output_paths if path.exists()]
        if not existing_outputs:
            self.log("Saida nao encontrada para copiar.")
            return

        destination = QFileDialog.getExistingDirectory(
            self,
            "Escolha onde salvar os resultados",
        )
        if not destination:
            self.log("Copia dos resultados cancelada.")
            return

        destination_path = Path(destination)
        sessions_dir = PROJECT_ROOT / "sessoes"
        if self.path_inside(destination_path, sessions_dir):
            self.log("Escolha uma pasta fora da pasta interna 'sessoes' para evitar copia recursiva.")
            return

        self.start_copy(existing_outputs, destination_path)

    def start_copy(self, session_paths, destination_path):
        self.status_label.setText("Status: Copiando resultados...")
        self.run_button.setEnabled(False)
        self.clear_button.setEnabled(False)

        self.copy_thread = QThread(self)
        self.copy_worker = CopyWorker(session_paths, destination_path)
        self.copy_worker.moveToThread(self.copy_thread)

        self.copy_thread.started.connect(self.copy_worker.run)
        self.copy_worker.message.connect(self.log)
        self.copy_worker.finished.connect(self.copy_finished)
        self.copy_worker.finished.connect(self.copy_thread.quit)
        self.copy_worker.finished.connect(self.copy_worker.deleteLater)
        self.copy_thread.finished.connect(self.copy_thread.deleteLater)

        self.copy_thread.start()

    def copy_finished(self, success, saved_paths):
        if success:
            self.status_label.setText("Status: Resultados salvos")
            self.open_saved_results_in_cloudcompare(saved_paths)
        else:
            self.status_label.setText("Status: Erro ao salvar")

        self.run_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.copy_thread = None
        self.copy_worker = None

    def open_saved_results_in_cloudcompare(self, saved_results):
        las_files = []
        for result in saved_results:
            las_files.extend(result.get("las_files", []))

        if not las_files:
            self.log("Nenhum arquivo LAS salvo foi encontrado para abrir no CloudCompare.")
            return

        command = self.cloudcompare_command(las_files)
        if not command:
            self.log("CloudCompare nao encontrado. Abra manualmente os arquivos LAS salvos.")
            return

        self.log("Abrindo resultados no CloudCompare:")
        for las_file in las_files:
            self.log(str(las_file))

        started = QProcess.startDetached(command[0], command[1:], str(PROJECT_ROOT))
        if not started:
            self.log("Nao foi possivel iniciar o CloudCompare automaticamente.")

    def cloudcompare_command(self, las_files):
        las_args = [str(path) for path in las_files]

        cloudcompare_path = shutil.which("cloudcompare")
        if cloudcompare_path:
            return [cloudcompare_path, *las_args]

        flatpak_path = shutil.which("flatpak")
        if flatpak_path:
            return [flatpak_path, "run", "org.cloudcompare.CloudCompare", *las_args]

        return None

    def path_inside(self, path, parent):
        try:
            path.resolve().relative_to(parent.resolve())
            return True
        except ValueError:
            return False

    def detect_batch_mode(self, folder_path):
        if self.has_lvx_files(folder_path):
            return False

        try:
            for child in folder_path.iterdir():
                if child.is_dir() and self.has_lvx_files(child):
                    return True
        except OSError:
            return self.batch_checkbox.isChecked()

        return self.batch_checkbox.isChecked()

    def has_lvx_files(self, folder_path):
        try:
            return any(folder_path.glob("*.lvx"))
        except OSError:
            return False

    def find_lvx_file(self, folder_path):
        try:
            lvx_files = sorted(
                folder_path.glob("*.lvx"),
                key=lambda path: path.stat().st_size,
                reverse=True,
            )
        except OSError:
            return None

        return lvx_files[0] if lvx_files else None

    def set_running_state(self, running):
        self.run_button.setEnabled(not running)
        self.browse_button.setEnabled(not running)
        self.folder_input.setEnabled(not running)
        self.fastlio_checkbox.setEnabled(not running)
        self.batch_checkbox.setEnabled(not running)
        self.stop_button.setEnabled(running)

        if running:
            self.status_label.setText("Status: Processando...")

    def log(self, message):
        self.log_output.appendPlainText(message)
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #f4f6f8;
            }

            QLabel {
                color: #253041;
            }

            QFrame#header {
                background: #ffffff;
                border: 1px solid #d9dee5;
                border-radius: 8px;
            }

            QLabel#logoLabel {
                background: #ffffff;
                border: 1px solid #d9dee5;
                border-radius: 8px;
            }

            QLabel#title {
                color: #17212f;
                font-size: 22px;
                font-weight: 700;
            }

            QLabel#subtitle {
                color: #475467;
                font-size: 13px;
            }

            QLabel#statusLabel {
                background: #eef6ff;
                color: #175cd3;
                border: 1px solid #b2ddff;
                border-radius: 6px;
                padding: 6px 10px;
                font-weight: 600;
            }

            QGroupBox {
                background: #ffffff;
                border: 1px solid #d9dee5;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
                font-weight: 600;
                color: #253041;
            }

            QGroupBox QLabel {
                color: #344054;
                font-weight: 400;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }

            QLineEdit {
                border: 1px solid #c8d0da;
                border-radius: 6px;
                padding: 8px;
                background: #ffffff;
                color: #17212f;
                selection-background-color: #1f6feb;
                selection-color: #ffffff;
            }

            QLineEdit:disabled {
                background: #f8fafc;
                color: #475467;
            }

            QPushButton {
                background: #1f6feb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #1959c9;
            }

            QPushButton:disabled {
                background: #d0d5dd;
                color: #667085;
            }

            QPlainTextEdit#logOutput {
                background: #101828;
                color: #d0d5dd;
                border: 1px solid #1d2939;
                border-radius: 8px;
                padding: 10px;
                font-family: monospace;
                font-size: 12px;
            }

            QCheckBox {
                color: #344054;
                spacing: 8px;
            }

            QCheckBox:disabled {
                color: #667085;
            }

            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border: 1px solid #98a2b3;
                border-radius: 3px;
                background: #ffffff;
            }

            QCheckBox::indicator:checked {
                background: #1f6feb;
                border-color: #1f6feb;
            }
        """)
