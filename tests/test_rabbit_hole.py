"""Tests for the Rabbit Hole strategy logic (no game window needed).

Run from the repository root:  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import source.rabbit_hole as rh
from source.utils.paths import PACKS, HARD_FLOORS, FLOORS


def make_params(hard=False, **kw):
    base = dict(
        RABBIT_HOLE=True, HARD=hard, BASE_HARD=hard, LVL=1, BUFF=[1, 1, 1, 1, 0, 0, 0, 0, 0, 0],
        SELECTED=["YISANG", "FAUST", "DONQUIXOTE"],
        GIFTS=[{"checks": ["Burn", "smallBurn", (315, 370), "reBurn", "bigBurn", 0]}], GIFT_SEARCH=None,
        PICK={f"floor{i}": ["TheOutcast"] for i in range(1, 6)},
        PICK_ALL={f"floor{i}": ["TheOutcast", "AutomatedFactory"] for i in range(1, 6)},
        IGNORE={f"floor{i}": ["HellsChicken", "TheUnloving"] for i in range(1, 6)},
    )
    base.update(kw)
    return SimpleNamespace(**base)


class RouteTests(unittest.TestCase):
    def test_route_is_valid_for_both_modes(self):
        rh.validate_route()

    def test_mdh_differs_only_on_floor_3(self):
        mdn, mdh = rh.route(False), rh.route(True)
        self.assertEqual(mdn[3], "TobeCleaved")
        self.assertEqual(mdh[3], "SEA")
        self.assertEqual({f for f in mdn if mdn[f] != mdh[f]}, {3})

    def test_each_floor_pack_is_offered_on_that_floor(self):
        for hard in (False, True):
            for floor, pack in rh.route(hard).items():
                on_hard = hard or floor >= rh.HARD_CONVERSION_FLOOR
                table = HARD_FLOORS if on_hard else FLOORS
                self.assertIn(pack, table[floor], f"{pack} floor {floor} hard={on_hard}")


class EgoPlanTests(unittest.TestCase):
    def casts(self, lvl, boss):
        return [t for t in (1, 2, 3, 4) if rh.wants_ego(lvl, boss, t)]

    def test_floors_1_and_2_cast_on_turn_1_only(self):
        for lvl in (1, 2):
            self.assertEqual(self.casts(lvl, False), [1])
            self.assertEqual(self.casts(lvl, True), [1])

    def test_floor_3(self):
        self.assertEqual(self.casts(3, False), [1])
        self.assertEqual(self.casts(3, True), [1, 2])

    def test_floors_4_and_5_only_on_boss_turns_1_and_2(self):
        for lvl in (4, 5):
            self.assertEqual(self.casts(lvl, False), [])
            self.assertEqual(self.casts(lvl, True), [1, 2])

    def test_no_ego_outside_the_five_floors(self):
        self.assertEqual(self.casts(6, True), [])
        self.assertEqual(self.casts(0, True), [])

    def test_heal_floors(self):
        self.assertEqual([l for l in range(1, 6) if rh.should_heal(l)], [4, 5])

    def test_slot_geometry_matches_chain(self):
        self.assertEqual(rh.ego_slot((100, 846)), (243, 990))


class DifficultyTests(unittest.TestCase):
    def test_mdn_converts_to_hard_on_floor_5_only(self):
        p = make_params(hard=False)
        for lvl in range(1, 5):
            p.LVL = lvl
            self.assertFalse(rh.convert_to_hard(p))
            self.assertFalse(p.HARD)
        p.LVL = 5
        self.assertTrue(rh.convert_to_hard(p))
        self.assertTrue(p.HARD)
        self.assertFalse(rh.convert_to_hard(p))  # already hard
        rh.reset_difficulty(p)
        self.assertFalse(p.HARD)

    def test_mdh_never_flips(self):
        p = make_params(hard=True, LVL=5)
        self.assertFalse(rh.convert_to_hard(p))
        rh.reset_difficulty(p)
        self.assertTrue(p.HARD)

    def test_disabled_does_nothing(self):
        p = make_params(hard=False, LVL=5, RABBIT_HOLE=False)
        self.assertFalse(rh.convert_to_hard(p))
        self.assertFalse(p.HARD)


class ConfigureTests(unittest.TestCase):
    def test_faust_solo_and_route_priority(self):
        p = make_params()
        rh.configure(p)
        self.assertEqual(p.SELECTED, ["FAUST"])
        for floor, pack in rh.route(False).items():
            self.assertEqual(p.PICK[f"floor{floor}"], [pack])
            self.assertEqual(p.PICK_ALL[f"floor{floor}"][0], pack)

    def test_user_lists_stay_as_fallback_and_route_pack_is_never_ignored(self):
        p = make_params()
        rh.configure(p)
        self.assertIn("TheOutcast", p.PICK_ALL["floor1"])
        self.assertNotIn("HellsChicken", p.IGNORE["floor2"])
        self.assertIn("TheUnloving", p.IGNORE["floor2"])
        self.assertEqual(len(p.PICK_ALL["floor1"]), len(set(p.PICK_ALL["floor1"])))

    def test_mdh_route_is_used_for_hard_runs(self):
        p = make_params(hard=True)
        rh.configure(p)
        self.assertEqual(p.PICK["floor3"], ["SEA"])

    def test_grace_recommendations(self):
        self.assertEqual(rh.missing_graces([1, 0, 1, 0] + [0] * 6, hard=False), [])
        self.assertEqual(rh.missing_graces([1, 0, 1, 0] + [0] * 6, hard=True), [4])
        self.assertEqual(rh.missing_graces([0] * 10, hard=True), [1, 3, 4])

    def test_incompatible_modes_disable_it(self):
        self.assertTrue(rh.is_enabled(True))
        self.assertFalse(rh.is_enabled(False))
        self.assertFalse(rh.is_enabled(True, hos_mode=True))
        self.assertFalse(rh.is_enabled(True, extreme=True))

    def test_every_route_pack_is_a_known_pack(self):
        for hard in (False, True):
            for pack in rh.route(hard).values():
                self.assertIn(pack, PACKS)


def fake_paths(*extra):
    """Icons that ship with the bot + the ones a user would add."""
    from source.utils.paths import PTH
    return {**PTH, **{name: f"{name}.png" for name in extra}}


class GiftTests(unittest.TestCase):
    ALL = ("fragmentofconceit", "fragmentofdecay", "tornbandolier", "puncturedmemory", "sharpneedlethread")

    def test_fusing_floors(self):
        self.assertEqual([l for l in range(1, 6) if rh.should_fuse(l, False)], [3, 4])
        self.assertEqual([l for l in range(1, 6) if rh.should_fuse(l, True)], [2, 3, 4])

    def test_without_new_icons_only_shipped_gifts_are_used(self):
        tables = rh.gift_tables(False, fake_paths())
        self.assertEqual([t["checks"][0] for t in tables], ["Poise", "Sinking"])
        self.assertEqual(list(tables[0]["uptie2"]), ["clearmirror"])
        self.assertEqual(list(tables[1]["uptie2"]), ["artisticsense"])
        self.assertEqual(tables[0]["uptie1"], {})

    def test_full_mdn_tables(self):
        poise, sinking = rh.gift_tables(False, fake_paths(*self.ALL))
        self.assertEqual(list(poise["uptie2"]), ["fragmentofconceit", "clearmirror"])  # Conceit is fused first
        self.assertEqual(poise["fuse_ex"], {"clearmirror": 4})
        self.assertEqual(poise["uptie1"], {"tornbandolier": 2})
        self.assertEqual(poise["skip_uptie"], ("fragmentofconceit",))
        self.assertEqual(list(sinking["uptie2"]), ["fragmentofdecay", "artisticsense"])
        self.assertEqual(sinking["skip_uptie"], ("fragmentofdecay",))
        for t in (poise, sinking):
            self.assertEqual((t["goal"], t["fuse2"], t["fuse4"], t["sin"]), ([], {}, {}, True))

    def test_full_mdh_adds_pierce_and_skips_bandolier_upgrade(self):
        poise, sinking, pierce = rh.gift_tables(True, fake_paths(*self.ALL))
        self.assertEqual(poise["uptie1"], {})
        self.assertEqual(pierce["checks"][0], "Pierce")
        self.assertEqual(list(pierce["uptie2"]), ["puncturedmemory"])
        self.assertEqual(pierce["skip_uptie"], ("puncturedmemory",))

    def test_pierce_dropped_until_its_icon_exists(self):
        self.assertEqual(len(rh.gift_tables(True, fake_paths())), 2)
        self.assertEqual(len(rh.gift_tables(True, fake_paths("puncturedmemory"))), 3)

    def test_every_listed_gift_has_an_icon_when_present(self):
        for hard in (False, True):
            for t in rh.gift_tables(hard, fake_paths(*self.ALL)):
                for key in ("buy", "all"):
                    for name in t[key]:
                        self.assertIn(name, fake_paths(*self.ALL), name)

    def test_strategy_gifts_are_protected_from_fusing(self):
        poise = rh.gift_tables(False, fake_paths(*self.ALL))[0]
        for name in ("grandwelcome", "sharpneedlethread", "holder", "stonetomb"):
            self.assertIn(name, poise["all"])
        self.assertNotIn("grandwelcome", poise["buy"])  # we only protect it, never buy duplicates

    def test_base_team_tables_are_not_mutated(self):
        from source.teams import TEAMS
        before = repr(TEAMS["POISE"])
        rh.gift_tables(False, fake_paths(*self.ALL))
        self.assertEqual(repr(TEAMS["POISE"]), before)

    def test_missing_icon_report(self):
        self.assertEqual(rh.missing_gift_icons(fake_paths(*self.ALL)), [])
        self.assertIn("puncturedmemory", rh.missing_gift_icons(fake_paths(), hard=True))
        self.assertNotIn("puncturedmemory", rh.missing_gift_icons(fake_paths(), hard=False))

    def test_configure_swaps_gifts_but_keeps_the_gift_search_keyword(self):
        p = make_params()
        original = p.GIFTS[0]
        rh.configure(p)
        self.assertIs(p.GIFT_SEARCH, original)
        self.assertEqual(p.GIFTS[0]["checks"][0], "Poise")


if __name__ == "__main__":
    unittest.main()
