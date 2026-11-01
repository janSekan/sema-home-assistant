# Rozšírenie čítania API v1, revízia 2

Kontrakt nasadený 1. 11. 2026 na sema-001/testing, dashboard 1.3.0-testing.2,
release 0553775b9ddc2cb8be4efa5390e8aa82efb0d7ea. HA klient je nasadený na používateľovom
OMV; autentifikované čítanie reálnych dát z HA overené. Existujúce polia
a API verzia 1 zostávajú kompatibilné. Nové entity vznikajú len pri príslušných
capabilities. Starý firmvér funguje s pôvodnou sadou entít.

`states` pridáva `power_on` (control.st1 1/2), `setback` (status.st4 0/1)
a `high_tariff` (status.st5 0/1). `modes` pridáva:

| Pole | Hodnoty | Zdroj |
| --- | --- | --- |
| operating_mode | heating, cooling | control.st2 1/2 |
| season | summer, winter | control.st3 1/2 |
| activity | heating, cooling, off, defrost, fault | status.st1 1..5 |
| heat_source | compressor, bivalent_1, bivalent_2, summer | status.st2 1..4 |
| dhw_mode | standby, heating, electric_heating | status.st3 0..2 |

Používajú sa už zbierané hodnoty zo spoločného snapshotu, bez nových XML GET.
Chýbajúce/neznáme kódy sú null. Pri nedostupnom status.xml sa nové prevádzkové
hodnoty konzervatívne maskujú; chýbajúce control.xml maskuje iba nastavené režimy
a power_on. Nejde o ovládacie entity ani potvrdenie fyzického stavu relé.

Voliteľný objekt `configuration` obsahuje `available`, `observed_at` (UTC),
`max_age_seconds=900`, `values` a `schedule`. Zariadenie ho zbiera samostatne
na pozadí každých 300 s, len ak je HA API zapnuté. Jeden GET parameters.htm
slúži pre všetky nastavenia a útlmy; jeden GET timer.htm pre harmonogram.
Čítanie HA endpointu nerobí pumpové GET ani DB operácie. Pôvodný zber telemetrie
nečaká na tento pomalší zber. Cache nastavení sa neukladá do DB.

`values` obsahuje 20 čísel: `reference_temp`, `min_indoor_cool`,
`max_indoor_heat`, `min_water_temp`, `max_water_temp`, `regulation_constant`,
`limit_water_percent`, `limit_heat_percent`, `limit_cool_percent`,
`cooling_water_temp`, `bivalent_temp`, `dhw_time_limit_minutes`,
`curve_minus20`, `curve_minus12`, `curve_minus4`, `curve_plus4`, `curve_plus12`,
`curve_plus20`, `setback_heat`, `setback_cool`.
Referenčná teplota je existujúca uložená hodnota SEMA, pri neprítomnosti null,
bez predvolenej dvadsiatky. Nie je to meraná izbová teplota ani absolútny posun.

`schedule` je null pri neúspešnom čítaní alebo objekt mon..sun s najviac štyrmi
intervalmi `from`/`to` ako HH:MM. Používa čas regulácie čerpadla, neprevádza ho
na UTC a neodvodzuje z neho aktuálny stav útlmu. Ten poskytuje status.st4.
V HA jeden senzor zobrazuje počet intervalov, rozpis má ako atribút.

Neúspešný zber parametrov zneprístupní konfiguráciu bez ponechania starých hodnôt.
Neúspešný harmonogram neblokuje ostatné nastavenia. Konfigurácia má vlastnú
čerstvosť nezávislú od rýchleho snapshotu. HA neinterpretuje starú cache ako
aktuálne nastavenia, ani keď generated_at odpovede práve vznikol.

Hodnoty nastavení sa v HA zobrazujú ako sensor, nie number/select/switch.
Nastavenia nemajú measurement state_class. Výkonové limity zostávajú percentá,
časový limit má minúty, teploty °C. Servisné hodnoty a body krivky sú
predvolene vypnuté diagnostické entity. Identita pôvodných entít sa nemení.
