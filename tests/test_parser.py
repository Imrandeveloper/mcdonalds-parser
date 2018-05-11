import os
import sys
import json
import unittest
from pyquery import PyQuery as pq

sys.path.append('..')

from utils import prepare_logs_dir

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIR_NAME = 'data'
TEST_DATA_DIR = os.path.join(CURRENT_DIR, TEST_DATA_DIR_NAME)

LOGS_DIR = 'logs'
LOGS_PATH = os.path.join(CURRENT_DIR, LOGS_DIR)

LIST_PAGE_FILENAME = 'vacancy_list.json'
LIST_PAGE_FILEPATH = os.path.join(TEST_DATA_DIR, LIST_PAGE_FILENAME)
VACANCY_PAGE_FILENAME = 'test_vacancy.html'
VACANCY_PAGE_FILEPATH = os.path.join(TEST_DATA_DIR, VACANCY_PAGE_FILENAME)

prepare_logs_dir(LOGS_PATH)


def get_test_data():
    """
    Load test data from file
    :return: json test data
    """
    if not os.path.exists(LIST_PAGE_FILEPATH):
        print("File with test data not found")
        return None
    with open(LIST_PAGE_FILEPATH) as f:
        return json.load(f)


class ParserTestCase(unittest.TestCase):
    """
    Parser tests
    """

    def setUp(self):
        from mcdonalds_parser import McDonaldsParser
        # get test data from file
        self.test_data = get_test_data()
        self.parser = McDonaldsParser()

    def test_parse_json(self):
        """
        Test 'parse_json' method
        :return: 
        """
        self.parser._parse_json(self.test_data)
        self.assertEqual(len(self.parser.vacancy_dict), 1223)
        self.assertIsNotNone(self.parser.vacancy_dict["req1655"])
        values = self.parser.vacancy_dict["req1655"]
        self.assertEqual('Restaurantbetriebe Uwe Süshardt',
                         values["location_name"])
        self.assertEqual('Petershütter Allee 4',
                         values["location_address"])
        self.assertEqual('https://karriere.mcdonalds.de'
                         '/stellenangebot/job-detail.html?jobId=req1655',
                         values["vacancy_url"])

    def test_vacancy_description(self):
        """
        Test parsing description
        :return: 
        """
        page = pq(filename=VACANCY_PAGE_FILEPATH)
        description = self.parser._get_vacancy_description(page)
        self.assertIsNotNone(description)
        self.assertNotEqual(description, "")


if __name__ == '__main__':
    unittest.main()
