# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 L2501
# v2026.1: feature update and efficiency pass
#
# Changes vs v0.1.0:
#
# 1. Song search added to the main menu and musicmp3_search() route.
#    The site always supported `all=songs` on its search endpoint but the
#    plugin never used it. Song results play directly — no extra click.
#
# 2. "Clear Cache" menu item added to the main menu.
#    Calls musicMp3.clear_cache() to wipe the PageCache table without
#    touching the Track table or the cookie file.
#
# 3. page_size and request_timeout are now read from user settings rather
#    than being hardcoded at 40 and 10. Defaults: 40 and 15.
#
# 4. musicMp3 is now instantiated once per route function (same as before),
#    but the timeout and cache_hours are passed in from settings so the
#    library is not responsible for reading addon settings itself.
#    This makes musicmp3.py testable without a running Kodi.
#
# 5. _make_musicmp3() helper to avoid repeating the three getSetting() calls
#    in every route function.
#
# 6. musicmp3_search() now routes cat="songs" to a playable track list instead
#    of trying to show them as directory items.
#
# 7. Track number shown in song listing when available (tracknumber info label).

import os
import sys
from urllib.parse import quote, unquote

from routing import Plugin
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

from resources.lib.musicmp3 import musicMp3, gnr_ids

try:
    from xbmcvfs import translatePath
except ImportError:
    from xbmc import translatePath

# --------------------------------------------------------------------------- #
# Add-on setup
# --------------------------------------------------------------------------- #

addon = xbmcaddon.Addon()
plugin = Plugin()
plugin.name = addon.getAddonInfo("name")

USER_DATA_DIR = translatePath(addon.getAddonInfo("profile"))
MEDIA_DIR     = os.path.join(translatePath(addon.getAddonInfo("path")), "resources", "media")
FANART        = os.path.join(MEDIA_DIR, "fanart.jpg")
MUSICMP3_DIR  = os.path.join(USER_DATA_DIR, "musicmp3")

if not os.path.exists(MUSICMP3_DIR):
    os.makedirs(MUSICMP3_DIR)

fixed_view_mode  = addon.getSetting("fixed_view_mode") == "true"
albums_view_mode = addon.getSetting("albums_view_mode")
songs_view_mode  = addon.getSetting("songs_view_mode")


def _make_musicmp3():
    """
    Construct a musicMp3 instance using the current user settings.
    Centralised here so every route reads the same values without duplication.
    """
    try:
        timeout = int(addon.getSetting("request_timeout"))
    except (ValueError, TypeError):
        timeout = 15
    try:
        cache_hours = int(addon.getSetting("cache_hours"))
    except (ValueError, TypeError):
        cache_hours = 6
    return musicMp3(MUSICMP3_DIR, timeout=timeout, cache_hours=cache_hours)


def _page_size():
    try:
        return int(addon.getSetting("page_size"))
    except (ValueError, TypeError):
        return 40


def _genre_icon(genre_name):
    filename = genre_name.lower().replace(" ", "").replace("&", "_") + ".jpg"
    return os.path.join(MEDIA_DIR, "genre", filename)


def _sub_genre_icon(parent_name, sub_name):
    filename = sub_name.lower().replace(" ", "").replace("&", "_") + ".jpg"
    return os.path.join(MEDIA_DIR, "genre", parent_name.lower(), filename)


def _set_view(content_type, view_mode):
    """Set content type and optionally force a view mode."""
    xbmcplugin.setContent(plugin.handle, content_type)
    if fixed_view_mode:
        xbmc.executebuiltin("Container.SetViewMode({0})".format(view_mode))


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@plugin.route("/")
def index():
    items = [
        ("Artists",          plugin.url_for(musicmp3_artist_main),          os.path.join(MEDIA_DIR, "artists.jpg")),
        ("Top Albums",       plugin.url_for(musicmp3_albums_main, "top"),    os.path.join(MEDIA_DIR, "topalbums.jpg")),
        ("New Albums",       plugin.url_for(musicmp3_albums_main, "new"),    os.path.join(MEDIA_DIR, "newalbums.jpg")),
        ("Search Artists",   plugin.url_for(musicmp3_search, "artists"),     os.path.join(MEDIA_DIR, "searchartists.jpg")),
        ("Search Albums",    plugin.url_for(musicmp3_search, "albums"),      os.path.join(MEDIA_DIR, "searchalbums.jpg")),
        # NEW: search for individual songs and play them directly
        ("Search Songs",     plugin.url_for(musicmp3_search, "songs"),       os.path.join(MEDIA_DIR, "searchsongs.jpg")),
        # NEW: wipe cached listing pages (does not affect playback or the track DB)
        ("Clear Page Cache", plugin.url_for(musicmp3_clear_cache),           os.path.join(MEDIA_DIR, "clearplaylist.jpg")),
    ]
    for label, url, icon in items:
        li = xbmcgui.ListItem(label)
        li.setArt({"fanart": FANART, "icon": icon})
        xbmcplugin.addDirectoryItem(plugin.handle, url, li, True)

    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route("/musicmp3/clear_cache")
def musicmp3_clear_cache():
    """Wipe the page HTML cache. Tracks and cookies are untouched."""
    api = _make_musicmp3()
    api.clear_cache()
    xbmcgui.Dialog().notification(
        plugin.name, "Page cache cleared.", xbmcgui.NOTIFICATION_INFO, 3000
    )
    # Re-open the home screen so the user sees we're done
    xbmc.executebuiltin("Container.Refresh")


@plugin.route("/musicmp3/albums_main/<sort>")
def musicmp3_albums_main(sort):
    directory_items = []
    for i, gnr in enumerate(gnr_ids):
        li = xbmcgui.ListItem("{0} {1} Albums".format(sort.title(), gnr[0]))
        li.setArt({"fanart": FANART, "icon": _genre_icon(gnr[0])})
        directory_items.append((plugin.url_for(musicmp3_albums_gnr, sort, i), li, True))

    xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route("/musicmp3/albums_gnr/<sort>/<gnr>")
def musicmp3_albums_gnr(sort, gnr):
    gnr_index = int(gnr)
    parent = gnr_ids[gnr_index]
    directory_items = []

    for sub_gnr in parent[1]:
        section = "compilations" if sub_gnr[0] == "Compilations" else \
                  "soundtracks"  if sub_gnr[0] == "Soundtracks"  else "main"

        li = xbmcgui.ListItem("{0} {1} Albums".format(sort.title(), sub_gnr[0]))
        li.setArt({"fanart": FANART, "icon": _sub_genre_icon(parent[0], sub_gnr[0])})
        directory_items.append(
            (plugin.url_for(musicmp3_main_albums, section, sub_gnr[1], sort, "0"), li, True)
        )

    xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route("/musicmp3/artists_main")
def musicmp3_artist_main():
    directory_items = []
    for i, gnr in enumerate(gnr_ids):
        li = xbmcgui.ListItem("{0} Artists".format(gnr[0]))
        li.setArt({"fanart": FANART, "icon": _genre_icon(gnr[0])})
        directory_items.append((plugin.url_for(musicmp3_artists_gnr, i), li, True))

    xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route("/musicmp3/artists_gnr/<gnr>")
def musicmp3_artists_gnr(gnr):
    gnr_index = int(gnr)
    parent = gnr_ids[gnr_index]
    directory_items = []

    for sub_gnr in parent[1]:
        if sub_gnr[0] in ("Compilations", "Soundtracks"):
            continue
        li = xbmcgui.ListItem("{0} Artists".format(sub_gnr[0]))
        li.setArt({"fanart": FANART, "icon": _sub_genre_icon(parent[0], sub_gnr[0])})
        directory_items.append(
            (plugin.url_for(musicmp3_main_artists, sub_gnr[1], "0"), li, True)
        )

    xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route("/musicmp3/search/<cat>")
def musicmp3_search(cat):
    """
    Unified search for artists, albums, or songs.
    - artists → directory of artist pages
    - albums  → directory of album pages
    - songs   → playable track list (NEW in v2026.1)
    """
    keyboardinput = ""
    keyboard = xbmc.Keyboard("", "Search")
    keyboard.doModal()
    if keyboard.isConfirmed():
        keyboardinput = keyboard.getText().strip()

    if not keyboardinput:
        xbmcplugin.endOfDirectory(plugin.handle, succeeded=False)
        return

    api = _make_musicmp3()
    results = api.search(keyboardinput, cat)
    directory_items = []

    if cat == "artists":
        for a in results:
            li = xbmcgui.ListItem(a.get("artist", ""))
            li.setInfo("music", {"title": a.get("artist", ""), "artist": a.get("artist", "")})
            directory_items.append((plugin.url_for(artists_albums, quote(a.get("link", ""))), li, True))

        xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
        _set_view("albums", albums_view_mode)
        xbmcplugin.endOfDirectory(plugin.handle)

    elif cat == "albums":
        for a in results:
            li = xbmcgui.ListItem(
                "{0}[CR][COLOR=darkmagenta]{1}[/COLOR]".format(a.get("title", ""), a.get("artist", ""))
            )
            li.setArt({"thumb": a.get("image", ""), "icon": a.get("image", "")})
            li.setInfo("music", {
                "title":  a.get("title", ""),
                "artist": a.get("artist", ""),
                "album":  a.get("title", ""),
                "year":   a.get("date", ""),
            })
            li.setProperty("Album_Description", a.get("details", ""))
            directory_items.append((plugin.url_for(musicmp3_album, quote(a.get("link", ""))), li, True))

        xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
        _set_view("albums", albums_view_mode)
        xbmcplugin.endOfDirectory(plugin.handle)

    elif cat == "songs":
        # Song results are playable immediately — no album page click required.
        for t in results:
            li = xbmcgui.ListItem(t.get("title", ""))
            li.setProperty("IsPlayable", "true")
            li.setArt({"thumb": t.get("image", ""), "icon": t.get("image", "")})
            li.setInfo("music", {
                "title":    t.get("title", ""),
                "artist":   t.get("artist", ""),
                "album":    t.get("album", ""),
                "duration": t.get("duration", ""),
            })
            directory_items.append(
                (plugin.url_for(musicmp3_play, track_id=t.get("track_id", ""), rel=t.get("rel", "")), li, False)
            )

        xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
        _set_view("songs", songs_view_mode)
        xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route("/musicmp3/main_albums/<section>/<gnr_id>/<sort>/<index>/dir")
def musicmp3_main_albums(section, gnr_id, sort, index):
    api = _make_musicmp3()
    count = _page_size()
    index = int(index)
    _section = "" if section == "main" else section

    albums = api.main_albums(_section, gnr_id, sort, index, count)
    directory_items = []

    for a in albums:
        li = xbmcgui.ListItem(
            "{0}[CR][COLOR=darkmagenta]{1}[/COLOR]".format(a.get("title", ""), a.get("artist", ""))
        )
        li.setArt({"thumb": a.get("image", ""), "icon": a.get("image", "")})
        li.setInfo("music", {
            "title":  a.get("title", ""),
            "artist": a.get("artist", ""),
            "album":  a.get("title", ""),
            "year":   a.get("date", ""),
        })
        directory_items.append((plugin.url_for(musicmp3_album, quote(a.get("link", ""))), li, True))

    if len(albums) >= count:
        next_index = str(index + count)
        li = xbmcgui.ListItem("More {0}+".format(next_index))
        directory_items.append(
            (plugin.url_for(musicmp3_main_albums, section, gnr_id, sort, next_index), li, True)
        )

    xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
    _set_view("albums", albums_view_mode)
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route("/musicmp3/main_artists/<gnr_id>/<index>/dir")
def musicmp3_main_artists(gnr_id, index):
    api = _make_musicmp3()
    count = _page_size()
    index = int(index)

    artists = api.main_artists(gnr_id, index, count)
    directory_items = []

    for a in artists:
        li = xbmcgui.ListItem(a.get("artist", ""))
        li.setInfo("music", {"title": a.get("artist", ""), "artist": a.get("artist", "")})
        li.setProperty("Album_Artist", a.get("artist", ""))
        directory_items.append((plugin.url_for(artists_albums, quote(a.get("link", ""))), li, True))

    if len(artists) >= count:
        next_index = str(index + count)
        li = xbmcgui.ListItem("More {0}+".format(next_index))
        directory_items.append(
            (plugin.url_for(musicmp3_main_artists, gnr_id, next_index), li, True)
        )

    xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
    _set_view("albums", albums_view_mode)
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route("/musicmp3/artists_albums/<link>")
def artists_albums(link):
    api = _make_musicmp3()
    url = unquote(link)
    albums = api.artist_albums(url)
    directory_items = []

    for a in albums:
        li = xbmcgui.ListItem(
            "{0}[CR][COLOR=darkmagenta]{1}[/COLOR]".format(a.get("title", ""), a.get("artist", ""))
        )
        li.setArt({"thumb": a.get("image", ""), "icon": a.get("image", "")})
        li.setInfo("music", {
            "title":  a.get("title", ""),
            "artist": a.get("artist", ""),
            "album":  a.get("title", ""),
            "year":   a.get("date", ""),
        })
        li.setProperty("Album_Description", a.get("details", ""))
        directory_items.append((plugin.url_for(musicmp3_album, quote(a.get("link", ""))), li, True))

    xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
    _set_view("albums", albums_view_mode)
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route("/musicmp3/album/<link>")
def musicmp3_album(link):
    api = _make_musicmp3()
    url = unquote(link)
    tracks = api.album_tracks(url)
    directory_items = []

    for i, t in enumerate(tracks, 1):
        li = xbmcgui.ListItem(t.get("title", ""))
        li.setProperty("IsPlayable", "true")
        li.setArt({"thumb": t.get("image", ""), "icon": t.get("image", "")})
        li.setInfo("music", {
            "title":       t.get("title", ""),
            "artist":      t.get("artist", ""),
            "album":       t.get("album", ""),
            "duration":    t.get("duration", ""),
            "tracknumber": i,          # site doesn't provide track numbers,
                                       # so we use position in the parsed list
        })
        directory_items.append(
            (plugin.url_for(musicmp3_play, track_id=t.get("track_id", ""), rel=t.get("rel", "")), li, False)
        )

    xbmcplugin.addDirectoryItems(plugin.handle, directory_items, len(directory_items))
    _set_view("songs", songs_view_mode)
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route("/musicmp3/play/<track_id>/<rel>")
def musicmp3_play(track_id, rel):
    api = _make_musicmp3()
    _track = api.get_track(rel)
    play_url = api.play_url(track_id, rel)

    li = xbmcgui.ListItem(_track.title or "", path=play_url)
    li.setInfo("music", {
        "title":    _track.title,
        "artist":   _track.artist,
        "album":    _track.album,
        "duration": _track.duration,
    })
    li.setArt({"thumb": _track.image, "icon": _track.image})
    li.setMimeType("audio/mpeg")
    li.setContentLookup(False)
    xbmcplugin.setResolvedUrl(plugin.handle, True, li)


if __name__ == "__main__":
    plugin.run(sys.argv)
