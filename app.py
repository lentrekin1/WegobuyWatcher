from flask import Flask, render_template, Response, redirect, request
import csv
import os
import threading
import watcher
import logging
import sys
from datetime import datetime

log_file = 'logs/{:%Y_%m_%d_%H}.log'.format(datetime.now())
log_format = u'%(asctime)s | %(levelname)-8s | %(message)s'
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
handler = logging.FileHandler(log_file, encoding='utf-8')
formatter = logging.Formatter(log_format)
handler.setFormatter(formatter)
root_logger.addHandler(handler)
printer = logging.StreamHandler(sys.stdout)
printer.setLevel(logging.DEBUG)
printer.setFormatter(formatter)
root_logger.addHandler(printer)

logger = logging.getLogger(__name__)

page_len = 100
watch_thread = threading.Thread(target=watcher.watch, args=())
watch_thread.start()
app = Flask(__name__)

def get_data(pg=None):
    if not os.path.isfile(watcher.data_file):
        with open(watcher.data_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(watcher.row_names)
    data = []
    with open(watcher.data_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
                data.append(row)
    if pg:
        data = data[(pg - 1) * page_len: pg * page_len]
    return list(reversed(data))

def get_last_page():
    data = get_data()
    return int(len(data) / page_len) + 1

@app.before_request
def log_connection():
    logger.info(f'IP address {request.remote_addr} is connecting to page "{request.path}"')

@app.route('/')
def show_data():
    return redirect('/page/' + str(get_last_page()))

@app.route('/page/<int:pg>')
def page(pg):
    last_pg = get_last_page()
    if pg > last_pg:
        return redirect('/page/' + str(last_pg))
    if pg < 1:
        return redirect('/page/' + str(1))
    return render_template('home.html', data=get_data(pg=int(pg)), isFirst='' if pg != 1 else 'none', isLast='' if pg != last_pg else 'none', totalNum=len(get_data()), header=watcher.row_names)

@app.route('/info')
def info():
    if os.path.isfile('templates/' + watcher.notebook_name + '.html'):
        return render_template(watcher.notebook_name + '.html')
    else:
        logger.info(f'Analysis file {watcher.notebook_name}.html was request by {request.remote_addr} and was not found')
        return 'Analysis file not found'

@app.route("/getcsv")
def give_data():
    with open(watcher.data_file, encoding='utf-8') as f:
        file = f.read()
        logger.info(f'IP address {request.remote_addr} downloaded {watcher.data_file}')
    return Response(
        file,
        mimetype="text/csv",
        headers={"Content-disposition":
                     f"attachment; filename={watcher.data_file}"})

@app.route('/cron')
def cron_job():
    logger.info('Cron job request recieved')
    return 'Wegobuy-Watcher'

@app.route('/test')
def diag():
    data = []
    data.append(str(os.path.dirname(os.path.realpath(__file__))))
    files = [f for f in os.listdir('.')]
    data.append('<br>'.join(files))
    files = [f for f in os.listdir('templates')]
    data.append('<br>'.join(files))
    with open('templates/notebook.html', 'r', encoding='utf-8') as f:
        lines = [l for i,l in enumerate(f) if 14280 < i < 14285]
    data.append('<br>'.join(lines))
    data = ''.join([x + '<br><br>' for x in data])
    return data

if __name__ == '__main__':
    app.run(port=80)
