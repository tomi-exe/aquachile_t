import shutil
import tempfile

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ResultFile, Scenario
from .services import CENTERS, ROUTES, simulate_two_trucks


class ScenarioFlowTests(TestCase):
    def setUp(self):
        self._media_dir = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self._media_dir)
        self._override.enable()

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self._media_dir, ignore_errors=True)

    def test_anonymous_user_can_create_scenario_and_generates_results(self):
        payload = {
            "name": "Test Simulation",
            "route_key": "SUR",
            "days": 2,
            "Q_proc_m3h": 6.0,
            "TS_in": 0.05,
            "TS_cake": 0.25,
            "eta_captura": 0.97,
        }

        response = self.client.post(reverse("scenario_new"), payload)
        scenario = Scenario.objects.get(name="Test Simulation")

        self.assertRedirects(response, reverse("scenario_detail", args=[scenario.id]))
        files = ResultFile.objects.filter(scenario=scenario)
        self.assertEqual(files.count(), 2)
        self.assertSetEqual(set(files.values_list("kind", flat=True)), {"excel", "grafico"})

    def test_simulation_uses_route_data_and_produces_assets(self):
        kpis, df_log, df_stock, png, xlsx = simulate_two_trucks(
            days=1,
            route_key="SUR",
            Q_proc_m3h=6.0,
            TS_in=0.05,
            TS_cake=0.25,
            eta_captura=0.97,
        )

        expected_centers = [c["name"] for c in CENTERS["SUR"]]
        for center in expected_centers:
            self.assertIn(f"stock_{center}", df_stock.columns)

        self.assertEqual(kpis["Ruta"], "SUR")
        self.assertGreater(df_log["stock_total_t"].iloc[-1], 0)
        self.assertGreater(len(png.read()), 0)
        self.assertGreater(len(xlsx.read()), 0)


class RouteDataTests(TestCase):
    def test_route_segments_match_expected_dataset(self):
        expected_norte = [
            {"from": "Puerto Varas", "to": "Curarrehue", "km": 357.00, "hours": 4.17},
            {"from": "Curarrehue", "to": "Catripulli", "km": 13.43, "hours": 0.22},
            {"from": "Catripulli", "to": "Melipeuco", "km": 175.00, "hours": 2.48},
            {"from": "Melipeuco", "to": "Caburga 2", "km": 170.00, "hours": 2.47},
            {"from": "Caburga 2", "to": "Codihue", "km": 116.00, "hours": 0.78},
        ]

        expected_sur = [
            {"from": "Puerto Varas", "to": "Hornopirén", "km": 126.00, "hours": 2.43},
            {"from": "Hornopirén", "to": "Pargua", "km": 167.00, "hours": 2.83},
            {"from": "Pargua", "to": "Reloncaví", "km": 43.96, "hours": 0.73},
            {"from": "Reloncaví", "to": "Centro Innovación ATC", "km": 11.87, "hours": 0.20},
            {"from": "Centro Innovación ATC", "to": "Agua Buena", "km": 80.30, "hours": 1.34},
            {"from": "Agua Buena", "to": "Aucar", "km": 61.47, "hours": 1.02},
        ]

        self.assertEqual(ROUTES["NORTE"], expected_norte)
        self.assertEqual(ROUTES["SUR"], expected_sur)

    def test_route_totals_are_consistent_with_segments(self):
        def totals(route):
            return round(sum(r["km"] for r in route), 2), round(sum(r["hours"] for r in route), 2)

        norte_km, norte_hours = totals(ROUTES["NORTE"])
        sur_km, sur_hours = totals(ROUTES["SUR"])

        self.assertEqual(norte_km, 831.43)
        self.assertEqual(norte_hours, 10.12)
        self.assertEqual(sur_km, 490.6)
        self.assertEqual(sur_hours, 8.55)
