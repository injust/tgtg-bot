from __future__ import annotations

archived: set[int] = {
    # Evana Patisserie & Cafe
    791287,  # Beautiful Pastries
    # Francesca Bakery - 1
    1209374,  # Surprise Bag
    # GG Sushi
    126130613638166529,  # Surprise Bag
    # Kin-Kin Bakery (Agincourt Mall)
    507834,  # Surprise Bag
    # La Rocca Creative Kitchen
    379533,  # Cakes
    # La Rocca Creative Kitchen
    505340,  # Cakes
    # McEwan Fine Foods (Don Mills) - SUSHI
    89306236213788353,  # $30 Surprise Bag
    89071801115092961,  # $24 Surprise Bag
    # NUBON MARKET
    82906386258609857,  # Groceries
    # Rose's Chester Fried Chicken
    519782,  # Assorted Fried Chicken & Filipino Foods
    # Sing Bakery
    766896,  # Bread Bag
    # Sugar N Spice
    1350295,  # Baked Goods
    # Summerhill Market - Annex
    376273,  # Baked Goods
    # Summerhill Market - Forest Hill
    376264,  # Baked Goods
    # Summerhill Market - Rosedale
    376263,  # Baked Goods
    # Sushi Shop - Union Station
    121403951647965025,  # Surprise Bag
    # Taste Good BBQ
    649873,  # BBQ and Chinese food
}

bad_timing: set[int] = {
    # Kung Fu Tea - Broadview
    1485596,  # Surprise Bag
    88553512050558529,  # Surprise Bag
    # Kung Fu Tea - Downtown - Wellesley on Yonge
    377151,  # Surprise Bag
    # Yin Ji Chang Fen - Warden
    790540,  # Prepared meal
}

disabled: set[int] = {
    # Bake Code (Midland Ave.) - Scarborough
    646160,  # Baked Goods
    # Ensanemada
    633196,  # Surprise Bag
}

far: set[int] = {
    # A Tavola
    82874509545092577,  # Surprise Bag
    # Aunt Beth Bakes
    940373,  # Whiskey Cookie Surprise Bag
    # Bingz Crispy Burger 西少爷肉夹馍 - CF Fairview Mall
    1076410,  # Surprise Bag!
    43839166580614081,  # Surprise Bag (L)
    114343305084580097,  # Surprise Bag
    # Bingz Crispy Burger 西少爷肉夹馍 - Eaton Center
    36249191346825633,  # Surprise Bag
    43837672200426849,  # Surprise Bag （L）  # noqa: RUF003
    # BKookies Cafe
    82076261892347489,  # Baked goods
    # bloomer's - Bayview
    1296083,  # Surprise bag
    # bloomer's - Bloor West
    1296080,  # Surprise Bag
    # bloomer's - Queen St
    1296132,  # Surprise bag
    # Burukudu Coffee
    941206,  # Assorted coffee beans
    941219,  # Assorted Coffee Beans Large
    1274072,  # Surprise Coffee
    # Cafe Our Hours
    1299996,  # Surprise Bag
    # Chocollata (Union Station)
    944731,  # Large Surprise Bag
    1026073,  # Small Surprise Bag
    15998870780703713,  # Easter Egg Bag
    # Chocollata Brigadeiros - Upper Beaches
    119476348672049089,  # Large Surprise Bag
    119477169111458113,  # Small Surprise Bag
    # ChocoSol
    907694,  # Chocolate Surprise
    1170829,  # Coffee rations
    1208932,  # Surprise Bag dark chocolate
    1271741,  # Unsweetened Chocolate
    48422911068547233,  # Chocolate and Spice Suprise!!
    # ChocoSol's Chocolate Bar & Boutique
    65195503724749217,  # Chocolate Surprise
    65201763237996257,  # Dark Chocolate Surprise Bag
    65209425391474465,  # Coffee Rations
    # Circles & Squares Bakery Café - North York
    1076222,  # Suprise bag
    # Circles & Squares Bakery Café - Yonge St
    1408783,  # Surprise bag
    # Courage Cookies - Dundas Street West
    648110,  # Cookies!
    # Courage Cookies - Stackt Market
    633174,  # Cookies!
    # Deer Cake - Markham
    1029354,  # Large Surprise Bag
    1029366,  # Surprise Bag - Toast Box/Baked Goods 冰面包吐司
    1029388,  # Surprise Bag
    # Delicious Empanadas - Dufferin St
    378983,  # $15 Value Meal
    1274040,  # $15 Value
    131924680033894145,  # $18 Value
    # Delicious Empanadas Latin Cafe
    1655516,  # Surprise Bag
    # Dolce & Gourmando - North York
    1025784,  # Big Goody Bag
    943892,  # Goody Bag
    # Eataly - Yorkville
    370413,  # Assorted Prepared Foods
    370421,  # Baked Goods
    379625,  # Charcuterie Items
    769120,  # Assorted Pantry Items
    1703451,  # Pastry
    # Filosophy Pastry and Espresso Bar
    1451690,  # Surprise Bag
    # Fruitful Market
    1659970,  # Surprise bag
    # Goûter (Eglinton West)
    632623,  # Surprise Bag
    # Greenhouse Juice - Brookfield Place
    631189,  # Assorted Items
    # Greenhouse Juice - Forest Hill
    234980,  # Assorted Items
    80010988711186273,  # Surprise Bag
    # Greenhouse Juice - Macpherson
    234974,  # Assorted Items
    # Greenhouse Juice - Queen West
    234968,  # Assorted Items
    114246763815273761,  # Surprise Bag
    122326876508919681,  # Surprise Bag
    # Greenhouse Juice - St. Clair
    234975,  # Assorted Items
    # Greenhouse Juice - Union Station
    372839,  # Assorted Items
    # Hattendo 八天堂 - Baldwin Village
    1078202,  # Surprise Bag of Heavenly Pastries
    # Hattendo 八天堂 - Holt Renfrew Centre
    1077232,  # Surprise Bag of Heavenly Pastries
    # Hattendo 八天堂 - Markham
    1078203,  # Surprise Bag of Heavenly Pastries
    # IKEA - North York
    14165470828971393,  # Morning Surprise Bag
    14166701768430177,  # Dinner Surprise Bag
    # IKEA - Toronto Downtown
    14165503645195489,  # Morning Surprise Bag
    14166714452012257,  # Dinner Surprise Bag
    # Kajun Chicken & Seafood - Kingston Rd
    33654749134141825,  # Surprise Bag
    # Kingston 12 Patty Shop
    20317924928427073,  # Patty Surprise Bag
    # Kingston 12 Patty Shop - Dundas
    102949654161238177,  # Surprise Bag
    # Kingyo Fisherman's Market
    765532,  # Gourmet Grocery Surprise Bag
    # La Rocca Creative Kitchen
    505336,  # Cupcakes and assorted baked goods
    1562890,  # Small Cake
    # Let's Soup
    515988,  # Surprise Bag
    # Levetto
    766633,  # Italian Surprise Bag
    # Lou-Lou's Flower Truck
    1561525,  # Flower Surprise bag
    # Maki Mart North York - North York
    10193768865923073,  # Surprise bag $24
    # Maman
    375980,  # Surprise Bag
    # Manal Bashir Pastry Co.
    1208268,  # Baked goods
    # Mr. Kane - Natural Juices & Exotic Fruits
    20617615905913633,  # Surprise Bag
    20757178189865601,  # Groceries
    # NUTTEA Toronto - 637 Bloor St W
    1406942,  # Tea Surprise Bag
    105257928138595425,  # NUTTEA Surprise Bag
    # Pusateri's - Avenue Rd
    373762,  # Baked Goods
    379051,  # Prepared Foods
    1078618,  # Pantry & General Grocery items
    # Rahier Patisserie
    509030,  # Bread and Pastries Surprise Bag
    1171586,  # Small Cake or Tarts
    1560990,  # Quiche Bag
    # Rosedale's Finest Specialty Foods
    909343,  # Large Surprise Bag
    942190,  # Regular Surprise Bag
    # Ruru Baked
    907452,  # Surprise Bag
    90751616844449665,  # Surprise Bag - Ice Cream + Baked Goods
    103253956677685665,  # Surprise Bag - Ice Cream Pints
    # Saving Gigi
    372245,  # Surprise Bag
    # Soma Bone Broth Co.
    509518,  # Surprise Bag
    # Subtext Coffee
    518854,  # Small Surprise Bag
    518861,  # Large Surprise Bag
    1563057,  # Baked goods
    # Summerhill Market - Annex
    376441,  # Prepared Foods
    # Summerhill Market - Forest Hill
    376660,  # Prepared Foods
    # Summerhill Market - Rosedale
    371532,  # Prepared Foods
    # Sushi Real Fruit
    516525,  # Sushi Surprise Bag
    # The Bake House - Markham
    62327179096036001,  # Surprise Bag
    66416703558784641,  # Surprise Bag (Frozen)
    97412266903335329,  # Ice Cream Cake!
    # The Night Baker - College
    515273,  # Assorted Cookies
    # The Night Baker - Danforth
    515081,  # Assorted Cookies
    # The Pie Commission
    1703444,  # Surprise bag
    # Tobiko Sushi
    649370,  # Sushi Surprise Bag
    # Tre Mari Bakery
    646010,  # Prepared Meals and Baked Goods
    1077771,  # Assorted Cannoli Bag
    # Village Juicery - Bloor St
    372812,  # Prepared Juices + Food
    # Village Juicery - Danforth
    373581,  # Prepared Juices + Food
    # Village Juicery - Spadina
    372813,  # Prepared Juices + Food
    # Whole Foods - ON - Unionville
    73322727368288545,  # Bakery Bag
    73340264039378913,  # Prepared Foods Bag
    # Whole Foods - ON - Yonge & Sheppard
    73322730623061985,  # Bakery Bag
    73340268166558753,  # Prepared Foods Bag
    # XCAKE 隨心意 - Markham
    38053218033566113,  # Surprise Bag (M)
    # 台客赞 Aitaiker Taiwanese Fried Chicken - Richmond Hill
    1489885,  # Surprise Bag (L)
    1489887,  # Surprise Bag (S)
}

filipino: set[int] = {
    # Manyaman Foods Filipino Cuisine - Scarborough
    34300334078310337,  # Surprise Bag
    # Tagpuan - College St
    1454297,  # Evening Surprise Bag
    87047176813977313,  # Surprise Bag
    119702167645600225,  # Desserts !
    # Tagpuan - Yonge st
    122045877528868801,  # Evening Surprise Bag
    122047137732662049,  # Surprise Bag
    # Tagpuan (Van Horne Ave)
    941790,  # Evening Surprise Bag
}

jtown: set[int] = {
    # Bakery Nakamura - Markham
    1274244,  # Baked goods
    1406748,  # Half whole cake
    1408604,  # Pastry goods
    # La Petite Colline
    505184,  # Baked Goods Surprise Bag
    127055692199864673,  # Baked goods
}

tien: set[int] = {
    # ABURI TORA - Yorkdale Mall
    630348,  # Surprise Bag
    # CHICHA San Chen 吃茶三千 (Ossington)
    88420443877014497,  # Surprise Bag
    # Goûter (Bathurst)
    647660,  # Surprise Bag
    # im mochi
    50994187116261217,  # Donuts
    # Kin-Kin Bakery (Yonge Sheppard Centre)
    507832,  # Surprise Bag
    # Nadege Patisserie - Bloor-Annex
    631882,  # Surprise bag - Large
    631883,  # Surprise bag - Small
    631884,  # Extra Large Baked/ Cake Goods Surprise Bag
    # Nadege Patisserie - Queen West
    372476,  # Small Baked/ Cake Goods Surprise Bag
    377764,  # Large Baked/ Cake Goods Surprise Bag
    378051,  # Extra Large Baked/ Cake Goods Surprise Bag
    # Nadege Patisserie - Rosedale
    507476,  # Surprise bag - Small
    507477,  # Extra Large Baked/ Cake Goods Surprise Bag
    507468,  # Surprise bag - Large
    # Nonna Lia - Oakwood
    85792504166058433,  # Single Dessert Bag
    85794643630215137,  # Double Dessert Bag
    96872852823024801,  # Assorted Surprise Bag
    99180077308855521,  # Double Sandwich Bag
    125208606788673473,  # Lasagna Surprise Bag
    # Tao Tea Leaf - Union Station
    631173,  # Night Surprise Bag
}

ignored: set[int] = set()

inactive: set[int] = {
    # A Tavola
    102924490584841441,  # Spatchcock Chicken
    # Bake Code (Yonge St.) - North York
    374970,  # Surprise Bag
    # Bake Code Croissanterie (Yonge St.) - Toronto
    374611,  # Surprise Bag
    # Courage Cookies - Dundas Street West
    37959769041115585,  # Cookie Dough
    # Daan Go Cake Lab - Scarborough
    518250,  # Surprise Bag Medium
    518251,  # Surprise Bag Large
    # Eataly - Yorkville
    374329,  # Pasta Kit
    # HiFruit Technology Inc. - Scarborough
    11913019614429185,  # Grapefruit Box 爆汁葡萄柚盲盒
    # IKI Shokupan - Richmond Hill
    41210055715544609,  # Baked Goods Surprise Bag
    # Metro - 16 William Kitchen Rd
    1354060,  # Assorted Meat
    # Moge & Mofu
    790645,  # Bubble Tea and/or Baked Goods
    # The Smoke Bloke Smoked Salmon and Fine Smoked Foods
    646846,  # Small Surprise Bag
    # Sugar N Spice
    1350245,  # Baking Groceries
    # Tagpuan - Yonge st
    122047724947037185,  # Dessert Surprise
    # Tao Tea Leaf - Union Station
    646186,  # Mid-day Surprise Bag
    # Torch GG Sushi - Downtown
    371930,  # Surprise Bag
    # YUBU - Scarborough - Skycity Mall
    1353655,  # Surprise Bag
}

tracked: set[int] = {
    # Cakeview Bakery & Cafe
    649947,  # Bread
    649979,  # Cake
    # Daan Go Cake Lab - Scarborough
    376271,  # Surprise Bag Small
    # Eataly - Don Mills
    48448666821020353,  # Baked Goods
    48448667190123489,  # Assorted Prepared Foods
    48448668062525921,  # Charcuterie Items
    48448668767184353,  # Assorted Pantry Items
    # LÀ LÁ Bakeshop - Scarborough
    1561993,  # Surprise Bag
    # La Rocca Creative Kitchen
    374252,  # Cupcakes and assorted baked goods
    # LaRochelle Confections Inc.
    518221,  # Surprise Bag
    # McEwan Foods - Don Mills
    377070,  # Surprise Bag
    # Metro - 15 Ellesmere Rd
    1354074,  # Assorted Meat
    # Metro - 1050 Don Mills Rd
    943701,  # Assorted Fruit & Salad
    1299767,  # Assorted Meat
    99712944450874561,  # Deli Surprise Bag
    # Metro - 2900 Warden Ave
    1354049,  # Assorted Meat
    # Nonna Lia - Oakwood
    85795141007552961,  # 6-Inch Cake Bag
    85795389478113761,  # 8-Inch Cake Bag
    85795679891750113,  # 10-Inch Cake Bag
    # The Night Baker - North York
    81417090592535617,  # Assorted Cookies
    # The Smoke Bloke Smoked Salmon and Fine Smoked Foods
    631121,  # Large Surprise Bag
    631574,  # Medium Surprise Bag
    # TYCOON TOFU - Pacific Mall - 2nd Floor in Pacific Heritage Town
    114202587358750689,  # Surprise Bag
    # Village Juicery - Yonge St
    378034,  # Prepared Juices + Food
}
