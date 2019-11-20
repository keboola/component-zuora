'''
Template Component main class.

'''

import logging
import logging_gelf.handlers
import logging_gelf.formatters
import sys
import os
import json
import datetime  # noqa
import dateparser
import pandas as pd

from kbc.env_handler import KBCEnvHandler
from kbc.result import KBCTableDef  # noqa
from kbc.result import ResultWriter  # noqa
from zuora_restful_python.zuora import Zuora


# configuration variables
KEY_USERNAME = 'username'
KEY_PASSWORD = '#password'
KEY_ENDPOINTS = 'endpoints'
KEY_BACKFILL = 'backfill_mode'

MANDATORY_PARS = [KEY_USERNAME, KEY_PASSWORD, KEY_ENDPOINTS]
MANDATORY_IMAGE_PARS = []

# Default Table Output Destination
DEFAULT_TABLE_SOURCE = "/data/in/tables/"
DEFAULT_TABLE_DESTINATION = "/data/out/tables/"
DEFAULT_FILE_DESTINATION = "/data/out/files/"
DEFAULT_FILE_SOURCE = "/data/in/files/"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)-8s : [line:%(lineno)3s] %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S")

if 'KBC_LOGGER_ADDR' in os.environ and 'KBC_LOGGER_PORT' in os.environ:

    logger = logging.getLogger()
    logging_gelf_handler = logging_gelf.handlers.GELFTCPSocketHandler(
        host=os.getenv('KBC_LOGGER_ADDR'), port=int(os.getenv('KBC_LOGGER_PORT')))
    logging_gelf_handler.setFormatter(
        logging_gelf.formatters.GELFFormatter(null_character=True))
    logger.addHandler(logging_gelf_handler)

    # remove default logging to stdout
    logger.removeHandler(logger.handlers[0])

APP_VERSION = '0.0.1'


class Component(KBCEnvHandler):

    def __init__(self, debug=False):
        KBCEnvHandler.__init__(self, MANDATORY_PARS)
        logging.info('Running version %s', APP_VERSION)
        logging.info('Loading configuration...')

        try:
            self.validate_config()
            self.validate_image_parameters(MANDATORY_IMAGE_PARS)
        except ValueError as e:
            logging.error(e)
            exit(1)

    def output_file(self, data, file_name, column_headers):
        '''
        Output dataframe intput to destination file
        Appending to file if file exist
        '''

        with open(file_name, 'a') as b:
            data.to_csv(b, index=False, header=False, columns=column_headers)

    def produce_manifest(self, file_name, columns):
        '''
        function for producting manifest
        '''

        file = DEFAULT_TABLE_DESTINATION+'{}.csv.manifest'.format(file_name)
        manifest = {
            "incremental": True,
            "primary_key": ["Id"],
            "columns": columns
        }

        try:
            with open(file, 'w') as file_out:
                json.dump(manifest, file_out)
                logging.info(
                    "Output manifest file [{}] produced.".format(file_name))
        except Exception as e:
            logging.error("Could not produce output file manifest.")
            logging.error(e)

    def run(self):
        '''
        Main execution code
        '''

        params = self.cfg_params  # noqa
        username = params.get(KEY_USERNAME)
        password = params.get(KEY_PASSWORD)
        endpoints = params.get(KEY_ENDPOINTS)
        backfill_mode = params.get(KEY_BACKFILL)
        backfill = backfill_mode['backfill']

        if params == {}:
            logging.error('Please enter required parameters.')
            sys.exit(1)

        if username == '' or password == '':
            logging.error('Please enter Zuora account credentials.')
            sys.exit(1)

        # Configuring date range
        if backfill == 'enable':
            logging.info('Backfill mode: Enabled')
            start_date_temp = backfill_mode['start_date']
            end_date_temp = backfill_mode['end_date']
            logging.info('Backfill Start Date: {}'.format(start_date_temp))
            logging.info('Backfill End Date: {}'.format(end_date_temp))

            # Error control in case user did not input date
            if start_date_temp == '' or end_date_temp == '':
                logging.error(
                    'Start date or end date cannot be empty with backfill mode enabled.' +
                    'Please enter start date and end date.'
                )
                sys.exit(1)

            # Validate if the input date range is valid
            self.start_date = dateparser.parse(start_date_temp)
            self.end_date = dateparser.parse(end_date_temp)
            if (self.end_date-self.start_date).days < 0:
                logging.error('Start date cannot be later than end date.')
                sys.exit(1)
        else:
            # Default request range
            self.start_date = dateparser.parse('yesterday')
            self.end_date = dateparser.parse('today')

        # Fetching columns required for the query reuqests
        with open('src/zuora_config.json', 'r') as f:
            zuora_config = json.load(f)

        # Zuora session
        zuora = Zuora(username, password)

        # BASE QUERY PARAMETER
        query = 'SELECT {{COLUMNS}} FROM {{REPORT}} {{CONDITIONS}}'

        for i in endpoints:
            endpoint = i['endpoint']
            logging.info('Fetching endpoint [{}]...'.format(endpoint))
            comma = ','
            columns_array = zuora_config[endpoint]['columns']
            columns = comma.join(columns_array)
            output_filename = DEFAULT_TABLE_DESTINATION + endpoint + '.csv'

            # ENDPOINTS DO NOT GET AFFECTED BY REQUEST TIME RANGE
            if endpoint in ('account', 'contact', 'product'):
                condition = ''
                temp_query = query.replace('{{REPORT}}', endpoint)
                temp_query = temp_query.replace('{{COLUMNS}}', columns)
                temp_query = temp_query.replace('{{CONDITIONS}}', condition)

                response = zuora.query(temp_query)
                data = pd.DataFrame(response['records'])

                self.output_file(data, output_filename, columns_array)

            # ENDPOINTS AFFECTED BY REQUEST TIME RANGE
            else:
                temp_date = self.start_date
                while temp_date.strftime('%Y-%m-%d') < self.end_date.strftime('%Y-%m-%d'):
                    temp_date_plus_1 = temp_date + datetime.timedelta(days=1)
                    logging.info('[{}] - {}'.format(endpoint,
                                                    temp_date.strftime('%Y-%m-%d')))

                    condition = 'WHERE CreatedDate >= {}T00:00:00 AND CreatedDate < {}T00:00:00'.format(
                        temp_date.strftime('%Y-%m-%d'), temp_date_plus_1.strftime('%Y-%m-%d'))
                    temp_query = query.replace('{{REPORT}}', endpoint)
                    temp_query = temp_query.replace('{{COLUMNS}}', columns)
                    temp_query = temp_query.replace(
                        '{{CONDITIONS}}', condition)

                    response = zuora.query(temp_query)
                    data = pd.DataFrame(response['records'])
                    self.output_file(data, output_filename, columns_array)

                    temp_date = temp_date_plus_1

            # Outputting manifest files for the files
            self.produce_manifest(endpoint, columns_array)

        logging.info("Extraction finished")


"""
        Main entrypoint
"""
if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug = sys.argv[1]
    else:
        debug = True
    comp = Component(debug)
    comp.run()
