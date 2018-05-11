import os
import sys
import json
import logging
import requests
import time

from splinter import Browser

from utils import prepare_logs_dir

CURRENT_PATH = os.path.abspath(os.path.dirname(__file__))

"""Settings for local testing on Linux/Mac with Chrome driver"""

LINUX_PLATFORM = 'linux'
MAC_PLATFORM = 'darwin'

WEB_DRIVERS = {
    LINUX_PLATFORM: 'chromedriver_linux_x64',
    MAC_PLATFORM: 'chromedriver_darwin'
}

try:
    DRIVER_PATH = os.path.join(CURRENT_PATH, 'drivers',
                               WEB_DRIVERS[sys.platform])
except:
    raise Exception

prepare_logs_dir()

logging.basicConfig(filename='logs/exchanger.log', level=logging.INFO,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%d-%m-%y %H:%M')


class Exchanger:
    """
    Class to apply for job with user data
    """
    DOWNLOADS_DIR = 'downloads'

    def __init__(self, vacancy_url, user_data):
        """
        Init class
        :param vacancy_url: url of vacancy page
        :param user_data: dict with user data
        """
        self.browser = self._setup_browser()
        self.vacancy_url = vacancy_url
        self.user_data = user_data

    @staticmethod
    def _setup_browser():
        """
        Prepare splinter browser
        :return: Browser object
        """
        logging.info('##### Prepare browser #####')
        options = {'executable_path': DRIVER_PATH, 'headless': True}
        return Browser('chrome', **options)

    def _open_page(self):
        """
        Visit vacancy page and apply for a job
        """
        logging.info('Open vacancy page {}'.format(self.vacancy_url))
        self.browser.visit(self.vacancy_url)
        self.browser.find_link_by_partial_href(
            "https://mcdonalds.csod.com/ATS/careersite/da.aspx").click()

    def _fill_inputs(self):
        """
        Fill required fields
        """
        logging.info('Fill inputs')
        # fill first name
        self.browser.fill('__ci_508',
                          self.user_data['first_name'])
        # fill last name
        self.browser.fill('__cl_508',
                          self.user_data['last_name'])
        # fill email
        self.browser.fill('__cq_508', self.user_data['email'])

    def _download_file(self):
        """
        Download cv file
        :return: str file path
        """
        logging.info('Download cv file')
        file_url = self.user_data['cv_path']
        r = requests.get(file_url, allow_redirects=True)
        filename = file_url.rsplit('/', 1)[1]

        downloads_dir = os.path.join(CURRENT_PATH, self.DOWNLOADS_DIR)

        # create directory to save downloaded cv file if it does not exists
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
        file_path = os.path.join(downloads_dir, filename)
        try:
            open(file_path, 'wb').write(r.content)
        except Exception as e:
            logging.info('Can not download file: {}'.format(str(e)))
        return file_path

    def _upload_file(self):
        """
        Upload file
        """
        file_path = self._download_file()
        logging.info('Try to attach file')
        try:
            self.browser.attach_file('files[]', file_path)
        except Exception as e:
            logging.info('Can not upload file: {}'.format(str(e)))
        while self.browser.is_element_not_present_by_css('.cso-hyper-link'):
            time.sleep(1)

    def _fill_cv(self):
        """
        Fill CV
        """
        logging.info('Fill additional information')

        # scroll to the bootom of the page
        self.browser.execute_script(
            'window.scrollTo(0, document.body.scrollHeight);')
        iframe_id = 'ctl00_ctl00_siteContent_applicationContent_ifrSelection'
        with self.browser.get_iframe(iframe_id) as iframe:
            iframe.is_element_not_present_by_text('Anrede', 2)

            # check sex
            logging.info('Check sex')
            male_label = 'radio_8f4016b6-1b91-11e8-cfde-005056b62a99_1'
            female_label = 'radio_8f4016b3-1b91-11e8-cfde-005056b62a99_0'
            if self.user_data['gender'] == 'M':
                iframe.find_by_xpath(
                    '//label[@for="{}"]'.format(male_label)).last.click()
            else:
                iframe.find_by_xpath(
                    '//label[@for="{}"]'.format(female_label)).last.click()

            # check title
            logging.info('Check title')
            title_label_for = 'radio_8f5e2609-1b91-11e8-cfde-005056b62a99_2'
            iframe.find_by_xpath(
                '//label[@for="{}"]'.format(title_label_for)).last.click()

            iframe.find_by_css('.next-button').last.click()

    def _accept(self):
        """
        Accept CV
        """
        logging.info('Accept cv')
        input_id = 'ctl00_ctl00_siteContent_applicationContent_cbAgree'
        self.browser.is_element_not_present_by_id(input_id, 1)
        self.browser.find_by_id(input_id).click()
        self.browser.find_by_id('ctl00_ctl00_siteContent_btnNext').click()

    def _skip_password(self):
        """
        Skip password settings
        """
        logging.info('Skip password settings')
        button_id = 'ctl00_ctl00_siteContent_btnCancel'
        modal_button_id = 'ctl00_ctl00_siteContent_dlgConfirm_btnDialogDelete'

        self.browser.is_element_not_present_by_id(button_id, 1)
        self.browser.find_by_id(button_id).click()

        self.browser.is_element_not_present_by_id(modal_button_id, 1)
        self.browser.find_by_id(modal_button_id).click()

    def _submit(self):
        """
        Submit vacancy form
        """
        logging.info('Submit vacancy form')

        next_button_id = 'ctl00_ctl00_siteContent_btnNext'

        self.browser.find_by_id('__de').click()
        self.browser.is_element_not_present_by_id(next_button_id, 1)

        # go to next page
        self.browser.find_by_id(next_button_id).click()

        # fill phone
        phone_field_name = 'ctl00$ctl00$siteContent$applicationContent$uc' \
                           'ResumeReview$txtPhone'
        self.browser.fill(phone_field_name, self.user_data['phone'])

        # go to next page
        self.browser.find_by_id(next_button_id).click()
        self._fill_cv()
        self._accept()
        self._skip_password()

    def run(self):
        """
        Run process of applying job
        """
        self._open_page()
        # wait until all items are loaded
        self.browser.is_element_not_present_by_id('___l', 1)
        self._upload_file()
        self._fill_inputs()
        self._submit()
        logging.info('##### Vacancy accepted successfully #####')
        self.browser.quit()


if __name__ == "__main__":
    url = 'https://karriere.mcdonalds.de/stellenangebot/' \
          'job-detail.html?jobId=req12149'
    data = json.load(open('test_user_data.json'))
    parser = Exchanger(user_data=data, vacancy_url=url)
    parser.run()
