#!/usr/bin/env python3

import cherrypy
import yaml
import sys
import argparse
from google.oauth2 import id_token
from google.auth.transport import requests

CRED_COOKIE = 'circlemud_login_creds'

def say(s):
    sys.stdout.write(f"{s}\n")
    sys.stdout.flush()

class VideoAuth():
    def __init__(self, config):
        self.config = config

    # raises an exception if authentication data is not present.
    # returns false if client is not authorized.
    def _check_auth(self):
        # Google one-tap login sets a cookie called "g_state" with a
        # value of {"i_l": 0}. This apparently breaks SimpleCookie's
        # parser so we have to do our own ersatz parsing, which is
        # annoying.
        cookies = cherrypy.request.headers.get("Cookie", "").split(';')
        cookies = [c.strip() for c in cookies]

        cred = None
        for cookie in cookies:
            kv = cookie.split('=')
            if len(kv) != 2:
                continue
            if kv[0] != CRED_COOKIE:
                continue
            cred = kv[1]

        if not cred:
            raise Exception("No credential cookie; denying")

        idinfo = id_token.verify_oauth2_token(
            cred,
            requests.Request(),
            self.config['oauth-client-id'])
        email = idinfo['email']
        say(f"Got request from {email}")

        for allowed_email in self.config['authorized-users']:
            if allowed_email == email:
                return True

        return False

    @cherrypy.expose
    def check_auth(self):
        try:
            if not self._check_auth():
                cherrypy.response.status = 403
                return "Not authorized"
            else:
                return "Authorized!"
        except Exception as e:
            say(f"Authentication exception: {e}")
            cherrypy.response.status = 401
            return "No auth data"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config-file",
        help='Path to config file',
        action='store',
        required=True,
    )
    args = parser.parse_args()
    config = yaml.safe_load(open(args.config_file))
    cherrypy.config.update({
        'server.socket_host': '::',
        'server.socket_port': config['listen-port'],
        'server.socket_timeout': 30,
        'tools.proxy.on': True,
        'engine.autoreload.on': False,
    })

    cherrypy.quickstart(VideoAuth(config), '/auth')

main()
