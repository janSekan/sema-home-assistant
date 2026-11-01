# Diagnostický export

Implementovaný `custom_components/sema/diagnostics.py` poskytuje štandardné
stiahnutie diagnostiky config entry v HA. Funkčnosť je overená aj cez skutočný
autentifikovaný HA diagnostics HTTP endpoint v izolovaných testoch.
Používateľov HA ani živé SEMA sa týmto netestovali.

Export z integrácie obsahuje iba vopred povolené technické polia:

- verziu diagnostickej schémy a API kontraktu;
- technický stav config entry a nastavenie vypnutia pollingu;
- výsledok posledného update, dostupnosť API/meraní, čerstvosť, interval;
- všeobecnú kategóriu chyby, nikdy jej text alebo traceback;
- podporované známe capability názvy a časové limity API;
- prítomnosť pozorovania, dostupnosť čerpadla, zoznamy známych polí a počet chýb.

Nikdy sa nekopíruje `entry.as_dict()`, entry.data/options, celý runtime ani raw
odpoveď zariadenia. Výstup neobsahuje token, IP/URL/hostname, device_uid/device_id,
entry ID, názov domácnosti/zariadenia, firmware text, časové pečiatky ani samotné
merané hodnoty. Neznáme budúce capability a kódy/texty chýb sa neexportujú.
Žiadne pseudonymizačné hashe identifikátorov sa nevytvárajú.

Export číta iba existujúcu pamäť koordinátora. Nespúšťa HTTP/XML, nezapisuje DB
ani nemení údaje. Funguje aj bez runtime alebo po neúspešnom prvom setup.
HA k súboru štandardne pridáva svoje systémové informácie a manifest integrácie;
vyššie uvedený rozsah opisuje sekciu `data` poskytovanú SEMA integráciou.

Testy kontrolujú neprítomnosť fiktívnych tajomstiev v konfigurácii, názvoch,
identifikátoroch, firmware, budúcich capabilities, chybách a výnimkách.
Kontrolujú aj JSON serializáciu, chýbajúci snapshot a nulový počet sieťových volaní.

Podklad: [HA Diagnostics](https://contributors.home-assistant.io/core/integrations/diagnostics/).
