# Návrh zariadenového API v1 pre Home Assistant

**API v1/revízia 2 je od 1. 11. 2026 nasadené iba na sema-001/testing: 1.3.0-testing.2, release 0553775b9ddc2cb8be4efa5390e8aa82efb0d7ea.** Živé info/state a rozšírená konfigurácia boli overené autentifikovaným klientom z používateľovho HA; v predchádzajúcej revízii aj oddelenie oprávnení a LAN mDNS. Fixtures zostávajú vymyslené príklady. Produkčný rollout a TLS ešte nie sú overené.

## Základ

Nasledujúce [rozšírenie revízie 2](API_EXTENSIONS.md) pridáva režimy a čítanie
nastavení v rovnakom API v1. Je implementované, testované a nasadené na sema-001
aj používateľovom HA; produkčný main sa nemenil.

Base URL: adresa lokálnej SEMA. Cesty /device-api/v1/info a /device-api/v1/state, JSON s číslami/booleanmi/null. Autentifikácia `Authorization: Bearer <HA_TOKEN>` na oboch endpointoch. HA token je samostatný, portálový proxy token sa nesmie použiť. Pri vypnutej integrácii má nové rozhranie zostať neprístupné; presné UX a stavový kód ešte dohodnúť.

Token vytvára lokálny správca v dashboarde, zobrazí sa iba pri vytvorení, na zariadení uchovávať jeho overovací hash. Má ísť odvolať/rotovať bez ovplyvnenia portálu; HA má podporovať zmenu tokenu. Zaviesť explicitné read oprávnenie; budúce ovládanie riešiť samostatne. Na HA GET nesprístupniť heslá pumpy, účty, provisioning ani Wi-Fi konfiguráciu. Nepovoliť API iba na základe LAN/Tailscale rozsahu alebo globálneho LAN_ACCESS.

Transport a párovanie: pre prvý lokálny prototyp HTTP v dôveryhodnej LAN; token cez HTTP nie je šifrovaný. Pred verejným vydaním rozhodnúť podporu HTTPS a bezpečného párovania. Rozhranie nezverejňovať port-forwardom na internet.

## GET /device-api/v1/info

Príklad: fixtures/info.json. Pole api_version=1; nemenné device_uid, používateľsky čitateľné device_id/name, manufacturer/model, firmware_version, zoznam capabilities, odporúčaný polling a maximálny vek snapshotu.

- device_uid je perzistentné UID fyzickej jednotky, nezávislé od IP, pomenovania a resetu telemetrickej DB. Implementácia ho ukladá do súkromného ~/.config/sema/ha-api.json (0600), spolu s hashom tokenu; factory image nesmie klonovať UID/tokeny.
- firmware_version je verzia softvéru SEMA, api_version verzia kontraktu. Sú odlišné.
- capabilities uvádzajú dostupné polia a funkcie. Staršia jednotka nemusí poskytovať všetky senzory. Zoznam má byť filtrovaný na skutočné možnosti.
- Odporúčaný interval 30 s; návrh max_age_seconds=60 s, doladiť s reálnym 15-sekundovým zberom.

## GET /device-api/v1/state

Príklady: fixtures/state.json a state_pump_unavailable.json. Odpoveď obsahuje api_version, device_uid, generated_at, observed_at, pump_available, temperatures, power_percent, states a errors.

- generated_at je čas vytvorenia odpovede; observed_at čas pozorovania čerpadla. Aktuálna HTTP odpoveď nesmie omladiť starý snapshot.
- Časy sú ISO 8601 UTC so Z alebo +00:00. Hodnoty sú °C a percentá, bez vložených jednotiek či lokalizovaných textov.
- Použiť existujúci zberač/cache. API GET nespúšťa nový zber pre každú entitu a nezapisuje SQLite meranie. Na disk sa nezapisuje kvôli samotnému HA pollingu.
- Neznáme číslo/stav je null. Nula a false sú platné známe hodnoty, nezamieňať ich s chýbajúcim údajom.
- Pri čiastočnom výpadku zachovať iba preukázateľne čerstvé údaje a rozlišovať dostupnosť jednotlivých zdrojov; prvý návrh ešte potrebuje rozhodnúť per-field freshness/availability. Odpoveď s pump_available=false nemá vydávať staré teploty/stavy za aktuálne.
- Bez jediného snapshotu observed_at=null a hodnoty null; HA entity sú nedostupné.
- states.heating je odvodený stav podľa existujúceho zberača, nie nezávislé potvrdenie relé/kompresora. errors môžu obsahovať iba skutočne zistené chyby.
- power_percent je percento z pumpy, nie elektrický príkon ani tepelný výkon. Bez merania nie sú power_w, energy_kwh ani COP.

## Chyby a kompatibilita

- 401: chýbajúci/neplatný/odvolaný token; HA vyvolá zmenu prihlasovania, nevypíše token.
- 404: endpoint neexistuje/starý firmware; oznámiť potrebnú verziu, nepokúšať sa o provisioning či legacy login.
- 429: dodržať Retry-After a obmedziť opakovanie, ak ho implementujeme.
- 5xx/timeout: komunikačná chyba SEMA, retry/backoff; neprepisovať senzory nulami.
- HTTP 200 + pump_available=false: SEMA odpovedá, čerpadlo je nedostupné.
- Novšie neznáme aditívne polia ignorovať. Chýbajúce capability neznamená fyzickú nulu. Nepodporovaná api_version má zrozumiteľnú chybu.
- Príkazy na zmenu kúrenia/teplôt zatiaľ nie sú súčasťou v1 prvej etapy. Simulátor odmieta POST/PUT/DELETE.

## Overenie a následná implementácia

Discovery je samostatný neautentifikovaný DNS-SD oznam `_sema._tcp.local.`
so schémou, verziou API a device_uid; token/hash sa neoznamuje. API endpointy
naďalej vždy vyžadujú HA token. HA po tokenovom potvrdení overí UID a nikdy
automaticky neposiela uložené poverenie na novo oznámenú adresu.
Presný [discovery kontrakt](DISCOVERY.md) je implementovaný lokálne na oboch stranách,
ale nie je nasadený ani overený multicastom v reálnej LAN.

### Overenie zdrojového kódu 1. 11. 2026

V lokálnom `sema/backend/telemetry.py` už existuje `collector.last_observed`
so sekciami `ts`, `values`, `state` a `raw`. Toto je overenie zdrojov, nie
potvrdenie nasadenia. GET má pod existujúcim `collector.lock` prevziať kópiu
snapshotu; nesmie volať `fetch_snapshot()` ani zapisovať meranie.

| Pole API | `last_observed` |
| --- | --- |
| outdoor_temp / indoor_temp | values.ot / values.it |
| water_temp / heat_temp | values.wt / values.ht |
| equitherm_temp / exchanger_temp | values.eqt / values.ext |
| e_temp / f_temp / g_temp | values.et / values.ft / values.gt |
| power_percent | values.pr |
| states.heating / dhw / defrost / fault | rovnomenné položky state |
| observed_at | ts |

`collector.previous` nie je vhodný pre aktuálne entity: zámerne zachováva
predchádzajúce hodnoty pri čiastočných výpadkoch. Neprítomný stav v aktuálnom
snapshote sa preto mapuje na null, nikdy na starú hodnotu z `previous`.

Implementované pravidlá lokálneho prototypu v1:

- `pump_available` znamená úspešné načítanie status.xml
  (`state["available.status"]`); bez snapshotu je null.
- Pri zlyhaní status.xml je `pump_available=false` a všetky hodnoty čerpadla
  sú null, aj keď iný XML zdroj odpovedal. Je to konzervatívna politika v1.
- Pri dostupnom status.xml a výpadku temperatures.xml zostávajú údaje zo
  status.xml použiteľné; teploty z temperatures.xml sú null. Výpadok control.xml
  neblokuje entity v tabuľke, ktoré z neho aktuálne nečítajú.
- Chýbajúce/neplatné čísla aj nerozpoznané stavy sú null; capabilities vyjadrujú
  podporu poľa, nie úspech jeho posledného načítania.
- `observed_at` pri neúspešnom pokuse môže označovať čas tohto pokusu, ale
  `pump_available=false` vždy zneprístupní merané entity. Bez pokusu je null.
- HA samostatne overí vek snapshotu podľa `max_age_seconds`; čerstvá HTTP
  odpoveď ani príznak dostupnosti nesmú prekryť staré pozorovanie.

Mapovanie a pravidlá vyššie sú implementované. Nasledujúce rozhodnutia nahrádzajú
otvorené body pôvodného návrhu v úvode:

- Perzistentné UUID a SHA-256 hash náhodného 256-bit tokenu so scope read sú
  v `~/.config/sema/ha-api.json` používateľa služby, mimo DB a checkoutu; alternatíva
  je SEMA_HA_STORE_PATH. Súbor 0600, zamknuté atomické zápisy len pri zmene.
- Administrátor/superadmin spravuje token v Informáciách o zariadení, aj cez
  existujúci portál pri LAN locku. GET `/device-api/integrations/home-assistant`,
  POST/DELETE `/device-api/integrations/home-assistant/token`.
- Token má prefix `sema_ha_`, zobrazuje sa iba pri vytvorení. Rotácia odvolá starý.
  Vypnuté API vracia 401 rovnako ako neplatný token. HA token mimo v1 info/state
  middleware odmietne 403; zápisy na info/state vracajú 405. Odpovede sú no-store.
- Bez snapshotu je pump_available=null, observed_at=null a všetky merané hodnoty
  null. Pri výpadku je observed_at čas dokončenia pokusu, nie posledného úspechu.
- Neznáma firmware_version je null. Capabilities znamenajú polia podporované
  backendovým dekodérom; reálne poskytovanie hodnôt konkrétnou pumpou treba overiť.

Vo firmvéri sú lokálne ASGI kontraktové a bezpečnostné testy; HA klient a validácia
protokolu sú lokálne otestované proti fixtures a simulátoru. Pred vydaním zostáva TLS/párovanie, limity pollingu, overenie reálnych
capabilities a autorizované testovanie sema-001 + HA. Zariadenový kontrakt a
postup sú v projekte sema v docs/HOME_ASSISTANT_API.md. Žiadne nasadenie neprebehlo.
