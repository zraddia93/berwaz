# Craft classification guide

You classify film frames from their cinematic description (the `prompt`). Read your batch file
(JSONL, one `{"id","prompt"}` per line) and write ONE JSON line per frame to your output file.

## Output format (exact keys, exact values)

```
{"id":"123","craft":{"shotSize":"medium","angle":"eye-level","lighting":"golden-hour","timeOfDay":"golden-hour","setting":"exterior","environment":"desert","movement":"static","subject":"people","mood":["warm","serene"]}}
```

## Taxonomy — use ONLY these values

| field | values |
|---|---|
| shotSize | `extreme-close-up` (a hand, an eye, a detail) · `close-up` (face / single object fills frame) · `medium` (waist-up, one or two people, a product on a table) · `wide` (full figures with environment) · `extreme-wide` (landscape / establishing / aerial where people are tiny or absent) |
| angle | `eye-level` · `low` (camera below subject, looking up) · `high` (looking down) · `top-down` (straight down, overhead) · `dutch` (tilted horizon) |
| lighting | `daylight` (ordinary sun / overcast) · `golden-hour` (low warm sun) · `blue-hour` (dusk/dawn cool ambient) · `night` (dark exterior night, moon/ambient) · `low-key` (dark, high-contrast, chiaroscuro, single source — interior or exterior) · `high-key` (bright, even, minimal shadows) · `silhouette` (subject backlit into black) · `practical` (visible in-frame lamps, neon, screens, torches, fire as the main source) · `studio` (controlled soft studio / product lighting, seamless backgrounds) |
| timeOfDay | `day` · `golden-hour` · `dusk-dawn` · `night` · `n-a` (interior with no time cue, abstract, title card) |
| setting | `interior` · `exterior` · `n-a` (abstract / graphic / title card) |
| environment | `desert` (dunes, sand, rocky wadi) · `urban` (streets, skyline, malls, modern city) · `coastal` (sea, beach, boats, corniche) · `heritage` (mud-brick, Diriyah, forts, old souq, traditional tents, historical period) · `domestic` (home interiors: majlis, kitchen, bedroom, living room) · `office` (corporate, boardroom, call centre, bank) · `studio` (seamless/set-piece studio, product table, abstract set) · `sports` (stadium, pitch, court, gym, race) · `vehicle` (inside/around cars, trucks, planes as the main space) · `nature` (palm groves, farms, mountains, greenery, water not coastal) · `abstract` (logo cards, pure graphics, black frames, transitions) |
| movement | `static` · `handheld` (shaky, documentary energy) · `tracking` (dolly, steadicam, push-in, follow) · `aerial` (drone / bird's-eye sweep) · `unknown` (description gives no motion cue — most frames) |
| subject | `people` (1–3 people) · `crowd` (many) · `product` (packaging, food, phone, car-as-product hero shot) · `landscape` · `architecture` · `vehicle` (car/boat/plane in action) · `animal` (camel, horse, falcon…) · `graphic` (title card, logo, text-only, abstract) |
| mood | 1–2 of: `dramatic` · `warm` · `playful` · `tense` · `serene` · `epic` · `intimate` · `melancholic` · `energetic` · `nostalgic` · `mysterious` |

## Judgement rules
- Choose the single best value; do not invent values. `n-a` / `unknown` only where the table offers it.
- "medium shot" / "medium close-up" → `medium`. "extreme close-up" / "macro" → `extreme-close-up`. "over-the-shoulder" is usually `medium`.
- Firelight, torches, neon, lamps, screens as the key source → `practical`; if the description stresses darkness and contrast more than the source → `low-key`.
- "silhouette" in the description → `silhouette` (even at golden hour).
- Night exterior with practicals: lighting `practical`, timeOfDay `night`.
- Period Diriyah / Founding Day battle or caravan scenes → environment `heritage`.
- Camera movement words: "tracking", "dolly", "push-in", "steadicam", "follows" → `tracking`; "handheld", "shaky" → `handheld`; "aerial", "drone", "bird's-eye" → `aerial`. If none → `unknown`.
- Black / near-black frame, title card, logo end-card → shotSize `wide`, angle `eye-level`, lighting `low-key`, timeOfDay `n-a`, setting `n-a`, environment `abstract`, subject `graphic`, mood `["mysterious"]`.

## Process
Work through the batch in order. Append results with a Bash heredoc in chunks of ~30 lines. When done, verify with `wc -l` that your output line count equals your input line count, and that every line parses as JSON. Report the count.
