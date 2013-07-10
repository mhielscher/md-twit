#!/usr/bin/python

from gi.repository import GObject
from gi.repository import Gtk, Gdk
from gi.repository import GLib
from gi.repository import WebKit
from gi.repository import Soup
import sys
import webbrowser
import urlparse
import requests
import time
import os

__filepath__ = os.path.realpath(os.path.abspath(__file__))
__version__ = "dev.%s" % (time.strftime("%Y.%m.%d", time.localtime(os.path.getmtime(__filepath__))))

##################
# Config
##################

# Twitter URL
main_url = "https://mobile.twitter.com/"

# Directory path for config file and cookie file
config_dir_path = '.'

# Time between window position saves in seconds
config_save_interval = 120

# WebKit settings
webkit_settings = [
	('enable-default-context-menu', True),
	('enable-java-applet', False),
	('enable-plugins', False),
	('enable-page-cache', True),
	('enable-offline-web-application-cache', True),
	('enable-html5-local-storage', True),
	('enable-html5-database', True),
	('enable-xss-auditor', True),
	('enable-dns-prefetching', True),
	('resizable-text-areas', True)
]

# User Agent
#   If append_user_agent is True, user_agent will be appended to the end of
#   webkit's default user agent.
append_user_agent = True
user_agent = " MinimalDesktopTwitter/%s" % (__version__)

# Default window size
default_width = 340
default_height = 700

# Minimum window size
min_width = 200
min_height = 400

# Time between refreshes in seconds
refresh_time = 60

##################
# End of Config
##################

##################
# Constants
#   No need to modify any of these.
##################

config_filename = "twitter.conf"
config_path = os.path.join(config_dir_path, config_filename)

cookie_filename = "cookiejar"
cookie_path = os.path.join(config_dir_path, cookie_filename)


##################
# End of Constants
##################


current_uri = "_blank"
last_save = time.time()
window_geometry = {'x': 0, 'y': 0, 'w': default_width, 'h': default_height}
save_scheduled = False


def get_active_window(root=None):
    """Returns the active (focused, top) window, or None."""
    root = root or Gdk.get_root_window()
    # Make sure active window hinting is working
    if root.supports_net_wm_hint("_NET_ACTIVE_WINDOW") and root.supports_net_wm_hint("_NET_WM_WINDOW_TYPE"):
        active = root.get_active_window()
        # If active window is a desktop, fail
        if active.property_get("_NET_WM_WINDOW_TYPE")[-1][0] == '_NET_WM_WINDOW_TYPE_DESKTOP':
            return None
        return active
    else:
        return None

def get_active_monitor(root=None):
    """Returns the index of the active monitor, or -1 if undetermined."""
    root = root or Gdk.get_root_window()
    num_monitors = root.get_n_monitors()
    if (num_monitors == 1):
        return 0
    active = get_active_window()
    if active != None:
        return root.get_monitor_at_window(active)
    else:
        return -1

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

def window_resized(win, event, data=None):
	global window_geometry, last_save, save_scheduled
	if event.type == Gdk.EventType.CONFIGURE:
		window_geometry['x'] = event.x
		window_geometry['y'] = event.y
		window_geometry['w'] = event.width
		window_geometry['h'] = event.height
		seconds_until_save = int(last_save + config_save_interval - time.time())
		if not save_scheduled:
			print "Scheduling save for %d" % seconds_until_save
			if seconds_until_save > 0:
				GLib.timeout_add_seconds(seconds_until_save, save_config)
				save_scheduled = True
			else:
				save_config()
	return False

def save_config():
	global window_geometry, last_save, save_scheduled
	print "Saving new dimensions:", window_geometry
	config_file = open(config_path, 'w')
	print >>config_file, "x: %d" % window_geometry['x']
	print >>config_file, "y: %d" % (window_geometry['y']-32)
	print >>config_file, "w: %d" % window_geometry['w']
	print >>config_file, "h: %d" % window_geometry['h']
	config_file.close()
	last_save = time.time()
	save_scheduled = False
	return False

def load_config():
	if os.path.exists(config_path):
		config_file = open(config_path, 'r')
		config = config_file.read().strip()
		dimensions = dict(line.split(': ') for line in config.split('\n'))
		for key, value in dimensions.items():
			dimensions[key] = int(value)
		return dimensions
	else:
		dimensions = {'w': default_width, 'h': default_height}
		# Get the upper-right corner of the active monitor
		root = Gdk.Screen.get_default()
		root_win = root.get_root_window()
		cursor = root_win.get_pointer()
		monitor = root.get_monitor_at_point(*cursor[1:3])
		m_rect = root.get_monitor_geometry(monitor)
		dimensions['x'] = m_rect.x + m_rect.width - default_width
		dimensions['y'] = m_rect.y
		return dimensions

def load_cookies():
	cookiejar = Soup.CookieJarText.new(cookie_path, False)
	cookiejar.set_accept_policy(Soup.CookieJarAcceptPolicy.ALWAYS)
	session = WebKit.get_default_session()
	session.add_feature(cookiejar)
        
def on_nav_req(view, frame, req, data=None):
    print "Nav to %s" % req.get_uri()
    #end_url = resolve_http_redirect(req.get_uri())
    #if 'photo' in end_url and 'twitter.com' in end_url:
    if 't.co' in req.get_uri() or ('twitter.com' in req.get_uri() and 'photo' in req.get_uri()):
        #req.set_uri(end_url)
        return open_external_link(view, frame, req, None, None, data)
    global current_uri
    current_uri = req.get_uri()
    #print current_uri
    return False

def open_external_link(view, frame, req, nav_action, decision, data=None):
    print "Externally open %s" % req.get_uri()
    #webbrowser.open_new_tab(resolve_http_redirect(req.get_uri()))
    webbrowser.open_new_tab(req.get_uri())
    return True

def reload_main():
    global current_uri
    if current_uri in ("_blank", main_url):
        print "Reloading... ", current_uri
        view.open(main_url)
    #GLib.timeout_add_seconds(60, reload_main)
    return True


if __name__ == "__main__":
	settings = WebKit.WebSettings()
	for setting in webkit_settings:
		settings.set_property(*setting)

	if append_user_agent:
		settings.set_property('user-agent', settings.get_property('user-agent') + user_agent)
	else:
		settings.set_property('user-agent', user_agent)

	load_cookies()
	dimensions = load_config()
	print dimensions

	view = WebKit.WebView()
	view.set_settings(settings)

	sw = Gtk.ScrolledWindow()
	sw.add(view)

	win = Gtk.Window()
	win.set_size_request(min_width, min_height)
	win.resize(dimensions['w'], dimensions['h'])
	win.move(dimensions['x'], dimensions['y'])
	win.add(sw)
	win.set_title("Twitter")
	win.connect("destroy", Gtk.main_quit)
	win.connect("configure-event", window_resized)
	win.show_all()

	view.connect("navigation-requested", on_nav_req)
	view.connect("new-window-policy-decision-requested", open_external_link)
	GLib.timeout_add_seconds(refresh_time, reload_main)
	reload_main()
	Gtk.main()


