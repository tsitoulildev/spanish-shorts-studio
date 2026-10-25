"""Scene catalogue. Every clip and recording is CC0 / public domain on Wikimedia Commons (licence checked via the Commons API,
2026-10-25) and shipped in assets/ (clips are trimmed to 30 s, audio to <= 400 s). Audio: (source, gain, loop fade seconds);
'synth:x' = generated. Clips were chosen by looking at them; see assets/SOURCES.md."""
C = "repo:clips/"
A = "repo:audio/"
THEMES = {
    "rain": {"video": ["repo:video/rain_window_night.webm"],
             "audio": [(A + "rain1.ogg", 1.0, 4), (A + "rain_veranda.ogg", 0.5, 3)]},
    "storm": {"video": ["repo:video/lightning_storm.ogv"],
              "audio": [(A + "thunder1.ogg", 1.0, 4), (A + "thunder3.ogg", 0.7, 4), (A + "rain1.ogg", 0.6, 4)]},
    "ocean": {"video": [C + n for n in ("ocean__Ocean_surface_waves_03.mp4", "ocean__Ocean_surface_waves_05.mp4", "ocean__Ocean_surface_waves.mp4",
                                        "ocean__Ocean_surface_waves_02.mp4", "ocean__Ocean_surface_waves_04.mp4")],
              "audio": [(A + "ocean_tropical.ogg", 1.0, 5), (A + "pebble_beach.ogg", 0.4, 4)]},
    "river": {"video": [C + n for n in ("river__Klamath_River_28205908032.mp4", "river__Sixes_River_33895113543.mp4", "river__Wallowa_River_35001236162.mp4",
                                        "river__White_Wild_and_Scenic_River_30126165673.mp4", "river__Running_Stream_Of_Water.mp4",
                                        "river__Delaneys_Falls.mp4", "forest__Little_Applegate_River_50982975823.mp4")],
              "audio": [(A + "shallow_river.ogg", 1.0, 3), (A + "swale.ogg", 0.6, 4), (A + "stream_close.ogg", 0.5, 4)]},
    "snow": {"video": [C + n for n in ("snow__Snow_falling_in_Charlton_MA_2025_12_14.mp4", "snow__KLO_Creek_gurgles_during_an_early_winter_snowfall.mp4",
                                       "snow__Aerial_view_of_Lake_Okanagan_snowfall_near_Bertram_Creek.mp4", "snow__Aerial_View_of_freezing_fog_in_the_Okanagan_Highlands.mp4")],
             "audio": [("synth:wind", 1.0, 0)]},
    "autumn": {"video": [C + "autumn__20141103Regen.mp4", C + "autumn__Overlooking_Browne_Lake_on_a_Calm_Rainy_Morning_in_Late_Autu.mp4"],
               "audio": [(A + "rain1.ogg", 1.0, 4), (A + "rain_veranda.ogg", 0.5, 3)]},
}
