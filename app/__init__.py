
import datetime
import os
from flask import Flask

webapp = Flask(__name__)
webapp.config["SECRET_KEY"] = b']\r7\x1f\xe20\xfc\xe8%\x15\xbd' #os.urandom(11)
webapp.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(hours=24)
webapp.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

from app import main
# from app import hello_v2
