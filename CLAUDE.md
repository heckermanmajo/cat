
Dies ist ein Analysetool für Skool communities.
Es läuft nur lokal und wird mit nutika zu einer EXECUTABLE compilliert.
Es gibt also nur einen Nutzer pro instanz -> Web ist NUR unser UI framework.
Es gibt ein Browser-PLUGIN, das die daten aus skool fetched.
- browser-extension/ -> altes Plugin für pyversion (deprecated)
- webserver/plugin/ -> aktuelles Plugin, wird vom Webserver als ZIP ausgeliefert
Es gibt ein alte depredated variante in pyversion.
Es gibt einen lizenz-webserver mit zwei aufgaben: EXECUTABLE ausliefern, lizenzen managen. ALLE BUSINESS LOGGIK IST IN myversion,d.h der Python code base.

Wir arbeiten im Refactoring: myversion.

Wir wollen das der code: Simple-Dense-Explicit ist wo es geht.

Mache kleine änderungen und halte danach Rücksprache -> dieses projekt muss 
LANGFRISTIG STABIL sein, was bedeutet ich muss als Menschlicher Entwickler die 
Kontrolle behalten.

LESE immer:

 - myversion/app.py
 - myversion/src/model.py
 - myversion/static/entity.js
 - webserver/core.php -> dient als Beispiel meines 'dichten und simplen' code styles
 - anleitungen/*

myversion/schemas hat die json schemas der Rohdaten die wir vom Plugin(von skool.com) bekommen.

Jede frontend seite ist eine html seite mit eigenem JS. Entkopplung ist 
wichitger als "DRY". Besonders bei dem html seiten. Jede seite soll 'self contained'
sein -> sie dürfen sich aber /static/api.js und /staic/app.js teilen und ggf. weitere 
Bibliotheken.

Im Frontend bevorzugen wir page-reload, weil es schnell ist und wenig komplexität hat,
weil ja eh alles (python-server und sqlite-db auf der selben maschiene läuft).

Jeder UI state sollte daher auch in der DB persistiert werden als "config-entry".