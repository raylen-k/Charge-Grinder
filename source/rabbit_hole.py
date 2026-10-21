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
  * Floors 1-3: Overclock Hollow Faust's EGO (press and hold it) on turn 1 of every fight.
  * Floors 4-5: Awaken it (plain click) on turn 1 AND turn 2 of the boss fight (King of Despair / Sign of Roses).
  * Floors 4-5 shop: heal Faust to 45 SP so she does not corrode.
  * Recommended graces: 1 3 (+ 4 on full MDH) and two Gift Searches.

Gifts: the bot's fuse/buy engine chases one target T4 gift per keyword (Poise: Fragment of Conceit and
  Clear Mirror, Calm Water; Sinking: Fragment of Decay and Artistic Sense; Hard also Pierce: Punctured Memory)
  and upgrades only the ones the guide upgrades. Each gift is only handled if its icon exists (GIFT_ICONS).

Not automated (needs game knowledge the bot cannot read from the screen):
  the shop's free refresh, extra sinners as meatshields on the Hard Floor 4 boss / Faelantern, healing a
  "Skill Checker" on floor 1, the two Gift Searches, and retrying a failed Floor 4 boss turn-2 kill.
"""
import logging
from copy import deepcopy

from source.teams import TEAMS, HARD as HARD_TEAMS
from source.utils.paths import PACKS, PTH

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

# Existing icons the strategy's gifts are known by (files under ImageAssets/UI/teams/<Keyword>/gifts/)
CONCEIT = "stone5"         # Fragment of Conceit (Poise, T4): fuse target, not upgraded
DECAY = "stone4"           # Fragment of Decay (Sinking, T4): fuse target, not upgraded
PUNCTURED = "piercememory" # Punctured Memory (Pierce, T4): Hard floor 4 fuse target, not upgraded

# Icons that do not ship with the bot yet: add a cropped inventory icon named <name>.png anywhere under
# ImageAssets/UI (names must be unique). Gifts without an icon are simply skipped.
GIFT_ICONS = {
    "tornbandolier":      "Torn Bandolier (Pierce, T2)",        # MDN starting gift, upgraded on floor 1
    "sharpneedlethread":  "Sharp Needle & Thread (T3)",         # only protected from fusing/selling
}
HARD_ONLY_ICONS = set()
FUSE_FLOORS = (3, 4)           # floors where the strategy fuses; Hard also fuses on floor 2


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


OVERCLOCK_HOLD = 1.5   # seconds the EGO is held to Overclock it (same hold the bot uses to open the EGO panel)


def ego_kind(lvl):
    """Floors 1-3 Overclock Hollow Faust (hold), floors 4-5 Awaken her (plain click)."""
    return "overclock" if lvl <= 3 else "awakening"


def should_heal(lvl):
    return lvl in HEAL_FLOORS


def ego_slot(gear_start):
    """Click point of Faust's first skill slot (same geometry chain() uses for slot 0)."""
    return int(gear_start[0] + 143), int(gear_start[1] + 144)


def missing_graces(buff, hard):
    """Recommended grace numbers (1-based) that are not enabled in the BUFF list."""
    return [g for g in GRACES[bool(hard)] if not (len(buff) >= g and buff[g - 1])]


def missing_gift_icons(paths, hard=False):
    return [name for name in GIFT_ICONS
            if name not in paths and (hard or name not in HARD_ONLY_ICONS)]


def should_fuse(lvl, hard):
    """Shops where fusing is worth the time. The guide postpones it on the early floors."""
    return lvl in FUSE_FLOORS or (hard and lvl == 2)


def gift_tables(hard, paths=PTH):
    """Gift tables (same shape as source/teams.py entries) for the Rabbit Hole build.

    The bot's engine fuses a random T4 of a keyword until the first `uptie2` gift shows up, then
    keeps fusing for every `fuse_ex` gift. Order here = Conceit, Decay, [Punctured Memory], then
    Clear Mirror and Artistic Sense (the ones that get upgraded). Gifts whose icon is missing are left
    out; a keyword whose target gift can't be recognised is dropped entirely, otherwise the bot
    would fuse forever.
    """
    src = HARD_TEAMS if hard else TEAMS

    def table(keyword, first, upgraded, protect=(), buy=None, uptie1=None):
        names = [n for n in first + upgraded if n in paths]
        if not names:
            return None
        t = deepcopy(src[keyword])
        targets = [n for n in first if n in paths]
        up = [n for n in upgraded if n in paths]
        t.update(
            floors=[],
            uptie1={n: 2 for n in (uptie1 or []) if n in paths},
            uptie2={n: 4 for n in targets + up},        # first key = what the engine fuses for first
            uptie3={},
            goal=[], fuse1={}, fuse2={}, fuse3={}, fuse4={},   # no recipe fusing
            fuse_ex={n: 4 for n in up},
            skip_uptie=tuple(targets),                    # guide: Fragments/Punctured Memory stay "IV -"
            buy=[n for n in (buy if buy is not None else names) if n in paths],
            all=[n for n in list(protect) + names if n in paths],
            sin=True,
        )
        return t

    tables = [
        table("POISE", [CONCEIT], ["clearmirror"],
              protect=["holder", "stonetomb", "tornbandolier", "grandwelcome", "sharpneedlethread"],
              buy=[CONCEIT, "clearmirror"],
              uptie1=[] if hard else ["tornbandolier"]),
        table("SINKING", [DECAY], ["artisticsense"]),
    ]
    if hard:
        tables.append(table("PIERCE", [PUNCTURED], []))
    return [t for t in tables if t]


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
    params.GIFT_SEARCH = params.GIFTS[0]        # the start-of-run gift search keeps using the team's keyword
    if (tables := gift_tables(params.BASE_HARD)):
        params.GIFTS = tables
    if (missing := missing_gift_icons(PTH, params.BASE_HARD)):
        logging.warning(f"Rabbit Hole gift icons not found (those gifts are skipped and may get fused/sold): {missing}")
    params.PICK, params.PICK_ALL, params.IGNORE = pack_tables(params.BASE_HARD, params.PICK_ALL, params.IGNORE)

    mode = "MDH" if params.BASE_HARD else "MDN+RR"
    logging.info(f"Rabbit Hole ({mode}): {route(params.BASE_HARD)}")
    if (missing := missing_graces(params.BUFF, params.BASE_HARD)):
        logging.warning(f"Rabbit Hole recommends graces {GRACES[bool(params.BASE_HARD)]}, missing: {missing}")
