# SEMA v Home Assistante – používateľský návod

SEMA prenáša do Home Assistanta aktuálne teploty a stavy tepelného čerpadla.
Táto verzia údaje iba číta. Teploty, režimy ani chod čerpadla z HA nenastavuje.
Komunikácia prebieha priamo medzi HA a zariadením SEMA v lokálnej sieti;
portál nie je potrebný na priebežné čítanie. Prvá inštalácia je testovacia.

**Stav rozšírení:** API v1/revízia 2 je od 1. 11. 2026 nasadené na sema-001/testing
vo vydaní 1.3.0-testing.2 a aktualizovaný HA klient na používateľovom OMV.
Autentifikované čítanie z HA overilo reálne nastavenia, harmonogram a čerstvý
snapshot. Ostatné zariadenia zatiaľ aktualizované neboli. Pôvodný firmvér funguje
s pôvodnými entitami; nové sa na ňom nevytvoria. Po aktualizácii zariadenového
API treba integráciu znovu načítať, aby si HA načítal rozšírené capabilities.
Pri tomto testovacom nasadení bol HA už reštartovaný: potvrdených je **49 entít,
z toho 25 zapnutých**. Ďalšie si môžeš povoliť podľa postupu nižšie.

## Pridanie zariadenia

1. Po nainštalovaní integrácie SEMA reštartuj HA.
2. V SEMA otvor **Informácie o zariadení → Home Assistant** ako administrátor.
   Vytvor token a použi **Skopírovať token**. Zobrazí sa iba pri vytvorení.
3. V HA otvor **Nastavenia → Zariadenia a služby**. Pri nájdenej SEMA zvoľ
   **Konfigurovať** a vlož token. Automatické objavenie vyžaduje priechodný
   mDNS multicast medzi HA a SEMA; VPN sama o sebe ho nezabezpečuje.
4. Ak sa zariadenie neobjaví, použi **Pridať integráciu → SEMA**. Zadaj lokálnu
   adresu vrátane `http://` alebo `https://` a token. Napríklad `http://192.0.2.10`;
   ide o ilustračnú adresu; nahraď ju skutočnou lokálnou adresou svojho zariadenia SEMA.
5. Po pridaní otvor zariadenie a skontroluj teploty aj diagnostiku spojenia.

Token je určený iba pre HA a čítanie údajov. Nepoužívaj heslo čerpadla ani
portálový token. Token neposielaj do správ, snímok obrazovky či verejných hlásení.
Pri HTTP používaj dôveryhodnú LAN; HTTP prenos token nešifruje.

## Čo znamenajú jednotlivé entity

| Entita | Význam |
| --- | --- |
| Vonkajšia teplota | Vonkajšia teplota hlásená čerpadlom. |
| Vnútorná teplota | Vnútorná teplota hlásená čerpadlom; dostupnosť závisí od jeho snímačov. |
| Teplota TÚV | Aktuálna teplota teplej úžitkovej vody hlásená čerpadlom. |
| Teplota kúrenia | Aktuálna teplota vykurovacej vody podľa údaja čerpadla. |
| Žiadaná teplota kúrenia | Cieľová teplota hlásená reguláciou; nie aktuálne nameraná teplota ani ovládací prvok. |
| Percentuálny výkon | Percentuálny údaj čerpadla. Nejde o elektrický príkon vo wattoch. |
| Kúrenie (odvodené) | Vyhodnotenie, či podľa dostupných stavov prebieha vykurovanie; podrobnosti nižšie. |
| Ohrev TÚV | Čerpadlo hlási stav ohrevu teplej úžitkovej vody. |
| Odmrazovanie | Čerpadlo hlási odmrazovanie. |
| Porucha | Všeobecný chybový stav hlásený čerpadlom; podrobnosti over v jeho regulácii alebo SEMA dashboarde. |

### Nové prevádzkové stavy a režimy

Všetky nasledujúce entity sú iba na čítanie, aj keď zobrazujú hodnoty, ktoré sa
v SEMA dashboarde dajú nastavovať. V HA zostávajú bežnými senzormi, bez prepínačov.

| Entita | Čo zobrazuje |
| --- | --- |
| Zapnutie čerpadla | Zapnuté alebo vypnuté podľa nastavenia regulácie; neznamená automaticky bežiaci kompresor. |
| Nastavený režim čerpadla | Kúrenie alebo chladenie podľa nastavenia regulácie. |
| Sezónny režim | Leto alebo zima. |
| Aktuálny prevádzkový stav | Čerpadlo hlási kúrenie, chladenie, vypnutie, odmrazovanie alebo poruchu. |
| Hlásený zdroj ohrevu | Kompresor, bivalent 1, bivalent 2 alebo letný režim; nejde o samostatné meranie relé či elektrického príkonu. |
| Stav ohrevu TÚV | Pohotovosť, ohrev alebo elektrický ohrev TÚV. |
| Teplotný útlm | Aktívny/neaktívny stav útlmu hlásený čerpadlom. |
| Vysoký tarif | Aktívny/neaktívny tarifný stav hlásený čerpadlom; nepredstavuje cenu elektriny ani nezávislé overenie HDO. |

**Nastavenie a skutočná činnosť sú rôzne údaje.** Čerpadlo môže byť zapnuté,
nastavené na kúrenie v zimnom režime, ale práve odmrazovať alebo čakať.
„Aktuálny prevádzkový stav: Kúrenie“ preberá hlásený stav regulácie. Pôvodné
„Kúrenie (odvodené)“ navyše zohľadňuje stav TÚV a nenulový výkon.

### Referenčná teplota a ďalšie nastavenia

**Referenčná teplota vykurovania** je hodnota z karty „Teplota“ v nastaveniach
SEMA. Nie je to meraná izbová teplota ani aktuálna žiadaná teplota vody.
Pri zmene v dashboarde z 20 na 21 °C sa všetkých šesť bodov vykurovacej krivky
posunie o +1 °C. Funkcia „Uložiť referenciu“ však vie zmeniť uloženú referenciu
bez posunu krivky. Hodnota preto nevyjadruje spoľahlivo absolútny posun voči
pôvodnej krivke. Ak uložená referencia chýba, HA nezobrazuje vymyslených 20 °C.
Z HA ju táto verzia nenastavuje.

Ďalších 19 číselných nastavení je predvolene vypnutých diagnostických entít:

| Skupina | Hodnoty |
| --- | --- |
| Vnútorná teplota | Minimum pre chladenie a maximum pre kúrenie, °C. |
| TÚV | Minimálna a maximálna teplota, °C. |
| Krivka vykurovania | Šesť nastavených teplôt vody pri vonkajších −20, −12, −4, +4, +12 a +20 °C. Nejde o šesť aktuálnych meraní. |
| Výkonové limity | Samostatné obmedzenie pre kúrenie, chladenie a TÚV, %. |
| Chladenie | Nastavená teplota chladiacej vody, °C. |
| Bivalent | Bivalentná teplota, °C. |
| Časový limit TÚV | Limit ohrevu v minútach, nie zostávajúci odpočet. |
| Regulácia | Regulačná konštanta bez jednotky. |
| Útlm | Veľkosť útlmu kúrenia a chladenia, °C. |

Zapneš ich v zozname entít zariadenia: otvor konkrétnu entitu, jej nastavenia
a povoľ ju. Výkonové limity sú nastavenia, nie skutočný okamžitý výkon.
Tieto entity sa nepoužívajú ako merania spotreby ani súčtové štatistiky.

### Harmonogram útlmu

Voliteľná, predvolene vypnutá entita **Počet intervalov útlmu** zobrazuje celkový
počet uložených týždenných intervalov. Atribút `schedule` obsahuje rozpis
`mon` až `sun`, vždy najviac štyri intervaly denne, s časmi `from` a `to`.
Napríklad pondelok `06:00–08:00`. Ide o čas podľa regulácie čerpadla,
nie UTC čas alebo automaticky prepočítané časové pásmo HA.
Prázdny načítaný plán má počet 0, neúspešné čítanie je neznáma hodnota.
Aktuálne zapnutie útlmu vždy čítaj z entity **Teplotný útlm**, nie výpočtom
z kalendára. Harmonogram sa do anonymizovaného diagnostického exportu nepridáva.

### Kúrenie (odvodené)

Aktívne znamená, že sú súčasne splnené tri podmienky v údajoch čerpadla:
prevádzkový stav `st1=1`, stav TÚV `st3=0` a percentuálny výkon `pwr>0`.
SEMA teda odvodený stav vypočíta z existujúcich údajov; nemá samostatné meranie
relé kúrenia, elektriny ani dodaného tepla. Nie je to povel na zapnutie.
Neaktívne znamená, že pri známych vstupoch táto kombinácia nie je splnená;
čerpadlo pritom môže napríklad ohrievať TÚV alebo odmrazovať.
Pri neznámych vstupoch sa nevymýšľa vypnutý stav.

Ohrev TÚV je aktívny pri hlásenom `st3=1` alebo `st3=2`. Odmrazovanie sa
preberá zo `st1=4`, všeobecná porucha zo `st1=5`. Význam vychádza z aktuálneho
dekodéra SEMA; interpretáciu pri inom modeli čerpadla treba overiť.

### Prečo sa zobrazovalo „Normálne“ a „Horúci“

Prvá verzia zaradila Kúrenie a Ohrev TÚV do HA triedy `heat`. Tá prekladá
vypnutý/zapnutý stav ako normálny/horúci, hoci tu sledujeme aktivitu režimu.
Tieto slová neznamenali prekročenie teploty, prehriatie ani poruchu.
Upravená verzia používa **Neaktívne/Aktívne**, s ikonou radiátora pre kúrenie
a ohrievača vody pre TÚV. Úprava sa prejaví až po aktualizácii súborov integrácie
a reštarte HA. V automatizáciách zostávajú hodnoty `off` a `on`.

## Diagnostika: ktoré spojenie nefunguje?

| Diagnostická entita | Čo kontroluje |
| --- | --- |
| Pripojenie k API SEMA | HA úspešne komunikuje s API a dostáva platné odpovede; nejde o samotné napájanie RPi. |
| Pripojenie čerpadla | SEMA pri poslednom čerstvom pokuse dostala odpoveď zo stavového rozhrania čerpadla. |
| Čerstvosť snapshotu | Spoločný súbor aktuálnych údajov a stavov nie je starší než povolený limit. |
| Posledný pokus o pozorovanie | Čas posledného dokončeného pokusu o čítanie čerpadla; pokus mohol aj zlyhať. |
| Čerstvosť nastavení | Nastavenia sa úspešne načítali a ich samostatná cache ešte neexpirovala. |
| Posledný pokus o čítanie nastavení | Čas posledného dokončeného pokusu pomalšieho zberu nastavení. |

HA bežne načíta jeden spoločný snapshot každých 30 sekúnd. SEMA zbiera údaje
približne každých 15 sekúnd; zobrazenie preto nie je okamžité. Pri chybách HA
interval dočasne predlžuje. Aktuálny limit čerstvosti API je 60 sekúnd.

Nastavenia a harmonogram sa zbierajú zvlášť približne každých **5 minút**, len
pri zapnutom HA API. Ich limit čerstvosti je **15 minút**. Zmena vykonaná
v dashboarde sa preto v HA môže objaviť s oneskorením do ďalšieho zberu a pollu.
Po prvom zapnutí API môže prvé čítanie chvíľu trvať. Výpadok parametrov
nezneprístupní rýchle teploty; staré nastavenia sa nezobrazujú ako aktuálne.
Ak načítanie parametrov zlyhá, nastavenia budú nedostupné už pri najbližšom
HA pollu; nečaká sa ďalších 15 minút. Samostatná chyba harmonogramu ponechá
ostatné úspešne načítané parametre dostupné.

**Neznáme** znamená chýbajúcu konkrétnu hodnotu. **Nedostupné** znamená, že
meraniu nemožno teraz veriť, napríklad pre výpadok spojenia alebo staré dáta.
Oba stavy sa líšia od skutočnej nuly alebo neaktívneho kúrenia.
Čerstvý pokus môže zlyhať: čerstvosť potom bude aktívna, ale čerpadlo nedostupné.

Teploty E/F/G a výmenníka sú predvolene vypnuté diagnostické entity. Ich fyzické
umiestnenie nie je pre každý model potvrdené. Môžeš ich povoliť v nastaveniach
entít zariadenia; nepremenúvaj ich na spiatočku alebo iný konkrétny snímač bez overenia.

## Vlastný prehľad

Na dashboard pridaj kartu **Entity** alebo **Dlaždica** a vyber entity SEMA
cez editor HA. Začni teplotou vonku, TÚV, kúrenia, žiadanou teplotou,
percentuálnym výkonom a stavmi Kúrenie, Ohrev TÚV, Odmrazovanie a Porucha.
Diagnostiku môžeš ponechať na samostatnej karte. Ikonu aj názov jednotlivých
entít si môžeš prispôsobiť cez ich nastavenia; vlastné úpravy môžu prekryť
predvolené názvy/ikony integrácie.

Kliknutím na teplotu otvoríš detail a dostupnú históriu HA. Tá vzniká až z údajov,
ktoré HA zaznamenáva podľa vlastného nastavenia Recorder; integrácia neimportuje
starú históriu zo SEMA ani portálu. Percentuálny výkon nepatrí do energetického
dashboardu ako W/kWh. Táto verzia nepočíta COP ani spotrebu energie.

## Bežné problémy a údržba

- **SEMA sa nenašla:** použi ručné pridanie. Over, či sú HA a SEMA dostupné
  v rovnakej LAN a či sieť neblokuje multicast. Pri HA Container pomáha správne
  nastavenie siete; používateľov overený kontajner na OMV používa `network_mode: host`.
- **Neplatný token:** over zapnutý HA prístup na SEMA. Vytvorenie nového tokenu
  okamžite odvolá predchádzajúci; nový zadaj do výzvy HA na obnovenie prihlásenia.
- **Zmenená IP:** na integrácii SEMA otvor ponuku a **Zmeniť konfiguráciu**.
  Uprav adresu tej istej jednotky. Prázdne pole tokenu zachová existujúci token.
  Rovnaká jednotka si zachová entity vďaka perzistentnému UID.
- **SEMA pripojená, čerpadlo nie:** over čerpadlo a jeho spojenie so SEMA.
  Samotná výmena HA tokenu tento výpadok neopraví.
- **Staré údaje:** skontroluj čerstvosť a čas posledného pokusu; staré hodnoty
  integrácia zámerne neponecháva ako aktuálne meranie.
- **Chcem zrušiť prístup:** odvolaj token v SEMA. Ak integráciu už nepoužívaš,
  odstráň ju aj v HA; samotné odstránenie v HA token na zariadení neodvoláva.

Pre bezpečné automatizácie používaj reálne ID entít z vlastného HA a interné
stavy `on`/`off`, nie preložené texty. Stav `unavailable` nepovažuj za `off`.
Prvé automatizácie môžu napríklad upozorniť na dlhšie trvajúcu poruchu alebo výpadok;
čerpadlo touto integráciou zatiaľ neovládaš.

Správanie štandardných tried stavov opisuje [dokumentácia binary sensor HA](https://www.home-assistant.io/integrations/binary_sensor/).
