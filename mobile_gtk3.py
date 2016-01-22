#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# from gi.repository import GObject
from gi.repository import Gtk, Gdk
from gi.repository import GLib
from gi.repository import WebKit
from gi.repository import Soup
import sys
import webbrowser
import urlparse
import time
import os
import logging

__filepath__ = os.path.realpath(os.path.abspath(__file__))
__version__ = "dev.%s" % (time.strftime("%Y.%m.%d",
                          time.localtime(os.path.getmtime(__filepath__))))

##################
# Config
##################

# Default username
default_username = "WasabiFlux"

# Twitter URL
main_url = "https://mobile.twitter.com/"

# Time between refreshes in seconds
refresh_time = 90

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
append_user_agent = False
#user_agent = ""
#user_agent = " MinimalDesktopTwitter/%s" % (__version__)
#user_agent = "Mozilla/5.0 (Linux; U; Android 2.3.5; en-us; HTC Vision Build/GRI40) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1"
#user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/7046A194A"
user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.137 Safari/4E423F"

# Default window size
default_width = 340
default_height = 700

# Minimum window size
min_width = 200
min_height = 400

# Debug level
debuglevel = logging.ERROR

# Non-mobile photo workaround
photo_workaround = True

##################
# End of Config
##################

##################
# Constants
#   No need to modify any of these.
##################

config_filename = "twitter.conf"
config_path = os.path.join(config_dir_path, config_filename)

cookie_filename = default_username+".cookiejar"
cookie_path = os.path.join(config_dir_path, cookie_filename)


##################
# End of Constants
##################


last_save = time.time()
window_geometry = {'x': 0, 'y': 0, 'w': default_width, 'h': default_height}
save_scheduled = False


def get_active_window(root=None):
    """Returns the active (focused, top) window, or None."""
    root = root or Gdk.get_root_window()
    # Make sure active window hinting is working
    if (root.supports_net_wm_hint("_NET_ACTIVE_WINDOW") and
            root.supports_net_wm_hint("_NET_WM_WINDOW_TYPE")):
        active = root.get_active_window()
        # If active window is a desktop, fail
        if (active.property_get("_NET_WM_WINDOW_TYPE")[-1][0] ==
                '_NET_WM_WINDOW_TYPE_DESKTOP'):
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
    if active is not None:
        return root.get_monitor_at_window(active)
    else:
        return -1


def window_resized(win, event, data=None):
    global window_geometry, last_save, save_scheduled
    if event.type == Gdk.EventType.CONFIGURE:
        window_geometry['x'] = event.x
        window_geometry['y'] = event.y
        window_geometry['w'] = event.width
        window_geometry['h'] = event.height
        seconds_until_save = int(last_save + config_save_interval - time.time())
        if not save_scheduled:
            # print "Scheduling save for %d" % seconds_until_save
            if seconds_until_save > 0:
                GLib.timeout_add_seconds(seconds_until_save, save_config)
                save_scheduled = True
            else:
                save_config()
    return False


def save_config():
    global window_geometry, last_save, save_scheduled
    # print "Saving new dimensions:", window_geometry
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
    # end_url = resolve_http_redirect(req.get_uri())

    # if 'photo' in end_url and 'twitter.com' in end_url:
    if 't.co' in req.get_uri() or ('twitter.com' in req.get_uri() and
                                   'photo' in req.get_uri()):
        # req.set_uri(end_url)
        return open_external_link(view, frame, req, None, None, data)
    return False


def open_external_link(view, frame, req, nav_action, decision, data=None):
    logger.debug("Externally open %s" % req.get_uri())
    if (photo_workaround and 'mobile.twitter.com' in req.get_uri() and
            'photo' in req.get_uri()):
        uri = req.get_uri().replace('mobile.', '')
        logger.debug("Workaround: %s", uri)
        webbrowser.open_new_tab(uri)
        return True
    # webbrowser.open_new_tab(resolve_http_redirect(req.get_uri()))
    webbrowser.open_new_tab(req.get_uri())
    return True


def scroll_tweets(view, event, data=None):
    print view.get_property('load-status')
    if view.get_property('load-status') == WebKit.LoadStatus.FINISHED:
        # logger.debug("Anchoring tweets:")
        params = urlparse.parse_qs(urlparse.urlparse(view.get_uri()).query)
        if params:
            print "Finished loading %s" % (view.get_uri(),)
            tweets = view.get_dom_document().get_elements_by_class_name('stream_item')
            top_id = params['id'][0]
            scroll_amount = int(params['scroll'][0])
            print "Starting with scroll_amount=%d" % (scroll_amount)
            for i in xrange(tweets.get_length()):
                if tweets.item(i).get_attribute('data_id') != top_id:
                    scroll_amount += tweets.item(i).get_offset_height()
                    print "Added %d to scroll; now at %d" % (tweets.item(i).get_offset_height(),
                                                             scroll_amount)
                else:
                    break
            adj = data.get_vadjustment()
            print "Before: %d" % (adj.get_value(),)
            adj.set_value(scroll_amount)
            print "After: %d" % (adj.get_value(),)
            print "Upper: %d" % (adj.get_upper(),)
            # adj = data.get_vadjustment()
            # print "After 2:", adj.get_value()
            # print "lower=%f, upper=%f" % (adj.get_lower(), adj.get_upper())
        # ALSO for every media link, add class activeLink so it opens in the browser
        GLib.timeout_add(250, revise_image_links, view)
    return True


def revise_image_links(view):
    links = view.get_dom_document().get_elements_by_class_name("twitter-media")
    print links.get_length()
    for i in xrange(0, links.get_length()):
        if links.item(i):
            links.item(i).set_class_name(links.item(i).get_class_name()+" activeLink")
            print links.item(i).get_outer_html()
    return False


def reload_main(view, sw):
    if not view.get_uri().split('?')[0] == main_url:
        print "Not refreshing: url = %s" % view.get_uri()
        return True

    document = view.get_dom_document()
    window = document.get_default_view()
    window_top = window.get_page_y_offset()
    nav = document.get_elements_by_class_name('navbar').item(0)
    if nav:
        min_scroll = nav.get_offset_top() + nav.get_offset_height()
    else:
        min_scroll = 0
    print "window_top=%d, min_scroll=%d" % (window_top, min_scroll)
    if False and window_top > min_scroll:
        tweets = view.get_dom_document().get_elements_by_class_name('stream-item')
        try:
            top_id = tweets.item(0).get_attribute('data_id')
        except AttributeError:
            print view.get_dom_document().get_body().get_inner_html()
            print tweets
            print dir(tweets)
            print tweets.get_length()
            for i in xrange(tweets.get_length()):
                print tweets.item(i)
        scroll_amount = sw.get_vadjustment().get_value()
        print "Opening %s?id=%s&scroll=%d" % (main_url, top_id, scroll_amount)
        view.open("%s?id=%s&scroll=%d" % (main_url, top_id, scroll_amount))
    else:
        view.open(main_url)
    return True


if __name__ == "__main__":
    username = default_username
    while len(sys.argv) > 1:
        if sys.argv[1] == '-u':
            username = sys.argv[2]
            del sys.argv[2]
            del sys.argv[1]
        elif sys.argv[1].startswith('--username='):
            username = sys.argv[1][11:]
            del sys.argv[1]
        elif sys.argv[1] == "-v" or sys.argv[1] == "--verbose":
            debugLevel = logging.DEBUG
            del sys.argv[1]
        else:
            main_url = sys.argv[1]
            del sys.argv[1]

    cookie_filename = username+".cookiejar"
    cookie_path = os.path.join(config_dir_path, cookie_filename)

    settings = WebKit.WebSettings()
    for setting in webkit_settings:
        settings.set_property(*setting)

    if append_user_agent:
        settings.set_property('user-agent', settings.get_property('user-agent')
                              + user_agent)
    elif user_agent is not None:
        settings.set_property('user-agent', user_agent)

    load_cookies()
    dimensions = load_config()
    # print dimensions

    view = WebKit.WebView()
    view.set_settings(settings)

    sw = Gtk.ScrolledWindow()
    sw.add(view)

    win = Gtk.Window()
    win.set_size_request(min_width, min_height)
    win.resize(dimensions['w'], dimensions['h'])
    win.move(dimensions['x'], dimensions['y'])
    win.add(sw)
    win.set_title(username+" - Twitter")
    win.connect("destroy", Gtk.main_quit)
    win.connect("configure-event", window_resized)
    win.show_all()

    view.connect("navigation-requested", on_nav_req)
    view.connect("new-window-policy-decision-requested", open_external_link)
    view.connect("notify::load-status", scroll_tweets, sw)
    GLib.timeout_add_seconds(refresh_time, reload_main, view, sw)

    logger = logging.getLogger(__name__)
    logger.setLevel(debuglevel)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(debuglevel)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    view.open(main_url)
    view.set_full_content_zoom(True)
    view.set_zoom_level(1.0)

    Gtk.main()
