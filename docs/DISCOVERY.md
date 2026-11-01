# Automatické objavenie SEMA

Implementované lokálne v HA integrácii aj zdrojovom projekte sema, **nenasadené**.
HA-native testy používajú fiktívne mDNS oznamy a mock API; skutočný multicast medzi
RPi a používateľovým HA Container ešte nebol testovaný.

## Postup zákazníka

1. Nainštaluje custom integráciu SEMA do HA (distribučný postup sa ešte pripravuje).
2. V SEMA → Informácie o zariadení → Home Assistant vytvorí token a skopíruje ho tlačidlom.
3. V HA sa pri dostupnom mDNS objaví nájdená SEMA. Klikne na pridať a zadá iba token.
4. HA overí oba autentifikované endpointy a porovná device_uid s nájdenou jednotkou.

Ručné pridanie adresou/tokenom zostáva dostupné, ak discovery nefunguje.
Oznamovanie sa zapne s HA API, pri odvolaní tokenu sa služba stiahne zo siete.
Rotácia nemení identitu ani nevysiela token do siete cez mDNS.

## DNS-SD kontrakt

| Položka | Hodnota |
| --- | --- |
| Typ služby | `_sema._tcp.local.` |
| Názov inštancie | `SEMA <device_uid>._sema._tcp.local.` |
| Server | `sema-<UUID bez pomlčiek>.local.` |
| Adresa | IPv4 zákazníckeho LAN rozhrania SEMA |
| Port | 80 štandardne cez nginx; konfigurovateľný |
| TXT device_uid | perzistentné UUID ako v autentifikovanom info/state |
| TXT api_version | reťazec `1` |
| TXT scheme | `http` alebo `https`, musí zodpovedať skutočnému endpointu |

TXT neobsahuje token/hash, účty, heslá pumpy, konfiguráciu ani osobné údaje.
HA nepoužíva ľubovoľnú URL/cestu z TXT: adresu zostaví z IP, portu a povolenej
schémy a používa svoje pevné info/state cesty. SEMA publikuje zatiaľ IPv4;
HA discovery flow vie prijať aj platnú IPv6 adresu a port.

mDNS je neautentifikovaný tip, nie dôkaz identity servera. Nové zariadenie vždy
vyžaduje token a následné porovnanie UID. Existujúcej config entry sa adresa ani
poverenie na základe mDNS automaticky nemenia a uložený token sa nikam neposiela.
Zmenu adresy existujúcej jednotky zatiaľ rieši Reconfigure. Duplicitný/pending
oznam ďalšiu entry nevytvorí. HTTP prototyp stále predpokladá dôveryhodnú LAN;
discovery ani samotné porovnanie UUID nenahrádza TLS/bezpečné párovanie.

## Zariadenie a testovacie nasadenie

Zariadenový backend potrebuje nové balíky `zeroconf==0.151.1` a `ifaddr==0.2.0`.
Pri autorizovanom testing kroku ich treba nainštalovať do runtime venv; bežný
updater to automaticky nerobí. Bez nich zostáva API funkčné s ručným pridaním,
discovery hlási statickú chybu do logu a skúša opäť neskôr.

Predvolené rozhranie je `wlan0` (zákaznícka LAN), nie pumpový Ethernet alebo VPN.
Konfigurácia v prostredí zariadenovej služby:

| Premenná | Predvolená hodnota / význam |
| --- | --- |
| SEMA_HA_DISCOVERY_INTERFACES | `wlan0`; zoznam povolených LAN rozhraní oddelených čiarkou |
| SEMA_HA_DISCOVERY_PORT | `80`; pri priamom vývojovom backende napr. `8000` |
| SEMA_HA_DISCOVERY_SCHEME | `http`; `https` iba pri skutočne nakonfigurovanom TLS |

Publisher sa prebúdza po zmene tokenu a každých 30 s preverí rozhrania. Zmenu
adresy publikuje znova, pri strate rozhrania alebo vypnutí API oznam odstráni.
Sieťová chyba nesmie vyradiť ručné HA API ani zber čerpadla.

V HA musí byť zapnutý Zeroconf (súčasť default_config, pri minimálnom configu
explicitne `zeroconf:`). Multicast musí prechádzať medzi HA a SEMA v LAN.
Pri HA Container/OMV treba overiť reálnu Docker sieť; host networking je bežná
možnosť, bridge/VLAN môžu vyžadovať osobitné nastavenie. Používateľov kontajner
sa zatiaľ nemenil. Izolovaný Compose s loopback simulátorom automaticky
neoznamuje fiktívne zariadenie: v ňom sa zatiaľ používa ručné pridanie.

Podklad: [HA Zeroconf](https://www.home-assistant.io/integrations/zeroconf/),
[manifest](https://contributors.home-assistant.io/core/integrations/manifest/),
[python-zeroconf](https://python-zeroconf.readthedocs.io/en/latest/api.html).
