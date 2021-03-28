import requests
import json
import csv
import os
import time
import logging
import sys
import boto3
import functools
from botocore.exceptions import ClientError
from datetime import datetime

time_delay = 5
data_file = 'data.csv'
url = 'https://front.wegobuy.com/shoppingguide/sale-daily-new?count='
num_items = 15
row_names = ['id', 'goodsId', 'goodsPicUrl', 'goodsTitle', 'goodsLink', 'goodsPrice', 'buyerId', 'buyerName', 'orderState', 'goodsOrderTime', 'status', 'createTime', 'updateTime', 'buyerAvatar', 'userLevel', 'userLevelType', 'currencySymbol', 'userName', 'timeName', 'countryCode', 'statePicUrl']

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

on_heroku = True if os.environ.get('on_heroku') == 'True' else False

def log_cron():
    logger.info('Request recieved from cron-job.org')

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
    try:
        with open(tmp_csv_name, 'wb') as f:
            s3.download_fileobj(bucket, data_file if on_heroku else 'data-local.csv', f)
        logger.info(f'Downloaded {data_file if on_heroku else "data-local.csv"} from S3 bucket {bucket} to file {tmp_csv_name}')
        return True
    except ClientError:
        logger.info(f'File {data_file if on_heroku else "data-local.csv"} not found on S3 bucket {bucket}')
    except:
        logger.exception(f'Error downloading file {data_file if on_heroku else "data-local.csv"} from S3 bucket {bucket}')

def trackcalls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.has_been_called = False
        return func(*args, **kwargs)
    wrapper.has_been_called = False
    return wrapper

#@trackcalls
def watch():
    #if not watch.has_been_called:
    watch.has_been_called = True
    try:
        last_upload = time.time()
        logger.info('**** STARTING WATCHER ****')
        logger.info(
            f'Program settings: time_delay: {time_delay}, data_file: {data_file}, num_items: {num_items}, log_file: {log_file}')
        old_ids = []
        old_times = []
        old_exists = download()
        if not os.path.isfile(data_file):
            with open(data_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row_names)
                logger.info(f'Data file {data_file} not found, created it with row names {row_names}')

        with open(data_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                old_ids.append(row['id'])
                old_times.append(row['goodsOrderTime'])
            logger.info(f'Read {len(old_ids)} ids and {len(old_times)} order times from {data_file}')
#todo fix error where, when deployed on heroku, watch() starts twice, idk y
#todo heroku deployment appears to not be working correctly
        if old_exists:
            with open(tmp_csv_name, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                with open(data_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=row_names)
                    num_added = 0
                    num_old = 0
                    for row in reader:
                        num_old += 1
                        if row['id'] not in old_ids and row['goodsOrderTime'] not in old_times:
                            writer.writerow(row)
                            old_ids.append(row['id'])
                            old_times.append(row['goodsOrderTime'])
                            num_added += 1
            logger.info(f'Read {num_old} entries from old data {tmp_csv_name} and added {num_added} entries to {data_file}')
            os.remove(tmp_csv_name)
            logger.info(f'Deleted temporary file {tmp_csv_name}')

        logger.info('Starting main loop...')
        while True:
            response = requests.get(url + str(num_items))
            logger.info('raw response ______________________________________________')
            logger.info(response)
            response = json.loads(response.text.encode('utf-8'))
            logger.info('json respone _____________________________')
            logger.info(response)
            curr_data = response['data']
            logger.info('response[data]_____________________________')
            logger.info(curr_data)
            curr_data = [{k: str(v) for k, v in c.items()} for c in curr_data]

            for c in list(curr_data):
                if c['id'] in old_ids and c['goodsOrderTime'] in old_times:
                    curr_data.remove(c)
                else:
                    old_ids.append(c['id'])
                    old_times.append(c['goodsOrderTime'])

            logger.info('post remove dups ____________________________________')
            logger.info(curr_data)
            if len(curr_data) > 0:
                with open(data_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, row_names)
                    writer.writerows(curr_data)
                    logger.info(f'Wrote {len(curr_data)} new items to {data_file}: {curr_data}')
            else:
                logger.info('No new items found')
            if time.time() - last_upload > upload_time:
                upload()
                last_upload = time.time()
            time.sleep(time_delay)
    except:
        logger.exception('ERROR')
    #else:
    #    print('already called')

if __name__ == '__main__':
    watch()
    #upload()


