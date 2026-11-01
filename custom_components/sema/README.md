# Read-only prototyp komponentu

Obsahuje async read-only klienta, protokolové modely, config flow a sk/en texty.
Pridanie overí info aj state, uloží adresu/token a použije device_uid pre identitu.
Reauth/reconfigure zachovávajú tú istú config entry a odmietnu iné zariadenie.
Token nie je predvyplnený; reconfigure ho pri prázdnom poli zachová.
Setup vytvorí jeden DataUpdateCoordinator, overí info/UID a načíta prvý snapshot.
Koordinátor používa spoločnú HA HTTP session. Info sa číta len pri setup,
každý poll číta jediný state pre všetkých odberateľov.
Manifest už má config_flow=true, súbor formulára existuje a má HA-native testy.
Koordinátor rieši dostupnosť, čerstvosť, backoff a Retry-After; polling sa spustí
až pri odberateľoch, ktorými sú entity platforiem sensor a binary_sensor.
Tie poskytujú teploty, percentá výkonu, stavy čerpadla a diagnostické entity
pre spojenie a čerstvosť snapshotu. Merania sa vytvárajú podľa capabilities,
neznáme hodnoty zostávajú unknown. E/F/G a výmenník sú predvolene vypnuté.
Tento prototyp je overený HA-native testami proti mock dátam, nie živým zariadením,
a zatiaľ nie je určený na produkčnú inštaláciu.
Diagnostický export poskytuje len povolený technický stav z cache, bez konfigurácie,
identifikátorov, tokenov, adries a meraných hodnôt. Je overený aj cez HA download API.
Lokálne prešli hassfest, Ruff a strict mypy; distribúcia a živý test ešte zostávajú.
Ďalšia implementácia vychádza z koreňového
AGENTS.md a docs/API_PROPOSAL.md.
