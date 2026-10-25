"""Scene catalogue. Every file is CC0 / public domain on Wikimedia Commons (licence checked via the Commons API on 2026-10-25).
'repo:' = shipped in assets/, 'commons:' = downloaded at render time (cached). Audio: (source, gain, loop fade seconds); 'synth:x' = generated."""
THEMES = {
    "rain": {"video": ["repo:video/rain_window_night.webm"],
             "audio": [("repo:audio/rain1.ogg", 1.0, 4), ("repo:audio/rain_veranda.ogg", 0.5, 3)]},
    "storm": {"video": ["repo:video/lightning_storm.ogv"],
              "audio": [("commons:Thunderstorm after hot summer day 17 minutes 01 of 04.ogg", 1.0, 4),
                        ("commons:Thunderstorm after hot summer day 17 minutes 03 of 04.ogg", 0.7, 4),
                        ("repo:audio/rain1.ogg", 0.6, 4)]},
    "fire": {"video": ["repo:video/fire.webm", "commons:Fire آتش 02.ogv", "commons:Fire آتش 07.ogv", "commons:Fire آتش 08.ogv"],
             "audio": [("synth:fire", 1.0, 0)]},
    "ocean": {"video": ["commons:Ocean surface waves.ogv", "commons:Ocean surface waves 02.ogv", "commons:Ocean surface waves 04.ogv"],
              "audio": [("commons:Ocean Waves on a Tropical Beach.ogg", 1.0, 5), ("commons:On a pebble beach.ogg", 0.4, 4)]},
    "river": {"video": ["commons:Klamath River (27693694384).webm", "commons:Smith River Falls Recreation Site (33862589984).webm",
                        "commons:Running Stream Of Water.webm", "commons:White Wild and Scenic River (30645047502).webm",
                        "commons:Wallowa River (35001236162).webm", "commons:Sixes River (33895113543).webm"],
              "audio": [("commons:433589 jackthemurray stream-river-water-up-close.wav", 1.0, 4), ("commons:Swale.ogg", 0.5, 4)]},
    "snow": {"video": ["commons:Snow falling in Charlton MA 2025-12-14.webm", "commons:KLO Creek gurgles during an early winter snowfall.webm",
                       "commons:Aerial view of Lake Okanagan snowfall near Bertram Creek.webm"],
             "audio": [("synth:wind", 1.0, 0)]},
    "autumn": {"video": ["commons:20141103Regen.ogv", "commons:Overlooking Browne Lake on a Calm Rainy Morning in Late Autumn.webm"],
               "audio": [("repo:audio/rain1.ogg", 1.0, 4), ("repo:audio/rain_veranda.ogg", 0.5, 3)]},
}
