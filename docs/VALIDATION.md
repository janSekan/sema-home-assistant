# Lokálne a automatické kontroly

Overené 1. 11. 2026. Kontroly sú prípravou na testing, nie potvrdením živého
nasadenia ani prijatím do HACS/Core. Produkčný HA, SEMA ani portál sa nemenili.

| Kontrola | Prostredie | Výsledok |
| --- | --- | --- |
| HA-native testy | Core 2026.9.4, Python 3.14.5 | 85 prešlo |
| Protokol a loopback simulátor | Python 3.12 | 11 prešlo |
| HTTP klient | Python 3.12, aiohttp 3.14.3 | 9 prešlo |
| Ruff check + format check | Ruff 0.16.9 | bez chýb, 26 Python súborov |
| Prísne mypy | mypy 2.3.1, HA 2026.9.4 typy | bez chýb v 11 zdrojových moduloch |
| Oficiálny hassfest | Core 2026.10.4 zdroje a runtime | 1 integrácia, 0 neplatných |
| Projektová statická kontrola, git diff --check | lokálne | prešlo |

## Testy a typy

### Rozšírenie v1/revízia 2 – 1. 11. 2026

Po pridaní režimov, nastavení a harmonogramu prešlo 88 HA-native testov,
13 standalone protokolových/simulačných a 9 HTTP klientových testov. Samostatný
zariadenový projekt: 36 backendových/release testov. Navyše sa overil výstup
skutočného zariadenového exportéra proti HA parseru s ilustračným snapshotom;
capabilities zodpovedajú rozšíreným fixtures. Ruff, strict mypy a hassfest prešli.
Testy overujú starý firmvér, 49 záznamov registra pri plnom kontrakte, disabled
servisné entity, reload, samostatnú expiráciu konfigurácie aj bez HTTP pollu,
hodnoty null/false/0, výpadok parametrov/plánu a súkromie diagnostiky.
Táto revízia zatiaľ nebola nasadená; nejde o živé overenie nových polí na čerpadle.

Izolované testovacie prostredie vytvor podľa [DEVELOPMENT.md](DEVELOPMENT.md).
Nástroje sa inštalujú do testovacieho venv, nie do produkčného HA:

```bash
.venv/bin/uv pip install --python /tmp/sema-ha-venv/bin/python -r requirements-validation.txt --cache-dir /tmp/sema-ha-uv-cache
/tmp/sema-ha-venv/bin/python -m ruff check custom_components/sema tests tools
/tmp/sema-ha-venv/bin/python -m ruff format --check custom_components/sema tests tools
/tmp/sema-ha-venv/bin/python -m mypy
/tmp/sema-ha-venv/bin/python -m pytest -c pytest-ha.ini -q --timeout=30
python3 tools/check_project.py
python3 -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s tests/client -v
git diff --check
```

Ruff pravidlá a strict mypy konfigurácia sú v pyproject.toml. Mypy kontroluje celú
integráciu s reálnymi typmi HA, nie s náhradnými stubmi. Externé HA moduly sa
typovo načítajú, ich vlastné chyby sa cez follow_imports=silent nereportujú.
Lint zahŕňa aj testy/nástroje; malé lokálne test fixtures majú výnimku ASYNC240.
Produkčný async kód túto výnimku nemá. Žiadne mypy ignore chyby sa nepridali.

## Oficiálny hassfest

Použitý je oficiálny custom-integration validačný režim bez preskočených pluginov,
zo zdrojov Core 2026.10.4, commit `357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b`.
Validator je oddelený od HA-native testov, aby nemenil ich cieľ Core 2026.9.4.
Nie je to test behu integrácie na Core 2026.10.4 ani pridelenie quality-scale tier.

Pri prvom vytvorení prostredia (Linux x86_64; Python je podľa DEVELOPMENT.md):

```bash
git clone --depth 1 --branch 2026.10.4 --filter=blob:none --sparse https://github.com/home-assistant/core.git /tmp/sema-hassfest-core
git -C /tmp/sema-hassfest-core sparse-checkout set script
.venv/bin/uv venv /tmp/sema-hassfest-venv --python /tmp/sema-ha-python/cpython-3.14.5-linux-x86_64-gnu/bin/python3.14 --cache-dir /tmp/sema-ha-uv-cache
.venv/bin/uv pip install --python /tmp/sema-hassfest-venv/bin/python -r requirements-hassfest.txt --cache-dir /tmp/sema-ha-uv-cache
/tmp/sema-hassfest-venv/bin/python tools/run_hassfest.py --core-path /tmp/sema-hassfest-core
```

Wrapper overí commit a spustí nezmenený oficiálny skript. Závislosti navyše sú
potrebné pre importy samotného validátora (infrared-protocols/PyGithub/tqdm),
nie pre SEMA runtime. Hassfest používa multiprocessing/IPC; miestny sandbox ho
blokoval, úspešný beh bol mimo sandboxu. Kontrola nevykonáva publish/generate.

## GitHub workflow

Pripravený `.github/workflows/validate.yml` má oddelené standalone, HA a hassfest
joby. Používa read-only oprávnenia, nepersistuje Git poverenia a nepublikuje release.
Zdroj validátora aj actions sú pripnuté na overené SHA. Workflow je zatiaľ len
lokálne pripravený; bez pushu na GitHub sa tam nespustil.

## Čo ešte nie je overené

Živý multicast, HA webUI a komunikácia so sema-001; testing nasadenie API;
licencia, brand/HACS metadata, verejný release a minimálna podporovaná verzia
firmvéru. Pre Core treba navyše oddeliť API klienta do verejnej knižnice a splniť
kompletné pravidlá prijatia. Táto etapa nevyberá licenciu ani nežiada zaradenie.
