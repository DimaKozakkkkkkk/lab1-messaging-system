import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import logging
from flask import Flask
from storage.database import init_db
from services.message_service import start_delivery_worker
from api.routes import bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def create_app(db_path: str = None):
    if db_path:
        os.environ["MESSENGER_DB"] = db_path

    app = Flask(__name__)
    app.register_blueprint(bp)

    with app.app_context():
        init_db()

    return app


if __name__ == "__main__":
    app = create_app()
    start_delivery_worker()
    app.run(host="0.0.0.0", port=8000, debug=False)
