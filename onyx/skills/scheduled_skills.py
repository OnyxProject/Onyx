# -*- coding: utf-8 -*-
"""
Onyx Project
http://onyxproject.fr
Software under licence Creative Commons 3.0 France
http://creativecommons.org/licenses/by-nc-sa/3.0/fr/
You may not use this software for commercial purposes.
@author :: Cassim Khouani
"""

import abc
from datetime import datetime
from threading import Timer, Lock
from time import mktime

import parsedatetime as pdt
from adapt.intent import IntentBuilder

from onyx.skills import time_rules
from onyx.skills.core import OnyxSkill
from onyx.util.log import getLogger

__author__ = 'jdorleans'

logger = getLogger(__name__)


class ScheduledSkill(OnyxSkill):
    """
    Abstract class which provides a repeatable notification behaviour at a
    specified time.

    Skills implementation inherits this class when it needs to schedule a task
    or a notification.
    """

    DELTA_TIME = int((datetime.now() - datetime.utcnow()).total_seconds())
    SECONDS_PER_DAY = 86400
    SECONDS_PER_HOUR = 3600
    SECONDS_PER_MINUTE = 60

    def __init__(self, name, emitter=None):
        super(ScheduledSkill, self).__init__(name, emitter)
        self.timer = None
        self.calendar = pdt.Calendar(pdt.Constants(localeID=self.lang.replace('-', '_'), usePyICU=False))
        self.time_rules = time_rules.create(self.lang)
        self.init_format()

    def init_format(self):
        if self.config.get('Time', 'date_format') == 'DMY':
            self.format = "%d %B, %Y at "
        else:
            self.format = "%B %d, %Y at "

        if self.config.get('Time', 'time_format') == 'full':
            self.format += "%H:%M"
        else:
            self.format += "%I:%M, %p"

    def schedule(self):
        times = sorted(self.get_times())

        if len(times) > 0:
            self.cancel()
            t = times[0]
            now = self.get_utc_time()
            delay = max(float(t) - now, 1)
            self.timer = Timer(delay, self.notify, [t])
            self.timer.daemon = True
            self.start()

    def start(self):
        if self.timer:
            self.timer.start()

    def cancel(self):
        if self.timer:
            self.timer.cancel()

    def convert_local(self, utc_time):
        return utc_time + self.DELTA_TIME

    def get_utc_time(self, sentence=''):
        return mktime(self.calendar.parse(sentence)[0]) - self.DELTA_TIME

    def get_formatted_time(self, timestamp):
        date = datetime.fromtimestamp(timestamp)
        now = datetime.now()
        diff = (date - now).total_seconds()
        if diff <= self.SECONDS_PER_DAY:
            hours, remainder = divmod(diff, self.SECONDS_PER_HOUR)
            minutes, seconds = divmod(remainder, self.SECONDS_PER_MINUTE)
            if hours:
                if self.lang == 'en-US':
                    return "%s hours and %s minutes from now" % \
                           (int(hours), int(minutes))
                elif self.lang == 'fr-FR':
                    return "%s heures et %s minutes" % \
                           (int(hours), int(minutes))
            else:
                if self.lang == 'en-US':
                    return "%s minutes and %s seconds from now" % \
                           (int(minutes), int(seconds))
                elif self.lang == 'fr-FR':
                    return "%s minutes et %s secondes" % \
                           (int(minutes), int(seconds))

        return date.strftime(self.format)

    @abc.abstractmethod
    def get_times(self):
        pass

    @abc.abstractmethod
    def notify(self, timestamp):
        pass

    def shutdown(self):
        super(ScheduledSkill, self).shutdown()
        self.cancel()


class ScheduledCRUDSkill(ScheduledSkill):
    """
    Abstract CRUD class which provides a repeatable notification behaviour at
    a specified time.

    It registers CRUD intents and exposes its functions to manipulate a
    provided ``data``

    Skills implementation inherits this class when it needs to schedule a task
    or a notification with a provided data
    that can be manipulated by CRUD commands.

    E.g. CRUD operations for a Reminder Skill
        #. "Onyx, list two reminders"
        #. "Onyx, list all reminders"
        #. "Onyx, delete one reminder"
        #. "Onyx, remind me to contribute to Onyx project"
    """

    LOCK = Lock()
    REPEAT_TASK = 'repeat'
    PENDING_TASK = 'pending'
    ONE_DAY_SECS = 86400

    def __init__(self, name, emitter=None, basedir=None):
        super(ScheduledCRUDSkill, self).__init__(name, emitter)
        self.data = {}
        self.repeat_data = {}
        if basedir:
            logger.debug('basedir argument is no longer required and is ' +
                         'depreciated.')
            self.basedir = basedir

    def initialize(self):
        self.load_data()
        self.load_repeat_data()
        self.register_regex("(?P<" + self.name + "Amount>\d+)")
        self.register_intent(
            self.build_intent_create().build(), self.handle_create)
        self.register_intent(
            self.build_intent_list().build(), self.handle_list)
        self.register_intent(
            self.build_intent_delete().build(), self.handle_delete)
        self.schedule()

    @abc.abstractmethod
    def load_data(self):
        pass

    @abc.abstractmethod
    def load_repeat_data(self):
        pass

    def build_intent_create(self):
        return IntentBuilder(
            self.name + 'CreateIntent').require(self.name + 'CreateVerb')

    def build_intent_list(self):
        return IntentBuilder(
            self.name + 'ListIntent').require(self.name + 'ListVerb') \
            .optionally(self.name + 'Amount').require(self.name + 'Keyword')

    def build_intent_delete(self):
        return IntentBuilder(
            self.name + 'DeleteIntent').require(self.name + 'DeleteVerb') \
            .optionally(self.name + 'Amount').require(self.name + 'Keyword')

    def get_times(self):
        return self.data.keys()

    def handle_create(self, message):
        utterance = message.data.get('utterance')
        date = self.get_utc_time(utterance)
        delay = date - self.get_utc_time()

        if delay > 0:
            self.feedback_create(date)
            self.add_sync(date, message)
            self.save_sync()
        else:
            #self.speak(str(date),self.lang)
            #self.speak(str(delay),self.lang)
            self.speak_dialog('schedule.datetime.error')

    def feedback_create(self, utc_time):
        self.speak_dialog(
            'schedule.create', data=self.build_feedback_payload(utc_time))

    def add_sync(self, utc_time, message):
        with self.LOCK:
            self.add(utc_time, message)

    def add(self, utc_time, message):
        utterance = message.data.get('utterance')
        self.data[utc_time] = None
        self.repeat_data[utc_time] = self.time_rules.get_week_days(utterance)

    def remove_sync(self, utc_time, add_next=True):
        with self.LOCK:
            val = self.remove(utc_time, add_next)
        return val

    def remove(self, utc_time, add_next=True):
        value = self.data.pop(utc_time)
        self.add_next_time(utc_time, value, add_next)
        return value

    def add_next_time(self, utc_time, value, add_next=True):
        days = self.repeat_data.pop(utc_time)
        if add_next and days:
            now_time = self.get_utc_time()
            next_time = utc_time + self.ONE_DAY_SECS
            now_day = datetime.fromtimestamp(utc_time).weekday()
            next_day = datetime.fromtimestamp(next_time).weekday()
            while next_day != now_day:
                if days[next_day] and next_time >= now_time:
                    self.data[next_time] = value
                    self.repeat_data[next_time] = days
                    break
                next_time += self.ONE_DAY_SECS
                next_day = datetime.fromtimestamp(next_time).weekday()

    def save_sync(self):
        with self.LOCK:
            self.save()

    @abc.abstractmethod
    def save(self):
        pass

    def handle_list(self, message):
        count = self.get_amount(message)
        if count > 0:
            for key in sorted(self.data.keys()):
                if count > 0:
                    self.feedback_list(key)
                    count -= 1
                else:
                    break
        else:
            self.speak_dialog('schedule.list.empty')

    def feedback_list(self, utc_time):
        self.speak_dialog(
            'schedule.list', data=self.build_feedback_payload(utc_time))

    def build_feedback_payload(self, utc_time):
        timestamp = self.convert_local(float(utc_time))
        payload = {
            'data': self.data.get(utc_time),
            'datetime': self.get_formatted_time(timestamp)
        }
        return payload

    def handle_delete(self, message):
        count = self.get_amount(message)
        if count > 0:
            amount = count
            for key in sorted(self.data.keys()):
                if count > 0:
                    self.remove_sync(key, False)
                    count -= 1
                else:
                    break
            self.feedback_delete(amount)
            self.save_sync()
        else:
            self.speak_dialog('schedule.delete.empty')

    def feedback_delete(self, amount):
        if amount > 1:
            self.speak_dialog('schedule.delete.many', data={'amount': amount})
        else:
            self.speak_dialog(
                'schedule.delete.single', data={'amount': amount})

    # TODO - Localization
    def get_amount(self, message, default=None):
        size = len(self.data)
        amount = message.data.get(self.name + 'Amount', default)
        if self.lang == "en-US":
            if amount in ['all', 'my', 'all my', None]:
                total = size
            elif amount in ['one', 'the next', 'the following']:
                total = 1
            elif amount == 'two':
                total = 2
            else:
                total = int(amount)
            return min(total, size)
        elif self.lang == "fr-FR":
            if amount in ['tout', 'tous', 'toutes', None]:
                total = size
            elif amount in ['un', 'une', 'le prochain']:
                total = 1
            elif amount == 'deux':
                total = 2
            else:
                total = int(amount)
            return min(total, size)
