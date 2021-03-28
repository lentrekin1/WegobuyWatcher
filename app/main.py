from flask import Flask, render_template, Response
import csv
import os
import watcher

app = Flask(__name__)

def get_data():
    if not os.path.isfile(watcher.data_file):
        with open(watcher.data_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(watcher.row_names)
    data = []
    with open(watcher.data_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

@app.route('/')
def show_data():
    return render_template('home.html', data=get_data(), header=watcher.row_names)

@app.route("/getcsv")
def give_data():
    with open(watcher.data_file, encoding='utf-8') as f:
        file = f.read()
    return Response(
        file,
        mimetype="text/csv",
        headers={"Content-disposition":
                     f"attachment; filename={watcher.data_file}"})

if __name__ == '__main__':
    app.run(port=80)