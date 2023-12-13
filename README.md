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
snippet. Here's a complete working example:

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

To adapt the example to your site, change the path of the `include` directives
to reflect where this repo is checked out on your system.

### Google login flow

The Google login page (example [here](https://github.com/jelson/nginx-googlesignin/blob/main/htmlroot/google-login-example.html)) creates a google signin popup that
calls a Javascript callback to `onSignIn` when the auth flow is complete.  For
details, see Google's documentation
[here](https://developers.google.com/identity/sign-in/web) and
[here](https://developers.google.com/identity/gsi/web/guides/display-button).

When the auth-complete callback is invoked, it stores the JSON Web Token in a
cookie and redirects the client back to the URL in the `r` parameter. This will
end up invoking the authorizer again -- but this time with JWT's credentials
stored in the request's cookie.

The example Google login page must be changed to include the Google API Client
ID you created in the first step. Then rename the file `google-login.html`.

### authorizer and its config file

The Python authorizer script looks for JSON Web Token in the client's
cookiejar. If it's not found, it returns an HTTP 401, which tells nginx to start
the auth flow. If found, it's verified using Google's oauth2 Python library, and
the email address it contains is checked against the list of allowed
addresses. If found, it returns 200. If not found, it returns 403.

If the JWT is valid, the authorizer also re-encrypts the email address again
using its own private key and sends the encrypted email back to the client as a
new cookie. I wanted this extra step because Google's JWT expires after one
hour, less than the length of a typical movie, and my use-case was serving
video. The authorizer's own tokens never expire. (This may be a security hazard
depending on what you're protecting.)

The authorizer is implemented as a
[CherryPy](https://docs.cherrypy.dev/en/latest/) web service. A command-line
option specifies a location of a configuration file. The repo contains an
[example configuration](https://github.com/jelson/nginx-googlesignin/blob/main/conf/googleauth-config-example.yaml). It needs:

* The port number on which to listen. The default is 17000; if you change it,
  make sure to also change the proxy_pass directive in
  `nginx-provides-auth-snippet.conf`.

* The Google API Client ID you created in the first step

* A secret key used to encrypt and decrypt tokens sent to clients. Generate a
  key by typing into Python

     `python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`

* A list of email addresses that are allowed

Place the config file somewhere accessible. In my example, it's in `~/.config/nginx-googleauth/config.yaml`.

You must also arrange to have the auth program run, e.g, by adding it to systemd
using a configuration file such as [this one](https://github.com/jelson/nginx-googlesignin/blob/main/conf/googleauth.service).
