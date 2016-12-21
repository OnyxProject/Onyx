"""
Onyx Project
http://onyxproject.fr
Software under licence Creative Commons 3.0 France 
http://creativecommons.org/licenses/by-nc-sa/3.0/fr/
You may not use this software for commercial purposes.
@author :: Cassim Khouani
"""
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import requests
import json

def decodeURL(url) :
	r = requests.get(url, auth=('user', 'pass'))
	t = r.json()
	return t

def decode(jsonToRead) :
	r = jsonToRead
	reply = json.loads(r)
	return reply