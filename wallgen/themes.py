"""Библиотека тем и оси разнообразия.

Каждая тема: русское название + список сюжетов (на английском — модели лучше понимают).
Тема может ограничить пул стилей (например, «Аниме» — только аниме-стили).
Остальные оси (композиция, палитра, свет, атмосфера) общие для всех тем.
"""

# --------------------------------------------------------------------------
# Стили
# --------------------------------------------------------------------------
PHOTO_STYLES = [
    "cinematic photography, shot on full-frame camera, shallow depth of field",
    "award-winning landscape photography, ultra sharp, high dynamic range",
    "moody film photography, Kodak Portra 400 film grain",
    "aerial drone photography, crisp details",
    "long exposure photography, silky smooth motion",
    "macro photography, extreme close-up, creamy bokeh",
]
ART_STYLES = [
    "digital matte painting, epic concept art",
    "oil painting with visible impasto brushstrokes",
    "soft watercolor illustration on textured paper",
    "Studio-style hand-painted anime background art",
    "highly detailed 3D render, octane render, volumetric light",
    "low-poly 3D art, clean geometric facets",
    "flat vector illustration, bold simple shapes",
    "Japanese ukiyo-e woodblock print style",
    # «art nouveau» убран: по итогам прогона 100 шт. рисовал декоративную рамку в 4 из 5 картинок
    "synthwave retro-futuristic art",
    "paper-cut layered art, depth with soft shadows",
    "tilt-shift miniature effect photography of a real scene",   # было «isometric diorama» — рисовал макет на столе
    "dreamy surrealist painting",
    "minimalist art, lots of negative space, edge-to-edge",
    "ink and gouache illustration, textured",
    "pixel art, detailed 16-bit style",
]
ANIME_STYLES = [
    "Studio-style hand-painted anime background art",
    "modern anime key visual, vibrant cel shading",
    "90s retro anime aesthetic, film grain",
    "anime illustration, soft pastel shading, light novel cover style",
    "detailed anime scenery, luminous sky and dramatic clouds",
]
MINIMAL_STYLES = [
    "minimalist art, lots of negative space, edge-to-edge",
    "flat vector illustration, bold simple shapes",
    "paper-cut layered art, depth with soft shadows",
    "clean gradient art, smooth shapes",
    "single continuous line art over a full-bleed color gradient",
]
ABSTRACT_STYLES = [
    "fluid acrylic pour art, cells and swirls",
    "3D abstract render, glossy glass and chrome shapes",
    "generative art, flowing particle trails",
    "liquid marble texture with gold veins",
    "holographic iridescent gradient waves",
    "Bauhaus geometric composition",
    "macro photography of ink drops in water",
    "fractal art, infinite recursive patterns",
]
ALL_STYLES = PHOTO_STYLES + ART_STYLES

# --------------------------------------------------------------------------
# Общие оси разнообразия
# --------------------------------------------------------------------------
COMPOSITIONS = [
    "centered symmetrical composition",
    "low angle view looking up, towering scale",
    "high angle bird's-eye view",
    "subject placed in the lower third, vast open sky above",
    "rule of thirds, strong leading lines",
    "tall upright vista with deep perspective, horizon in the lower half",
    "close-up with layered foreground depth",
    "tiny subject in an immense environment, sense of scale",
    "vertical diagonal composition, dynamic flow",
    "calm empty upper area, main subject at the bottom",
]
PALETTES = [
    "warm amber and deep violet palette",
    "teal and orange palette",
    "pastel pink, lavender and baby blue palette",
    "monochrome blue palette",
    "neon magenta and electric cyan palette",
    "earthy greens and browns palette",
    "black and gold palette",
    "icy white and pale blue palette",
    "crimson red and charcoal palette",
    "emerald and turquoise palette",
    "soft beige and sage muted palette",
    "vivid rainbow spectrum palette",
    "deep navy and silver palette",
    "sunset peach and coral palette",
]
LIGHTING = [
    "golden hour light",
    "blue hour twilight",
    "soft diffused overcast light",
    "dramatic god rays",
    "moonlight with a starry sky",
    "neon glow",
    "bioluminescent glow",
    "backlit rim lighting",
    "misty atmospheric haze",
    "harsh midday sun with deep shadows",
    "candlelight warm glow",
    "aurora light",
]
MOODS = [
    "serene and calm",
    "epic and majestic",
    "mysterious",
    "dreamy and nostalgic",
    "cozy",
    "dramatic",
    "melancholic",
    "joyful and vibrant",
    "otherworldly",
    "peaceful and minimal",
]

# --------------------------------------------------------------------------
# Темы
# --------------------------------------------------------------------------
THEMES: dict[str, dict] = {
    "space": {
        "name": "Космос",
        "lighting": ["starlight", "glowing nebula light", "rim light from a distant star",
                     "dramatic god rays through cosmic dust", "bioluminescent glow", "aurora light",
                     "eclipse corona glow"],
        "subjects": [
            "a swirling spiral galaxy in deep space",
            "a colorful nebula with newborn stars",
            "a ringed gas giant seen from its icy moon",
            "an astronaut floating above Earth",
            "a black hole bending light around it",
            "a lone observatory under the Milky Way",
            "a comet streaking past a red planet",
            "an alien planet surface with two suns on the horizon",
            "a space station orbiting a blue planet",
            "a field of glowing asteroids",
            "a solar eclipse with a glowing corona",
            "a planet sunrise seen from orbit",
        ],
    },
    "mountains": {
        "name": "Горы",
        "subjects": [
            "a lone snow-capped peak above a sea of clouds",
            "an alpine lake reflecting jagged mountains",
            "a winding mountain road through a valley",
            "a tiny wooden cabin at the foot of giant mountains",
            "a mountain ridge silhouette layered into the distance",
            "a waterfall cascading down a steep cliff",
            "a climber standing on a narrow summit",
            "a volcano with glowing lava under the night sky",
            "terraced hills with morning fog",
            "a glacier with deep blue ice crevasses",
            "a mountain village with lit windows",
            "rocky canyon walls with a river below",
        ],
    },
    "ocean": {
        "name": "Океан и море",
        "subjects": [
            "a giant curling ocean wave",
            "a lighthouse on a rocky cliff during a storm",
            "a tropical turquoise lagoon from above",
            "an underwater coral reef with sunbeams",
            "a whale swimming under the surface",
            "a lonely sailboat on a calm sea",
            "sea foam patterns on a black sand beach",
            "a pier stretching into the misty sea",
            "jellyfish glowing in the dark ocean",
            "sea stacks and cliffs on a wild coast",
            "a sunken shipwreck in clear water",
            "footprints on an empty beach at low tide",
        ],
    },
    "forest": {
        "name": "Лес и природа",
        "subjects": [
            "a path through an ancient misty forest",
            "giant redwood trees looking up to the canopy",
            "a lone tree on a hill in a vast meadow",
            "an autumn forest with falling orange leaves",
            "a mossy stream with small waterfalls",
            "a bamboo forest with light filtering through",
            "a snowy pine forest in silence",
            "a field of wildflowers swaying in the wind",
            "a deer standing in a foggy clearing",
            "a cherry blossom tree in full bloom",
            "glowing mushrooms on the forest floor",
            "lavender fields stretching to the horizon",
        ],
    },
    "cyberpunk": {
        "name": "Киберпанк-город",
        "subjects": [
            "a rainy neon-lit street in a futuristic megacity",
            "flying cars between towering skyscrapers",
            "a lone figure with an umbrella under neon signs",
            "a futuristic night market with holograms",
            "a rooftop view over an endless glowing city",
            "a cyberpunk alley with steam and cables",
            "a giant holographic koi fish over the city",
            "a monorail train crossing a neon skyline",
            "a hacker's room with glowing screens overlooking the city",
            "a vertical city with layered bridges and walkways",
        ],
    },
    "city": {
        "name": "Города и архитектура",
        "subjects": [
            "a narrow European street with cafe lights",
            "a skyscraper looking straight up into the sky",
            "a cozy Japanese street at dusk",
            "Santorini white houses above the blue sea",
            "a bridge over a river at night with reflections",
            "a spiral staircase seen from above",
            "a tram passing through an old city in the rain",
            "a futuristic white building with curved lines",
            "rooftops of an old town covered in snow",
            "an empty subway station with symmetrical lights",
            "a Venetian canal with gondolas",
            "a modern glass tower reflecting clouds",
        ],
    },
    "anime": {
        "name": "Аниме-пейзажи",
        "styles": ANIME_STYLES,
        "subjects": [
            "a girl standing on a hill looking at giant summer clouds",
            "a countryside train station at sunset",
            "a starry night sky over a quiet rural town",
            "a school rooftop with a view of the city",
            "a shrine gate in a forest with fireflies",
            "a cozy room with a window view of the rain",
            "a sky island with waterfalls falling into clouds",
            "a bicycle on a seaside road in summer",
            "cherry blossom petals falling over a river",
            "a convenience store glowing at night on an empty street",
            "a field of sunflowers under a bright blue sky",
            "a magical floating castle above the clouds",
        ],
    },
    "fantasy": {
        "name": "Фэнтези",
        "subjects": [
            "a dragon flying over a medieval castle",
            "an enchanted glowing forest with fairy lights",
            "a wizard tower on a cliff in a storm",
            "a giant ancient tree with a city in its branches",
            "a portal of light in ancient ruins",
            "floating islands connected by rope bridges",
            "an elven city with waterfalls",
            "a knight facing a huge creature in the mist",
            "a crystal cave glowing with magic",
            "a phoenix rising from flames",
            "a hidden library with endless bookshelves",
            "a mystical lake with a sword rising from the water",
        ],
    },
    "abstract": {
        "name": "Абстракция",
        "styles": ABSTRACT_STYLES,
        "subjects": [
            "flowing liquid shapes",
            "intertwined ribbons of color",
            "layered translucent waves",
            "floating geometric spheres",
            "organic swirling patterns",
            "crystalline shards of light",
            "smooth gradient dunes",
            "exploding particles of color",
            "interlocking circles and arcs",
            "melting color fields",
        ],
    },
    "minimal": {
        "name": "Минимализм",
        "styles": MINIMAL_STYLES,
        "subjects": [
            "a single moon over a calm sea",
            "a lone tree on a gentle hill",
            "layered mountain silhouettes",
            "a small boat on a still lake",
            "a sun setting between two dunes",
            "a single flower stem",
            "a cat sitting on a windowsill",
            "a paper plane in an empty sky",
            "a lighthouse on a tiny island",
            "a hot air balloon in a clear sky",
        ],
    },
    "animals": {
        "name": "Животные",
        "subjects": [
            "a majestic lion portrait with a flowing mane",
            "a red fox in fresh snow",
            "an owl with glowing eyes in the dark forest",
            "a wolf howling at the full moon",
            "a hummingbird near a flower",
            "a tiger walking through tall grass",
            "a koi fish pond from above",
            "a polar bear on drifting ice",
            "a flock of flamingos at a lake",
            "a sleepy cat curled in sunlight",
            "a chameleon on a branch with vivid colors",
            "a herd of horses running across a plain",
        ],
    },
    "flowers": {
        "name": "Цветы и макро",
        "subjects": [
            "dew drops on a rose petal",
            "a single peony in full bloom",
            "a dandelion seed head with seeds flying away",
            "a field of tulips",
            "water lilies on a dark pond",
            "a sunflower close-up showing the spiral pattern",
            "frost crystals on a leaf",
            "a butterfly resting on lavender",
            "a monstera leaf with light and shadow",
            "a bouquet of wildflowers in a glass vase",
            "a lotus flower rising from the water",
        ],
    },
    "sky": {
        "name": "Небо и погода",
        "subjects": [
            "a lightning storm over the plains",
            "the northern lights over a frozen lake",
            "towering cumulus clouds at sunset",
            "a rainbow after the rain over green hills",
            "a full moon rising behind clouds",
            "a tornado over a wheat field",
            "the Milky Way over a desert",
            "mammatus clouds glowing orange",
            "a meteor shower over the mountains",
            "fog rolling over the hills at dawn",
        ],
    },
    "desert": {
        "name": "Пустыня",
        "subjects": [
            "rippled sand dunes with sharp shadows",
            "a camel caravan crossing the dunes",
            "an oasis with palm trees",
            "a red rock arch under the stars",
            "a lonely road through the desert",
            "a slot canyon with beams of light",
            "a cracked salt flat reflecting the sky",
            "an abandoned desert town",
            "a giant cactus at sunset",
            "a desert monument valley landscape",
        ],
    },
    "winter": {
        "name": "Зима",
        "subjects": [
            "a cozy cabin in a snowstorm with warm windows",
            "snow-covered pine trees in silence",
            "a frozen lake with cracks in the ice",
            "a reindeer in a snowy tundra",
            "an ice cave with blue walls",
            "a winter village with Christmas lights",
            "snowflakes close-up on dark fabric",
            "a frozen waterfall",
            "a sleigh path through a snowy forest",
            "a snowy mountain hut under the stars",
        ],
    },
    "scifi": {
        "name": "Научная фантастика",
        "subjects": [
            "a colossal spaceship over an alien city",
            "a robot sitting alone in a field of flowers",
            "a Mars colony under a glass dome",
            "a futuristic city on another planet",
            "a mech standing in the ruins",
            "a space elevator rising into the clouds",
            "an alien jungle with giant glowing plants",
            "a time portal opening in the sky",
            "an abandoned spacecraft overgrown with plants",
            "a starship engine glowing blue",
        ],
    },
    "retro": {
        "name": "Ретро и синтвейв",
        "styles": [
            "synthwave retro-futuristic art",
            "80s airbrush illustration",
            "vaporwave aesthetic, glitch details",
            "vintage travel illustration, full-bleed",
            "retro pixel art",
        ],
        "subjects": [
            "a sunset over a grid landscape with palm trees",
            "a retro sports car on an endless highway",
            "a neon palm beach at night",
            "a retro arcade room glowing",
            "a giant sun over a chrome city",
            "a cassette tape floating in space",
            "a vintage motel sign in the desert",
            "a retro space shuttle launch",
        ],
    },
    "cozy": {
        "name": "Уют",
        "lighting": ["candlelight warm glow", "warm lamp light", "golden hour light through a window",
                     "soft fairy lights", "soft diffused overcast light", "blue hour twilight"],
        "subjects": [
            "a cup of coffee by a rainy window",
            "a reading nook with books and warm lamp light",
            "a cat sleeping on a knitted blanket",
            "a little bakery on a snowy street",
            "fairy lights in a bedroom at night",
            "a cabin porch with a view of autumn mountains",
            "a desk with plants and a sunset window view",
            "hot tea and candles on a winter evening",
            "a treehouse with lanterns",
            "a greenhouse full of plants",
        ],
    },
    "japan": {
        "name": "Япония",
        "subjects": [
            "Mount Fuji with cherry blossoms",
            "a red torii gate in the sea",
            "a pagoda among autumn maples",
            "a quiet Kyoto street with lanterns",
            "a zen garden with raked sand",
            "a bamboo grove path",
            "a koi pond in a Japanese garden",
            "a snowy temple in the mountains",
            "a Shinkansen passing Mount Fuji",
            "paper lanterns floating on a river",
        ],
    },
    "underwater": {
        "name": "Подводный мир",
        "lighting": ["sunbeams filtering through the water", "bioluminescent glow",
                     "dappled caustic light patterns", "deep blue ambient light",
                     "backlit rim lighting from the surface"],
        "subjects": [
            "a sea turtle swimming through sunbeams",
            "a school of fish forming a spiral",
            "a manta ray gliding over the reef",
            "a kelp forest with light rays",
            "a mysterious underwater temple",
            "a diver exploring a sea cave",
            "an octopus on colorful corals",
            "bioluminescent deep sea creatures",
            "a seahorse among sea grass",
            "a shark silhouette from below",
        ],
    },
}

# Общие технические требования, добавляются в конец любого промпта.
# ВАЖНО: не упоминать «phone/smartphone/wallpaper» — Seedream тогда рисует мокап телефона с рамкой.
WALLPAPER_SUFFIX = (
    "Tall vertical full-bleed artwork, the scene fills the entire canvas edge to edge, "
    "highly detailed, sharp focus, masterpiece quality. "
    "No device, no screen, no frame, no border, no outline, no canvas on a wall, no mockup, "
    "no split panels, no text, no letters, no signs, no watermark"
)


def theme_choices() -> list[tuple[str, str]]:
    """[(русское название, ключ)] для интерфейса."""
    return [(t["name"], k) for k, t in THEMES.items()]
