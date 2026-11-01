# Izolovaný HA pre vývoj

Pripravená konfigurácia pre Docker Engine s Compose v2. V prostredí Codexu
Docker nie je dostupný; tento stack zatiaľ **nebol spustený**. Samostatný Python
3.14.5/HA 2026.9.4 venv už slúži na HA-native testy podľa docs/DEVELOPMENT.md.
Nie je to inštalačný postup hotovej SEMA integrácie.

Z koreňa repozitára na vývojovom počítači s Dockerom:

```bash
docker compose -f dev/compose.yaml config --quiet
docker compose -f dev/compose.yaml pull
docker compose -f dev/compose.yaml up -d
docker compose -f dev/compose.yaml logs --tail=100 homeassistant mock
```

Testovací HA je na http://127.0.0.1:18123. Pri prvom spustení vytvor nový
testovací účet. Konfigurácia a DB zostávajú v samostatnom Docker volume
`sema-ha-dev_ha-config`, mimo Gitu. Nepoužívaj produkčný HA config ani zálohu.
Projekt používa vlastnú internú sieť, bez host network, zariadení a D-Bus.
HA preto nebude mať bežné LAN discovery ani internetový prístup.

Mock zdieľa sieťový namespace testovacieho HA. Jeho adresa **z HA** je
`http://127.0.0.1:8124`, token je verejný demo token z hlavného README.
Port simulátora sa nepublikuje na hostiteľa. Prvý beh over takto:

```bash
docker compose -f dev/compose.yaml exec homeassistant python3 --version
docker compose -f dev/compose.yaml exec homeassistant python3 -c 'import json, urllib.request; r=urllib.request.Request("http://127.0.0.1:8124/device-api/v1/info", headers={"Authorization":"Bearer sema-demo-token-not-for-production"}); print(json.load(urllib.request.urlopen(r, timeout=5)))'
```

Komponent sa pripája read-only zo zdrojov; po zmene Python kódu reštartuj
testovací HA. Cez Nastavenia → Zariadenia a služby → Pridať integráciu → SEMA
sa dá v konfiguračnom prototype pridať adresa/token. Použi adresu mocku vyššie.
Po setup vzniknú podporované senzory/stavové entity a diagnostické entity;
všetky používajú jeden spoločný poll od 30 s. E/F/G a výmenník sú predvolene
vypnuté v registri entít. Zobrazujú sa fiktívne dáta simulátora, nie čerpadla.
Browserový tok zatiaľ nebol overený; HA-native flow testy sú samostatné.
Pri opätovnom vytvorení HA kontajnera znovu vytvor aj mock, aby zdieľal
aktuálny sieťový namespace (`up -d --force-recreate`).

Zastavenie so zachovaním testovacích dát:

```bash
docker compose -f dev/compose.yaml down
```

Podklad: [HA Container](https://www.home-assistant.io/installation/linux#install-home-assistant-container)
a [Docker Compose networking](https://docs.docker.com/compose/how-tos/networking/).
