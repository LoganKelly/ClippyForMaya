#!/usr/bin/python

import os
import ast
import glob
import time
import random
import datetime
import subprocess

from PyQt4 import QtCore, QtGui

CLIPPY_DIR = os.path.abspath(os.path.dirname(__file__)) + '/'
CLIPPY_LIVES_PATH = CLIPPY_DIR + 'CLIPPY_LIVES'
ALL_USERS_PATH = CLIPPY_DIR + 'all_users.txt'
CLIPPED_PATH = CLIPPY_DIR + 'clipped/%s.dat'
ACTIVE_USERS_PATH = CLIPPY_DIR + 'active_users/%s.txt'
ANIMATION_PATH = CLIPPY_DIR + 'animation/'
EVENTS_PATH = CLIPPY_DIR + 'events.txt'
IDLE_TIME_PATH = CLIPPY_DIR + 'idletime'

IMAGES_DIR = CLIPPY_DIR + 'images/'
SPEECH_TOP_PATH = IMAGES_DIR + 'speech_top.png'
SPEECH_MIDDLE_PATH = IMAGES_DIR + 'speech_middle.png'
SPEECH_BOTTOM_PATH = IMAGES_DIR + 'speech_bottom.png'
STATIC_PATH = IMAGES_DIR + 'clippy.png'

DEFAULT_HELP_URL = ('https://www.google.com/webhp?sourceid=chrome-instant'
                    '&ion=1&espv=2&ie=UTF-8#q=april%20fools%20day')
DEFAULT_SENDER_MSG = 'Be nice to clippy. He saved my life once.'


ALL_USERS = list()
USERS_BY_DEPT = dict()
USERS_BY_NAME = dict()

USERNAME = os.getenv('USER', os.getenv('USERNAME', 'dvader'))
MY_ACTIVE_PATH = ACTIVE_USERS_PATH % USERNAME

# current user data (defaults)
RUSER = dict()
FIRST_NAME = 'You'
LAST_NAME = 'You'
REAL_NAME = 'You'
NICK_NAME = 'You'
TITLE = 'professional artist'
PHONE = '867-5309'
DEPARTMENT = 'Global'
DEPARTMENT_TOKEN = 'global'

# check for clippy ativation/deactivation every few seconds
CHECK_INTERVAL = 5
# random periodic range in seconds between generic periodic reactions
PERIODIC_RANGE = (10, 15)
# the minimum time between two clippy event reactions in seconds
MIN_EVENT_TIME = 2
# the minimum time (in seconds) before firing an idle return event
MIN_IDLE_EVENT = 120
# the amount of since a user has been active before they are
# excluded from the clippy recipient list
ACTIVE_DURATION = datetime.timedelta(hours=2)
# idle time in seconds when the active user stops being updated
IDLE_TIME = 120
# the last idle time in seconds the previous time it was checked
LAST_IDLE_TIME = 0
# the minimum number of eligilble recipients before we loosen requirements
MIN_CLIPPY_RECIPIENTS = 2

def load_all_user_data():
    """
    Loads the list of all users.
    """
    global ALL_USERS
    global USERS_BY_DEPT
    global USERS_BY_NAME
    global RUSER
    global FIRST_NAME
    global LAST_NAME
    global REAL_NAME
    global NICK_NAME
    global TITLE
    global PHONE
    global DEPARTMENT
    global DEPARTMENT_TOKEN
    if not os.path.isfile(ALL_USERS_PATH):
        return list()
    try:
        import json
        json_str = open(ALL_USERS_PATH, 'r').read()
        decoder = json.JSONDecoder()
        USERS_BY_NAME = decoder.decode(json_str)
        USERS_BY_DEPT = dict()
        ALL_USERS = USERS_BY_NAME.values()
        for username, user in USERS_BY_NAME.iteritems():
            dept = user['department_token']
            USERS_BY_DEPT.setdefault(dept, list()).append(user)
        RUSER = USERS_BY_NAME.get(USERNAME, dict())
        FIRST_NAME = RUSER.get('first_name', FIRST_NAME)
        LAST_NAME = RUSER.get('last_name', LAST_NAME)
        REAL_NAME = RUSER.get('real_name', REAL_NAME)
        NICK_NAME = RUSER.get('nick_name', NICK_NAME)
        TITLE = RUSER.get('job_title', TITLE)
        PHONE = RUSER.get('phone', PHONE)
        DEPARTMENT = RUSER.get('department', DEPARTMENT)
        DEPARTMENT_TOKEN = RUSER.get('department_token', DEPARTMENT_TOKEN)
        return ALL_USERS
    except (ImportError, AttributeError, KeyError,
            TypeError, ValueError, RuntimeError):
        return list()

load_all_user_data()

def get_is_clipped(username=None):
    if not get_clippy_lives():
        return False
    if username is None:
        username = USERNAME
    path = CLIPPED_PATH % USERNAME
    return os.path.isfile(path)

def get_clippy_lives():
    return os.path.isfile(CLIPPY_LIVES_PATH)

def get_eligible_recipients(sender):
    """
    Gets the list of users who may receive clippy from the current user.
    """
    recipients = USERS_BY_DEPT.get(DEPARTMENT_TOKEN, list())
    recipients = [u for u in recipients if u['username'] != USERNAME]
    if sender is not None:
        # prevent the clipped user from sending it back to the sender
        # unless there are not enough other options.
        sender_user = sender['username']
        no_sender = [r for r in recipients if r['username'] != sender_user]
        if len(no_sender) > MIN_CLIPPY_RECIPIENTS:
            recipients = no_sender
    # only include users that do not already have
    # clippy unless there are not enough other options.
    unclipped_rusers = remove_clipped_rusers(recipients)
    if len(unclipped_rusers) > MIN_CLIPPY_RECIPIENTS:
        recipients = unclipped_rusers
    # only include active users in the list
    # unless there are not enough other options.
    active_rusers = remove_inactive_rusers(recipients)
    if len(active_rusers) > MIN_CLIPPY_RECIPIENTS:
        recipients = active_rusers
    return recipients

def get_user_is_active(username):
    active_path = ACTIVE_USERS_PATH % username
    if not os.path.isfile(active_path):
        return False
    return time_last_modified(active_path) > get_min_active_time()

def remove_inactive_rusers(rusers):
    min_active_time = get_min_active_time()
    out_rusers = list()
    for ruser in rusers:
        active_path = ACTIVE_USERS_PATH % ruser['username']
        if os.path.isfile(active_path):
            if time_last_modified(active_path) > min_active_time:
                out_rusers.append(ruser)
    return out_rusers

def remove_clipped_rusers(rusers):
    out_rusers = list()
    for ruser in rusers:
        if not get_is_clipped(username=ruser['username']):
            out_rusers.append(ruser)
    return out_rusers

def get_active_users():
    users = list()
    min_active_time = get_min_active_time()
    for path in glob.glob(ACTIVE_USERS_PATH % '*'):
        username = os.path.basename(path).partition('.')[0]
        if time_last_modified(path) > min_active_time:
            users.append(username)
    return users

def check_activity(check_idle=True):
    global LAST_IDLE_TIME
    idle_time = 0
    idle_difference = 0
    if check_idle:
        idle_time = get_idle_time()
        idle_difference = LAST_IDLE_TIME - idle_time
    if idle_time < IDLE_TIME:
        touch(MY_ACTIVE_PATH)
    LAST_IDLE_TIME = idle_time
    return idle_difference

def get_min_active_time():
    min_active_time = datetime.datetime.now() - ACTIVE_DURATION
    return time.mktime(min_active_time.timetuple())

def get_idle_time():
    """
    Returns user idletime in seconds (float).
    """
    process = subprocess.Popen([IDLE_TIME_PATH], stdout=subprocess.PIPE)
    output = process.communicate()[0]
    if output and output.strip().isdigit():
        return int(output.strip())
    return 0

def get_sender_and_message(username=None):
    """
    Gets the user who sent clippy to the specified user and their message.
    """
    if username is None:
        username = USERNAME
    path = CLIPPED_PATH % username
    if not os.path.isfile(path):
        return None, DEFAULT_SENDER_MSG
    with open(path, 'r') as clipped_fd:
        contents = clipped_fd.read()
        if not contents.strip() or '\n' not in contents:
            return None, DEFAULT_SENDER_MSG
        sender, _, message = contents.partition('\n')
        return USERS_BY_DEPT.get(sender.strip()), message.strip()

def unclip_user(ruser):
    """
    Deactivates clippy for the specified user.
    """
    path = CLIPPED_PATH % ruser['username']
    if os.path.isfile(path):
        os.remove(path)

def clip_user(ruser, sender_ruser, sender_message):
    """
    Activates clippy for the specified user.
    """
    path = CLIPPED_PATH % ruser['username']
    output = ''
    if sender_ruser and sender_message:
        output = '%s\n%s' % (sender_ruser['username'], sender_message)
    with open(path, 'w') as clipped_fd:
        clipped_fd.write(output)

def get_animations():
    generic = dict()
    for path in glob.glob(ANIMATION_PATH + '*.gif'):
        name = os.path.basename(path).partition('.')[0]
        generic[name] = path
    categories = dict()
    for path in glob.glob(ANIMATION_PATH + '*/*.gif'):
        tokens = path.split('/')
        name = tokens.pop(-1)
        category = tokens.pop(-1)
        name = name.partition('.')[0]
        categories.setdefault(category, dict())[name] = path
    return generic, categories

def get_duration_str(num_secs, include_secs=False):
    """
    get_duration_str is a function that returns a readable string based
    on an integer passed in.

    """
    time_left = int(num_secs)
    labels = ['seconds', 'minutes', 'hours', 'days', 'weeks']
    divisors = [60, 60, 24, 7, 99999]
    amounts = [0] * len(divisors)
    for i, divisor in enumerate(divisors):
        amounts[i] = time_left % divisor
        time_left = time_left / divisor
    if not include_secs:
        labels.pop(0)
        amounts.pop(0)
        if num_secs < 60:
            return '<1 %s' % labels[0]
    non_zero = False
    tokens = list()
    for label, unit in reversed(zip(labels, amounts)):
        non_zero = unit > 0 or non_zero
        if non_zero:
            # plural or singular unit label
            label = label[:-1] if unit == 1 else label
            tokens.append('%d %s' % (unit, label))
    if len(tokens) == 0:
        tokens.append('0 %s' % labels[0])
    if len(tokens) > 1:
        tokens.insert(len(tokens) - 1, 'and')
    return ' '.join(tokens)

def time_last_modified(path):
    """
    Gets the time the specified path was last modified.
    :param path: a file system path
    :type path: str
    :return: the time the path was last modified expressed in seconds since
             the UNIX epoch
    :rtype: float
    """
    return os.stat(path).st_mtime

def touch(path, times=None):
    try:
        with open(path, 'a'):
            os.utime(path, times)
    except (OSError, AttributeError, RuntimeError, ValueError):
        pass

def print_event_name(event):
    ignore_names = ('UpdateRequest', 'Paint', 'HoverMove',
                    'HoverEnter', 'HoverLeave')
    for name, value in vars(QtCore.QEvent).iteritems():
        if value == event.type():
            if name in ignore_names:
                return
            print 'Event: %s : %d' % (name, value)
            break

class ClippyEvent(object):

    generic_paths, category_paths = get_animations()
    generic_movies = dict()
    category_movies = dict()

    @classmethod
    def _get_movie(cls, movie_name, category=None):
        paths = cls.generic_paths
        movies = cls.generic_movies
        if category is not None:
            paths = cls.category_paths.setdefault(category, dict())
            movies = cls.category_movies.setdefault(category, dict())
        movie = movies.get(movie_name)
        if movie is not None:
            return movie
        path = paths.get(movie_name)
        if path and os.path.isfile(path):
            movie = QtGui.QMovie(path)
            movies[movie_name] = movie
            return movie
        return None

    @classmethod
    def load(cls):
        if not os.path.isfile(EVENTS_PATH):
            return dict()
        events = ast.literal_eval(open(EVENTS_PATH, 'r').read())
        result = dict()
        for event_name, items in events.iteritems():
            movie_names = items.get('movies', ['random'])
            msg = items.get('messages', None)
            help_url = items.get('help', DEFAULT_HELP_URL)
            result[event_name] = cls(event_name, movie_names, msg, help_url)
        return result

    def __init__(self, event_name, movie_names, messages, help_url):
        self.event_name = event_name
        if isinstance(movie_names, basestring):
            movie_names = [movie_names]
        self.movie_names = movie_names
        if isinstance(messages, basestring):
            messages = [messages]
        self.messages = messages
        self.movie_index = 0
        self.category_index = 0
        self.message_index = 0
        self.help_url = help_url

    def get_movie(self):
        movie_name = self.movie_names[self.movie_index]
        category = None
        if movie_name in self.category_paths:
            category = movie_name
            movie_name = random.choice(self.category_paths[category].keys())
        else:
            self.movie_index = (self.movie_index + 1) % len(self.movie_names)
            if movie_name == 'random':
                movie_name = random.choice(self.generic_paths.keys())
        return self._get_movie(movie_name, category)

    def get_message(self, **kwargs):
        message = self.messages[self.message_index]
        self.message_index = (self.message_index + 1) % len(self.messages)
        return message.format(**kwargs)

    def get_help_url(self, **kwargs):
        return self.help_url.format(**kwargs)
