#!/usr/bin/python

import os
import sys
import time
import random
import datetime
import traceback
import subprocess

from PyQt4 import QtGui, QtCore

RWindow = QtGui.QWidget
try:
    from ui_lib.window import RWindow
except ImportError:
    pass

import clippy_api as api
import clippy_translator as translator


class ClippyWindow(RWindow):
    """
    The main clippy window locked to a parent window.
    """
    # flag indicating if we are in testing mode
    TESTING = False
    # background timer that regularly checks for
    # clippy assignment changes and user activity
    CLIPPY_TIMER = None
    CHECK_IDLE = True
    WINDOW_SCREEN_GRAB = True
    APPLICATION = 'Linux'

    INSTANCE = None
    WINDOW_SIZE = QtCore.QSize(200, 250)
    CLIPPY_SIZE = QtCore.QSize(124, 93)
    CORNERS = ('Top Left', 'Top Right', 'Bottom Left', 'Bottom Right')
    CORNER_OFFSETS = ((30, 5), (-40, 5), (30, -10), (-40, -10))
    DEFAULT_CORNER = 1

    UPDATE_REQUEST = 77
    MOVE_EVENT = 13
    PARENT_WINDOW_EVENTS = (
    # 12,  # Paint
    MOVE_EVENT,  # Move
    14,  # Resize
    24,  # WindowActivate
    25,  # WindowDeactivate
    76,  # LayoutRequest
    )

    @classmethod
    def start_clippy_timer(cls, testing=False):
        cls.TESTING = testing
        cls.CLIPPY_TIMER = QtCore.QTimer()
        cls.CLIPPY_TIMER.setInterval(api.CHECK_INTERVAL * 1000 * 4)
        cls.CLIPPY_TIMER.timeout.connect(cls.regular_interval)
        cls.CLIPPY_TIMER.start()
        if testing:
            cls.regular_interval()

    @classmethod
    def stop_clippy_timer(cls):
        if cls.CLIPPY_TIMER is not None:
            if cls.CLIPPY_TIMER.isActive():
                cls.CLIPPY_TIMER.stop()
                cls.CLIPPY_TIMER = None

    @classmethod
    def regular_interval(cls):
        """
        Called at a regular interval to check if clippy should start, stop
        and see if the user is considered "active".
        """
        is_clipped = api.get_is_clipped()
        if cls.TESTING:
            is_clipped = True
        idle_time = api.check_activity(check_idle=cls.CHECK_IDLE)
        if cls.INSTANCE is None:
            if is_clipped:
                if cls.CLIPPY_TIMER is not None:
                    cls.CLIPPY_TIMER.setInterval(api.CHECK_INTERVAL * 1000)
                cls.start_clippy()
        else:
            if not is_clipped:
                cls.close_clippy()
            elif idle_time > api.MIN_IDLE_EVENT:
                idle_time_str = api.get_duration_str(idle_time)
                cls.INSTANCE.fire_event('idle_return', force=True,
                                        idle_time=idle_time_str)

    @classmethod
    def start_clippy(cls):
        if cls.INSTANCE is not None:
            cls.close_clippy()
        cls.INSTANCE = cls()
        cls.INSTANCE.start()
        cls.INSTANCE.show()
        cls.INSTANCE.fire_event('start')

    @classmethod
    def close_clippy(cls):
        if cls.INSTANCE is not None:
            cls.INSTANCE.was_killed = True
            if cls.INSTANCE.kill_window is not None:
                cls.INSTANCE.kill_window.close()
                cls.INSTANCE.kill_window.deleteLater()
                cls.INSTANCE.kill_window = None
            cls.INSTANCE.close()
            cls.INSTANCE.deleteLater()
            cls.INSTANCE = None
        if cls.TESTING:
            cls.stop_clippy_timer()

    @classmethod
    def reload_events(cls):
        if cls.INSTANCE is not None:
            cls.INSTANCE.reload_clippy_events()

    def __init__(self, parent_window):
        self.timers = list()
        self.bg_pixmap = None
        self.event_time = 0
        self.last_event = None
        self.current_movie = None
        self.corner = self.DEFAULT_CORNER
        self.language = 0  # english
        self.sender = None
        self.msg_kwargs = dict()
        self.last_msg_kwargs = dict()
        self.app_callbacks = []
        self.events = dict()
        self.last_event_load_time = 0
        self.closed = False
        self.is_killing = False
        self.was_killed = False
        self.kill_window = None
        self.background_is_updating = False
        self.menu = None
        self.clippy = None
        self.viewport_fix = None
        self.speech_bubble = None
        self.background = None
        self.hide_msg_timer = None
        self.periodic_timer = None
        self.parent_window = parent_window
        RWindow.__init__(self, parent=self.parent_window)
        self.static_pixmap = QtGui.QPixmap(api.STATIC_PATH)
        self.setFixedSize(self.WINDOW_SIZE)
        self.reload_clippy_events()
        self._init_ui()
        self._init_menu()
        self._init_msg_kwargs()
        self.start_periodic_timer()
        if self.parent_window is not None:
            self.add_event_filter()
            self._init_app_event_triggers()

    def _init_msg_kwargs(self):

        now = datetime.datetime.now()
        self.msg_kwargs = dict(real_name=api.REAL_NAME,  # first and last name
                               first_name=api.FIRST_NAME,
                               nick_name=api.NICK_NAME,
                               last_name=api.LAST_NAME,
                               username=api.USERNAME,  # actual user name
                               project=os.getenv('PROJ_SHORT', 'the movie'),
                               job_title=api.TITLE.lower(),
                               phone=api.PHONE,
                               app=self.APPLICATION,
                               discipline='doing nothing',
                               context='important thing',  # asset or shot name
                               department=api.DEPARTMENT,
                               # day of the week (e.g. Monday)
                               day=now.strftime('%A'),
                               year=now.strftime('%Y'),
                               sender_message=api.DEFAULT_SENDER_MSG,
                               sender_username='Somebody',
                               sender_real_name='Somebody',
                               sender_nick_name='Somebody',
                               sender_first_name='Somebody',
                               sender_last_name='Somebody')
        self.sender, message = api.get_sender_and_message()
        if self.sender is not None:
            self.msg_kwargs['sender_message'] = message
            self.msg_kwargs['sender_username'] = self.sender['username']
            self.msg_kwargs['sender_real_name'] = self.sender['real_name']
            self.msg_kwargs['sender_nick_name'] = self.sender['nick_name']
            self.msg_kwargs['sender_last_name'] = self.sender['last_name']
        try:
            import clippy_site as site
            site.add_site_specific_msg_kwargs(self.msg_kwargs)
        except Exception:
            pass

    def _init_ui(self):
        # self.setMouseTracking(True)
        # self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setWindowFlags(# QtCore.Qt.SplashScreen |
                            QtCore.Qt.FramelessWindowHint |
                            # QtCore.Qt.Dialog |
                            # QtCore.Qt.X11BypassWindowManagerHint |
                            # QtCore.Qt.Popup
                            # QtCore.Qt.Window |
                            QtCore.Qt.Tool |
                            # QtCore.Qt.SubWindow |
                            QtCore.Qt.CustomizeWindowHint
                            # QtCore.Qt.ToolTip
                            # QtCore.Qt.WindowStaysOnTopHint |
                            # self.windowFlags()
                            )
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow, True)
        self.background = QtGui.QLabel(self)
        self.background.resize(self.size())
        self.viewport_fix = QtGui.QWidget(self)
        self.viewport_fix.resize(self.size())
        self.viewport_fix.setAutoFillBackground(False)
        
        self.speech_bubble = SpeechBubble(self)
        self.speech_bubble.setFixedWidth(self.width())
        self.speech_bubble.move(0, 0)

        self.clippy = QtGui.QLabel(self)
        self.clippy.setAutoFillBackground(False)
        self.clippy.setPixmap(self.static_pixmap)
        self.clippy.resize(self.CLIPPY_SIZE)

        # justify clippy sprite into the bottom right corner
        posx = self.width() - self.clippy.width()
        posy = self.height() - self.clippy.height()
        self.clippy.move(posx, posy)

    def _init_menu(self):
        self.menu = QtGui.QMenu(self)
        position_menu = self.menu.addMenu('Position')
        for i, corner in enumerate(self.CORNERS):
            callback = self._set_corner_lambda(i)
            position_menu.addAction(corner, callback)
        language_menu = self.menu.addMenu('Language')
        for i, language in enumerate(translator.LANGUAGES):
            callback = self._set_language_lambda(i)
            language_menu.addAction(language.capitalize(), callback)
        self.menu.addSeparator()
        self.menu.addAction('Yes I Need Help!', self.on_open_help)
        self.menu.addAction('Kill Clippy...', self.on_kill_clippy)
        self.menu.addMenu(InfiniteMenu(1, self))
        if self.TESTING:
            self.menu.addAction('Actually Really Kill Clippy',
                                self.close_clippy)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.update_geometry()

    def _init_app_event_triggers(self):
        """
        Virtual method to add any application specific event triggers.
        """
        pass

    def _remove_app_event_triggers(self):
        """
        Virtual method to remove any application specific event triggers.
        """
        pass

    def scene_fire_event(self, event_name):
        self.fire_event(event_name)

    def add_event_filter(self):
        if self.parent_window is not None:
            self.parent_window.installEventFilter(self)

    def remove_event_filter(self):
        if self.parent_window is not None:
            self.parent_window.removeEventFilter(self)

    def eventFilter(self, target, event):
        """
        An event filter for the parent window to keep clippy in front of the
        parent window and to refresh the background display.
        """
        # api.print_event_name(event)
        if event.type() in self.PARENT_WINDOW_EVENTS:
            # api.print_event_name(event)
            self.update_geometry()
            if event.type() == self.MOVE_EVENT:
                self.fire_event('window_moved')
        return QtGui.QWidget.eventFilter(self, target, event)

    def start_periodic_timer(self):
        if not self.closed:
            self.periodic_timer = QtCore.QTimer(parent=self)
            self.update_periodic_timer()
            self.periodic_timer.timeout.connect(self.periodic_event)
            self.periodic_timer.start()
            self.timers.append(self.periodic_timer)

    def update_periodic_timer(self):
        period = random.randint(*api.PERIODIC_RANGE) * 1000
        self.periodic_timer.setInterval(period)

    def periodic_event(self):
        """
        Method periodically called by a timer event to display a semi-random
        reaction from clippy.
        """
        self.fire_event('periodic', update_event_time=False)
        self.update_periodic_timer()
        # good change to make sure the background is up to date.
        self.update_background()
        # auto reload clippy events
        self.reload_clippy_events()

    def fire_event(self, event_name, **kwargs):
        """
        Fires a clippy reaction event, usually playing an animation
        and updating the currently displayed message.
        """
        if self.closed or self.is_killing:
            return
        force = kwargs.pop('force', False)
        update_event_time = kwargs.pop('update_event_time', True)
        duration = time.time() - self.event_time
        if not force and duration < api.MIN_EVENT_TIME:
            # only run events every so often
            return
        event = self.events.get(event_name)
        if event is None:
            return
        msg_kwargs = dict(self.msg_kwargs)
        msg_kwargs.update(kwargs)
        msg_kwargs.setdefault('event_name', event_name)
        msg_kwargs.setdefault('first_name', api.FIRST_NAME)
        if update_event_time:
            self.event_time = time.time()
        self.last_event = event
        self.last_msg_kwargs = msg_kwargs
        msg = event.get_message(**msg_kwargs)
        movie = event.get_movie()
        self.play_movie(movie)
        self.current_movie = movie
        msg = translator.translate(self.language, msg)
        self.speech_bubble.set_message(msg)

    def movie_finished(self, set_static=True):
        """
        Callback when a clippy animation finishes playing.
        """
        self.stop_movie()
        self.clippy.setMovie(None)
        if not self.is_killing and set_static:
            self.set_static_clippy()

    def set_static_clippy(self):
        """
        Sets the clippy sprite to the static clippy image.
        """
        self.clippy.setPixmap(self.static_pixmap)

    def play_movie(self, movie):
        """
        Plays the specified clippy animation.
        """
        self.stop_movie()
        if movie is None:
            self.set_static_clippy()
            return
        self.current_movie = movie
        # self.current_movie.setSpeed(10)
        self.current_movie.setScaledSize(self.clippy.size())
        self.current_movie.finished.connect(self.movie_finished)
        self.clippy.setMovie(movie)
        self.current_movie.start()

    def stop_movie(self):
        """
        Stops the currently playing clippy animation and removes any listeners.
        """
        try:
            movie = self.current_movie
            if movie is not None:
                self.current_movie = None
                movie.stop()
                movie.finished.discconect()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

    def _set_corner_lambda(self, new_corner):
        return lambda: self.set_corner(new_corner)

    def _set_language_lambda(self, language):
        return lambda: self.set_language(language)

    def set_corner(self, new_corner):
        self.corner = new_corner
        self.fire_event('moved_corner')
        QtCore.QTimer.singleShot(500, self.update_geometry)

    def set_language(self, new_language):
        self.language = new_language
        self.fire_event('language_changed', force=True)

    def reload_clippy_events(self):
        if self.last_event_load_time > api.time_last_modified(api.EVENTS_PATH):
            return
        try:
            self.events = api.ClippyEvent.load()
            self.last_event_load_time = time.time()
        except (SyntaxError, RuntimeError, TypeError, ValueError):
            if self.TESTING:
                traceback.print_exc()
                sys.stderr.write('EVENT PARSE ERROR!\n')

    def on_open_help(self):
        help_url = None
        if self.last_event is not None:
            help_url = self.last_event.get_help_url(**self.last_msg_kwargs)
        if not help_url:
            help_url = api.DEFAULT_HELP_URL
        subprocess.Popen(['google-chrome', help_url])

    def on_kill_clippy(self):
        self.fire_event('kill_clippy', force=True)
        self.is_killing = True
        if self.kill_window is None:
            self.kill_window = KillClippyWindow(self)
        self.kill_window.exec_()

    def moveEvent(self, event):
        self.update_geometry()
        QtGui.QWidget.moveEvent(self, event)

    def mousePressEvent(self, event):
        if event.button() in (QtCore.Qt.LeftButton, QtCore.Qt.RightButton):
            event.accept()
            position = self.mapToGlobal(event.pos())
            self.menu.popup(position)
            return
        return QtGui.QWidget.mousePressEvent(self, event)

    def resizeEvent(self, event):
        self.update_geometry()
        QtGui.QWidget.resizeEvent(self, event)

    def closeEvent(self, event):
        self.closed = True
        self.remove_event_filter()
        if self.parent_window is not None:
            self._remove_app_event_triggers()
        for timer in self.timers:
            if timer and timer.isActive():
                timer.stop()
        self.timers = list()
        QtGui.QWidget.closeEvent(self, event)

    def update_geometry(self):
        """
        Updates the geometry of the clippy window to be
        the correct size and position.
        """
        if self.background_is_updating:
            return
        if self.parent_window is not None:
            parent_geo = self.parent_window.geometry()
        else:
            app = QtGui.QApplication.instance()
            desktop = app.desktop()
            screen_number = desktop.screenNumber(self)
            parent_geo = desktop.availableGeometry(screen_number)
        corner_method = (parent_geo.topLeft, parent_geo.topRight,
                         parent_geo.bottomLeft, parent_geo.bottomRight)
        parent_corner = corner_method[self.corner]()
        offset = self.CORNER_OFFSETS[self.corner]
        new_corner = QtCore.QPoint(parent_corner.x() + offset[0],
                                   parent_corner.y() + offset[1])
        geo = QtCore.QRect(0, 0, self.width(), self.height())
        move_method = (geo.moveTopLeft, geo.moveTopRight,
                       geo.moveBottomLeft, geo.moveBottomRight)[self.corner]
        move_method(new_corner)
        self.setGeometry(geo)
        self.update_background()

    def update_background(self):
        if (self.parent_window is None or self.background_is_updating
            or self.closed):
            return
        if not self.WINDOW_SCREEN_GRAB:
            style = 'QLabel { background-color : #3a3a3a; }'
            self.background.setStyleSheet(style)
            self.background.setAutoFillBackground(True)
            return
        self.background_is_updating = True
        rectangle = QtCore.QRect(0, 0, self.width(), self.height())
        topl = self.mapToGlobal(rectangle.topLeft())
        botr = self.mapToGlobal(rectangle.bottomRight())
        topl = self.parent_window.mapFromGlobal(topl)
        botr = self.parent_window.mapFromGlobal(botr)
        rectangle = QtCore.QRect(topl, botr)
        self.bg_pixmap = QtGui.QPixmap.grabWidget(self.parent_window, rectangle)
        self.background.setPixmap(self.bg_pixmap)
        self.background_is_updating = False


class KillClippyWindow(QtGui.QDialog):

    MSG = ('Unfortunately Clippy cannot be killed. You can only send him'
           ' elsewhere. Select a colleague to receive clippy and enter a'
           ' message telling them how much they mean to you.')

    def __init__(self, window):
        self.window = window
        self.was_sent = False
        QtGui.QDialog.__init__(self, parent=window)
        vlayout = QtGui.QVBoxLayout(self)
        msg_lbl = QtGui.QLabel(self.MSG)
        font = msg_lbl.font()
        font.setBold(True)
        msg_lbl.setFont(font)
        msg_lbl.setWordWrap(True)
        vlayout.addWidget(msg_lbl)

        self.rusers = api.get_eligible_recipients(window.sender)
        self.rusers.sort(cmp=lambda x, y: cmp(x['real_name'], y['real_name']))
        lbls = [u['real_name'] for u in self.rusers]
        self.user_cmb = QtGui.QComboBox()
        self.user_cmb.addItems(lbls)
        self.user_cmb.setCurrentIndex(random.randint(0, len(self.rusers) - 1))
        vlayout.addWidget(self.user_cmb)
        self.message_txt = QtGui.QTextEdit()
        self.message_txt.setText('Clippy is here to help!')
        self.message_txt.setFixedHeight(100)
        vlayout.addWidget(self.message_txt)
        btn1 = QtGui.QPushButton("Nevermind, we're becoming fast friends.")
        btn1.clicked.connect(self.close)
        vlayout.addWidget(btn1)
        btn2 = QtGui.QPushButton("Send Clippy... With Your Love.")
        btn2.clicked.connect(self.send_clippy)
        vlayout.addWidget(btn2)
        self.setWindowTitle('Kill Clippy')
        self.setFixedWidth(350)
        self.setFixedHeight(self.sizeHint().height())

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Enter:
            # prevent unintentional window closure
            e.accept()
            return
        return QtGui.QWidget.keyPressEvent(self, e)

    def closeEvent(self, event):
        if not self.was_sent:
            self.window.is_killing = False
            self.window.fire_event('spared', force=True)
        return QtGui.QWidget.closeEvent(self, event)

    def send_clippy(self):
        """
        Callback to forward clippy to a new user.
        """
        ruser = self.rusers[self.user_cmb.currentIndex()]
        msg = str(self.message_txt.toPlainText())
        api.unclip_user(api.RUSER)
        api.clip_user(ruser, api.RUSER, msg)
        ClippyWindow.close_clippy()
        self.was_sent = True
        self.close()


class SpeechBubble(QtGui.QWidget):
    TXT_MARGIN = 7

    def __init__(self, window):
        self.window = window
        QtGui.QWidget.__init__(self, parent=window)
        self.setAutoFillBackground(False)
        top_pixmap = QtGui.QPixmap(api.SPEECH_TOP_PATH)
        mid_pixmap = QtGui.QPixmap(api.SPEECH_MIDDLE_PATH)
        bot_pixmap = QtGui.QPixmap(api.SPEECH_BOTTOM_PATH)

        self.top_lbl = QtGui.QLabel('', self)
        self.top_lbl.setPixmap(top_pixmap)
        self.top_lbl.setFixedSize(top_pixmap.size())
        self.mid_lbl = QtGui.QLabel('', self)
        self.mid_lbl.setPixmap(mid_pixmap)
        self.mid_lbl.setScaledContents(True)
        self.bot_lbl = QtGui.QLabel('', self)
        self.bot_lbl.setPixmap(bot_pixmap)
        self.bot_lbl.setFixedSize(bot_pixmap.size())

        self.end_height = self.top_lbl.height() + self.bot_lbl.height()
        self.msg_lbl = QtGui.QLabel('', self)
        font = self.msg_lbl.font()
        font.setBold(True)
        self.msg_lbl.setFont(font)
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom)
        style = 'QLabel { color : black; background-color : #ffffcc; }'
        self.msg_lbl.setStyleSheet(style)
        self.msg_lbl.setAutoFillBackground(True)
        self.txt_margin = 7
        self.update_lbl_geometry()

    def set_message(self, msg):
        msg = msg.strip()
        width = self.width()
        metrics = self.msg_lbl.fontMetrics()
        bounds = QtCore.QRect(0, 0, self.msg_lbl.width(), 200)
        flags = (QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom |
                 QtCore.Qt.TextWordWrap)
        new_bounds = metrics.boundingRect(bounds, flags, msg)
        txt_height = new_bounds.height()
        height = txt_height + self.end_height
        height = max(height, 40)
        self.move(0, self.window.height() - height - 90)
        self.setFixedSize(width, height)
        self.mid_lbl.setFixedSize(width, height - self.end_height)
        geo = QtCore.QRect(0, 0, width, 0)
        for lbl in (self.top_lbl, self.mid_lbl, self.bot_lbl):
            lbl.move(geo.bottomLeft())
            geo = lbl.geometry()
        self.msg_lbl.setText(msg)
        self.update_lbl_geometry()

    def update_lbl_geometry(self):
        ypos = self.top_lbl.geometry().bottom()
        self.msg_lbl.move(self.TXT_MARGIN, ypos)
        lbl_height = self.bot_lbl.geometry().top() - ypos
        msg_width = self.width() - self.TXT_MARGIN * 2
        self.msg_lbl.setFixedSize(msg_width, lbl_height)


class InfiniteMenu(QtGui.QMenu):
    REALLY = ['Really', 'Actually', 'Totally', 'Very', '100%', 'Probably']

    def __init__(self, depth, parent):
        self.submenu = None
        self.depth = depth
        if depth > 10:
            depth = 10
        if depth > 1:
            tokens = list()
            for _ in xrange(depth):
                tokens.append(random.choice(self.REALLY))
        else:
            tokens = ['Actually']
        label = ' '.join(tokens) + ' Kill Clippy'
        QtGui.QMenu.__init__(self, label, parent)
        self.aboutToShow.connect(self.add_submenu)

    def add_submenu(self, *args, **kwargs):
        if self.submenu is None:
            self.submenu = InfiniteMenu(self.depth + 1, self)
            self.addMenu(self.submenu)

