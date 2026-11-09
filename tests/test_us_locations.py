import unittest
from scraper.us_locations import USLocations


class USLocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classifier = USLocations()

    def test_us_locations(self):
        for text in ["United States", "US", "USA", "U.S. Remote", "Remote - United States", "US-CA",
            "San Francisco", "New York", "New York City", "New York, NY", "San Francisco, CA",
            "New York, New York, United States", "Boston, MA", "Seattle, WA", "Vancouver, WA",
            "Paris, TX", "Remote - New Mexico", "Atlanta, Georgia", "California", "Austin TX",
            "San Francisco, CA • New York, NY • United States", "Washington, D.C.", "Arlington, VA or Remote",
            "San Francisco Bay Area, CA", "Ontario, CA", "US - AR", "Starbase, TX", "Remote, TX", "USA_Remote"]:
            with self.subTest(text=text):
                self.assertTrue(self.classifier.match(text)[0], (text,self.classifier.match(text)))

    def test_non_us_and_ambiguous_locations(self):
        for text in ["", "Remote", "Anywhere", "Worldwide", "Canada", "Toronto, Ontario", "Toronto, CA",
            "London", "Paris", "Berlin", "Cambridge", "Perth, WA", "India", "Bangalore, India",
            "San Francisco, Philippines", "San Francisco, PH", "California, Colombia", "Georgia", "Tbilisi, Georgia",
            "Remote - Non-US", "Remote - US timezones", "Remote - North America", "Remote (US | Canada)",
            "United States / Canada", "San Francisco / London", "San Francisco, London", "Remote - CA",
            "Los Angeles, Chile", "Baja California, Mexico", "US, Australia", "US, London", "Ontario", "Alberta", "Remote, BC", "US, uk",
            "Remote - USA, CAN, MEX", "US-AUS", "US-CAN"]:
            with self.subTest(text=text):
                self.assertFalse(self.classifier.match(text)[0], (text,self.classifier.match(text)))

    def test_source_country_evidence_enriches_city_state_pairs(self):
        classifier = USLocations(["Example Campus, California, United States", "Non-US Place, CA, Canada"])
        self.assertTrue(classifier.match("Example Campus, CA")[0])
        self.assertFalse(classifier.match("Non-US Place, CA")[0])


if __name__ == "__main__":
    unittest.main()
