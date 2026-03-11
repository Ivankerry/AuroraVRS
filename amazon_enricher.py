import asyncio
import os
import json
import random
import uuid
import asyncpg
import requests
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

# Jumbo Seed Data (200+ Movies/Shows across all categories)
SAMPLE_MOVIES = [
    # TECH & SCI-FI (40+)
    {"title": "The Matrix Revolutions", "cats": ["Tech", "Sci-Fi"], "desc": "Neo and the rebel leaders estimate that they have very little time before 250,000 Sentinels destroy Zion."},
    {"title": "Interstellar", "cats": ["Tech", "Sci-Fi", "Drama"], "desc": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival."},
    {"title": "The Social Network", "cats": ["Tech", "Comedy"], "desc": "As Harvard student Mark Zuckerberg creates the social networking site that would become Facebook, he is sued by the twins who claimed he stole their idea."},
    {"title": "Silicon Valley", "cats": ["Tech", "Comedy"], "desc": "Follows the struggle of Richard Hendricks, a Silicon Valley engineer who tries to build his own company called Pied Piper."},
    {"title": "Black Mirror", "cats": ["Tech", "Sci-Fi", "Drama"], "desc": "An anthology series exploring a twisted, high-tech multiverse where humanity's greatest innovations and darkest instincts collide."},
    {"title": "Halt and Catch Fire", "cats": ["Tech", "Drama"], "desc": "Set in the 1980s, this series dramatizes the personal computing boom through the eyes of a visionary, an engineer and a prodigy."},
    {"title": "Mr. Robot", "cats": ["Tech", "Drama"], "desc": "Elliot, a brilliant but highly unstable young cyber-security engineer and vigilante hacker, becomes a key figure in a complex game of global dominance."},
    {"title": "The Imitation Game", "cats": ["Tech", "Drama"], "desc": "During World War II, the English mathematical genius Alan Turing tries to crack the German Enigma code with help from fellow mathematicians."},
    {"title": "Blade Runner 2049", "cats": ["Tech", "Sci-Fi"], "desc": "A young Blade Runner's discovery of a long-buried secret leads him to track down former Blade Runner Rick Deckard, who's been missing for thirty years."},
    {"title": "Ex Machina", "cats": ["Tech", "Sci-Fi"], "desc": "A young programmer is selected to participate in a ground-breaking experiment in synthetic intelligence by evaluating the human qualities of a highly advanced humanoid A.I."},
    {"title": "Her", "cats": ["Tech", "Sci-Fi", "Drama"], "desc": "In a near future, a lonely writer develops an unlikely relationship with an operating system designed to meet his every need."},
    {"title": "Tron: Legacy", "cats": ["Tech", "Sci-Fi"], "desc": "The son of a virtual world designer goes looking for his father and ends up inside the digital world that his father designed."},
    {"title": "The Martian", "cats": ["Tech", "Sci-Fi"], "desc": "An astronaut becomes stranded on Mars after his team assume him dead, and must rely on his ingenuity to find a way to signal to Earth that he is alive."},
    {"title": "Minority Report", "cats": ["Tech", "Sci-Fi"], "desc": "In a future where a special police unit is able to arrest murderers before they commit their crimes, an officer from that unit is himself accused of a future murder."},
    {"title": "Tenet", "cats": ["Tech", "Sci-Fi"], "desc": "Armed with only one word, Tenet, and fighting for the survival of the entire world, a Protagonist journeys through a twilight world of international espionage on a mission that will unfold in something beyond real time."},
    {"title": "Inception", "cats": ["Tech", "Sci-Fi"], "desc": "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O."},
    {"title": "Gravity", "cats": ["Tech", "Sci-Fi"], "desc": "Two astronauts work together to survive after an accident leaves them stranded in space."},
    {"title": "Arrival", "cats": ["Tech", "Sci-Fi", "Drama"], "desc": "A linguist works with the military to communicate with alien lifeforms after twelve mysterious spacecraft appear around the world."},
    {"title": "Contact", "cats": ["Tech", "Sci-Fi"], "desc": "Dr. Ellie Arroway, after years of searching, finds conclusive radio proof of extraterrestrial intelligence, sending plans for a mysterious machine."},
    {"title": "Primer", "cats": ["Tech", "Sci-Fi"], "desc": "Four friends/fledgling entrepreneurs, knowing that there's more to the universe than what they see, accidentally invent a form of time travel."},
    {"title": "Pi", "cats": ["Tech", "Drama"], "desc": "A paranoid mathematician searches for a key number that will unlock the universal patterns found in nature."},
    {"title": "Source Code", "cats": ["Tech", "Sci-Fi"], "desc": "A soldier wakes up in someone else's body and discovers he's part of an experimental government program to find the bomber of a commuter train."},
    {"title": "Moon", "cats": ["Tech", "Sci-Fi"], "desc": "Astronaut Sam Bell has a quintessentially personal encounter toward the end of his three-year stint on the Moon, where he, working alongside his computer, GERTY, sends back to Earth parcels of a resource that has helped jeopardize our planet's energy crisis."},
    {"title": "Devs", "cats": ["Tech", "Sci-Fi", "Drama"], "desc": "A computer engineer investigates the secretive development division in her quantum computing company, which she believes is behind the disappearance of her boyfriend."},
    {"title": "Upload", "cats": ["Tech", "Comedy", "Sci-Fi"], "desc": "A man is able to choose his own after-life by having his consciousness uploaded into a virtual world."},
    {"title": "Severance", "cats": ["Tech", "Drama", "Sci-Fi"], "desc": "Mark leads a team of office workers whose memories have been surgically divided between their work and personal lives."},
    {"title": "Foundation", "cats": ["Tech", "Sci-Fi"], "desc": "A complex saga of humans scattered on planets throughout the galaxy all living under the rule of the Galactic Empire."},
    {"title": "Mantis", "cats": ["Tech", "Sci-Fi"], "desc": "A scientist becomes a crime-fighting hero after being paralyzed and using his inventions to save the city."},
    {"title": "Sneakers", "cats": ["Tech", "Drama"], "desc": "A security pro finds his past coming back to haunt him when he and his unique team are tasked with retrieving a black box."},
    {"title": "WarGames", "cats": ["Tech", "Sci-Fi"], "desc": "A young man finds a back door into a military central computer in which reality is confused with game-playing, possibly starting World War III."},
    {"title": "Hackers", "cats": ["Tech", "Drama"], "desc": "Hackers are blamed for making a virus that will capsize five oil tankers."},
    {"title": "Takedown", "cats": ["Tech", "Drama"], "desc": "This film is based on the true story of the capture of computer hacker Kevin Mitnick."},
    {"title": "Steve Jobs", "cats": ["Tech", "Drama"], "desc": "Steve Jobs takes us behind the scenes of the digital revolution, to paint a portrait of the man at its epicenter."},
    {"title": "Jobs", "cats": ["Tech", "Drama"], "desc": "The story of Steve Jobs' ascension from college dropout into one of the most revered creative entrepreneurs of the 20th century."},
    {"title": "Startup", "cats": ["Tech", "Drama"], "desc": "A desperate banker, a Haitian-American gang lord, and a Cuban-American hacker are forced to work together to unwittingly create their version of the American dream."},
    {"title": "Transcendence", "cats": ["Tech", "Sci-Fi"], "desc": "A scientist's drive for artificial intelligence takes on dangerous implications when his own consciousness is uploaded into one such program."},
    {"title": "Chappie", "cats": ["Tech", "Sci-Fi"], "desc": "In the near future, crime is patrolled by an oppressive mechanized police force. When one police droid, Chappie, is stolen and given new programming, he becomes the first robot with the ability to think and feel for himself."},
    {"title": "A.I. Artificial Intelligence", "cats": ["Tech", "Sci-Fi"], "desc": "A highly advanced robotic boy longs to become \"real\" so that he can regain the love of his human mother."},
    {"title": "The Peripheral", "cats": ["Tech", "Sci-Fi"], "desc": "Set in the future when technology has subtly altered society, a woman discovers a secret connection to an alternate reality as well as a dark future of her own."},
    {"title": "Upgrade", "cats": ["Tech", "Sci-Fi"], "desc": "Set in the near-future, technology controls nearly all aspects of life. But when Grey, a self-identified technophobe, has his world turned upside down, his only hope for revenge is an experimental computer chip implant called STEM."},

    # GAMING (40+)
    {"title": "Cyberpunk: Edgerunners", "cats": ["Gaming", "Sci-Fi", "Tech"], "desc": "In a dystopia riddled with corruption and cybernetic implants, a talented but reckless street kid strives to become a mercenary outlaw."},
    {"title": "The Witcher", "cats": ["Gaming", "Fantasy"], "desc": "Geralt of Rivia, a solitary monster hunter, struggles to find his place in a world where people often prove more wicked than beasts."},
    {"title": "Arcane", "cats": ["Gaming", "Sci-Fi", "Drama"], "desc": "Set in utopian Piltover and the oppressed underground of Zaun, the story follows the origins of two iconic League champions-and the power that will tear them apart."},
    {"title": "Ready Player One", "cats": ["Gaming", "Sci-Fi"], "desc": "When the creator of a virtual reality called the OASIS dies, he makes a posthumous challenge to all OASIS users to find his Easter Egg."},
    {"title": "Wreck-It Ralph", "cats": ["Gaming", "Comedy"], "desc": "A video game villain wants to be a hero and sets out to fulfill his dream, but his quest brings havoc to the whole arcade where he lives."},
    {"title": "The Last of Us", "cats": ["Gaming", "Drama"], "desc": "After a global pandemic destroys civilization, a hardened survivor takes charge of a 14-year-old girl who may be humanity's last hope."},
    {"title": "Free Guy", "cats": ["Gaming", "Comedy"], "desc": "A bank teller discovers that he's actually an NPC inside a brutal, open world video game."},
    {"title": "Pixels", "cats": ["Gaming", "Comedy"], "desc": "When aliens misinterpret video feeds of classic arcade games as a declaration of war, they attack the Earth using the games as models."},
    {"title": "Lara Croft: Tomb Raider", "cats": ["Gaming", "Fantasy"], "desc": "Video game adventurer Lara Croft comes to life in a movie where she races against time and villains to recover powerful ancient artifacts."},
    {"title": "Mortal Kombat", "cats": ["Gaming", "Fantasy"], "desc": "Three unknowing martial artists are summoned to a mysterious island to compete in a tournament whose outcome will decide the fate of the world."},
    {"title": "Sonic the Hedgehog", "cats": ["Gaming", "Comedy", "Sci-Fi"], "desc": "After discovering a small, blue, fast hedgehog, a small-town police officer must help him defeat an evil genius who wants to do experiments on him."},
    {"title": "Detective Pikachu", "cats": ["Gaming", "Comedy", "Fantasy"], "desc": "In a world where people collect Pokémon to do battle, a boy comes across an intelligent talking Pikachu who seeks to be a detective."},
    {"title": "Uncharted", "cats": ["Gaming", "Drama"], "desc": "Street-smart Nathan Drake is recruited by seasoned treasure hunter Victor \"Sully\" Sullivan to recover a fortune amassed by Ferdinand Magellan and lost 500 years ago by the House of Moncada."},
    {"title": "Resident Evil", "cats": ["Gaming", "Sci-Fi"], "desc": "A special military unit fights a powerful, out-of-control supercomputer and hundreds of scientists who have mutated into flesh-eating creatures after a laboratory accident."},
    {"title": "Silent Hill", "cats": ["Gaming", "Drama"], "desc": "A woman, Rose, goes in search for her adopted daughter within the confines of a strange, desolate town called Silent Hill."},
    {"title": "Assassin's Creed", "cats": ["Gaming", "Sci-Fi"], "desc": "Callum Lynch explores the memories of his ancestor Aguilar de Nerha and gains the skills of a Master Assassin, before taking on the secret Templar society."},
    {"title": "Doom", "cats": ["Gaming", "Sci-Fi"], "desc": "Space Marines are sent to investigate strange events at a research facility on Mars but find themselves at the mercy of genetically enhanced killing machines."},
    {"title": "Super Mario Bros.", "cats": ["Gaming", "Comedy", "Fantasy"], "desc": "Two Brooklyn plumbers, Mario and Luigi, must travel to another dimension to rescue a princess from the evil dictator King Koopa and stop him from taking over the world."},
    {"title": "Castlevania", "cats": ["Gaming", "Fantasy"], "desc": "A vampire hunter fights to save a besieged city from an army of otherworldly creatures controlled by Dracula himself."},
    {"title": "DOTA: Dragon's Blood", "cats": ["Gaming", "Fantasy"], "desc": "A conflicted yet courageous Dragon Knight must use the power of the dragon within to stop a deadly demon."},
    {"title": "Fallout", "cats": ["Gaming", "Sci-Fi", "Drama"], "desc": "In a future, post-apocalyptic Los Angeles brought about by nuclear decimation, citizens must live in underground bunkers to protect themselves from radiation, mutants and bandits."},
    {"title": "Gran Turismo", "cats": ["Gaming", "Drama"], "desc": "Based on the unbelievable, inspiring true story of a team of underdogs - a struggling, working-class gamer, a failed former race-car driver, and an idealistic motorsport exec - who risk it all to take on the most elite sport in the world."},
    {"title": "Halo", "cats": ["Gaming", "Sci-Fi"], "desc": "Dramatizing an epic 26th-century conflict between humanity and an alien threat known as the Covenant, the series weaves deeply drawn personal stories with action, adventure and a richly imagined vision of the future."},
    {"title": "Prince of Persia: The Sands of Time", "cats": ["Gaming", "Fantasy"], "desc": "A young fugitive prince and princess must stop a villainous ruler who threatens to destroy the world with a special dagger that can reverse time."},
    {"title": "Street Fighter", "cats": ["Gaming", "Drama"], "desc": "Col. Guile and various other martial artists fight against the tyranny of M. Bison and his cohorts."},
    {"title": "Tekken", "cats": ["Gaming", "Drama"], "desc": "A young man seeks revenge against his father and grandfather after the murder of his mother, by entering a global martial arts tournament."},
    {"title": "Final Fantasy VII: Advent Children", "cats": ["Gaming", "Sci-Fi", "Fantasy"], "desc": "An ex-mercenary is forced out of isolation when three mysterious men kidnap children infected with an unknown disease."},
    {"title": "The Cuphead Show!", "cats": ["Gaming", "Comedy"], "desc": "Follow the misadventures of the impulsive Cuphead and his cautious but easily swayed brother Mugman in this animated series based on the hit video game."},
    {"title": "Angry Birds Movie", "cats": ["Gaming", "Comedy"], "desc": "Find out why the birds are so angry. When an island populated by happy, flightless birds is visited by mysterious green piggies, it's up to three unlikely outcasts - Red, Chuck and Bomb - to figure out what the pigs are up to."},
    {"title": "Ratchet & Clank", "cats": ["Gaming", "Comedy", "Sci-Fi"], "desc": "When the galaxy comes under threat from a space-faring villain, two unlikely heroes must join forces with a team of galactic rangers to save the day."},
    {"title": "Sly Cooper", "cats": ["Gaming", "Comedy"], "desc": "A kinetic and comedically edgy heist movie that tells the story of Sly Cooper, an orphaned raccoon thief, along with his childhood friends Bentley Turtle and Murray Hippo."},
    {"title": "Mega Man", "cats": ["Gaming", "Sci-Fi"], "desc": "A robotic boy created by a scientist to be his assistant is converted into a powerful battle robot to stop an evil mad scientist and his army of robots."},
    {"title": "World of Warcraft", "cats": ["Gaming", "Fantasy"], "desc": "As an Orc horde invades the planet Azeroth using a magic portal, a few human heroes and dissenting Orcs must attempt to stop the true evil behind this war."},
    {"title": "Gears of War", "cats": ["Gaming", "Sci-Fi", "Drama"], "desc": "A group of hardened soldiers fight a desperate battle against an underground reptilian threat known as the Locust Horde."},
    {"title": "God of War", "cats": ["Gaming", "Fantasy", "Drama"], "desc": "After settling into a new land of Norse gods and monsters, Kratos must fight to survive and teach his son to do the same."},
    {"title": "Horizon Zero Dawn", "cats": ["Gaming", "Sci-Fi"], "desc": "In a world where giant machines roam the Earth and humans live in primitive tribes, a young hunter named Aloy sets out to discover her origin and the fate of the ancestors."},
    {"title": "Twisted Metal", "cats": ["Gaming", "Comedy", "Sci-Fi"], "desc": "A motor-mouthed outsider is offered a chance at a better life, but only if he can successfully deliver a mysterious package across a post-apocalyptic wasteland."},
    {"title": "The Super Mario Bros. Movie", "cats": ["Gaming", "Comedy", "Fantasy"], "desc": "A plumber named Mario travels through an underground labyrinth with his brother, Luigi, trying to save a captured princess."},
    {"title": "Borderlands", "cats": ["Gaming", "Sci-Fi", "Comedy"], "desc": "An infamous outlaw returns to her home planet and forms an alliance with a team of unlikely heroes to find the missing daughter of the most powerful man in the universe."},
    {"title": "Monster Hunter", "cats": ["Gaming", "Fantasy"], "desc": "When Lt. Artemis and her loyal soldiers are transported to a new world, they engage in a desperate battle for survival against enormous enemies with incredible powers."},

    # MUSIC (40+)
    {"title": "Whiplash", "cats": ["Music", "Drama"], "desc": "A promising young drummer enrolls at a cut-throat music conservatory where his dreams of greatness are mentored by an instructor who will stop at nothing."},
    {"title": "Bohemian Rhapsody", "cats": ["Music", "Drama"], "desc": "The story of the legendary British rock band Queen and their lead singer Freddie Mercury, leading up to their famous performance at Live Aid (1985)."},
    {"title": "A Star Is Born", "cats": ["Music", "Drama"], "desc": "A musician helps a young singer find fame as age and alcoholism send his own career into a downward spiral."},
    {"title": "Straight Outta Compton", "cats": ["Music", "Drama"], "desc": "The story of the pioneering hip-hop group N.W.A, and its members Eazy-E, Dr. Dre, and Ice Cube."},
    {"title": "School of Rock", "cats": ["Music", "Comedy"], "desc": "After being kicked out of his rock band, Dewey Finn becomes a substitute teacher of a strict elementary private school, only to try and turn it into a rock band."},
    {"title": "The Greatest Showman", "cats": ["Music", "Drama"], "desc": "Celebrates the birth of show business and tells of a visionary who rose from nothing to create a spectacle that became a worldwide sensation."},
    {"title": "Yesterday", "cats": ["Music", "Comedy"], "desc": "A struggling musician realizes he's the only person on Earth who can remember The Beatles after waking up in an alternate timeline."},
    {"title": "Coco", "cats": ["Music", "Fantasy"], "desc": "Aspiring musician Miguel, confronted with his family's ancestral ban on music, enters the Land of the Dead to find his great-great-grandfather, a legendary singer."},
    {"title": "Amadeus", "cats": ["Music", "Drama"], "desc": "The life, success and troubles of Wolfgang Amadeus Mozart, as told by Antonio Salieri, the contemporaneous composer who was insanely jealous of Mozart's talent and claimed to have murdered him."},
    {"title": "Walk the Line", "cats": ["Music", "Drama"], "desc": "A chronicle of country music legend Johnny Cash's life, from his early days on an Arkansas cotton farm to his rise to fame with Sun Records in Memphis."},
    {"title": "Rocketman", "cats": ["Music", "Drama"], "desc": "A musical fantasy about the fantastical human story of Elton John's breakthrough years."},
    {"title": "The Sound of Music", "cats": ["Music", "Drama"], "desc": "A woman leaves an Austrian convent to become a governess to the seven children of a naval officer widower."},
    {"title": "La La Land", "cats": ["Music", "Comedy", "Drama"], "desc": "While navigating their careers in Los Angeles, a pianist and an actress fall in love while attempting to reconcile their aspirations for the future."},
    {"title": "Elvis", "cats": ["Music", "Drama"], "desc": "The life of American music icon Elvis Presley, from his childhood to becoming a rock and movie star in the 1950s while maintaining a complex relationship with his manager, Colonel Tom Parker."},
    {"title": "Ray", "cats": ["Music", "Drama"], "desc": "The story of the life and career of the legendary rhythm and blues musician Ray Charles, from his humble beginnings in the South, where he went blind at age seven, to his meteoric rise to stardom during the 1950s and 1960s."},
    {"title": "8 Mile", "cats": ["Music", "Drama"], "desc": "A young rapper, struggling with every aspect of his life, wants to make it big but his friends and foes make this difficult."},
    {"title": "Almost Famous", "cats": ["Music", "Drama"], "desc": "A high-school boy is given the chance to write a story for Rolling Stone Magazine about an up-and-coming rock band as he accompanies them on their concert tour."},
    {"title": "Across the Universe", "cats": ["Music", "Drama", "Fantasy"], "desc": "The music of the Beatles and the Vietnam War form the backdrop for the romance between an upper-class American girl and a poor Glaswegian artist."},
    {"title": "Sing Street", "cats": ["Music", "Comedy", "Drama"], "desc": "A boy growing up in Dublin during the 1980s escapes his strained family life by starting a band to impress the mysterious girl he likes."},
    {"title": "Pitch Perfect", "cats": ["Music", "Comedy"], "desc": "Beca, a freshman at Barden University, is cajoled into joining The Bellas, her school's all-girls singing group. Injecting some much needed energy into their repertoire, The Bellas take on their male rivals in a campus competition."},
    {"title": "Moulin Rouge!", "cats": ["Music", "Drama"], "desc": "A poet falls in love with a beautiful courtesan whom a jealous duke covets in this musical set in Paris."},
    {"title": "Blues Brothers", "cats": ["Music", "Comedy"], "desc": "Jake Blues, just out of prison, puts together his old band to save the Catholic orphanage where he and his brother Elwood were raised."},
    {"title": "This Is Spinal Tap", "cats": ["Music", "Comedy"], "desc": "Spinal Tap, one of England's loudest bands, is chronicled by film director Marty DeBergi on what proves to be a very fateful tour."},
    {"title": "Hairspray", "cats": ["Music", "Comedy"], "desc": "Pleasantly plump teenager Tracy Turnblad teaches 1962 Baltimore a thing or two about integration after landing a spot on a local TV dance show."},
    {"title": "High School Musical", "cats": ["Music", "Comedy", "Drama"], "desc": "A popular high school athlete and an academically gifted girl get roles in the school musical and develop a friendship that threatens the school's social order."},
    {"title": "Empire Records", "cats": ["Music", "Comedy", "Drama"], "desc": "The employees of an independent music store stay open late to try and save the shop from being sold to a large chain."},
    {"title": "Green Book", "cats": ["Music", "Drama"], "desc": "A working-class Italian-American bouncer becomes the driver of an African-American classical pianist on a tour through the 1960s American South."},
    {"title": "The Pianist", "cats": ["Music", "Drama"], "desc": "A Polish Jewish musician struggles to survive the destruction of the Warsaw ghetto of World War II."},
    {"title": "Phantom of the Opera", "cats": ["Music", "Drama", "Fantasy"], "desc": "A young soprano becomes the obsession of a disfigured and murderous musical genius who lives beneath the Paris Opéra House."},
    {"title": "Mamma Mia!", "cats": ["Music", "Comedy"], "desc": "The story of a bride-to-be searching for her real father told through the hit songs of the popular 1970s musical group ABBA."},
    {"title": "Les Misérables", "cats": ["Music", "Drama"], "desc": "In 19th-century France, Jean Valjean, who for decades has been hunted by the ruthless policeman Javert after breaking parole, agrees to care for a factory worker's daughter. The decision changes their lives forever."},
    {"title": "Chicago", "cats": ["Music", "Comedy", "Drama"], "desc": "Two death-row murderesses develop a fierce rivalry while competing for the publicity, celebrity, and a sleazy lawyer who can keep them from the gallows in 1920s Chicago."},
    {"title": "Jersey Boys", "cats": ["Music", "Drama"], "desc": "The story of four young men from the wrong side of the tracks in New Jersey who came together to form the iconic 1960s rock group The Four Seasons."},
    {"title": "Sing", "cats": ["Music", "Comedy"], "desc": "In a city of humanoid animals, a hustling theater impresario's attempt to save his theater with a singing competition becomes grander than he anticipates even as its finalists find that their lives will never be the same."},
    {"title": "Hamilton", "cats": ["Music", "Drama"], "desc": "The real life of one of America's foremost founding fathers and first Secretary of the Treasury, Alexander Hamilton. Captured live on Broadway from the Richard Rodgers Theatre with the original Broadway cast."},
    {"title": "Tick, Tick... Boom!", "cats": ["Music", "Drama"], "desc": "On the cusp of his 30th birthday, a promising young theater composer navigates love, friendship and the pressures of life as an artist in New York City."},
    {"title": "Encanto", "cats": ["Music", "Fantasy", "Comedy"], "desc": "A young Colombian girl has to face the frustration of being the only member of her family without magical powers."},
    {"title": "Moana", "cats": ["Music", "Fantasy", "Comedy"], "desc": "In Ancient Polynesia, when a terrible curse incurred by the Demigod Maui reaches Moana's island, she answers the Ocean's call to seek out the Demigod to set things right."},
    {"title": "Turning Red", "cats": ["Music", "Comedy", "Fantasy"], "desc": "A thirteen-year-old girl named Mei Lee is torn between staying her mother's dutiful daughter and the changes of adolescence. And as if her interests, relationships and body weren't enough, whenever she gets too excited, she \"poofs\" into a giant red panda."},
    {"title": "Purple Rain", "cats": ["Music", "Drama"], "desc": "A young man with a talent for music has a rocky personal life with his victimized mother and his abusive father. He must find another way to express himself through his music."},

    # EDUCATION (40+)
    {"title": "Planet Earth", "cats": ["Education", "Sci-Fi"], "desc": "Emmy Award-winning, 11-part nature documentary series from the BBC, five years in the making and the most expensive nature documentary series ever commissioned by the BBC."},
    {"title": "Cosmos: A Spacetime Odyssey", "cats": ["Education", "Tech"], "desc": "An exploration of our discovery of the laws of nature and coordinates in space and time."},
    {"title": "The Mind, Explained", "cats": ["Education"], "desc": "Ever wonder what's happening inside your head? From dreaming to anxiety disorders, discover how your brain works with this illuminating series."},
    {"title": "Abstract: The Art of Design", "cats": ["Education", "Tech"], "desc": "Step inside the minds of the most innovative designers in a variety of disciplines and learn how design impacts every aspect of life."},
    {"title": "Our Planet", "cats": ["Education"], "desc": "Documentary series focusing on the breadth of the diversity of habitats around the world, from the remote Arctic wilderness to the jungles of South America."},
    {"title": "Explained", "cats": ["Education", "Tech"], "desc": "This enlightening series from Vox digs into a wide range of topics such as the rise of cryptocurrency, why diets fail, and the wild world of K-pop."},
    {"title": "Apollo 11", "cats": ["Education", "Tech"], "desc": "A look at the Apollo 11 mission to land on the moon led by commander Neil Armstrong and pilots Buzz Aldrin and Michael Collins."},
    {"title": "Dead Poets Society", "cats": ["Education", "Drama"], "desc": "English teacher John Keating inspires his students to look at poetry with a different perspective of authentic self-expression."},
    {"title": "Blue Planet II", "cats": ["Education"], "desc": "David Attenborough returns to the world's oceans in this sequel to the celebrated documentary series, exploring the rare and unusual creatures of the deep."},
    {"title": "Free Solo", "cats": ["Education", "Drama"], "desc": "Alex Honnold attempts to become the first person to ever free solo climb El Capitan."},
    {"title": "Becoming", "cats": ["Education", "Drama"], "desc": "An intimate look into the life of former First Lady Michelle Obama during a moment of profound change, not only for her but for the country she served as she embarked on a 34-city tour that highlighted the power of community to bridge our divides."},
    {"title": "The Last Dance", "cats": ["Education", "Drama"], "desc": "Charting the rise of the 1990s Chicago Bulls, led by Michael Jordan, one of the most notable dynasties in sports history."},
    {"title": "Chef's Table", "cats": ["Education"], "desc": "Docuseries that takes viewers inside the lives and kitchens of six of the world's most renowned international chefs."},
    {"title": "Inside Bill's Brain", "cats": ["Education", "Tech"], "desc": "Take a trip into the mind of Bill Gates as the billionaire opens up about his childhood, business career and passion for improving the lives of people in the developing world."},
    {"title": "Man on Wire", "cats": ["Education", "Drama"], "desc": "A look at Philippe Petit's daring mural walk between the Twin Towers of the World Trade Center in 1974."},
    {"title": "Minimalism: A Documentary", "cats": ["Education"], "desc": "How might your life be better with less? Minimalism: A Documentary About the Important Things examines the many flavors of minimalism by taking audiences inside the lives of minimalists from all walks of life."},
    {"title": "Dirty Money", "cats": ["Education", "Drama"], "desc": "An anthology series highlighting some of the world's most shocking stories of white-collar crime and corruption."},
    {"title": "The Social Dilemma", "cats": ["Education", "Tech", "Drama"], "desc": "Explores the dangerous human impact of social networking, with tech experts sounding the alarm on their own creations."},
    {"title": "13th", "cats": ["Education", "Drama"], "desc": "An in-depth look at the prison system in the United States and how it reveals the nation's history of racial inequality."},
    {"title": "My Octopus Teacher", "cats": ["Education", "Drama"], "desc": "A filmmaker forges an unusual friendship with an octopus living in a South African kelp forest, learning as the animal shares the mysteries of her world."},
    {"title": "Crip Camp", "cats": ["Education", "Drama"], "desc": "Down the road from Woodstock, a revolution blossomed in a summer camp for teenagers with disabilities, transforming their lives and igniting a landmark movement."},
    {"title": "Summer of Soul", "cats": ["Education", "Music", "Drama"], "desc": "Explores the legendary 1969 Harlem Cultural Festival which celebrated African American music and culture, and promoted Black pride and unity."},
    {"title": "Prehistoric Planet", "cats": ["Education", "Sci-Fi"], "desc": "Experience the world of dinosaurs like never before in this epic docuseries from Executive Producer Jon Favreau and the producers of Planet Earth. Travel back 66 million years to when majestic dinosaurs and extraordinary creatures roamed the lands, seas, and skies."},
    {"title": "Life on Our Planet", "cats": ["Education"], "desc": "The story of Earth's epic 4-billion-year journey to survive and thrive across time, told through its most remarkable creatures and the cataclysmic events that shaped their world."},
    {"title": "Secret of the Whale", "cats": ["Education"], "desc": "Sigourney Weaver narrates this series that plunges viewers deep within the epicenter of whale culture to experience the extraordinary communication skills and intricate social structures of five different whale species."},
    {"title": "The Elephant Whisperers", "cats": ["Education", "Drama"], "desc": "Bomman and Bellie, a couple in South India, devote their lives to caring for an orphaned baby elephant named Raghu, forging a family like no other that tests the barrier between the human and animal world."},
    {"title": "Navalny", "cats": ["Education", "Drama"], "desc": "Follows the investigation into the assassination attempt of Russian opposition leader and anti-corruption activist Alexei Navalny."},
    {"title": "Icarus", "cats": ["Education", "Drama"], "desc": "When Bryan Fogel sets out to uncover the truth about doping in sports, a chance meeting with a Russian scientist transforms his personal spiritual journey into a geopolitical thriller."},
    {"title": "Wild Wild Country", "cats": ["Education", "Drama"], "desc": "When a controversial cult leader builds a utopian city in the Oregon desert, conflict with local neighbors escalates into a national scandal."},
    {"title": "Tiger King", "cats": ["Education", "Comedy", "Drama"], "desc": "A rivalry between big cat eccentric Joe Exotic and animal rights activist Carole Baskin takes a dark turn in this documentary series about the world of exotic animal breeding."},
    {"title": "Making a Murderer", "cats": ["Education", "Drama"], "desc": "Filmed over a 10-year period, Making a Murderer is an unprecedented real-life thriller about Steven Avery, a DNA exoneree who, while in the midst of exposing corruption in local law enforcement, finds himself the prime suspect in a grisly new crime."},
    {"title": "The Keepers", "cats": ["Education", "Drama"], "desc": "This docuseries explores the unsolved murder of nun Sister Cathy Cesnik and the secrets that remain nearly five decades after her death."},
    {"title": "Wormwood", "cats": ["Education", "Drama"], "desc": "Errol Morris examines the mysterious death of a Cold War era scientist involved in a secret biological warfare program."},
    {"title": "Five Came Back", "cats": ["Education", "Drama"], "desc": "Three modern filmmakers take us inside the lives and work of five legendary directors who served in World War II, using their talents to tell the story of the war to the American public."},
    {"title": "The Toys That Made Us", "cats": ["Education", "Comedy"], "desc": "The minds behind history's most iconic toy franchises discuss the rise and sometimes fall of their multi-billion dollar creations."},
    {"title": "Movies That Made Us", "cats": ["Education", "Comedy"], "desc": "Explore the blockbusters that defined a generation and the people who brought them to life."},
    {"title": "The Last Movie Stars", "cats": ["Education", "Drama"], "desc": "An epic six-part documentary series from Ethan Hawke that celebrates the enigmatic personas and love story of Paul Newman and Joanne Woodward."},
    {"title": "Unknown: Cosmic Time Machine", "cats": ["Education", "Tech"], "desc": "With unique access behind the scenes to NASA's ambitious mission to launch the James Webb Space Telescope, we follow a team of engineers and scientists as they take the next giant leap in our quest to understand the universe."},
    {"title": "Sly", "cats": ["Education", "Drama"], "desc": "Sylvester Stallone's love of movies began as an escape from a rocky childhood. From underdog to Hollywood legend, Stallone tells his story in this intimate documentary."},
    {"title": "Stutz", "cats": ["Education", "Drama"], "desc": "In candid conversations with actor Jonah Hill, leading psychiatrist Phil Stutz explores his early life experiences and unique visual model of therapy."},

    # COMEDY (40+)
    {"title": "The Office", "cats": ["Comedy"], "desc": "A mockumentary on a group of typical office workers, where the workday consists of ego clashes, inappropriate behavior, and tedium."},
    {"title": "Brooklyn Nine-Nine", "cats": ["Comedy"], "desc": "Detective Jake Peralta, a talented and carefree cop, and his diverse group of colleagues investigate crimes in the 99th Precinct of the NYPD."},
    {"title": "Parks and Recreation", "cats": ["Comedy"], "desc": "The absurd antics of Indiana town's public officials as they pursue sundry projects to make their city a better place."},
    {"title": "The Big Bang Theory", "cats": ["Comedy", "Tech"], "desc": "A woman who moves into an apartment next door to two brilliant but socially awkward physicists shows them how little they know about life outside of the laboratory."},
    {"title": "Friends", "cats": ["Comedy"], "desc": "Follows the personal and professional lives of six twenty to thirty-something-year-old friends living in Manhattan."},
    {"title": "Superbad", "cats": ["Comedy"], "desc": "Two co-dependent high school seniors are forced to deal with separation anxiety after their plan to stage a booze-soaked party goes awry."},
    {"title": "Curb Your Enthusiasm", "cats": ["Comedy"], "desc": "The life and times of Larry David and the various predicaments he gets himself into with his friends and complete strangers."},
    {"title": "Modern Family", "cats": ["Comedy"], "desc": "Three different but related families face trials and tribulations in their own uniquely comedic ways."},
    {"title": "Seinfeld", "cats": ["Comedy"], "desc": "The continuing misadventures of neurotic New York City stand-up comedian Jerry Seinfeld and his equally neurotic New York City friends."},
    {"title": "The Simpsons", "cats": ["Comedy"], "desc": "The satiric adventures of a working-class family in the misfit city of Springfield."},
    {"title": "South Park", "cats": ["Comedy"], "desc": "Follows the misadventures of four irreverent grade-schoolers in the quiet, dysfunctional town of South Park, Colorado."},
    {"title": "Rick and Morty", "cats": ["Comedy", "Sci-Fi", "Tech"], "desc": "An animated series that follows the exploits of a super scientist and his easily influenced grandson."},
    {"title": "Ted Lasso", "cats": ["Comedy", "Drama"], "desc": "American college football coach Ted Lasso heads to London to manage AFC Richmond, a struggling English Premier League football team."},
    {"title": "Arrested Development", "cats": ["Comedy"], "desc": "Level-headed son Michael Bluth takes over family affairs after his father is imprisoned. But the rest of his spoiled, dysfunctional family are making his job unbearable."},
    {"title": "30 Rock", "cats": ["Comedy"], "desc": "Liz Lemon, head writer of a sketch comedy show, must deal with an arrogant new boss and a crazy new star, all while trying to run a successful TV show without losing her mind."},
    {"title": "Community", "cats": ["Comedy"], "desc": "A suspended lawyer is forced to enroll in a community college with an eccentric staff and student body."},
    {"title": "Schitt's Creek", "cats": ["Comedy"], "desc": "When rich video-store magnate Johnny Rose and his family suddenly find themselves broke, they are forced to leave their pampered lives to regroup and rebuild their empire from within the rural city limits of their only remaining asset, Schitt's Creek."},
    {"title": "Veep", "cats": ["Comedy"], "desc": "Former Senator Selina Meyer finds that being Vice President of the United States is nothing like she hoped and everything that everyone ever warned her about."},
    {"title": "It's Always Sunny in Philadelphia", "cats": ["Comedy"], "desc": "Five friends with big egos and small brains own and operate a neighborhood pub in Philadelphia and find themselves in various crazy situations."},
    {"title": "The Good Place", "cats": ["Comedy", "Fantasy"], "desc": "Four people and their otherworldly savior struggle in the afterlife to define what it means to be good."},
    {"title": "Broad City", "cats": ["Comedy"], "desc": "Broad City follows two women throughout their daily lives in New York City, making the smallest and most mundane events hysterical and disturbing to watch all at the same time."},
    {"title": "Fleabag", "cats": ["Comedy", "Drama"], "desc": "A dry-witted woman, known only as Fleabag, has no filter as she navigates life and love in London while trying to cope with tragedy."},
    {"title": "Barry", "cats": ["Comedy", "Drama"], "desc": "A hit man from the Midwest moves to Los Angeles and gets caught up in the city's theatre arts scene."},
    {"title": "Silicon Valley", "cats": ["Comedy", "Tech"], "desc": "Follows the struggle of Richard Hendricks, a Silicon Valley engineer who tries to build his own company called Pied Piper."},
    {"title": "The Marvelous Mrs. Maisel", "cats": ["Comedy", "Drama"], "desc": "A housewife in the 1950s decides to become a stand-up comedian."},
    {"title": "Insecure", "cats": ["Comedy", "Drama"], "desc": "Follows the awkward experiences and racy tribulations of a modern-day African-American woman."},
    {"title": "Atlanta", "cats": ["Comedy", "Drama"], "desc": "Earnest \"Earn\" Marks and his cousin Alfred \"Paper Boi\" Miles, an up-and-coming rapper, navigate the Atlanta music scene while facing social and economic issues."},
    {"title": "The Hangover", "cats": ["Comedy"], "desc": "Three buddies wake up from a bachelor party in Las Vegas, with no memory of the previous night and the bachelor missing. They make their way around the city in order to find their friend before his wedding."},
    {"title": "Bridesmaids", "cats": ["Comedy"], "desc": "Competition between the maid of honor and a bridesmaid, over who is the bride's best friend, threatens to upend the life of an out-of-work pastry chef."},
    {"title": "Ghostbusters", "cats": ["Comedy", "Sci-Fi", "Fantasy"], "desc": "Three parapsychologists forced out of their university funding set up shop as a unique ghost removal service in New York City, attracting frightened yet skeptical customers."},
    {"title": "Airplane!", "cats": ["Comedy"], "desc": "A man afraid to fly must ensure that a plane lands safely after the pilots become sick."},
    {"title": "Monty Python and the Holy Grail", "cats": ["Comedy", "Fantasy"], "desc": "King Arthur and his Knights of the Round Table embark on a surreal, low-budget search for the Holy Grail, encountering many, many strange obstacles."},
    {"title": "Borat", "cats": ["Comedy"], "desc": "Kazakh TV talking head Borat is dispatched to the United States to report on the greatest country in the world. With a documentary crew in tow, Borat becomes more interested in locating and marrying Pamela Anderson."},
    {"title": "The Truman Show", "cats": ["Comedy", "Drama", "Sci-Fi"], "desc": "An insurance salesman discovers his whole life is actually a reality TV show."},
    {"title": "Groundhog Day", "cats": ["Comedy", "Fantasy", "Drama"], "desc": "A weather man finds himself inexplicably living the same day over and over again."},
    {"title": "Dumb and Dumber", "cats": ["Comedy"], "desc": "After a woman leaves a briefcase at the airport terminal, two unintelligent friends go on a cross-country trip to Aspen to return it."},
    {"title": "Ferris Bueller's Day Off", "cats": ["Comedy"], "desc": "A high school wise guy is determined to have a day off from school, despite what the Principal thinks of it."},
    {"title": "Coming to America", "cats": ["Comedy"], "desc": "An extremely pampered African prince travels to Queens, New York, and goes undercover to find a wife whom he can respect for her intelligence and will."},
    {"title": "Step Brothers", "cats": ["Comedy"], "desc": "Two middle-aged, loosely employed men who still live with their parents are forced to live together when their parents marry."},
    {"title": "Pineapple Express", "cats": ["Comedy", "Drama"], "desc": "A process server and his marijuana dealer wind up on the run from hit men and a corrupt police officer after he witnesses the city's most powerful drug lord murder a competitor."},
]

async def enrich_from_amazon():
    print("\n" + "═" * 80)
    print("       🚀 AURORA-VRS JUMBO AMAZON METADATA ENRICHER")
    print("═" * 80)
    
    conn = await asyncpg.connect(DATABASE_URL)

    # 1. Sync Categories
    categories = list(set([c for m in SAMPLE_MOVIES for c in m.get("cats", [])]))
    print(f"📦 Syncing categories: {', '.join(categories)}")
    
    for cat in categories:
        await conn.execute("""
            INSERT INTO categories (id, name)
            VALUES ($1, $2)
            ON CONFLICT (name) DO NOTHING
        """, uuid.uuid4(), cat)

    # 2. Add Anchor Videos
    print(f"\n🎥 Injecting {len(SAMPLE_MOVIES)} Semantic Anchor Videos...")
    
    count = 0
    now = datetime.utcnow()
    
    for movie in SAMPLE_MOVIES:
        v_id = uuid.uuid4()
        title = movie.get("title")
        desc = movie.get("desc")
        cats = movie.get("cats", [])
        
        # Insert video only if title doesn't exist to avoid duplicates
        exists = await conn.fetchval("SELECT id FROM videos WHERE title = $1 LIMIT 1", title)
        if exists:
            # print(f"  ⏩ Skipping (already exists): {title[:30]}...")
            continue

        await conn.execute("""
            INSERT INTO videos (id, title, description, privacy, status, created_at, view_count, like_count, duration_sec)
            VALUES ($1, $2, $3, 'PUBLIC', 'READY', $4, $5, $6, $7)
        """, v_id, title, desc, now, random.randint(100, 1000), random.randint(10, 50), random.randint(30, 180))
        
        # Link to categories
        for cat_name in cats:
            cat_id = await conn.fetchval("SELECT id FROM categories WHERE name = $1", cat_name)
            if cat_id:
                await conn.execute("""
                    INSERT INTO video_categories (video_id, category_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                """, v_id, cat_id)
        
        if count % 20 == 0:
            print(f"  ... Injecting {count}/{len(SAMPLE_MOVIES)}")
        count += 1

    await conn.close()
    print(f"\n🚀 SUCCESS: Injected {count} high-quality anchor videos.")
    print("═" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(enrich_from_amazon())
