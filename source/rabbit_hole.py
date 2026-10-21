"""
Rabbit Hole [兔子洞] farming strategy.

Source: "MD Crates Farming Guide - UPDATED RABBIT HOLE" (strategy by the guide authors,
special thanks to @Cabric). Everything that is pure data/decision logic lives here so
it can be tested without a game window; the bot modules only call into these helpers.

Summary of the strategy (MDN+RR route, Hard MD differences in brackets):
  * Field Faust solo (Hollow Faust EGO is the only EGO equipped), rotate everyone else.
  * Pack route: Flatbroke Gamblers -> Hell's Chicken -> To Be Cleaved [S.E.A.]
                -> Hatred and Despair -> Line 2.
  * MDN+RR starts on Normal and converts to Hard on floor 5; full MDH is Hard from floor 1.
  * Floors 1-3: cast Hollow Faust's EGO on turn 1 of every fight (everything dies in one turn).
  * Floors 4-5: cast it on turn 1 AND turn 2 of the boss fight (King of Despair / Sign of Roses).
  * Floors 4-5 shop: heal Faust to 45 SP so she does not corrode.
  * Recommended graces: 1 3 (+ 4 on full MDH) and two Gift Searches.

Not automated (needs game knowledge the bot cannot read from the screen):
  fusing/buying the strategy-specific gifts (see GIFT_ICONS), extra sinners as meatshields on
  the Hard Floor 4 boss / Faelantern, healing a "Skill Checker" on floor 1, and retrying a failed
  Floor 4 boss turn-2 kill.
"""
import logging

from source.utils.paths import PACKS

# Pack names as they appear in source/utils/paths.py (PACKS)
ROUTE_MDN = {
    1: "FlatbrokeGamblers",
    2: "HellsChicken",
    3: "TobeCleaved",
    4: "HatredandDespair",
    5: "Line2",
}
ROUTE_MDH = {**ROUTE_MDN, 3: "SEA"}

HARD_CONVERSION_FLOOR = 5      # MDN+RR converts the run to Hard here
SOLO = ["FAUST"]
GRACES = {False: (1, 3), True: (1, 3, 4)}   # 1-based grace numbers, keyed by "is Hard MD"
HEAL_FLOORS = (4, 5)           # heal Faust to 45 SP in these shops
FLOORS = range(1, 6)

# Icons the strategy-specific gift handling would need (none of them ship with the bot yet).
# Drop a cropped screenshot with this name anywhere under ImageAssets/UI to make it available
# to future gift logic. See missing_gift_icons().
GIFT_ICONS = [
    "tornbandolier", "fragmentofconceit", "fragmentofdecay", "sinkingrock",
    "sharpneedlethread", "puncturedmemory", "fragmentoffriction",
]


def route(hard):
    """Floor -> pack name for the base difficulty of the run."""
    return dict(ROUTE_MDH if hard else ROUTE_MDN)


def validate_route():
    """Raise if a route pack is unknown or cannot be offered on its floor."""
    for hard in (False, True):
        for floor, pack in route(hard).items():
            if pack not in PACKS:
                raise ValueError(f"Unknown pack {pack!r}")
            # floor 5 of the MDN+RR route is played on Hard after the conversion
            on_hard = hard or floor >= HARD_CONVERSION_FLOOR
            if floor not in PACKS[pack][int(on_hard)]:
                raise ValueError(f"{pack} is not offered on floor {floor} ({'hard' if on_hard else 'normal'})")


def convert_to_hard(params):
    """MDN+RR: switch the run to Hard on floor 5. Returns True if the switch happened now."""
    if params.RABBIT_HOLE and not params.HARD and params.LVL >= HARD_CONVERSION_FLOOR:
        params.HARD = True
        return True
    return False


def reset_difficulty(params):
    """Undo convert_to_hard() before a new run starts."""
    params.HARD = params.BASE_HARD


def wants_ego(lvl, is_boss, turn):
    """Should Hollow Faust's EGO be cast on this planning turn (1-based)?"""
    if lvl in (1, 2):
        return turn == 1
    if lvl == 3:
        # Fairy-Long-Legs / Alleyway Watchdog die on turn 1; Faelantern needs a second cast
        return turn == 1 or (is_boss and turn == 2)
    if lvl in (4, 5):
        return is_boss and turn in (1, 2)
    return False


def should_heal(lvl):
    return lvl in HEAL_FLOORS


def ego_slot(gear_start):
    """Click point of Faust's first skill slot (same geometry chain() uses for slot 0)."""
    return int(gear_start[0] + 143), int(gear_start[1] + 144)


def missing_graces(buff, hard):
    """Recommended grace numbers (1-based) that are not enabled in the BUFF list."""
    return [g for g in GRACES[bool(hard)] if not (len(buff) >= g and buff[g - 1])]


def missing_gift_icons(paths):
    return [name for name in GIFT_ICONS if name not in paths]


def pack_tables(hard, user_pick_all=None, user_ignore=None):
    """Build p.PICK / p.PICK_ALL / p.IGNORE style dicts that force the Rabbit Hole route.

    The user's own priority/avoid lists are kept as the fallback when the route pack is not
    offered on the last refresh.
    """
    user_pick_all = user_pick_all or {}
    user_ignore = user_ignore or {}
    path = route(hard)
    pick, pick_all, ignore = {}, {}, {}
    for floor in FLOORS:
        key = f"floor{floor}"
        pack = path[floor]
        pick[key] = [pack]
        pick_all[key] = [pack] + [x for x in user_pick_all.get(key, []) if x != pack]
        ignore[key] = [x for x in user_ignore.get(key, []) if x != pack]
    return pick, pick_all, ignore


def is_enabled(requested, hos_mode=False, extreme=False):
    """Rabbit Hole only exists for Normal/Hard MD6 and can't be combined with other modes."""
    if not requested:
        return False
    if hos_mode or extreme:
        logging.warning("Rabbit Hole is not compatible with Arayashu/Extreme MD, ignoring it")
        return False
    return True


def configure(params):
    """Apply the strategy to the bot parameters. Call after the team has been loaded."""
    params.SELECTED = list(SOLO)
    params.HARD = params.BASE_HARD
    params.PICK, params.PICK_ALL, params.IGNORE = pack_tables(params.BASE_HARD, params.PICK_ALL, params.IGNORE)

    mode = "MDH" if params.BASE_HARD else "MDN+RR"
    logging.info(f"Rabbit Hole ({mode}): {route(params.BASE_HARD)}")
    if (missing := missing_graces(params.BUFF, params.BASE_HARD)):
        logging.warning(f"Rabbit Hole recommends graces {GRACES[bool(params.BASE_HARD)]}, missing: {missing}")
