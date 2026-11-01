# Entity prvej čítacej verzie

## Rozšírenie v1/revízia 2 – pripravené, nenasadené

Nové capabilities pridávajú 31 entít k pôvodným 18 záznamom: 3 binary sensors
(zapnutie, útlm, vysoký tarif), 5 enum senzorov (nastavený režim, sezóna, činnosť,
hlásený zdroj ohrevu, TÚV), 20 číselných nastavení, počet intervalov útlmu,
čas čítania nastavení a ich čerstvosť. Pri plných capabilities je teda 49 registry
záznamov, predvolene 25 aktívnych entít. Pôvodné UID sa nemenia.
Referenčná teplota je predvolene aktívna; ďalších 19 nastavení a harmonogram
sú predvolene vypnuté diagnostické entity. Nastavenia nemajú measurement
state_class a žiadna nová entita nič neovláda.

Konfigurácia používa vlastný 300 s zber/900 s expiráciu. Je nezávislá od
dostupnosti rýchleho snapshotu, ale vyžaduje platné API spojenie a úspešný zber.
Samostatný časovač koordinátora oznámi expiráciu aj bez ďalšieho HTTP requestu.
Harmonogram sa zobrazuje ako počet intervalov a atribút schedule; chýbajúci
harmonogram je unknown, platný prázdny 0. Neodvodzovať z neho zapnutie útlmu.
Podrobný [kontrakt](API_EXTENSIONS.md) a [používateľský návod](USER_GUIDE.sk.md).

## Pôvodná sada entít

Implementované v lokálnom prototype, overené HA-native testami na Core 2026.9.4
s mock dátami. Zatiaľ bez živého testu alebo nasadenia. Jedna config entry
reprezentuje fyzickú SEMA a jeden DataUpdateCoordinator načíta snapshot pre všetky entity.

| API pole | HA typ | Jednotka / význam |
| --- | --- | --- |
| temperatures.outdoor_temp | sensor | °C, vonkajšia teplota |
| temperatures.indoor_temp | sensor | °C, vnútorná teplota |
| temperatures.water_temp | sensor | °C, teplota TÚV |
| temperatures.heat_temp | sensor | °C, teplota kúrenia |
| temperatures.equitherm_temp | sensor | °C, aktuálna žiadaná teplota kúrenie |
| temperatures.exchanger_temp | sensor | °C, výmenník; význam overiť pri konkrétnom modeli |
| temperatures.e_temp / f_temp / g_temp | sensor | °C, neutrálne E/F/G; nezačať ich premenovávať na spiatočku bez overenia |
| power_percent | sensor | %, percentuálny výkon, nie W |
| states.heating | binary_sensor | odvodené kúrenie |
| states.dhw | binary_sensor | ohrev TÚV |
| states.defrost | binary_sensor | odmrazovanie |
| states.fault | binary_sensor | všeobecná chyba/problém |
| sema_available (odvodené z koordinátora) | binary_sensor / diagnostika | úspešná validovaná komunikácia s API SEMA |
| pump_available | binary_sensor / diagnostika | odpoveď čerpadla, odlíšiť od dostupnosti samotnej SEMA |
| snapshot_fresh (odvodené z observed_at) | binary_sensor / diagnostika | vek posledného dokončeného pokusu o pozorovanie je v limite |
| observed_at | diagnostický sensor | UTC čas posledného dokončeného pokusu o pozorovanie, nie posledného úspechu |
| info.firmware_version | device info | verzia SEMA |

Teploty majú device_class temperature, state_class measurement a natívne °C.
Percentá majú jednotku % a measurement bez energy/power device_class; nie sú to W.
Kúrenie/TÚV majú vlastné preklady Neaktívne/Aktívne a ikony radiátora/ohrievača,
bez device_class heat (tá zobrazovala zavádzajúce Normálne/Horúci).
Porucha má device_class problem a spojenia connectivity.
Odvodené kúrenie je tak označené aj v názve, nie je potvrdením stavu relé.
E/F/G a výmenník sú diagnostické a predvolene vypnuté v registri entít;
používateľ ich môže zapnúť. Názvy E/F/G nepriraďujú nepotvrdený fyzický význam.
Ostatné podporované entity sú predvolene zapnuté a majú sk/en názvy.

Unique ID je `<device_uid>_<API pole>`, napríklad
`<device_uid>_temperatures.outdoor_temp`, nikdy IP alebo používateľské DEVICE_ID.
Všetky entity patria jednému HA zariadeniu s identifikátorom `(sema, device_uid)`.
Zmena adresy/verejného názvu alebo ID nezakladá nové entity ani zariadenie.
Merané teploty/power/states sa vytvárajú len podľa capabilities pri setup/reload.
Štyri diagnostické entity používajú povinné metadáta v1, preto nezávisia od
capabilities jednotlivých meraní. Neznáme budúce capabilities sa ignorujú.
Ilustračné info fixtures vytvoria 18 záznamov v registri, z nich 14 aktívnych.

Pri čerstvom dostupnom čerpadle je neznáme pole unknown (None), nie 0/false.
Pri výpadku SEMA, offline/neznámom čerpadle alebo starom snapshote sú meracie entity
unavailable. Čiastočný výpadok jednej teploty nezneprístupní ostatné čerstvé polia.

| Situácia | Spojenie SEMA | Spojenie čerpadla | Čerstvosť | Merané entity |
| --- | --- | --- | --- | --- |
| Čerstvé dáta | on | on | on | hodnoty alebo unknown pre null |
| Čerpadlo nedostupné, čerstvý pokus | on | off | on | unavailable |
| Offline čerpadlo bez času pokusu | on | off | unknown | unavailable |
| Ešte žiadny snapshot | on | unknown | unknown | unavailable |
| Zastaraný snapshot | on | unavailable | off | unavailable |
| Chyba komunikácie/tokenu/protokolu | off | unavailable | unavailable | unavailable |

Timestamp observed_at zostáva čitateľný aj pri starom snapshote, pokiaľ SEMA
úspešne odpovedá; null je unknown. Čerstvosť opisuje pokus/snapshot a nezaručuje
úspešné meranie. Expirácia sa oznámi aj počas čakajúceho HTTP requestu.
Merané entity používajú coordinator.measurements_available. Diagnostika spojenia
SEMA môže ukázať off aj pri 429 alebo neplatnom protokole: označuje úspech API,
nie fyzické napájanie Raspberry Pi. Po unload sa entity odpoja a polling sa zastaví.

Climate, number, select, water_heater a nastavovanie teplôt až ďalšia etapa. Nevystavovať prepínanie servisných nastavení, reštart, aktualizácie, pumpové heslá ani provisioning ako entity prvej verzie.
