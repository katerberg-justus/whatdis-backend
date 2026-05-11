"""
Seed all challenge packs and their challenges.
Run from the backend directory:  python scripts/seed_packs.py
Re-running is safe — existing packs (matched by name) are skipped.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api import create_app, db
from api.models.challenge_pack import ChallengePack
from api.models.challenge import Challenge
from api.common.challenge_enums import PERSON, OBJECT, EASY, MEDIUM

PACKS = [
    {
        "name": "Whisperers of the Silver Screen",
        "description": "Golden-age film icons",
        "challenge_type": PERSON,
        "difficulty": MEDIUM,
        "subjects": [
            "Alfred Hitchcock", "Audrey Hepburn", "Charlie Chaplin", "Marilyn Monroe",
            "Stanley Kubrick", "Greta Garbo", "Orson Welles", "Akira Kurosawa",
            "Ingmar Bergman", "Federico Fellini", "Buster Keaton", "Vivien Leigh",
            "James Dean", "Grace Kelly", "Humphrey Bogart", "Cary Grant",
            "Bette Davis", "Katharine Hepburn", "Clark Gable", "Rita Hayworth",
        ],
    },
    {
        "name": "Vessels of the Morning Ritual",
        "description": "Objects from the morning routine",
        "challenge_type": OBJECT,
        "difficulty": EASY,
        "subjects": [
            "French press", "espresso machine", "kettle", "teapot", "coffee mug",
            "travel thermos", "milk frother", "sugar bowl", "toaster", "blender",
            "juicer", "cereal bowl", "butter knife", "breakfast tray", "newspaper",
            "alarm clock", "bathrobe", "slippers", "toothbrush", "hairbrush",
        ],
    },
    {
        "name": "Architects of the Unseen Realm",
        "description": "Pioneering scientists and inventors",
        "challenge_type": PERSON,
        "difficulty": MEDIUM,
        "subjects": [
            "Marie Curie", "Nikola Tesla", "Albert Einstein", "Isaac Newton",
            "Charles Darwin", "Galileo Galilei", "Thomas Edison", "Alexander Graham Bell",
            "Louis Pasteur", "Ada Lovelace", "Rosalind Franklin", "Stephen Hawking",
            "Richard Feynman", "Niels Bohr", "Werner Heisenberg", "Gregor Mendel",
            "James Watson", "Tim Berners-Lee", "Alan Turing", "Dmitri Mendeleev",
        ],
    },
    {
        "name": "Companions of the Long Voyage",
        "description": "Things you pack in a suitcase",
        "challenge_type": OBJECT,
        "difficulty": EASY,
        "subjects": [
            "passport", "toothbrush", "sunglasses", "neck pillow", "paperback book",
            "charging cable", "power adapter", "rolled socks", "swimsuit", "sunscreen",
            "umbrella", "money belt", "packing cubes", "eye mask", "earplugs",
            "guidebook", "camera", "water bottle", "flip-flops", "laundry bag",
        ],
    },
    {
        "name": "Sovereigns of Forgotten Ages",
        "description": "Historical rulers from across the ages",
        "challenge_type": PERSON,
        "difficulty": MEDIUM,
        "subjects": [
            "Cleopatra", "Julius Caesar", "Genghis Khan", "Queen Elizabeth I",
            "Napoleon Bonaparte", "Catherine the Great", "Henry VIII", "Louis XIV",
            "Tutankhamun", "Alexander the Great", "Queen Victoria", "Suleiman the Magnificent",
            "Charlemagne", "Hammurabi", "Montezuma II", "Mansa Musa",
            "Ivan the Terrible", "Marie Antoinette", "Hatshepsut", "Kublai Khan",
        ],
    },
    {
        "name": "Inhabitants of the Tangled Wild",
        "description": "Things you find in a forest",
        "challenge_type": OBJECT,
        "difficulty": EASY,
        "subjects": [
            "acorn", "pinecone", "mushroom", "fern", "moss", "fallen log",
            "anthill", "spider web", "deer antler", "bird's nest", "treehouse",
            "hiking boot", "walking stick", "lantern", "compass", "axe",
            "tent", "campfire", "hammock", "beehive",
        ],
    },
    {
        "name": "Voices of the Wandering Stage",
        "description": "Legendary musicians from across genres",
        "challenge_type": PERSON,
        "difficulty": MEDIUM,
        "subjects": [
            "David Bowie", "Freddie Mercury", "Bob Dylan", "Joni Mitchell",
            "Prince", "Aretha Franklin", "Johnny Cash", "Stevie Wonder",
            "Dolly Parton", "Bob Marley", "Elvis Presley", "John Lennon",
            "Paul McCartney", "Madonna", "Michael Jackson", "Whitney Houston",
            "Janis Joplin", "Jimi Hendrix", "Tina Turner", "Ray Charles",
        ],
    },
]

app = create_app()

with app.app_context():
    total_packs = 0
    total_challenges = 0

    for pack_data in PACKS:
        existing = db.session.execute(
            db.select(ChallengePack).where(ChallengePack.name == pack_data["name"])
        ).scalar_one_or_none()

        if existing:
            print(f"  ~ skipping existing pack: {pack_data['name']}")
            continue

        pack = ChallengePack(
            name=pack_data["name"],
            description=pack_data["description"],
            challenge_type=pack_data["challenge_type"],
            difficulty=pack_data["difficulty"],
            is_active=True,
        )
        db.session.add(pack)
        db.session.flush()

        for position, subject in enumerate(pack_data["subjects"]):
            db.session.add(Challenge(
                pack_id=pack.id,
                subject=subject,
                challenge_type=pack_data["challenge_type"],
                difficulty=pack_data["difficulty"],
                is_active=True,
                position=position,
            ))
            total_challenges += 1

        print(f"  + {pack_data['name']} ({len(pack_data['subjects'])} challenges)")
        total_packs += 1

    try:
        db.session.commit()
        print(f"\nDone. Seeded {total_packs} packs, {total_challenges} challenges.")
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        sys.exit(1)
