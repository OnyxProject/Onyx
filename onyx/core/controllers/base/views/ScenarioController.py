# -*- coding: utf-8 -*-
"""
Onyx Project
http://onyxproject.fr
Software under licence Creative Commons 3.0 France
http://creativecommons.org/licenses/by-nc-sa/3.0/fr/
You may not use this software for commercial purposes.
@author :: Cassim Khouani
"""

from .. import core
from flask import render_template, request, jsonify
from flask.ext.login import login_required
from onyx.api.events import *

@core.route('scenario')
@login_required
def scenario():
	events = get_events()
	return render_template('scenario/index.html',events=events)

@core.route('scenario',methods=['POST'])
@login_required
def add_scenario():
	str = ""
	for param in request.form.getlist('param'):
		str+=param
	return str
