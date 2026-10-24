"""Catalog of crowded places in India. ALL coordinates are APPROXIMATE and all sizes (area m2, gate width m,
popularity, visit minutes) are ASSUMED placeholders - replace them with surveyed values.
To use your own map for a place, save it as data/<key>.kml (same key as below), e.g. data/kolkata_puja.kml.
Optional numbers in each KML placemark description:  area=1200 gate=4 pop=1.6 dwell=25
Placemarks whose name contains exit / metro / station / ground / hospital become dispersal exits.
"""

def V(name, kind, lat, lon, area, gate, pop, dwell):
    return dict(name=name, kind=kind, lat=lat, lon=lon, area=area, gate=gate, pop=pop, dwell=dwell)

def X(name, lat, lon):
    return dict(name="Exit - " + name, lat=lat, lon=lon)

# peaks = (hour of day, width, weight): when crowds arrive.  days = label -> relative footfall.
CATALOG = {
 "kolkata_puja": dict(
    title="Kolkata - Durga Puja pandals", note="North, central and south Kolkata pandal clusters",
    peaks=[(11, 6, .45), (21, 5, 1.05)], base=.12, start=16.0, day="Ashtami",
    days={"Shashthi": .5, "Saptami": .8, "Ashtami": 1.0, "Navami": 1.15, "Dashami": .7},
    venues=[V("North - Shyambazar side", "pandal", 22.6010, 88.3735, 1500, 6, 1.9, 22), V("North - Baghbazar side", "pandal", 22.6040, 88.3665, 1200, 5, 2.0, 22),
            V("North - Kumartuli side", "pandal", 22.6000, 88.3650, 900, 4, 1.6, 20), V("North - Hatibagan side", "pandal", 22.5880, 88.3670, 900, 4, 1.4, 20),
            V("College Street side", "pandal", 22.5750, 88.3645, 1800, 6, 1.8, 25), V("Central - Sealdah side", "pandal", 22.5660, 88.3700, 1200, 5, 1.1, 20),
            V("Central - Wellington side", "pandal", 22.5640, 88.3560, 900, 4, 1.3, 20), V("Central - Park Circus side", "pandal", 22.5400, 88.3700, 1200, 4, .9, 20),
            V("South - Maddox Square side", "pandal", 22.5380, 88.3590, 1200, 5, 1.5, 22), V("South - Ballygunge side", "pandal", 22.5280, 88.3660, 1800, 6, 2.1, 25),
            V("South - Ekdalia side", "pandal", 22.5200, 88.3630, 1200, 4, 1.7, 22), V("South - Deshapriya Park side", "pandal", 22.5190, 88.3470, 1800, 6, 2.2, 25),
            V("South - Kalighat side", "pandal", 22.5200, 88.3430, 600, 3, .8, 18), V("South - Gariahat side", "pandal", 22.5180, 88.3680, 900, 4, 1.2, 20)],
    exits=[X("Shyambazar Metro", 22.6015, 88.3740), X("MG Road Metro", 22.5705, 88.3640), X("Esplanade Metro", 22.5645, 88.3515),
           X("Kalighat Metro", 22.5200, 88.3465), X("Maidan open ground", 22.5500, 88.3450), X("Rabindra Sarobar open ground", 22.5100, 88.3600)]),

 "mumbai_ganesh": dict(
    title="Mumbai - Ganeshotsav (Lalbaug to Dadar)", note="Large mandals, temples and immersion beaches",
    peaks=[(11, 6, .35), (21, 6, 1.0)], base=.12, start=16.0, day="Day 7",
    days={"Day 1": .5, "Day 3": .8, "Day 5": .9, "Day 7": 1.0, "Weekend": 1.15, "Anant Chaturdashi (immersion)": 1.3},
    venues=[V("Lalbaug area mandal", "pandal", 18.9843, 72.8336, 1500, 5, 2.3, 40), V("Chinchpokli area mandal", "pandal", 18.9815, 72.8343, 1200, 4, 1.6, 30),
            V("Ganesh Galli mandal", "pandal", 18.9858, 72.8315, 900, 3, 1.5, 25), V("Khetwadi lanes", "pandal", 18.9578, 72.8187, 1200, 4, 1.3, 25),
            V("Girgaum Chowpatty", "beach", 18.9548, 72.8133, 9000, 25, 1.2, 40), V("King's Circle mandal", "pandal", 19.0278, 72.8570, 2000, 6, 1.7, 30),
            V("Siddhivinayak Temple", "temple", 19.0169, 72.8302, 2500, 6, 2.0, 45), V("Shivaji Park Dadar", "ground", 19.0270, 72.8377, 15000, 30, 1.0, 50),
            V("Juhu Beach", "beach", 19.0988, 72.8264, 12000, 30, 1.0, 45)],
    exits=[X("CSMT station", 18.9400, 72.8350), X("Churchgate station", 18.9322, 72.8270), X("Mumbai Central station", 18.9693, 72.8195),
           X("Dadar station", 19.0186, 72.8428), X("Currey Road station", 18.9940, 72.8320), X("Mahalaxmi station", 18.9829, 72.8232)]),

 "delhi_hubs": dict(
    title="Delhi - stations, markets and monuments", note="Railway stations, bazaars, India Gate, Jama Masjid",
    peaks=[(9, 3, .7), (18.5, 3, .9), (13, 6, .2)], base=.15, start=8.0, day="Weekday",
    days={"Weekday": .8, "Weekend": 1.0, "Festival eve (Diwali / Chhath)": 1.4},
    venues=[V("New Delhi Railway Station", "station", 28.6430, 77.2197, 6000, 12, 1.6, 25), V("Old Delhi Railway Station", "station", 28.6606, 77.2273, 5000, 10, 1.5, 25),
            V("Hazrat Nizamuddin Station", "station", 28.5880, 77.2535, 3500, 8, 1.1, 25), V("Anand Vihar Terminal", "station", 28.6469, 77.3159, 4000, 8, 1.3, 25),
            V("Kashmere Gate ISBT", "station", 28.6672, 77.2285, 4500, 8, 1.2, 20), V("Chandni Chowk market", "market", 28.6506, 77.2303, 5000, 8, 2.0, 45),
            V("Jama Masjid", "temple", 28.6507, 77.2334, 3500, 6, 1.5, 40), V("Connaught Place", "market", 28.6315, 77.2167, 8000, 15, 1.2, 60),
            V("India Gate lawns", "ground", 28.6129, 77.2295, 12000, 20, .9, 60), V("Sarojini Nagar market", "market", 28.5755, 77.1980, 3000, 6, 1.9, 45)],
    exits=[X("Rajiv Chowk Metro", 28.6328, 77.2197), X("Chandni Chowk Metro", 28.6577, 77.2301), X("Kashmere Gate Metro", 28.6676, 77.2280),
           X("Central Secretariat Metro", 28.6152, 77.2117), X("Lodhi Garden open ground", 28.5930, 77.2197)]),

 "prayagraj_sangam": dict(
    title="Prayagraj - Sangam and Kumbh area", note="Bathing ghats, mela ground approaches and stations",
    peaks=[(5, 2.5, .85), (11, 4, .45)], base=.08, start=2.0, day="Snan day",
    days={"Normal day": .7, "Snan day": 1.3, "Peak snan (Amrit Snan)": 1.8},
    venues=[V("Triveni Sangam ghat", "ghat", 25.4271, 81.8886, 20000, 60, 1.4, 30), V("Sangam approach road", "road", 25.4310, 81.8800, 12000, 25, 1.2, 25),
            V("Hanuman Mandir", "temple", 25.4235, 81.8800, 2500, 6, 1.5, 30), V("Fort-side ghat", "ghat", 25.4285, 81.8750, 8000, 25, 1.1, 30),
            V("Prayagraj Junction", "station", 25.4437, 81.8267, 8000, 14, 1.3, 25), V("Sangam station area", "station", 25.4348, 81.8700, 4000, 8, 1.2, 25),
            V("Arail ghat", "ghat", 25.4100, 81.8800, 6000, 15, 1.0, 30)],
    exits=[X("Parade ground open area", 25.4300, 81.8600), X("Jhunsi side open ground", 25.4230, 81.9100), X("Civil Lines bus stand", 25.4520, 81.8330)]),

 "haridwar": dict(
    title="Haridwar - Har Ki Pauri and temples", note="Ganga aarti crowds, Kanwar Yatra and Kumbh bathing days",
    peaks=[(5.5, 2.5, .7), (18.5, 2, .95)], base=.1, start=15.0, day="Weekend",
    days={"Weekday": .6, "Weekend": 1.0, "Kanwar Yatra / Kumbh bath": 1.6},
    venues=[V("Har Ki Pauri", "ghat", 29.9570, 78.1710, 3500, 10, 2.1, 30), V("Subhash Ghat", "ghat", 29.9505, 78.1688, 2500, 8, 1.2, 25),
            V("Mansa Devi Temple", "temple", 29.9617, 78.1648, 800, 3, 1.6, 45), V("Maya Devi Temple", "temple", 29.9500, 78.1650, 700, 3, 1.1, 30),
            V("Bara Bazaar", "market", 29.9540, 78.1680, 2500, 5, 1.4, 40), V("Haridwar Railway Station", "station", 29.9457, 78.1642, 3500, 8, 1.2, 25)],
    exits=[X("Bus stand open area", 29.9490, 78.1620), X("Bhupatwala open ground", 29.9800, 78.1900), X("Haridwar Railway Station forecourt", 29.9450, 78.1640)]),

 "varanasi": dict(
    title="Varanasi - ghats and Kashi Vishwanath", note="Narrow lanes around the temple and the ghats",
    peaks=[(5, 2, .6), (18.5, 2.5, .95)], base=.1, start=15.0, day="Weekend",
    days={"Weekday": .7, "Weekend": 1.0, "Mahashivratri / Dev Deepawali": 1.7},
    venues=[V("Kashi Vishwanath Temple", "temple", 25.3109, 83.0107, 2500, 6, 2.2, 35), V("Dashashwamedh Ghat", "ghat", 25.3070, 83.0105, 4000, 12, 1.8, 30),
            V("Manikarnika Ghat", "ghat", 25.3103, 83.0145, 1500, 4, .9, 20), V("Godowlia market", "market", 25.3095, 83.0100, 2500, 6, 1.7, 40),
            V("Assi Ghat", "ghat", 25.2880, 83.0060, 3500, 10, 1.2, 30), V("Sankat Mochan Temple", "temple", 25.2796, 82.9970, 1200, 4, 1.5, 30),
            V("Varanasi Junction", "station", 25.3269, 82.9876, 6000, 12, 1.3, 25)],
    exits=[X("Cantt open area", 25.3340, 82.9900), X("Rajghat open ground", 25.3250, 83.0300), X("Lanka crossing", 25.2750, 82.9990)]),

 "puri": dict(
    title="Puri - Jagannath Temple and Rath Yatra", note="Temple, Grand Road, Gundicha Temple and the beach",
    peaks=[(8, 4, .6), (17, 5, .95)], base=.1, start=6.0, day="Rath Yatra day",
    days={"Normal day": .6, "Weekend / festival": 1.0, "Rath Yatra day": 2.0},
    venues=[V("Jagannath Temple (Singhadwara)", "temple", 19.8049, 85.8180, 4000, 8, 2.2, 45), V("Grand Road (Bada Danda)", "road", 19.8070, 85.8250, 12000, 30, 1.6, 40),
            V("Gundicha Temple", "temple", 19.8190, 85.8300, 6000, 14, 1.5, 40), V("Puri Beach (Swargadwar)", "beach", 19.7970, 85.8280, 20000, 40, 1.0, 45),
            V("Puri Railway Station", "station", 19.8100, 85.8240, 4000, 8, 1.2, 25)],
    exits=[X("Bus stand open area", 19.8150, 85.8200), X("Beach open ground", 19.7950, 85.8200)]),

 "tirupati": dict(
    title="Tirupati and Tirumala - pilgrim hubs", note="Temple queue complexes and the town stations",
    peaks=[(6, 3, .7), (18, 3, .7)], base=.2, start=6.0, day="Weekend",
    days={"Weekday": .7, "Weekend": 1.0, "Brahmotsavam / Vaikunta Ekadasi": 1.6},
    venues=[V("Tirumala Venkateswara Temple", "temple", 13.6833, 79.3472, 6000, 10, 2.0, 90), V("Alipiri footpath start", "road", 13.6510, 79.4140, 1500, 4, 1.2, 20),
            V("Srinivasam pilgrim complex", "station", 13.6285, 79.4190, 3000, 6, 1.4, 60), V("Tirupati Railway Station", "station", 13.6280, 79.4190, 5000, 10, 1.3, 25),
            V("Govindaraja Swamy Temple", "temple", 13.6285, 79.4170, 1500, 4, 1.1, 30)],
    exits=[X("Tirupati bus stand open area", 13.6300, 79.4230), X("Alipiri open ground", 13.6500, 79.4120)]),

 "ujjain": dict(
    title="Ujjain - Mahakaleshwar and ghats", note="Temple corridor, Ram Ghat and Simhastha crowds",
    peaks=[(4, 2, .7), (19, 3, .8)], base=.1, start=15.0, day="Monday / weekend",
    days={"Weekday": .7, "Monday / weekend": 1.0, "Mahashivratri / Sawari": 1.8},
    venues=[V("Mahakaleshwar Temple", "temple", 23.1828, 75.7683, 3000, 6, 2.2, 45), V("Ram Ghat", "ghat", 23.1769, 75.7673, 3000, 10, 1.5, 30),
            V("Harsiddhi Temple", "temple", 23.1843, 75.7630, 900, 3, 1.1, 25), V("Ujjain Junction", "station", 23.1818, 75.7745, 4000, 8, 1.2, 25)],
    exits=[X("Bus stand open area", 23.1900, 75.7700), X("Kshipra riverside open ground", 23.1750, 75.7600)]),
}
