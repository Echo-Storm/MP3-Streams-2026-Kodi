<hr>

<h2>ORIGINAL V0.7 (2022)</h2>

<h1>plugin.audio.m3sr2019</h1>

<p><strong>MP3 Streams Reloaded</strong></p>

<h3>Notes</h3>
<ul>
  <li>Force fixed viewmode in settings if needed (default ids for Confluence, other skins will be different)</li>
  <li>Seeking is not possible (server side)</li>
  <li>Try not to queue everything at once, one album/artist at a time should be fine.</li>
  <li>
    Kodi 18 PAPlayer can crash Kodi if something goes wrong with stream/server<br>
    To avoid this crash use different player for audio playback eg. VideoPlayer<br>
    advancedsettings.xml:
  </li>
</ul>

<pre><code>&lt;audio&gt;
    &lt;defaultplayer&gt;VideoPlayer&lt;/defaultplayer&gt;
&lt;/audio&gt;
</code></pre>

<hr>

<h2>Changes v2026.1 / 2026.1.1</h2>

<h3>Fixes</h3>

<p>
addon.xml declared three dependencies (script.module.six, script.module.kodi-six, script.module.future) that are Python 2/3 bridge libraries. Kodi 19 (Matrix) and later run Python 3.8 exclusively, and these modules may not be installed at all on modern Kodi systems — causing the plugin to fail at the dependency check before even loading.
</p>

<h4>default.py</h4>
<ul>
  <li>Was importing from future.backports.urllib.parse and kodi_six instead of the standard library. In Python 3, urllib.parse has everything needed — quote, unquote — natively.</li>
  <li>
    Hard crash: in musicmp3_search(), keyboardinput was only assigned inside the if keyboard.isConfirmed() block, but referenced unconditionally on the next line. If the user pressed Cancel on the keyboard dialog, this raised UnboundLocalError: name 'keyboardinput' is not defined and crashed the plugin. Fixed by initialising it to "" before the check.
  </li>
  <li>
    xbmcaddon.Addon() was called twice — once for the addon variable, then again inline when building MEDIA_DIR. Wasteful and inconsistent; now reuses the single addon object.
  </li>
</ul>

<h4>musicmp3.py</h4>
<ul>
  <li>Same future import issue.</li>
  <li>
    DB connect crash: the plugin uses reuselanguageinvoker=true, meaning the same Python process can handle multiple route calls. Each call created a new musicMp3() object which called db.connect() — but the database was already connected from the previous call, raising OperationalError: Connection already open. Fixed with reuse_if_open=True.
  </li>
  <li>
    boo() token bug: the hex padding slice was [len(d)-4:] which is logically inverted (for short hex strings it returns too many chars, for long ones too few). Fixed to [-4:] which correctly takes the last 4 characters.
  </li>
  <li>
    Missing cookie guard in boo(): if the SessionId cookie wasn't present, it crashed with a bare KeyError. Now raises a clear RuntimeError with an explanation.
  </li>
  <li>
    Bare except: in get_track() was swallowing everything including KeyboardInterrupt. Changed to except Track.DoesNotExist.
  </li>
  <li>
    User-Agent string was Firefox 68 from 2019. Updated to Firefox 121 — many servers now reject very old UAs.
  </li>
  <li>
    Missing Referer header on main_albums() requests (it was present on main_artists() but not here).
  </li>
</ul>

<p>
settings.xml was in the Kodi 18 format. Updated to the Kodi 19+ version="2" format.
</p>

<h3>Changes</h3>

<h4>New features pulled from the site</h4>
<p>
The site's search endpoint (search.html) accepts all=songs as a parameter, which the old plugin never used at all — it only wired up artists and albums. Song search is now a first-class item on the main menu. When you search for a song title, you get a playable track list directly, no extra click through an album page. The Track cache table is written at the same time, so if you play something from the results, the metadata is already there.
</p>

<h4>Layout / navigation improvements</h4>
<p>
The main menu has two new entries: "Search Songs" and "Clear Page Cache". The cache clear does exactly what it sounds like — it wipes the PageCache table in SQLite without touching your cookies, the track metadata table, or anything else. It pops a notification toast to confirm, then refreshes the container. That's it, fully reversible.
</p>

<p>
Track numbers are now set on song list items (tracknumber: i). The site doesn't provide them in metadata, so they're assigned by position in the parsed order, which is the correct album sequence. Most Kodi skins use this to display "1 / 12" style info in the now-playing overlay.
</p>

<h4>Efficiency improvements</h4>
<p>
The biggest one is the HTML cache. The old plugin fetched the same genre listing page from the server fresh every single time you opened it. Now, listing pages (artist lists, album grids) are cached in SQLite for 6 hours by default. The cache is keyed by URL + an MD5 hash of the query params, so "Rock top albums page 2" and "Rock new albums page 2" are separate entries. Album track pages are always fetched live, because those involve the session state needed for the CDN token. You can tune the cache lifetime in Settings → Network, or set it to 0 to disable entirely.
</p>

<p>
The duplicated album-report parsing code (which appeared separately in search(), artist_albums(), main_albums(), and the search function) is now consolidated into one _parse_album_report() method. It's also None-safe — if the site's HTML is missing an expected class (layout change on their end), it logs a warning and skips that entry instead of crashing the whole listing with AttributeError.
</p>

<p>
page_size and request_timeout are now real settings in the Settings dialog instead of being hardcoded at 40 and 10. Page size goes from 10 to 100 in steps of 10; timeout from 5 to 60 in steps of 5. The _make_musicmp3() helper reads both once per route call and passes them into the library, which means musicmp3.py itself has no Kodi dependency at all — useful if you ever want to test it outside Kodi.
</p>

<p>
The song search bug I discovered after writing has been fixed:  the search results page uses song__name--search, song__artist--search, song__album--search CSS classes — not the itemprop meta tags the parser was looking for. It was hitting the guard check on line 335, silently continuing past every row, and returning an empty list every time. Song search would have appeared to work (no crash, keyboard dialog would close) but the list would always come up empty. That's now fixed in 2026.1.1.
</p>