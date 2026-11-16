Mohammed validates before production seed.

Numeric values are volumetric water content. Names and training-system text are catalogue data, not UI strings. Rows marked draft are not for production until the agronomist confirms them.

## crops.yaml

| value | unit | source | status |
| --- | --- | --- | --- |
| table_grape, perennial, sort 1, fr Vigne (raisin de table), ar كرمة (عنب المائدة), en Table grape | — | AGRECT catalogue | cited |
| apple, perennial, sort 2, fr Pommier, ar التفاح, en Apple | — | AGRECT catalogue | cited |
| olive, perennial, sort 3, fr Olivier, ar الزيتون, en Olive | — | AGRECT catalogue | cited |
| wheat, annual, sort 4, fr Blé, ar القمح, en Wheat | — | AGRECT catalogue | cited |
| barley, annual, sort 5, fr Orge, ar الشعير, en Barley | — | AGRECT catalogue | cited |

## training_systems.yaml

Wheat and barley have no training system.

| value | unit | source | status |
| --- | --- | --- | --- |
| table_grape vsp, fr Position verticale des rameaux / Rameaux attachés à la verticale sur un seul mur, ar الوضع العمودي للطرود / طرود مربوطة عمودياً على جدار واحد, en Vertical shoot position / Shoots tied upright on one wall | — | draft labels, agronomist to validate | draft |
| table_grape pergola, fr Pergola surélevée / Couvert étalé à plat au-dessus de la hauteur d'homme, ar العريشة العلوية / مجموع خضري مبسوط أفقياً فوق مستوى الرأس, en Overhead pergola / Canopy spread flat above head height | — | draft labels, agronomist to validate | draft |
| table_grape open_gable, fr Gable ouvert (Y) / Deux bras de végétation ouverts en Y, ar الجملون المفتوح (Y) / ذراعان نباتيان مفتوحان على شكل Y, en Open gable (Y) / Two canopy arms open in a Y | — | draft labels, agronomist to validate | draft |
| table_grape lyre, fr Lyre / Deux rideaux verticaux en U, ar القيثارة / ستارتان عموديتان على شكل U, en Lyre / Two upright curtains in a U | — | draft labels, agronomist to validate | draft |
| apple tall_spindle, fr Fuseau haut / Axe unique, couronne étroite, ar المغزل الطويل / محور واحد وتاج ضيق, en Tall spindle / Single leader, narrow canopy | — | draft labels, agronomist to validate | draft |
| apple central_leader, fr Axe central / Un tronc principal avec des étages de branches, ar المحور المركزي / جذع رئيسي واحد مع طبقات من الأفرع, en Central leader / One main trunk with tiers of branches | — | draft labels, agronomist to validate | draft |
| apple trellis, fr Palissage (V ou plan) / Branches attachées à un mur ou en V, ar التعريشة (على شكل V أو مستوية) / أفرع مربوطة إلى جدار أو على شكل V, en Trellis (V or planar) / Branches tied to a wall or a V | — | draft labels, agronomist to validate | draft |
| olive hedgerow, fr Haie fruitière / Mur continu, récolte mécanique, ar السياج الشجري / جدار متصل يُحصد آلياً, en Hedgerow / Continuous wall, machine harvested | — | draft labels, agronomist to validate | draft |
| olive vase, fr Gobelet / Centre ouvert avec trois à quatre charpentières, ar الكأس / مركز مفتوح بثلاثة إلى أربعة أذرع, en Vase / Open centre with three to four arms | — | draft labels, agronomist to validate | draft |
| olive single_trunk, fr Tronc unique (forme libre) / Conduite traditionnelle sur un seul tronc, ar جذع واحد (شكل حر) / تربية تقليدية على جذع واحد, en Single trunk (free form) / Traditional, trained to one trunk | — | draft labels, agronomist to validate | draft |

## varieties.yaml

The proper name is the same in French, Arabic and English. code is the lower-case slug of that name.

| value | unit | source | status |
| --- | --- | --- | --- |
| table_grape red_globe, Red Globe, sort 1 | — | draft list, agronomist to validate | draft |
| table_grape crimson_seedless, Crimson Seedless, sort 2 | — | draft list, agronomist to validate | draft |
| table_grape thompson_seedless, Thompson Seedless, sort 3 | — | draft list, agronomist to validate | draft |
| table_grape muscat_of_alexandria, Muscat of Alexandria, sort 4 | — | draft list, agronomist to validate | draft |
| table_grape cardinal, Cardinal, sort 5 | — | draft list, agronomist to validate | draft |
| apple golden_delicious, Golden Delicious, sort 1 | — | draft list, agronomist to validate | draft |
| apple gala, Gala, sort 2 | — | draft list, agronomist to validate | draft |
| apple granny_smith, Granny Smith, sort 3 | — | draft list, agronomist to validate | draft |
| apple fuji, Fuji, sort 4 | — | draft list, agronomist to validate | draft |
| apple red_delicious, Red Delicious, sort 5 | — | draft list, agronomist to validate | draft |
| olive chemlal, Chemlal, sort 1 | — | draft list, agronomist to validate | draft |
| olive sigoise, Sigoise, sort 2 | — | draft list, agronomist to validate | draft |
| olive arbequina, Arbequina, sort 3 | — | draft list, agronomist to validate | draft |
| olive koroneiki, Koroneiki, sort 4 | — | draft list, agronomist to validate | draft |
| olive picholine, Picholine, sort 5 | — | draft list, agronomist to validate | draft |
| wheat vitron, Vitron, sort 1 | — | draft list, agronomist to validate | draft |
| wheat waha, Waha, sort 2 | — | draft list, agronomist to validate | draft |
| wheat simeto, Simeto, sort 3 | — | draft list, agronomist to validate | draft |
| wheat boussellam, Boussellam, sort 4 | — | draft list, agronomist to validate | draft |
| wheat hd1220, HD1220, sort 5 | — | draft list, agronomist to validate | draft |
| barley saida_183, Saida 183, sort 1 | — | draft list, agronomist to validate | draft |
| barley tichedrett, Tichedrett, sort 2 | — | draft list, agronomist to validate | draft |

## soil_textures.yaml

theta_fc and theta_wp are the midpoint of the Table 19 range. Citation, when present: Allen R.G., Pereira L.S., Raes D., Smith M. (1998). Crop evapotranspiration. FAO Irrigation and Drainage Paper 56, Table 19 (typical soil water characteristics); typical value = midpoint of the range.

sandy_clay_loam, clay_loam and sandy_clay are not in Table 19. Their theta values and citation are null on purpose.

| value | unit | source | status |
| --- | --- | --- | --- |
| sand, fc 0.070–0.170 midpoint 0.120, wp 0.020–0.070 midpoint 0.045, fr Sable, ar رملية, en Sand | m3/m3 | FAO-56 Table 19, midpoint of the range | cited |
| loamy_sand, fc 0.110–0.190 midpoint 0.150, wp 0.030–0.100 midpoint 0.065, fr Sable loameux, ar رملية طميية, en Loamy sand | m3/m3 | FAO-56 Table 19, midpoint of the range | cited |
| sandy_loam, fc 0.180–0.280 midpoint 0.230, wp 0.060–0.160 midpoint 0.110, fr Loam sableux, ar طميية رملية, en Sandy loam | m3/m3 | FAO-56 Table 19, midpoint of the range | cited |
| loam, fc 0.200–0.300 midpoint 0.250, wp 0.070–0.170 midpoint 0.120, fr Loam, ar طميية, en Loam | m3/m3 | FAO-56 Table 19, midpoint of the range | cited |
| silt_loam, fc 0.220–0.360 midpoint 0.290, wp 0.090–0.210 midpoint 0.150, fr Loam limoneux, ar طميية غرينية, en Silt loam | m3/m3 | FAO-56 Table 19, midpoint of the range | cited |
| silt, fc 0.280–0.360 midpoint 0.320, wp 0.120–0.220 midpoint 0.170, fr Limon, ar غرينية, en Silt | m3/m3 | FAO-56 Table 19, midpoint of the range | cited |
| silty_clay_loam, fc 0.300–0.370 midpoint 0.335, wp 0.170–0.240 midpoint 0.205, fr Loam argilo-limoneux, ar طميية طينية غرينية, en Silty clay loam | m3/m3 | FAO-56 Table 19, midpoint of the range | cited |
| silty_clay, fc 0.300–0.420 midpoint 0.360, wp 0.170–0.290 midpoint 0.230, fr Argile limoneuse, ar طينية غرينية, en Silty clay | m3/m3 | FAO-56 Table 19, midpoint of the range | cited |
| clay, fc 0.320–0.400 midpoint 0.360, wp 0.200–0.240 midpoint 0.220, fr Argile, ar طينية, en Clay | m3/m3 | FAO-56 Table 19, midpoint of the range | cited |
| sandy_clay_loam, all theta null, citation null, fr Loam argilo-sableux, ar طميية طينية رملية, en Sandy clay loam | m3/m3 | not in FAO-56 Table 19 | cited |
| clay_loam, all theta null, citation null, fr Loam argileux, ar طميية طينية, en Clay loam | m3/m3 | not in FAO-56 Table 19 | cited |
| sandy_clay, all theta null, citation null, fr Argile sableuse, ar طينية رملية, en Sandy clay | m3/m3 | not in FAO-56 Table 19 | cited |
