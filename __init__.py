"""
X11 window switcher (prototype)
"""

from albert import *

import os
import time

from pathlib import Path
from hashlib import sha256

from memoization import cached

import gi
gi.require_version("Wnck", "3.0")
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
from gi.repository import Gtk, Wnck, GdkX11, Gdk

md_iid = "2.0"
md_version = "1.0"
md_name = "XSwitcher"
md_description = "X11 window switcher"
md_license = "BSD-3"
md_url = "https://github.com/TexDash/albert_xswitcher"

def is_hidden_window(window):
    state = window.get_state()
    return state & Wnck.WindowState.SKIP_PAGER or state & Wnck.WindowState.SKIP_TASKLIST

def sync_gtk_events():
    # adapted from: https://gist.github.com/adewes/6960581
    while Gtk.events_pending():
        Gtk.main_iteration()
        time.sleep(0.01)

def get_window_appname(window):
    # app_name = window.get_application().get_name().split(' - ')[-1].lower()
    app_name = window.get_class_group_name().lower()
    return app_name

@cached(ttl=2)
def get_window_list(cache_dir):
    windows = []
    screen = Wnck.Screen.get_default()
    if screen is not None:
        for win in screen.get_windows():
            if not is_hidden_window(win):
                title = win.get_name()
                xid = win.get_xid()
                workspace_name = win.get_workspace().get_name()
                app_name = get_window_appname(win)
                windows.append({
                    "title": title,
                    "workspace_name": workspace_name,
                    "app_name": app_name,
                    "icon_url": retrieve_or_save_icon(cache_dir, app_name, win.get_icon()),
                    "xid": xid
                })
    return windows

def get_x_server_time():
    return GdkX11.x11_get_server_time(Gdk.get_default_root_window())

def activate_window(xid):
    # https://stackoverflow.com/questions/27448224/why-python-wnck-window-activateinttime-time
    screen = Wnck.Screen.get_default()
    if screen is not None:
        for win in screen.get_windows():
            if win.get_xid() == xid:
                sync_gtk_events()
                win.activate(get_x_server_time())

def close_window(xid):
    screen = Wnck.Screen.get_default()
    if screen is not None:
        for win in screen.get_windows():
            if win.get_xid() == xid:
                win.close(get_x_server_time())

def close_all_window(app_name):
    screen = Wnck.Screen.get_default()
    if screen is not None:
        for win in screen.get_windows():
            if get_window_appname(win) == app_name:
                win.close(get_x_server_time())

def retrieve_or_save_icon(cache_dir, app_name, icon):
    if not cache_dir.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
    # Some app have crazy names, ensure we use something reasonable
    file_name = sha256(app_name.lower().encode("utf-8")).hexdigest()
    icon_full_path = str(cache_dir) + "/" + file_name
    if not os.path.isfile(icon_full_path):
        icon.savev(icon_full_path, "png", [], [])
    return f"file:{icon_full_path}"


class Plugin(PluginInstance, GlobalQueryHandler):
    def __init__(self):
        GlobalQueryHandler.__init__(self,
                                     id=md_id,
                                     name=md_name,
                                     description=md_description,
                                     synopsis="<xswitcher filter>",
                                     defaultTrigger='w ')
        PluginInstance.__init__(self, extensions=[self])

        self.cache_dir = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'albert/xswitcher'
        # init Wnck
        Gtk.init([])
        screen = Wnck.Screen.get_default()
        screen.force_update()

    def handleGlobalQuery(self, query):
        rank_items = []
        user_query = query.string.strip().lower()
        # info(user_query)

        windows = get_window_list(self.cache_dir)
        # info(windows)
        
        for win in windows:
            window_title = win['title']
            workspace_name = win['workspace_name']
            app_name = win['app_name']
            xid = win['xid']

            short_window_title = window_title[:15]
            if short_window_title != window_title:
                short_window_title += ' ...'

            target_str = (window_title + workspace_name + app_name).lower()
            if user_query in target_str:
                albert_id = sha256(window_title.lower().encode('utf-8')).hexdigest()

                rank_items.append(RankItem(
                    item=StandardItem(
                        id=albert_id,
                        text=window_title,
                        subtext=workspace_name,
                        inputActionText=window_title,
                        iconUrls=[win["icon_url"]],
                        actions=[
                            Action("activate_win", "Activate window: %s" % short_window_title, lambda w=win: activate_window(w['xid'])),
                            Action("close_win", "Close window: %s" % short_window_title, lambda w=win: close_window(w['xid'])),
                            Action("close_all_win", "Close all windows of app: %s" % app_name, lambda w=win: close_all_window(w['app_name'])),
                        ]
                    ),
                    score=0
                ))

        return rank_items
