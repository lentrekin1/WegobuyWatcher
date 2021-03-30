from flask import Flask, render_template, Response, redirect
import csv
import os
import threading
import watcher

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

@app.route("/getcsv")
def give_data():
    with open(watcher.data_file, encoding='utf-8') as f:
        file = f.read()
    return Response(
        file,
        mimetype="text/csv",
        headers={"Content-disposition":
                     f"attachment; filename={watcher.data_file}"})

@app.route('/cron')
def cron_job():
    watcher.log_cron()
    return 'Wegobuy-Watcher'

if __name__ == '__main__':
    app.run(port=80)
