import sys
import html
import json
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTreeWidget, QTreeWidgetItem, QSlider, QStackedWidget, QComboBox, QCheckBox, QSizePolicy
from PyQt5.QtGui import QIcon, QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QTimer, QThread, QSize, pyqtSignal
import requests
import yt_dlp
import vlc

# Load API key from config.json
with open('config.json') as config_file:
    config = json.load(config_file)
    YOUTUBE_API_KEY = config.get('YOUTUBE_API_KEY')

current_stream = None
is_paused = False
update_progress = False
seeking = False

class SearchThread(QThread):
    search_results = pyqtSignal(list)

    def __init__(self, query, filter_enabled):
        QThread.__init__(self)
        self.query = query
        self.filter_enabled = filter_enabled

    def run(self):
        if self.filter_enabled:
            url = f'https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&maxResults=10&q={self.query}+music&key={YOUTUBE_API_KEY}'
        else:
            url = f'https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&maxResults=35&q={self.query}&key={YOUTUBE_API_KEY}'
        
        response = requests.get(url)
        data = response.json()
        results = []
        for item in data.get('items', []):
            title = html.unescape(item['snippet']['title'])
            if self.filter_enabled and not any(keyword in title.lower() for keyword in ['music', 'song', 'track', 'official video', 'lyrics']):
                continue
            video_id = item['id']['videoId']
            thumbnail_url = item['snippet']['thumbnails']['high']['url']
            results.append((title, video_id, thumbnail_url))
        self.search_results.emit(results)

class PlayerThread(QThread):
    play_signal = pyqtSignal(str)

    def __init__(self, video_id):
        QThread.__init__(self)
        self.video_id = video_id

    def run(self):
        global current_stream
        try:
            ydl_opts = {
                'format': 'bestaudio',
                'noplaylist': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(f'https://www.youtube.com/watch?v={self.video_id}', download=False)
                audio_url = info_dict['url']
                song_title = info_dict['title']
                current_stream = audio_url
                self.play_signal.emit(song_title)
        except Exception as e:
            print(f"Error: {e}")

class YouTufyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('YouTufy')
        self.setWindowIcon(QIcon('assets/YouTufy.png'))
        self.setGeometry(100, 100, 1200, 800)
        
        # Set the font to Roboto
        font = QFont("Roboto", 10)
        self.setFont(font)

        self.dark_theme_stylesheet = """
            QWidget {
                background-color: #1a1a1a;
                color: white;
                font-family: Roboto;
            }
            QTreeWidget {
                background-color: #1c1c1c;
                color: white;
            }
            QTreeWidget::item {
                height: 25px;
            }
            QHeaderView::section {
                background-color: #333333;
                color: white;
                font-weight: bold;
                padding: 4px;
                border: none;
            }
            QLabel {
                color: white;
            }
            QComboBox {
                border: none;
                background-color: #2a2a2a;
                color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
            QCheckBox {
                color: white;
            }
        """
        self.light_theme_stylesheet = """
            QWidget {
                background-color: #f0f0f0;
                color: black;
                font-family: Roboto;
            }
            QTreeWidget {
                background-color: white;
                color: black;
            }
            QTreeWidget::item {
                height: 25px;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                color: black;
                font-weight: bold;
                padding: 4px;
                border: none;
            }
            QLabel {
                color: black;
            }
            QComboBox {
                border: none;
                background-color: #e0e0e0;
                color: black;
            }
            QComboBox::drop-down {
                border: none;
            }
            QCheckBox {
                color: black;
            }
        """
        
        self.initUI()

    def initUI(self):
        self.current_video_id = None
        self.pending_video_id = None

        hbox_main = QHBoxLayout(self)
        
        # Stacked widget for pages
        self.stacked_widget = QStackedWidget()
        
        # Home Page
        self.home_page = QWidget()
        self.home_layout = QVBoxLayout(self.home_page)
        self.init_home_page()
        self.stacked_widget.addWidget(self.home_page)
        
        # Settings Page
        self.settings_page = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_page)
        self.init_settings_page()
        self.stacked_widget.addWidget(self.settings_page)
        
        hbox_main.addWidget(self.stacked_widget)
        
        # Sidebar
        vbox_sidebar = QVBoxLayout()
        vbox_sidebar.addStretch(1)
        self.home_button = QPushButton()
        self.settings_button = QPushButton()
        self.home_button.clicked.connect(self.show_home)
        self.settings_button.clicked.connect(self.show_settings)
        self.home_button.setStyleSheet("background: none; border: none;")
        self.settings_button.setStyleSheet("background: none; border: none;")
        
        vbox_sidebar.addWidget(self.home_button, alignment=Qt.AlignCenter)
        vbox_sidebar.addSpacing(20)
        vbox_sidebar.addWidget(self.settings_button, alignment=Qt.AlignCenter)
        vbox_sidebar.addStretch(1)
        
        hbox_main.addLayout(vbox_sidebar)
        
        self.setLayout(hbox_main)
        self.show_home()
        self.setStyleSheet(self.dark_theme_stylesheet)
        self.update_icons()

    def init_home_page(self):
        # Search bar
        hbox_search = QHBoxLayout()
        search_label = QLabel('Enter song or video name:')
        self.search_entry = QLineEdit()
        self.search_entry.setFixedHeight(30)
        self.search_button = QPushButton()
        self.search_button.setIcon(QIcon('assets/search_icon_dark.png'))
        self.search_button.setIconSize(QSize(24, 24))
        self.search_button.setFixedSize(50, 50)
        self.search_button.setStyleSheet("background: none; border: none;")
        self.search_button.clicked.connect(self.search_videos)

        hbox_search.addStretch(1)
        hbox_search.addWidget(search_label)
        hbox_search.addWidget(self.search_entry)
        hbox_search.addWidget(self.search_button)
        hbox_search.addStretch(1)

        self.home_layout.addLayout(hbox_search)

        # Results
        self.results_tree = QTreeWidget()
        self.results_tree.setColumnCount(2)
        self.results_tree.setHeaderLabels(['Title', 'Video ID'])
        self.results_tree.setColumnWidth(0, 400)
        self.results_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1c1c1c;
                color: white;
            }
            QTreeWidget::item {
                height: 25px;
            }
            QHeaderView::section {
                background-color: #333333;
                color: white;
                font-weight: bold;
                padding: 4px;
                border: none;
            }
        """)
        self.results_tree.itemClicked.connect(self.select_song)

        self.home_layout.addWidget(self.results_tree)

        # Thumbnail display
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("background-color: #2a2a2a;")
        self.home_layout.addWidget(self.thumbnail_label)

        # Currently playing
        self.currently_playing_label = QLabel('Currently playing: ')
        self.home_layout.addWidget(self.currently_playing_label)

        # Controls
        hbox_controls = QHBoxLayout()
        self.play_button = QPushButton()
        self.play_button.setIcon(QIcon('assets/play_icon_dark.png'))
        self.play_button.setIconSize(QSize(32, 32))
        self.play_button.setFixedSize(50, 50)
        self.play_button.setStyleSheet("background: none; border: none;")
        self.play_button.clicked.connect(self.toggle_play_pause)
        self.play_button.setEnabled(False)  # Disable play button initially

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.set_volume)

        hbox_controls.addStretch(1)
        hbox_controls.addWidget(self.play_button)
        hbox_controls.addWidget(self.volume_slider)
        hbox_controls.addStretch(1)

        self.home_layout.addLayout(hbox_controls)

        # Progress bar
        self.progress_bar = QSlider(Qt.Horizontal)
        self.progress_bar.sliderReleased.connect(self.seek_audio)
        self.progress_bar.sliderPressed.connect(self.start_seeking)
        self.home_layout.addWidget(self.progress_bar)

        # Time labels
        hbox_time = QHBoxLayout()
        self.current_time_label = QLabel('00:00')
        self.total_time_label = QLabel('00:00')

        hbox_time.addWidget(self.current_time_label)
        hbox_time.addStretch(1)
        hbox_time.addWidget(self.total_time_label)

        self.home_layout.addLayout(hbox_time)

        # Initialize VLC player
        self.instance = vlc.Instance()
        self.mediaplayer = self.instance.media_player_new()
        self.mediaplayer.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, self.song_ended)

    def init_settings_page(self):
        theme_label = QLabel("Select Theme:")
        self.theme_dropdown = QComboBox()
        self.theme_dropdown.addItems(["Dark", "Light"])
        self.theme_dropdown.setFixedHeight(30)
        self.theme_dropdown.setStyleSheet("""
            QComboBox {
                font-size: 14px;
                padding: 5px;
                border: none;
                background-color: #2a2a2a;
                color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.theme_dropdown.currentIndexChanged.connect(self.change_theme)

        filter_label = QLabel("Enable Music Filter:")
        self.filter_checkbox = QCheckBox()
        self.filter_checkbox.setChecked(True)

        self.settings_layout.addWidget(theme_label)
        self.settings_layout.addWidget(self.theme_dropdown)
        self.settings_layout.addWidget(filter_label)
        self.settings_layout.addWidget(self.filter_checkbox)
        self.settings_layout.addStretch(1)
        
    def show_home(self):
        self.stacked_widget.setCurrentWidget(self.home_page)

    def show_settings(self):
        self.stacked_widget.setCurrentWidget(self.settings_page)
        
    def change_theme(self, index):
        if index == 0:
            self.setStyleSheet(self.dark_theme_stylesheet)
            self.results_tree.setStyleSheet("""
                QTreeWidget {
                    background-color: #1c1c1c;
                    color: white;
                }
                QTreeWidget::item {
                    height: 25px;
                }
                QHeaderView::section {
                    background-color: #333333;
                    color: white;
                    font-weight: bold;
                    padding: 4px;
                    border: none;
                }
            """)
            self.thumbnail_label.setStyleSheet("background-color: #2a2a2a;")
            self.theme_dropdown.setStyleSheet("""
                QComboBox {
                    font-size: 14px;
                    padding: 5px;
                    border: none;
                    background-color: #2a2a2a;
                    color: white;
                }
                QComboBox::drop-down {
                    border: none;
                }
            """)
        else:
            self.setStyleSheet(self.light_theme_stylesheet)
            self.results_tree.setStyleSheet("""
                QTreeWidget {
                    background-color: white;
                    color: black.
                }
                QTreeWidget::item {
                    height: 25px.
                }
                QHeaderView::section {
                    background-color: #e0e0e0.
                    color: black.
                    font-weight: bold.
                    padding: 4px.
                    border: none.
                }
            """)
            self.thumbnail_label.setStyleSheet("background-color: #f0f0f0.")
            self.theme_dropdown.setStyleSheet("""
                QComboBox {
                    font-size: 14px.
                    padding: 5px.
                    border: none.
                    background-color: #e0e0e0.
                    color: black.
                }
                QComboBox::drop-down {
                    border: none.
                }
            """)
        self.update_icons()
        
    def update_icons(self):
        sidebar_icon_size = QSize(64, 64)
        button_icon_size = QSize(32, 32)
        if self.theme_dropdown.currentIndex() == 0:
            self.home_button.setIcon(QIcon('assets/home_icon_dark.png'))
            self.home_button.setIconSize(sidebar_icon_size)
            self.settings_button.setIcon(QIcon('assets/settings_icon_dark.png'))
            self.settings_button.setIconSize(sidebar_icon_size)
            self.play_button.setIcon(QIcon('assets/play_icon_dark.png'))
            self.play_button.setIconSize(button_icon_size)
            self.search_button.setIcon(QIcon('assets/search_icon_dark.png'))
            self.search_button.setIconSize(button_icon_size)
        else:
            self.home_button.setIcon(QIcon('assets/home_icon_light.png'))
            self.home_button.setIconSize(sidebar_icon_size)
            self.settings_button.setIcon(QIcon('assets/settings_icon_light.png'))
            self.settings_button.setIconSize(sidebar_icon_size)
            self.play_button.setIcon(QIcon('assets/play_icon_light.png'))
            self.play_button.setIconSize(button_icon_size)
            self.search_button.setIcon(QIcon('assets/search_icon_light.png'))
            self.search_button.setIconSize(button_icon_size)
        
    def search_videos(self):
        query = self.search_entry.text()
        filter_enabled = self.filter_checkbox.isChecked()
        self.search_thread = SearchThread(query, filter_enabled)
        self.search_thread.search_results.connect(self.display_search_results)
        self.search_thread.start()

    def display_search_results(self, results):
        self.results_tree.clear()
        self.thumbnails = {}
        for title, video_id, thumbnail_url in results:
            item = QTreeWidgetItem([title, video_id])
            self.results_tree.addTopLevelItem(item)
            self.thumbnails[video_id] = thumbnail_url

    def select_song(self, item):
        video_id = item.text(1)
        self.pending_video_id = video_id
        self.show_thumbnail(item)
        self.play_button.setEnabled(True)  # Enable play button when a song is selected

    def show_thumbnail(self, item):
        video_id = item.text(1)
        thumbnail_url = f'https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg'
        try:
            response = requests.get(thumbnail_url)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            thumbnail_url = self.thumbnails.get(video_id, None)
        if thumbnail_url:
            image = QImage()
            image.loadFromData(requests.get(thumbnail_url).content)
            self.thumbnail_label.setPixmap(QPixmap(image).scaled(400, 400, Qt.KeepAspectRatio))

    def play_selected_song(self):
        self.play_button.setEnabled(True)
        self.player_thread = PlayerThread(self.current_video_id)
        self.player_thread.play_signal.connect(self.play_audio)
        self.player_thread.start()

    def play_audio(self, song_title):
        global is_paused, update_progress
        self.currently_playing_label.setText(f'Currently playing: {song_title}')
        media = self.instance.media_new(current_stream)
        self.mediaplayer.set_media(media)
        self.mediaplayer.play()
        is_paused = False
        self.play_button.setIcon(QIcon('assets/pause_icon_dark.png' if self.theme_dropdown.currentIndex() == 0 else 'assets/pause_icon_light.png'))
        update_progress = True
        self.update_progress_bar()

    def toggle_play_pause(self):
        global is_paused
        if self.current_video_id or self.pending_video_id:  # Ensure a song is selected before toggling play/pause
            if self.pending_video_id:
                self.current_video_id = self.pending_video_id
                self.pending_video_id = None
                self.play_selected_song()
            elif self.mediaplayer.is_playing():
                self.mediaplayer.pause()
                is_paused = True
                self.play_button.setIcon(QIcon('assets/play_icon_dark.png' if self.theme_dropdown.currentIndex() == 0 else 'assets.play_icon_light.png'))
            else:
                self.mediaplayer.play()
                is_paused = False
                self.play_button.setIcon(QIcon('assets/pause_icon_dark.png' if self.theme_dropdown.currentIndex() == 0 else 'assets/pause_icon_light.png'))
                self.update_progress_bar()

    def set_volume(self, value):
        self.mediaplayer.audio_set_volume(value)

    def start_seeking(self):
        global seeking
        seeking = True

    def seek_audio(self):
        global seeking
        if self.mediaplayer.is_playing() or is_paused:
            seek_time = self.progress_bar.value() * self.mediaplayer.get_length() / 100
            self.mediaplayer.set_time(int(seek_time))
        seeking = False
        self.update_progress_bar()

    def update_progress_bar(self):
        global update_progress, seeking
        if update_progress and not seeking:
            current_time = self.mediaplayer.get_time() / 1000
            duration = self.mediaplayer.get_length() / 1000
            if duration > 0:
                progress = int((current_time / duration) * 100)
                self.progress_bar.setValue(progress)
                self.current_time_label.setText(self.format_time(current_time))
                self.total_time_label.setText(self.format_time(duration))
            QTimer.singleShot(500, self.update_progress_bar)  # Update more frequently for better accuracy

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f'{minutes:02}:{seconds:02}'

    def song_ended(self, event):
        self.play_button.setIcon(QIcon('assets/play_icon_dark.png' if self.theme_dropdown.currentIndex() == 0 else 'assets/play_icon_light.png'))
        self.play_button.setEnabled(True)

    def closeEvent(self, event):
        self.mediaplayer.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = YouTufyApp()
    ex.show()
    sys.exit(app.exec_())