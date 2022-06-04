# Google Sign-In Module for Nginx

This is a simple Python program that makes it easy to serve a set of files with
nginx that can only be accessed by authorized users, using Google accounts for
authorization. Using google signin for auth lets you simply specify a list of
email addresses of users allowed to access the site; they can then log in with
their own Google passwords.

## Setup

### Setting up a Google API Client ID

For auth to work, you must first create a Client ID using Google's API
console. Instructions can be found
[here](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).
Note that when you create a credential on the Google console, one field will be
a list of "Authorized JavaScript origins". This must contain the complete URL of
your site for the auth flow to work.

The google client ID will look something like
`123456789-abcde.apps.googleusercontent.com`. It needs to be specified in two
steps below: in `google-login.html` and the configuration file for the Python
authorizer.

### nginx config file

An example config file can be found [here](https://github.com/jelson/nginx-googlesignin/blob/main/conf/nginx.conf).

The nginx config file's `location` block for the location that requires
authorization has an `auth_request` directive, meaning any request first gets
passed to the authorizing URL to ensure accessed is allowed. Details of this
nginx feature can be found
[here](http://nginx.org/en/docs/http/ngx_http_auth_request_module.html). The
authorizing program is the Python program in this repo.

  * If the authorizer returns 200, access is allowed.

  * If the authorizer returns an http 401 error, it means no credentials were
    found and the login flow should start; nginx is configured to generate a
    redirect to the static page `google-login.html`. It also sets the URL
    argument `r` to be the original URL on which access was attempted, and where
    the client will be redirected after auth is complete.

  * If the auth program returns 403, that means the login flow has been
    completed and we've decided the user is not allowed. The static page
    `not-authorized.html` is returned.

To adapt the example to your site, update
  * server_name in the two places it appears

  * SSL credentials (e.g., run certbot)

  * logfile locations as desired

### google login flow

The google login page (example [here](https://github.com/jelson/nginx-googlesignin/blob/main/htmlroot/google-login-example.html)) creates a google signin popup that
calls a Javascript callback to `onSignIn` when the auth flow is complete.  For
details, see Google's documentation
[here](https://developers.google.com/identity/sign-in/web) and
[here](https://developers.google.com/identity/gsi/web/guides/display-button).

When the auth-complete callback is invoked, it stores the JSON Web Token in a
cookie and redirects the client back to the URL in the `r` parameter. This will
end up invoking the authorizer again -- but this time with JWT's credentials
stored in the request's cookie.

The example google login page must be changed to include the Google API Client
ID you created in the first step.

### authorizer and its config file

The python authorizer script looks for JSON Web Token in the client's
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
[example configuration](https://github.com/jelson/nginx-googlesignin/blob/main/conf/config-example.yaml). It needs:

* The port number on which to listen (default is 17000; it must match the proxy
  statement in the nginx.conf).
  
* The Google API Client ID you created in the first step

* A secret key used to encrypt and decrypt tokens sent to clients. Generate a
  key by typing into Python

     `python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`

* A list of email addresses that are allowed

You must also arrange to ahve the auth program run, e.g, by adding it to systemd
using a configuration file such as [this one](https://github.com/jelson/nginx-googlesignin/blob/main/conf/videoauth.service).

