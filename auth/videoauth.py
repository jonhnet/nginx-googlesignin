#!/usr/bin/env python3

import argparse
import cherrypy
import sys
import time
import yaml

from cryptography.fernet import Fernet
from google.auth.transport import requests
from google.oauth2 import id_token

GOOGLE_CRED_COOKIE = 'circlemud_goog_creds'
PRIVATE_CRED_COOKIE = 'circlemud_private_creds'

def say(s):
    sys.stdout.write(f"{s}\n")
    sys.stdout.flush()

class VideoAuth():
    def __init__(self, config):
        self.config = config
        self._cred_encryptor = Fernet(config['private-cred-key'])

    def _get_cookies(self):
        # Google one-tap login sets a cookie called "g_state" with a
        # value of {"i_l": 0}. This apparently breaks SimpleCookie's
        # parser so we have to do our own ersatz parsing, which is
        # annoying.
        cookies = cherrypy.request.headers.get("Cookie", "").split(';')
        cookies = [c.strip() for c in cookies]
        d = {}
        for c in cookies:
            s = c.split('=')
            if len(s) < 2:
                continue
            k = s[0]
            v = "=".join(s[1:])
            if v[0] == '"' and v[-1] == '"':
                v = v[1:-1]
            d[k] = v
        return d

    def _private_cred_is_valid(self, private_cred):
        # Unencrypt our secure private cred to get the email addr out
        email = self._cred_encryptor.decrypt(private_cred.encode()).decode()
        say(f"Got request from {email}")

        for allowed_email in self.config['authorized-users']:
            if allowed_email == email:
                return True

        say(f"...and {email} is not on the allowed list")
        return False

    def _convert_google_cred_to_private_cred(self, google_cred):
        idinfo = id_token.verify_oauth2_token(
            google_cred,
            requests.Request(),
            self.config['oauth-client-id'])
        email = idinfo['email']
        ttl_min = (idinfo['exp'] - time.time())/60
        say(f"Got valid google creds for {email}, expires in {ttl_min:.1f}min")
        private_cred = self._cred_encryptor.encrypt(email.encode()).decode()
        return private_cred

    def _delete_cookie(self, cookiename):
        cherrypy.response.cookie[cookiename] = ''
        cherrypy.response.cookie[cookiename]['path'] = '/'
        cherrypy.response.cookie[cookiename]['expires'] = 0
        cherrypy.response.cookie[cookiename]['max-age'] = 0

    # raises an exception if authentication data is not present.
    # returns false if client is not authorized.
    def _check_auth(self):
        cookies = self._get_cookies()

        # Ideally we'd like to delete the Google credential cookie and replace
        # it with our private cookie in a single operation. Unfortunately, a bug
        # in nginx limits us to a single cookie operation per request to an auth
        # server at a time. So, we only delete the google cookie once the
        # private cookie has succeded.


        # First check if there's a private cred provided. If so, delete any
        # google cred that might be hanging around. If not, fall through to
        # check for Google credentials.
        if PRIVATE_CRED_COOKIE in cookies:
            try:
                if self._private_cred_is_valid(cookies[PRIVATE_CRED_COOKIE]):
                    say("Private creds succeeded")
                    self._delete_cookie(GOOGLE_CRED_COOKIE)
                    return True
            except Exception as e:
                say(f"Private cookie invalid: {e}")

        # Check to see if new Google-issued credentials have arrived. If so, and
        # if valid, extract the email address and convert it into a non-expiring
        # credential we encrypt with our own private key. Either way, delete the
        # cookie.
        if GOOGLE_CRED_COOKIE in cookies:
            google_cred = cookies[GOOGLE_CRED_COOKIE]

            try:
                private_cred = self._convert_google_cred_to_private_cred(google_cred)
                if self._private_cred_is_valid(private_cred):
                    cherrypy.response.cookie[PRIVATE_CRED_COOKIE] = private_cred
                    cherrypy.response.cookie[PRIVATE_CRED_COOKIE]['path'] = '/'
                    return True
                else:
                    return False
            except Exception as e:
                say(f"Received invalid google cookie: {e}")
                self._delete_cookie(GOOGLE_CRED_COOKIE)

        raise Exception("No creds from any source!")


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
