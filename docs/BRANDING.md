# Logo SEMA v Home Assistante

Používateľ poskytol pôvodné logo SEMA (SeMa/eco) na použitie v tejto integrácii.
Zdrojový PNG má 948 × 914 px a už obsahuje priehľadnosť. Nemeníme jeho motív,
text ani farby. Pri zmenšení sa zachováva pomer strán a pridáva sa priehľadný
okraj, aby logo nebolo orezané.

Distribučné obrázky sú v `custom_components/sema/brand/`:

- `icon.png`: 256 × 256 px, PNG RGBA.
- `icon@2x.png`: 512 × 512 px, PNG RGBA pre displeje s vyššou hustotou pixelov.

Rovnaký znak slúži ako ikona aj logo; HA pre požiadavku na `logo.png` použije
podporovaný fallback na `icon.png`. Duplicitné logo súbory preto nepridávame.
V Core 2026.9.4 aj chýbajúce `logo@2x.png` spadne na základné `icon.png`,
nie na `icon@2x.png`; 512-pixelová verzia je dostupná pri požiadavke na ikonu @2x.
Lokálne obrázky značky podporuje HA od verzie 2026.3; náš cieľ 2026.9.4 ich
vie použiť priamo, bez publikovania do centrálneho repozitára značiek.

Pri ručnej inštalácii skopíruj aj celý adresár `brand`. Po aktualizácii HA
reštartuj a obnov stránku prehliadača, aby sa znovu načítali metadáta a obrázky.
Toto logo označuje integráciu SEMA v UI; jednotlivé teploty a stavy si ponechajú
svoje funkčné ikony (teplomer, radiátor, ohrievač vody).

Podklady: [lokálne obrázky značky v HA](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/)
a [rozmery a fallback loga](https://github.com/home-assistant/brands/blob/master/README.md).
