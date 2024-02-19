# Google Sign-In Module for Nginx

This is a simple Python program that makes it easy to serve a set of files with
nginx that can only be accessed by authorized users, using Google accounts for
authorization. Using Google signin for auth lets you simply specify a list of
Google email addresses of users allowed to access the site; they can then log in
with their own Google passwords. This relieves you of the responsibility of
managing passwords.

## Setup

### Setting up a Google API Client ID

You must first create a Client ID using Google's API console. Instructions can
be found
[here](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).
Note that when you create a credential on the Google console, one field will be
a list of "Authorized JavaScript origins". This must contain the complete URL of
your site for the auth flow to work. If you do not have the proper URL listed,
the auth popup will just be an empty frame.

The Google client ID will look something like
`123456789-abcde.apps.googleusercontent.com`. You'll need it in two steps below:
in `google-login.html` and the configuration file for the Python authorizer.

### nginx config file

This module comes with two nginx configuration file snippets that you can
include in your own nginx configuration file. The first,
[nginx-requires-auth-snippet](https://github.com/jelson/nginx-googlesignin/blob/main/conf/nginx-requires-auth-snippet.conf),
should be included inside any nginx `location` block whose contents should only
be viewed by authorized users. The second,
[nginx-provides-auth-snippet](https://github.com/jelson/nginx-googlesignin/blob/main/conf/nginx-provides-auth-snippet.conf),
should be included in the `server` block of any server that uses the `requires`
snippet. Here's a complete working example demonstrating how to use the snippets:

```
server {
    server_name example.com;
    listen [::]:443 ssl;
    listen 443 ssl;

    location / {
        alias /my/private/files;

        include /home/jelson/projects/nginx-googleauth/conf/nginx-requires-auth-snippet.conf;
    }

    include /home/jelson/projects/nginx-googleauth/conf/nginx-provides-auth-snippet.conf;

    ssl_certificate /my/cert/fullchain.pem; # managed by Certbot
    ssl_certificate_key /my/cert/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot

    access_log /var/log/nginx/access.log;
    error_log  /var/log/nginx/error.log;
}
```

To adapt the example to your site, change the path of the `include` directives
to reflect where this repo is checked out on your system.

The `nginx-provides-auth-snippet.conf` itself must also be customized to reflect
the absolute path to your checkout of this repository. It contains the following
stanza:

```
# Change to where the "htmlroot" directory from this repo lives on your system
location /googleauth {
    alias /home/jelson/projects/nginx-googleauth/htmlroot;
}
```

Change the `alias` path to match where the location of this repository's
`htmlroot` directory on your system.

### Google login page

Create the login page. A simple
[example](https://github.com/jelson/nginx-googlesignin/blob/main/htmlroot/google-login-example.html)
is included which does nothing but create a Google login popup.

Make a copy of the example named `google-login.html`. In your copy, change the
Google API Client ID (the `data-client_id` field) to Google Client ID you
created in the first step.

Of course, the page itself can also be customized to look more interesting.

### The authorizer program and its config file

The authorizer is implemented as a
[CherryPy](https://docs.cherrypy.dev/en/latest/) web service. A command-line
option specifies a location of a configuration file. The repo contains an
[example configuration](https://github.com/jelson/nginx-googlesignin/blob/main/conf/googleauth-config-example.yaml). It needs:

* The Google Auth python module:

  `apt install python3-google-auth`

* The port number on which to listen. The default is 17000; if you change it,
  make sure to also change the proxy_pass directive in
  `nginx-provides-auth-snippet.conf`.

* The Google API Client ID you created in the first step

* A secret key used to encrypt and decrypt tokens sent to clients. Generate a
  key by typing into Python

     `python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`

* A list of email addresses that are allowed

Place the config file somewhere accessible. In my example, it's in `~/.config/nginx-googleauth/config.yaml`.

Arrange to have the auth program run, e.g, by adding it to systemd using a
configuration file such as [this
one](https://github.com/jelson/nginx-googlesignin/blob/main/conf/googleauth.service). Ensure
that you pass `--config /path/to/config.yaml` to the script, giving it the
location of the config file you created in the prior step.

### Troubleshooting

After all the steps above, restart nginx and everything should work! When you
visit your newly protected site for the first time, you should get a popup
asking you to complete the Google login flow. Once complete, the site will
operate normally. Your browser will get a cookie indicating you've completed the
auth so future visits to the site will not have to reauthorize.

If you do not get a Google login popup, ensure the requires-auth snippet is in
the same `location` block nginx is using to serve the protected content.

If you get a 500 error, make sure `googleauth.py` is running. Use `netstat` to
ensure it's listening on the same port that the nginx requires-auth snippet is
expecting. Try to connect to the authorizer manually using wget:

```
TORG:/etc/nginx/sites-available(226074) wget http://localhost:17000/check_auth
--2023-12-13 14:46:40--  http://localhost:17000/check_auth
Resolving localhost (localhost)... ::1, 127.0.0.1
Connecting to localhost (localhost)|::1|:17000... connected.
HTTP request sent, awaiting response... 401 Unauthorized
```

If you see 401 Unauthorized, that means it's working. 404 means it is not
configured properly.

If you get a Google login popup but the contents are blank, it means the URL of
your web page was not in the list of allowed URLs when you created the Google
Client ID at the Google Cloud Platform console. (See step 1.)

## Internal details

The `requires_auth` snippet adds an `auth_request` directive, meaning any
request first gets passed to the authorizing URL to ensure accessed is
allowed. Details of this nginx feature can be found
[here](http://nginx.org/en/docs/http/ngx_http_auth_request_module.html). The
authorizing program is the Python program in this repo.

  * If the authorizer returns 200, access is allowed.

  * If the authorizer returns an http 401 error, it means no credentials were
    found and the login flow should start; nginx is configured to generate a
    redirect to the static page `/googleauth/google-login.html`. It also sets the URL
    argument `r` to be the original URL on which access was attempted, and where
    the client will be redirected after auth is complete.

  * If the auth program returns 403, that means the login flow has been
    completed and we've decided the user is not allowed. The static page
    `/googleauth/not-authorized.html` is returned.

The Google login page does nothing but pop up a Google login popup using
Google's JavaScript and their standard "Log in as <you>" button. For details,
see Google's documentation
[here](https://developers.google.com/identity/sign-in/web) and
[here](https://developers.google.com/identity/gsi/web/guides/display-button).
It is configured to invoke a Javascript function called `onSignIn` when the user
has completed the login process.

When the auth-complete callback is invoked, it stores the JSON Web Token in a
cookie and redirects the client back to the URL in the `r` parameter. This will
end up invoking the authorizer again---but this time with JWT's credentials
stored in the request's cookie.

The Python authorizer script looks for JSON Web Token in the client's
cookiejar. If it's not found, it returns an HTTP 401, which tells nginx to start
the auth flow. If found, it's verified using Google's oauth2 Python library, and
the email address it contains is checked against the list of allowed
addresses. If found, it returns 200. If not found, it returns 403.

If the JWT is valid, the authorizer also re-encrypts the email address again
using its own private key and sends the encrypted email back to the client as a
new cookie. I wanted this extra step because Google's JWT expires after one
hour, less than the length of a typical movie, and my use-case was serving
video. The authorizer's own tokens never expire. This may be a security hazard
depending on what you're protecting. However, the script can be easily changed
to encrypt both the email address and an expiration date in its private token,
instead.

