import requests
import json
import csv
import os
import time
import logging
import sys
import boto3
import pandas as pd
from botocore.exceptions import ClientError
from datetime import datetime
import subprocess

time_delay = 5
data_file = 'data.csv'
url = 'https://front.wegobuy.com/shoppingguide/sale-daily-new?count='
num_items = 15
row_names = ['id', 'goodsId', 'goodsPicUrl', 'goodsTitle', 'goodsLink', 'goodsPrice', 'buyerId', 'buyerName', 'orderState', 'goodsOrderTime', 'status', 'createTime', 'updateTime', 'buyerAvatar', 'userLevel', 'userLevelType', 'currencySymbol', 'userName', 'timeName', 'countryCode', 'statePicUrl']
check_cols = ['goodsId', 'buyerId', 'goodsOrderTime']

notebook_name = 'notebook'
notebook_load_wait = 60 * 60

if not os.path.isdir('logs'):
    os.mkdir('logs')

log_file = 'logs\{:%Y_%m_%d_%H}.log'.format(datetime.now())
log_format = u'%(asctime)s | %(levelname)-8s | %(message)s'
logger = logging.getLogger('WegobuyWatcher')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(log_file, encoding='utf-8')
formatter = logging.Formatter(log_format)
handler.setFormatter(formatter)
logger.addHandler(handler)
printer = logging.StreamHandler(sys.stdout)
printer.setLevel(logging.DEBUG)
printer.setFormatter(formatter)
logger.addHandler(printer)

bucket = os.environ.get('S3_BUCKET_NAME')
key = os.environ.get('AWS_ACCESS_KEY_ID')
secret = os.environ.get('AWS_SECRET_ACCESS_KEY')
s3 = boto3.client('s3')
upload_time = 10 * 60
tmp_csv_name = 'tmp_csv'

on_heroku = True #if os.environ.get('on_heroku') == 'True' else False

def upload():
    upload_file = data_file if on_heroku else 'data-local.csv'
    upload_log_file = log_file if on_heroku else log_file.split('.')[0] + '-local.log'
    try:
        with open(data_file, 'rb') as f:
            s3.upload_fileobj(f, bucket, upload_file)
        logger.info(f'Uploaded {upload_file} to S3 bucket {bucket}')
    except:
        logger.exception(f'Upload of {upload_file} to S3 bucket {bucket} failed')
    try:
        with open(log_file, 'rb') as f:
            s3.upload_fileobj(f, bucket, upload_log_file)
        logger.info(f'Uploaded {upload_log_file} to S3 bucket {bucket}')
    except:
        logger.exception(f'Upload of {upload_log_file} to S3 bucket {bucket} failed')

def download():

    logger.info(f'Attempting to download {data_file if on_heroku else "data-local.csv"} from bucket {bucket}')
    try:
        with open(tmp_csv_name, 'wb') as f:
            s3.download_fileobj(bucket, data_file if on_heroku else 'data-local.csv', f)
        logger.info(f'Downloaded {data_file if on_heroku else "data-local.csv"} from S3 bucket {bucket} to file {tmp_csv_name}')
        return True
    except ClientError:
        logger.info(f'File {data_file if on_heroku else "data-local.csv"} not found on S3 bucket {bucket}')
    except:
        logger.exception(f'Error downloading file {data_file if on_heroku else "data-local.csv"} from S3 bucket {bucket}')

def log_cron():
    logger.info('Request recieved from cron-job.org')

def log_subprocess_output(pipe):
    for line in iter(pipe.readline, b''):
        logger.info('Notebook conversion output: %r', line.decode().strip())

def load_notebook():
    logger.info(f'Converting {notebook_name}.ipynb to {notebook_name}.html')
    converter = subprocess.Popen(['jupyter', 'nbconvert', '--execute', '--no-input', '--no-prompt', '--output-dir="./templates"', '--to', 'html', notebook_name + '.ipynb'])#, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    converter.communicate()
    #with converter.stdout:
    #    log_subprocess_output(converter.stdout)
    #exitcode = converter.wait()
    #logger.info(f'Notebook conversion finished with exitcode {exitcode}')
    #return exitcode

def watch():
    try:
        last_upload = time.time()
        logger.info('**** STARTING WATCHER ****')
        logger.info(
            f'Program settings: time_delay: {time_delay}, data_file: {data_file}, num_items: {num_items}, log_file: {log_file}')
        old_exists = download()
        if not os.path.isfile(data_file):
            with open(data_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row_names)
                logger.info(f'Data file {data_file} not found, created it with row names {row_names}')
        df = pd.read_csv(data_file, encoding='utf-8')
        logger.info(f'Read {len(df)} entries from {data_file}')

        if old_exists:
            old_df = df.copy()
            download_df = pd.read_csv(tmp_csv_name, encoding='utf-8')
            df = pd.concat([df, download_df])
            df = df.drop_duplicates(subset=check_cols)
            df = df.reset_index(drop=True)
            df.to_csv(data_file, encoding='utf-8', index=False)
            logger.info(f'Read {len(download_df)} entries from old data {tmp_csv_name} and added {len(df) - len(old_df)} entries to {data_file}')
            os.remove(tmp_csv_name)
            logger.info(f'Deleted temporary file {tmp_csv_name}')

        load_notebook()
        last_conversion = time.time()

        logger.info('Starting main loop...')
        while True:
            response = requests.get(url + str(num_items))
            response = json.loads(response.text.encode('utf-8'))
            curr_data = response['data']
            curr_data = [{k: str(v) for k, v in c.items()} for c in curr_data]
            old_df = df.copy()
            tmp = pd.DataFrame(curr_data)
            df = pd.concat([df, tmp])
            df = df.drop_duplicates(subset=check_cols)
            df = df.reset_index(drop=True)
            if len(df) - len(old_df) > 0:
                df.to_csv(data_file, encoding='utf-8', index=False)
                logger.info(f'Wrote {len(df) - len(old_df)} new items to {data_file}: {curr_data}')
            #else:
                #logger.info('No new items found')
            if time.time() - last_upload > upload_time:
                upload()
                last_upload = time.time()

            if time.time() - last_conversion > notebook_load_wait:
                load_notebook()
                last_conversion = time.time()

            time.sleep(time_delay)
    except:
        logger.exception('ERROR')

if __name__ == '__main__':
    watch()
