import random
import unittest
from datetime import date

from django.test import Client, SimpleTestCase
from django.urls import reverse

from .parser import DateInputError, _month_lexicon, parse_date


class CalendarMathTests(unittest.TestCase):
    def test_known_dates(self):
        cases = [
            ("1/1/0001", 0),     # Monday
            ("14 de febrero de 2011", 0),
            ("14-3-2015", 5),    # Saturday
            ("29/2/2000", 1),
            ("1/3/1900", 3),
            ("29/2/2400", 1),
            ("31/12/9999", 4),
        ]
        for text, weekday in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_date(text).weekday_index, weekday)

    def test_many_dates_match_python_datetime(self):
        rng = random.Random(42)
        for _ in range(1000):
            year = rng.randint(1, 9999)
            month = rng.randint(1, 12)
            day = rng.randint(1, 28)
            expected = date(year, month, day).weekday()
            self.assertEqual(parse_date(f"{year:04d}-{month:02d}-{day:02d}").weekday_index, expected)

    def test_400_year_periodicity_and_enormous_year(self):
        self.assertEqual(parse_date("2000-02-29").weekday_index, parse_date("2400-02-29").weekday_index)
        self.assertEqual(parse_date("1/1/" + "1" + "0" * 5000).weekday_index, date(400, 1, 1).weekday())
        self.assertEqual(parse_date("1/1/" + "9" * 5001).weekday_index, date(399, 1, 1).weekday())

    def test_leap_rules(self):
        for text in ("29/2/1900", "29/2/2100", "29/2/2023", "31/4/2015", "29/2/0001"):
            with self.subTest(text=text), self.assertRaises(DateInputError):
                parse_date(text)
        for text in ("29/2/2000", "29/2/2400", "29/2/2024"):
            self.assertEqual(parse_date(text).month, 2)

    def test_languages_and_formats(self):
        cases = [
            ("14 de febrero de 2011", "lunes", "es"),
            ("March 14, 2015", "Saturday", "en"),
            ("14 mars 2015", "samedi", "fr"),
            ("14 marzo 2015", "sábado", "es"),
            ("14 марта 2015", "суббота", "ru"),
            ("14 de março de 2015", "sábado", "pt"),
            ("14. März 2015", "Samstag", "de"),
            ("14/3/2015", "sábado", "es"),
            ("2015年3月14日", "sábado", "es"),
            ("2015년3월14일", "sábado", "es"),
            ("١٤ مارس ٢٠١٥", "السبت", "ar"),
        ]
        for raw, name, language in cases:
            with self.subTest(raw=raw):
                result = parse_date(raw)
                self.assertEqual(result.weekday_name, name)
                self.assertEqual(result.language, language)

    def test_explicit_result_language_and_browser_fallback(self):
        self.assertEqual(parse_date("14/3/2015", language="en").weekday_name, "Saturday")
        self.assertEqual(parse_date("March 14, 2015", language="gl").weekday_name, "sábado")
        self.assertEqual(parse_date("14/3/2015", accept_language="gl-ES,es;q=0.9").weekday_name, "sábado")
        self.assertEqual(parse_date("03/14/2015", language="en_US").weekday_name, "Saturday")

    def test_numeric_order_is_controllable(self):
        self.assertEqual(parse_date("03/04/2015", order="DMY").weekday_index, date(2015, 4, 3).weekday())
        self.assertEqual(parse_date("03/04/2015", order="MDY").weekday_index, date(2015, 3, 4).weekday())
        self.assertEqual(parse_date("2015/03/14").weekday_index, date(2015, 3, 14).weekday())
        self.assertEqual(parse_date("03/04/2015", language="en_US").weekday_index, date(2015, 3, 4).weekday())
        self.assertEqual(parse_date("03/04/2015").weekday_index, date(2015, 4, 3).weekday())

    def test_two_digit_year_pivot(self):
        self.assertEqual(parse_date("14/3/15").year, "2015")
        self.assertEqual(parse_date("14/3/00").year, "2000")
        self.assertEqual(parse_date("14/3/68").year, "2068")
        self.assertEqual(parse_date("14/3/69").year, "1969")
        self.assertEqual(parse_date("0001-01-01").year, "1")

    def test_errors_are_controlled(self):
        bad = ["", " ", "garbage", "14/13/2015", "0/2/2000", "1/1/0000", "14/3/" + "9" * 10001,
               "a" * 12001, "14/3/\n2015", "2015-02-30", "1/2/2015/5"]
        for text in bad:
            with self.subTest(text=text[:40]), self.assertRaises(DateInputError):
                parse_date(text)
        with self.assertRaises(DateInputError):
            parse_date("14/3/2015", language="made-up-language")
        with self.assertRaises(DateInputError):
            parse_date("14/3/2015", order="invalid")

    def test_month_dictionary_not_empty(self):
        self.assertIn((2, "es"), _month_lexicon()["febrero"])
        self.assertIn((3, "en"), _month_lexicon()["march"])


class SiteTests(SimpleTestCase):
    def test_get_page(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Calendario infinito")

    def test_form_post_success(self):
        response = self.client.post("/", {"date": "14 de febrero de 2011", "language": "es", "order": "auto"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "lunes")
        self.assertContains(response, "2011")

    def test_form_post_validation(self):
        response = self.client.post("/", {"date": "31/2/2015", "language": "es", "order": "DMY"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No se pudo interpretar")

    def test_form_escapes_html(self):
        response = self.client.post("/", {"date": "<script>alert(1)</script>", "language": "es"})
        self.assertNotContains(response, "<script>alert(1)</script>", html=False)
        self.assertContains(response, "&lt;script&gt;")

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post("/", {"date": "14/3/2015"}).status_code, 403)

    def test_only_get_and_post(self):
        self.assertEqual(self.client.put("/").status_code, 405)
