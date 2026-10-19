import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from textnorm import tokens  # noqa: E402
from vocab import Vocab, match_terms, slugify  # noqa: E402
import extract  # noqa: E402


def skills_in(vocab, text):
    return {vocab.term_skill[t] for t in match_terms(tokens(text), vocab.grams)}


class MatchingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = Vocab()

    def test_vocabulary_loads_without_duplicates(self):
        self.assertGreater(len(self.v.skills), 300)
        self.assertEqual(len({s["id"] for s in self.v.skills}), len(self.v.skills))

    def test_special_programming_forms(self):
        found = skills_in(self.v, "Erfarenhet av C#, C++ och .NET samt Python/Django.")
        self.assertTrue({"csharp", "c-cplusplus", "dotnet", "python"} <= found)

    def test_hyphenated_and_inflected_terms(self):
        found = skills_in(self.v, "B-körkort krävs och truckkortet A1 är meriterande.")
        self.assertIn("b-korkort", found)
        self.assertIn("truckkort", found)

    def test_common_words_do_not_match(self):
        self.assertEqual(skills_in(self.v, "Mig och dig. No problem, it is safe for teams."), set())

    def test_four_word_terms(self):
        self.assertIn("palliativ-vard", skills_in(self.v, "Vi arbetar med vård i livets slut."))

    def test_slugify(self):
        self.assertEqual(slugify("Utdrag ur belastningsregistret"), "utdrag-ur-belastningsregistret")
        self.assertEqual(slugify("C#"), "csharp")


class FactTest(unittest.TestCase):
    def test_fact_handles_old_and_new_formats(self):
        v = Vocab()
        tid = {t: i for i, t in enumerate(v.term_skill)}
        old = {"id": None, "publication_date": "2016-10-21", "headline": "Tandsköterska",
               "occupation": {"concept_id": None, "legacy_ams_taxonomy_id": "5724"},
               "occupation_group": {"concept_id": None},
               "workplace_address": {"municipality_code": "0180"},
               "employer": {"name": "Tandläkarna AB"}, "number_of_vacancies": "1",
               "description": {"text": "B-körkort krävs."}}
        new = {"id": 123456789, "publication_date": "2024-12-31T00:01:33", "headline": "Säljare",
               "occupation": [{"concept_id": "2YDV_mGq_LpN"}], "occupation_group": [{"concept_id": "iWcY_mko_rq2"}],
               "workplace_address": {"municipality_code": "0180", "postcode": "111 22"},
               "employer": {"organization_number": "5565595450", "name": "AB"},
               "working_hours_type": {"label": "Heltid"}, "experience_required": True,
               "description": {"text": "Engelska"}}
        f_old = extract.fact(old, v.grams, tid)
        f_new = extract.fact(new, v.grams, tid)
        self.assertTrue(f_old[0].startswith("h"))
        self.assertEqual(f_old[2], "L5724")
        self.assertEqual(f_old[13], 1)
        self.assertEqual(f_new[0], "123456789")
        self.assertEqual(f_new[3], "iWcY_mko_rq2")
        self.assertEqual(f_new[5], "11122")
        self.assertEqual(f_new[9], "H")
        self.assertEqual(f_new[11], 1)
        self.assertEqual(len(f_new), len(extract.COLUMNS))


if __name__ == "__main__":
    unittest.main()
