# Lokálny vývoj a overovanie

## Aktuálny základ

Python 3.12+ postačuje na simulátor, fixtures a kontrolné skripty; netreba npm, HA ani externé balíky. Toto nie je deklarácia podporovanej verzie Pythonu pre samotný Home Assistant.

Z koreňa:

```bash
python3 tools/check_project.py
python3 -m unittest discover -s tests -v
python3 tools/mock_device.py --port 8124
```

Mock API sa viaže iba na loopback, prijíma iba verejný demo token uvedený v README. Nemá účet zákazníka, tajomstvá ani prístup k čerpadlu. Príklady v fixtures majú pevné ilustračné časy; mock pri odpovedi nastavuje čerstvý čas. Pump-offline režim zachováva dostupnosť transportu, no hodnoty čerpadla sú null. Port 8124 je zvolený, aby nekolidoval s bežným HA 8123 či lokálnym portálom 8000/5173.

## Implementácia integrácie

### Testovanie klienta bez HA

Protokolové testy sú zahrnuté v pôvodnom `python3 -m unittest discover -s tests -v`
a nepotrebujú externé balíky. Samostatné HTTP testy klienta vyžadujú izolovaný venv:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-client-test.txt
.venv/bin/python -m unittest discover -s tests/client -v
```

Použitý aiohttp 3.14.3 zodpovedá závislosti cieľového Core 2026.9.4. Tieto testy
bežia aj na miestnom Pythone 3.12; neinštalujú ani nespúšťajú Home Assistant.
HTTP servery testov sú iba loopback s náhodnými portmi a verejným demo tokenom.
Pôvodný unittest discovery nerekurzuje do tests/client (úmyselne bez __init__.py),
preto na kompletné overenie spusti oba príkazy. Produkčný HA dodáva aiohttp sám;
requirements-client-test.txt je určený iba pre tieto samostatné testy.

Klient prijíma HTTP(S) base URL bez prihlasovacích údajov, query a cesty; posiela
iba GET info/state, neprechádza presmerovania, má 10 s timeout a limit 64 KiB.
Žiadna výnimka nevypisuje URL, token ani telo odpovede. Retry-After (sekundy aj
HTTP dátum) nastaví lokálnu prestávku; klient nespí a automaticky neopakuje volania.
Koordinátor rieši plánovanie ďalšieho pokusu a bežný backoff.
Protocol model oddeľuje pump_available od čerstvosti; metóda measurements_available
vyžaduje dostupné čerpadlo aj čerstvé observed_at (max 5 s tolerancia do budúcnosti).
Čiastočne neznáme polia zostávajú None. Stav spojenia sleduje koordinátor samostatne.

### HA runtime a ďalšie kroky

Cieľ potvrdený používateľom: **HA Container, Core 2026.9.4**.
[pyproject tejto verzie](https://github.com/home-assistant/core/blob/2026.9.4/pyproject.toml)
vyžaduje Python >=3.14.2;
[.python-version](https://github.com/home-assistant/core/blob/2026.9.4/.python-version)
uvádza 3.14.5. Miestny Python 3.12 je vhodný pre existujúce smoke testy,
nie pre inštaláciu tohto HA. Vývojový HA musí mať samostatnú prázdnu konfiguráciu
a testovať simulátor, bez pripojenia produkčnej HA konfigurácie či čerpadla.
Izolované HA-native testovacie prostredie je pripravené v `/tmp/sema-ha-venv`.
Testy config flow a lifecycle bežia na skutočnom Core 2026.9.4 s Pythonom 3.14.5
a pytest-homeassistant-custom-component 0.13.367. HTTP odpovede sú mockované;
nejde o browserový test ani o test na používateľovom RPi.

Reprodukcia prostredia z koreňa (sťahuje Python a balíčky, žiadne produkčné dáta):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install uv==0.13.6
.venv/bin/uv python install 3.14.5 --install-dir /tmp/sema-ha-python --no-bin --cache-dir /tmp/sema-ha-uv-cache
.venv/bin/uv venv /tmp/sema-ha-venv --python /tmp/sema-ha-python/cpython-3.14.5-linux-x86_64-gnu/bin/python3.14 --cache-dir /tmp/sema-ha-uv-cache
.venv/bin/uv pip install --python /tmp/sema-ha-venv/bin/python -r requirements-ha-test.txt --cache-dir /tmp/sema-ha-uv-cache
/tmp/sema-ha-venv/bin/python -m pytest -c pytest-ha.ini -q --timeout=30
```

Cesta k stiahnutému interpreteru v príklade je pre miestny Linux x86_64.
Na ARM použi cestu, ktorú vypíše uv; používateľov HA Container už vlastný Python má.
Adresáre `/tmp` sú dočasné, po ich vyčistení prostredie vytvor znova.
Testy používajú prázdne dočasné HA config adresáre vytvorené testovacím frameworkom.
Pôvodné stdlib/HTTP testy spúšťaj podľa predchádzajúcich sekcií.

Konfigurácia izolovaného Container runtime a postup sú v [dev/README.md](../dev/README.md).
Compose zatiaľ nebol spustený: miestne prostredie nemá Docker/Podman.

Formulár požaduje úplnú adresu HTTP(S) a token v password poli. Overuje oba
endpointy, ale nedostupné čerpadlo nebráni párovaniu, ak SEMA odpovedá platne.
Duplicitné UID skončí already_configured, adresu potom uprav cez Reconfigure.
Reconfigure umožní ponechať token prázdnym poľom; reauth vyžaduje nový token.
Obe operácie zachovajú UID aj config entry a pri inej jednotke zmenu odmietnu.
Uložený token sa nikdy nevracia do defaultov formulára. HA ho štandardne uloží
vo vlastnom .storage; tento adresár nikdy nekopíruj do repozitára.

Manifest má Zeroconf matcher `_sema._tcp.local.`. Discovery flow žiada iba token,
predvyplnenú adresu skladá zo sieťového oznamu a overuje UID odpovede proti oznamu.
20 nových testov v tests/ha/test_discovery.py overuje validáciu oznamov, IPv6/port,
duplicitné flow, chybný token aj odmietnutie iného UID. Existujúcu adresu neprepisuje
na základe mDNS a uložené tokeny pri discovery nepoužíva. [Podrobnosti](DISCOVERY.md).

Runtime pri setup vytvorí jeden SemaDataUpdateCoordinator a zavolá
async_config_entry_first_refresh. Info/UID/capabilities sa načítajú raz pri setup,
ďalšie aktualizácie čítajú iba state. Reload znova načíta aj info.
Po prvom načítaní sa forwardujú platformy sensor a binary_sensor. Vytvárajú len
podporované merania podľa capabilities a diagnostiku povinných metadát API v1.

### Spoločný koordinátor

Interval je max(30 s, odporúčanie zariadenia). Koordinátor používa štandardný HA
mechanizmus: prvý odberateľ spustí polling, posledný odberateľ ho zastaví.
Entity sú implementované cez CoordinatorEntity, ich aktívne odbery spustia polling.
Koordinátorové testy izolujú odbery od platforiem a testy entít overujú aj skutočné
platformy/registre a to, že množstvo senzorov nezvyšuje počet GET požiadaviek.

- `sema_available` vyjadruje poslednú úspešnú validovanú odpoveď info/state.
- `snapshot_fresh` porovnáva observed_at s UTC časom HA a max_age_seconds.
- `measurements_available` vyžaduje úspešný transport, čerstvý snapshot aj
  pump_available=true. Budúce meracie entity musia použiť túto podmienku,
  nie iba last_update_success. Chýbajúce či nepodporované polia zostávajú None.

HTTP 200 s pump_available=false/null, bez snapshotu alebo so starým snapshotom
je úspech komunikácie, nie platné aktuálne meranie. Pri chybe komunikácie sa
posledný snapshot zachová, ale merania sú nedostupné. Vlastný časovač upozorní
odberateľov pri prekročení veku snapshotu aj počas čakajúcej HTTP požiadavky;
nespúšťa nový GET ani neprepisuje hodnoty. Výpadok jedného XML už API mapuje na null
príslušných polí, koordinátor nezneprístupní ostatné čerstvé hodnoty.

Transportné chyby predlžujú interval pokusov na 30/60/120/240/300 s pri predvolenom
pollingu; úspech ho obnoví. Retry-After môže prestávku predĺžiť. Pri opakovanom
setup sa ponechá ten istý klient s cooldownom, ak sa adresa/token nezmenili,
aby skorší HA setup retry nespôsobil predčasný HTTP request. Nové poverenie
dostane nový klient. Odvolaný token vyvolá HA reauth a zastaví automatický polling.
Neplatná verzia/identita/protokol merania zneprístupnia; cudzie údaje sa neprijmú.
Unload zruší interval, expiráciu aj HA-spravovanú rozbehnutú požiadavku;
spoločná HTTP session ostáva vo vlastníctve HA.

85 HA-native testov zahŕňa 18 testov koordinátora: spoločný poll pre odberateľov,
stale/partial/offline, obnovu, expiráciu počas požiadavky, backoff, Retry-After,
reauth, štart bez čerpadla, pomalší odporúčaný interval a unload vrátane in-flight.
Ďalších 16 testov entít overuje hodnoty, jednotky/triedy, predvolene vypnuté
teploty, sk/en názvy, capabilities, čiastočné/unknown/offline/stale údaje, tokenovú
reauth, spoločný polling, registry pri zmene IP/názvu/ID a unload/reload.
Podrobná dostupnosť a predvolené entity sú v [ENTITIES.md](ENTITIES.md).
Diagnostický export a jeho 4 testy sú implementované vrátane HA download API;
rozsah anonymizácie je v [DIAGNOSTICS.md](DIAGNOSTICS.md). Lokálne prešiel oficiálny
hassfest 2026.10.4, projektový Ruff check/format a strict mypy celej integrácie.
Oddelené prostredia, verzie, príkazy a pripravený GitHub workflow sú
v [VALIDATION.md](VALIDATION.md). GitHub workflow bez pushu ešte nebežal.
Zostáva browserové/živé overenie a distribučné kontroly.
Reálny test na sema-001 až po autorizovanom testing nasadení nového API.

## Zdroje

- https://contributors.home-assistant.io/core/integrations/fetching-data/
- https://contributors.home-assistant.io/core/integrations/config-flow/
- https://contributors.home-assistant.io/core/integrations/reauth-reconfigure/
- https://github.com/home-assistant/core/blob/2026.9.4/homeassistant/config_entries.py
- https://contributors.home-assistant.io/core/integrations/manifest/
- https://contributors.home-assistant.io/marketplace/reference/repository-structure/

Integrácia je Python custom component, nie HA add-on ani ESPHome firmware. Automatické discovery, ovládanie a verejné publikovanie zatiaľ nie sú implementované.
