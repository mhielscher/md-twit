#!/usr/bin/python

import gtk
import glib
import webkit
import sys
import webbrowser
import urlparse
import requests
import time
import os

__version__ = "dev.%s" % (time.strftime("%Y.%m.%d", time.localtime(os.path.getmtime(__file__))))

current_uri = "_blank"

# Recursively follow redirects until there isn't a location header
def resolve_http_redirect(url, depth=0):
    if depth > 10:
        return url
    try:
        r = requests.head(url)
    except IOError:
        sleep(2)
        return resolve_http_redirect(url, depth+1)
    if r.headers.has_key('location') and r.headers['location'] != url:
        new_url = r.headers['location']
        new_parsed = urlparse.urlparse(new_url)
        old_parsed = urlparse.urlparse(url)
        if new_parsed.netloc == '':
            new_url = old_parsed.netloc + new_url
        if new_parsed.scheme == '':
            new_url = old_parsed.scheme + "://" + new_url
        return resolve_http_redirect(new_url, depth+1)
    else:
        return url
        
def on_nav_req(view, frame, req, data=None):
    print "Nav to %s" % req.get_uri()
    #end_url = resolve_http_redirect(req.get_uri())
    #if 'photo' in end_url and 'twitter.com' in end_url:
    if 't.co' in req.get_uri():
        #req.set_uri(end_url)
        return open_external_link(view, frame, req, None, None, data)
    global current_uri
    current_uri = req.get_uri()
    #print current_uri
    return False

def open_external_link(view, frame, req, nav_action, decision, data=None):
    print "Externally open %s" % req.get_uri()
    webbrowser.open_new_tab(resolve_http_redirect(req.get_uri()))
    return True

def reload_and_schedule():
    #print "Reloading... ", current_uri
    if current_uri in ("_blank", "https://mobile.twitter.com/"):
        view.open("https://mobile.twitter.com/")
    glib.timeout_add_seconds(60, reload_and_schedule)

settings = webkit.WebSettings()

settings.set_property('enable-default-context-menu', True)
#settings.set_property('enable-java-applet', True)
settings.set_property('enable-plugins', True)
settings.set_property('enable-page-cache', True)
settings.set_property('enable-offline-web-application-cache', True)
settings.set_property('enable-html5-local-storage', True)
settings.set_property('enable-html5-database', True)
settings.set_property('enable-xss-auditor', True)
settings.set_property('enable-dns-prefetching', True)
settings.set_property('resizable-text-areas', True)

settings.set_property('user-agent', settings.get_property('user-agent') + " MinimalDesktopTwitter/%s" % (__version__))

view = webkit.WebView()

view.set_settings(settings)


sw = gtk.ScrolledWindow()
sw.add(view)

win = gtk.Window()
win.set_size_request(200, 400)
win.resize(340, 700)
win.move(1280-340, 24)
win.add(sw)
win.set_title("Twitter")
win.connect("destroy", gtk.main_quit)
win.show_all()

view.connect("navigation-requested", on_nav_req)
view.connect("new-window-policy-decision-requested", open_external_link)
reload_and_schedule()
gtk.main()


