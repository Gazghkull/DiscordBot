from flask import Flask
from threading import Thread
import os

app = Flask('')


@app.route('/')
def home():
    return "Bot en ligne !"


def run():
    port = int(os.environ.get(
        "PORT", 8080))  # Replit fournit le PORT via variable d'environnement
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run)
    t.start()
