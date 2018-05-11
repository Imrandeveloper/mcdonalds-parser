import os
import sys
import logging

import grequests as grq
import requests as rq
import urllib3

from datetime import datetime
from urllib import parse
from lxml import etree
from pyquery import PyQuery as pq
from fake_useragent import UserAgent

from utils import prepare_logs_dir

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

prepare_logs_dir()

logging.basicConfig(filename='logs/parser.log', level=logging.INFO,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%d-%m-%y %H:%M')


def progress(count, total, status=''):
    """
    Console progress bar
    """
    bar_len = 50
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    sys.stdout.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    sys.stdout.flush()


class McDonaldsParser:
    """
    McDonald's Parser
    """
    # Url of api to get vacancy list
    DEFAULT_URL = 'https://karriere.mcdonalds.de/ajax/careermap/vicinitySearch'
    CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
    # Config path for xml export
    OUTPUT_DIR = 'parsed_xml'
    OUTPUT_FILENAME = 'vacancies.xml'
    DIR_TO_EXPORT = os.path.join(CURRENT_DIR, OUTPUT_DIR)
    # the maximum number of responses stored in memory
    MAX_ID = 100
    # the maximum number of requests sent at one time
    WORKERS_NUM = 30
    # the maximum number of attempts to obtain a response,
    # in case the server responded with an error
    ATTEMPTS_COUNT = 3
    # Base url to get vacancy
    BASE_VACANCY_URL = 'https://karriere.mcdonalds.de/stellenangebot/' \
                       'job-detail.html?jobId='

    # Set of locations covering all Germany
    DEFAULT_LOCATIONS_REST = [
        {'latitude': '53.61334884173276', 'longitude': '12.681224089435432',
         'radius': '130'},
        {'latitude': '54.485599338054136', 'longitude': '9.828327753454914',
         'radius': '95'},
        {'latitude': '53.13647603266737', 'longitude': '8.246296503454914',
         'radius': '94'},
        {'latitude': '53.53010766171482', 'longitude': '10.090071086695389',
         'radius': '53'},
        {'latitude': '51.70278145409504', 'longitude': '13.495832805445389',
         'radius': '135'},
        {'latitude': '52.109459921009105', 'longitude': '10.299648551076302',
         'radius': '134'},
        {'latitude': '50.15182910444893', 'longitude': '11.508144644826302',
         'radius': '124'},
        {'latitude': '48.72313505927419', 'longitude': '12.804531363576302',
         'radius': '76'},
        {'latitude': '47.752907406324944', 'longitude': '12.672695426076302',
         'radius': '46'},
        {'latitude': ' 48.267390358256925', 'longitude': '10.958828238576302',
         'radius': '118'},
        {'latitude': '48.1649043023955', 'longitude': '8.695644644826302',
         'radius': '103'},
        {'latitude': '50.217961529121105', 'longitude': '7.904629019826302',
         'radius': '141'},
        {'latitude': '52.081707263566685', 'longitude': '7.306014569931449',
         'radius': '75'},
        {'latitude': '51.31911917737777', 'longitude': '6.163436444931449',
         'radius': '76'},
        {'latitude': '51.55197830773196', 'longitude': '8.294784101181449',
         'radius': '41'},
        {'latitude': '50.80189961582029', 'longitude': '9.790254110352407',
         'radius': '37'},
        {'latitude': '49.36234044436509', 'longitude': '9.55472632888086',
         'radius': '65'}
    ]

    # Work types from site select
    DEFAULT_TYPES_REST = [
        'INT_REST_EMP',
        'MINIJOB',
        'INT_REST_MGMT',
        'INT_REST_DSTD',
        'INT_REST_AZB'
    ]

    # Main location for administrative vacancies
    DEFAULT_LOCATION_ADM = {'latitude': '50.664954',
                            'longitude': '10.96041', 'radius': '350'}

    # Work types for administrative vacancies
    DEFAULT_TYPES_ADM = [
        'INT_VW_BE',
        'INT_VW_AZDS',
        'INT_VW_PRWS',
    ]

    # Types of work depending on time
    JOBS_KIND = {
        'Vollzeit': 'FULL_TIME',
        'Teilzeit': 'PART_TIME',
        '€450-Minijob': 'MINI_JOB'
    }

    UA_SUFFIX = 'JobUFO GmbH'

    def __init__(self):
        """
        Init class
        """
        self.user_agent = UserAgent()
        self.vacancy_dict = {}

    @property
    def _request_settings(self):
        """
        Settings to make requests with random user agent
        :return: dict with settings
        """
        return {
            'timeout': 60,
            'headers': {'User-Agent': '{} {}'.format(self.user_agent.random,
                                                     self.UA_SUFFIX)},
            'verify': False,
        }

    @staticmethod
    def _get_start_date(timestamp):
        """
        :param timestamp: Date from json as timestamp
        :return: Date in normalized format dd.mm.yyyy or
                 empty string if None was in json
        """
        if timestamp:
            date = datetime.fromtimestamp(timestamp / 1000).date()
            str_date = date.strftime("%d.%m.%Y")
            return str_date
        else:
            return ""

    def _parse_json(self, json):
        """
        Parse vacancy info from json response
        :param json: json response 
        :return: 
        """
        # pass through all locations in current json
        for place in json:
            location_name = place["locationName"]
            location_city = place["locationAddress"]["municipality"]
            location_address = place["locationAddress"]["addressLine"]
            # pass through all all jobs in current location
            for job in place["locationJobs"]:
                self.vacancy_dict[job["jobId"]] = {
                    "location_name": location_name,
                    "location_city": location_city,
                    "location_address": location_address,
                    "vacancy_url": 'https://karriere.mcdonalds.de' + job[
                        "applicationUrl"],
                    "vacancy_label": job["label"],
                    "start_date": self._get_start_date(job["startDate"]),
                    "description": ""
                }
        logging.info("Vacancies count: {}".format(len(self.vacancy_dict)))

    def _do_requests(self):
        """
        Do requests to api url with params from DEFAULT lists above, and
        parse received data to vacancy dict
        """
        # Prepare params for progress bar
        total = len(self.DEFAULT_LOCATIONS_REST) * len(
            self.DEFAULT_TYPES_REST) + len(self.DEFAULT_TYPES_ADM)
        i = 0

        # receive ordinary vacancies
        for city in self.DEFAULT_LOCATIONS_REST:
            for rest_type in self.DEFAULT_TYPES_REST:
                progress(i, total, status='Parse vacancies')
                i += 1
                attempt = 1
                # Prepare request params
                city.update({'pos': rest_type})
                logging.info('Do request for vacancies in {}'.format(city))
                # Do request on api url
                res = rq.post(self.DEFAULT_URL, data=city,
                              **self._request_settings)
                # Trying to get response without error, if first was with
                while res.status_code != 200 and \
                                attempt <= self.ATTEMPTS_COUNT:
                    res = rq.post(self.DEFAULT_URL, data=city,
                                  **self._request_settings)
                    logging.info('Retry to receive from {}'.format(city))
                try:
                    # check the response format
                    result = res.json()
                    # Fetching vacancy data from json response
                    self._parse_json(result)
                except Exception as e:
                    logging.info(
                        'Can not parse json \nurl:{} code:{} error{}'.format(
                            res.url, res.status_code, str(e)))

        # receive administrative vacancies in the same way as ordinary
        for adm_type in self.DEFAULT_TYPES_ADM:
            progress(i, total, status='Parse vacancies')
            i += 1
            attempt = 1
            logging.info(
                'Do request to receive administrative vacancies {}'.format(
                    self.DEFAULT_LOCATION_ADM))
            self.DEFAULT_LOCATION_ADM.update({'pos': adm_type})
            res = rq.post(self.DEFAULT_URL, data=self.DEFAULT_LOCATION_ADM,
                          **self._request_settings)
            while res.status_code != 200 and attempt <= self.ATTEMPTS_COUNT:
                res = rq.post(self.DEFAULT_URL, data=self.DEFAULT_LOCATION_ADM,
                              **self._request_settings)
                logging.info('Retry to receive from administrative vacancies')
            try:
                result = res.json()
                self._parse_json(result)
            except Exception as e:
                logging.info(
                    'Can not parse json \nurl:{} code:{} error{}'.format(
                        res.url, res.status_code, str(e)))

    @staticmethod
    def exception_handler(request, exception):
        """
        Exception handler for request
        """
        logging.info(
            "Request failed. \nurl:{} error:{}".format(request.url, exception))

    @staticmethod
    def _get_vacancy_description(response):
        """
        Get vacancy description from html response
        :param response: fetched response
        :return: text content
        """
        content = response('.box-spacing-md')('.col-sm-8').text()
        return content

    def _get_description(self, rs):
        """
        Creates asynchronous requests using the grequests library,
        if request was successful - gets vacancy description from vacancy page,
        if not - appends url in list of urls, which will be used again
        :param rs: list of urls
        :return: list of urls with error in response
        """
        error_rs = []
        for r in grq.imap(rs, size=self.WORKERS_NUM,
                          exception_handler=self.exception_handler):
            if r.status_code == 200:
                try:
                    index = self._get_job_id(r.url)
                    self.vacancy_dict[index]["description"] = \
                        self._get_vacancy_description(pq(r.text))
                except Exception as e:
                    logging.info(
                        'Error in response {}, exception:{}'.
                            format(r.url, str(e)))
            else:
                error_rs.append(r.url)
        return error_rs

    def _get_url_list(self):
        """
        Creates list of urls from vacancies list
        :return: list of url
        """
        url_list = []
        for vacancy in self.vacancy_dict.values():
            url = vacancy["vacancy_url"]
            url_list.append(url)
        return url_list

    def _prepare_data(self, url_list):
        """
        Prepares list of requests to urls defined in url_list, and
        submits for execution in batches indicated in MAX_ID
        :param url_list: list of urls
        :return: list of urls which need to be requested again
        """
        # list of requests
        rs = []
        # list of urls which need to be requested again
        error_rs = []
        counter = 0
        # prepare data for progress bar
        i = 0
        total = len(self.vacancy_dict)
        for url in url_list:
            progress(i, total, status='Getting vacancy descriptions')
            i += 1
            rs.append(grq.get(url))
            # count the number of queries
            counter += 1
            if counter == self.MAX_ID:
                # execute request and prepare variables for new batch,
                # also extend list urls which will used again
                error_rs.extend(self._get_description(rs))
                counter = 0
                rs = []
        error_rs.extend(self._get_description(rs))
        return error_rs

    @staticmethod
    def _get_job_id(link):
        """
        Fetching job id from vacancy url
        :param link: vacancy url
        :return: Job ID
        """
        try:
            return parse.parse_qs(parse.urlparse(link).query)['jobId'][0]
        except Exception as e:
            logging.info(
                'Can not get identifier from url {} {}'.format(link, str(e)))
            return ""

    def _export_to_xml(self):
        """
        Export vacancies to xml file
        :return: xml file path
        """
        root = etree.Element('vacancies')
        # Prepare values for progress bar
        i = 0
        total = len(self.vacancy_dict)
        for data in self.vacancy_dict.values():
            i += 1
            progress(i, total, status='Export in xml')
            vacancy = etree.SubElement(root, 'position')
            etree.SubElement(vacancy, 'link').text = data["vacancy_url"]
            etree.SubElement(vacancy, 'identifier').text = self._get_job_id(
                data['vacancy_url'])
            split_title = data["vacancy_label"].rsplit('(', maxsplit=1)
            title = split_title[0]
            kind = split_title[1][:-1]
            etree.SubElement(vacancy, 'title').text = title
            etree.SubElement(vacancy, 'start_date').text = data["start_date"]
            try:
                etree.SubElement(vacancy, 'kind').text = self.JOBS_KIND[kind]
            except Exception as e:
                logging.info("Can't get kind of vacancy  {}".format(str(e)))
                etree.SubElement(vacancy, 'kind')
            etree.SubElement(vacancy, 'description').text = \
                etree.CDATA(data["description"])
            etree.SubElement(vacancy, 'top_location').text = data[
                "location_city"]
            locations = etree.SubElement(vacancy, 'locations')
            etree.SubElement(locations, 'location').text = data[
                "location_name"]
            etree.SubElement(vacancy, 'images')
            company = etree.SubElement(vacancy, 'company')
            etree.SubElement(company, 'name').text = "McDonald's"
            address = etree.SubElement(company, 'address')
            etree.SubElement(address, 'street').text = data[
                "location_address"]
            etree.SubElement(address, 'zip')
            etree.SubElement(address, 'city').text = data[
                "location_city"]
            etree.SubElement(vacancy, 'contact_email').text = \
                'fallback@jobufo.com'

        # create directory to save parsed xml if it does not exists
        if not os.path.exists(self.DIR_TO_EXPORT):
            os.makedirs(self.DIR_TO_EXPORT)

        filepath = os.path.join(self.DIR_TO_EXPORT, self.OUTPUT_FILENAME)

        tree = etree.ElementTree(root)
        tree.write(filepath, pretty_print=True, xml_declaration=True,
                   encoding='utf-8')
        return filepath

    def run(self):
        """
        Run process of applying job
        """
        # obtaining a dict of vacancies
        self._do_requests()
        # obtaining a list of vacancies urls
        main_url_list = self._get_url_list()
        logging.info("Main urls count : {}".format(len(main_url_list)))
        # obtaining vacancies descriptions and list of urls to parse again
        error_url_list = self._prepare_data(main_url_list)
        logging.info("Error urls count : {}".format(len(error_url_list)))
        attempt = 1
        # trying to get responses from all urls
        while len(error_url_list) > 0 and attempt <= self.ATTEMPTS_COUNT:
            logging.info("Attempt to reach error urls: {}".format(attempt))
            error_url_list = self._prepare_data(error_url_list)
            attempt += 1
        # export vacancies into xml file
        self._export_to_xml()


if __name__ == "__main__":
    parser = McDonaldsParser()
    parser.run()
