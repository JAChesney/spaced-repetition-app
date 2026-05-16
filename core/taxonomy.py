TAXONOMY: dict[str, dict[str, list[str]]] = {
    "History": {
        "Ancient India": [
            "Indus Valley Civilization",
            "Vedic Age",
            "Mauryan Empire",
            "Gupta Empire",
            "Buddhism",
            "Jainism",
            "Sangam Age",
        ],
        "Medieval India": [
            "Delhi Sultanate",
            "Mughal Empire",
            "Vijayanagara Empire",
            "Bhakti Movement",
            "Sufi Movement",
            "Marathas",
        ],
        "Modern India": [
            "British Rule",
            "Revolt of 1857",
            "Freedom Movement",
            "Congress Sessions",
            "Gandhian Era",
            "Revolutionary Movements",
            "Governor Generals",
            "Constitutional Development",
        ],
        "World History": [
            "World Wars",
            "Revolutions",
            "Cold War",
            "Colonialism",
            "International Organizations",
        ],
    },
    "Geography": {
        "Physical Geography": [
            "Mountains",
            "Plateaus",
            "Plains",
            "Rivers",
            "Deserts",
            "Volcanoes",
            "Earthquakes",
        ],
        "Indian Geography": [
            "States and Capitals",
            "Rivers",
            "Climate",
            "Soils",
            "Agriculture",
            "Minerals",
            "National Parks",
            "Biosphere Reserves",
        ],
        "World Geography": [
            "Continents",
            "Oceans",
            "Countries",
            "Capitals",
            "Important Straits",
            "Climate Regions",
        ],
        "Environment": [
            "Climate Change",
            "Biodiversity",
            "Pollution",
            "Conservation",
            "Environmental Treaties",
        ],
    },
    "Polity": {
        "Constitution": [
            "Preamble",
            "Fundamental Rights",
            "DPSP",
            "Fundamental Duties",
            "Amendments",
        ],
        "Parliament": [
            "Lok Sabha",
            "Rajya Sabha",
            "Bills",
            "Committees",
            "Sessions",
        ],
        "Executive": [
            "President",
            "Prime Minister",
            "Governor",
            "Chief Minister",
            "Cabinet",
        ],
        "Judiciary": [
            "Supreme Court",
            "High Courts",
            "Judicial Review",
            "PIL",
        ],
        "Federalism": [
            "Centre-State Relations",
            "Emergency Provisions",
            "Finance Commission",
        ],
        "Elections": [
            "Election Commission",
            "Voting",
            "Political Parties",
        ],
        "Local Government": [
            "Panchayati Raj",
            "Municipalities",
        ],
        "Governance": [
            "Government Schemes",
            "Policies",
            "Digital Governance",
            "Welfare Programs",
        ],
    },
    "Economy": {
        "Banking": [
            "RBI",
            "Monetary Policy",
            "Interest Rates",
            "Digital Banking",
        ],
        "Budget": [
            "Union Budget",
            "Taxation",
            "Fiscal Policy",
            "Government Expenditure",
        ],
        "Inflation": [
            "CPI",
            "WPI",
            "Deflation",
        ],
        "Agriculture Economy": [
            "MSP",
            "Subsidies",
            "Crop Insurance",
        ],
        "External Sector": [
            "IMF",
            "World Bank",
            "WTO",
            "Trade",
            "Forex",
        ],
        "Industry": [
            "Manufacturing",
            "MSME",
            "Startup Ecosystem",
        ],
        "Economic Indicators": [
            "GDP",
            "GNP",
            "Unemployment",
            "Poverty",
        ],
    },
    "Science": {
        "Physics": [
            "Motion",
            "Electricity",
            "Magnetism",
            "Light",
            "Heat",
        ],
        "Chemistry": [
            "Elements",
            "Acids and Bases",
            "Metals",
            "Chemical Reactions",
        ],
        "Biology": [
            "Human Body",
            "Diseases",
            "Nutrition",
            "Genetics",
        ],
        "Space": [
            "Satellites",
            "Missions",
            "ISRO",
            "NASA",
            "Astronomy",
        ],
        "Technology": [
            "AI",
            "Robotics",
            "Quantum Computing",
            "Semiconductors",
        ],
        "Biotechnology": [
            "DNA",
            "Vaccines",
            "Cloning",
        ],
        "Environment Science": [
            "Renewable Energy",
            "Climate Science",
            "Ecosystems",
        ],
    },
    "International Relations": {
        "Bilateral Relations": [
            "India-US",
            "India-China",
            "India-Russia",
            "India-France",
        ],
        "International Organizations": [
            "UN",
            "WHO",
            "IMF",
            "WTO",
            "NATO",
        ],
        "Summits": [
            "G20",
            "BRICS",
            "SCO",
            "ASEAN",
        ],
        "Treaties and Agreements": [
            "Defence Agreements",
            "Trade Agreements",
            "Climate Agreements",
        ],
    },
    "Defence": {
        "Military Exercises": [
            "Joint Exercises",
            "Naval Exercises",
            "Air Exercises",
        ],
        "Defence Organizations": [
            "DRDO",
            "Armed Forces",
            "CDS",
        ],
        "Weapons and Technology": [
            "Missiles",
            "Aircraft",
            "Drones",
            "Cybersecurity",
        ],
    },
    "Art and Culture": {
        "Dance": [
            "Classical Dance",
            "Folk Dance",
        ],
        "Music": [
            "Classical Music",
            "Instruments",
        ],
        "Architecture": [
            "Temples",
            "Monuments",
            "UNESCO Sites",
        ],
        "Literature": [
            "Books",
            "Authors",
            "Languages",
        ],
        "Festivals": [
            "Religious Festivals",
            "Cultural Festivals",
        ],
    },
    "Sports": {
        "Events": [
            "Olympics",
            "Asian Games",
            "Cricket World Cup",
        ],
        "Sports Personalities": [
            "Awards",
            "Rankings",
            "Records",
        ],
        "Organizations": [
            "ICC",
            "FIFA",
            "IOC",
        ],
    },
    "Awards and Honours": {
        "National Awards": [
            "Bharat Ratna",
            "Padma Awards",
        ],
        "International Awards": [
            "Nobel Prize",
            "Oscar",
            "Booker Prize",
        ],
    },
    "Important Days": {
        "National Days": [
            "Republic Day",
            "Independence Day",
        ],
        "International Days": [
            "Environment Day",
            "Yoga Day",
        ],
    },
    "Current Affairs": {
        "National": [],
        "International": [],
        "Economy": [],
        "Science & Technology": [],
        "Sports": [],
        "Environment": [],
        "Defence": [],
        "Others": [],
    },
    "Miscellaneous": {
        "Books and Authors": [],
        "Obituaries": [],
        "Appointments": [],
        "Reports and Indices": [],
        "Government Schemes": [],
        "Persons in News": [],
        "Places in News": [],
    },
}


def subjects() -> list[str]:
    return list(TAXONOMY.keys())


def topics(subject: str) -> list[str]:
    return list(TAXONOMY.get(subject, {}).keys())


def subtopics(subject: str, topic: str) -> list[str]:
    return TAXONOMY.get(subject, {}).get(topic, [])
