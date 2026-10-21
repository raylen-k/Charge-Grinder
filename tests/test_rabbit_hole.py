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


if __name__ == "__main__":
    unittest.main()
