from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_bootstrap import Bootstrap5
from flask_login import UserMixin, LoginManager
from datetime import datetime, timezone
from pymongo import MongoClient


app = Flask(__name__)

bootstrap = Bootstrap5(app)
client = MongoClient(os.getenv('MONGODB_CONNECTION_STRING'))
db = client['kuharica_database']
recepti_collection = db['recepti']
users_collection = db['users']
fs = gridfs.GridFS(db)
mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, email, admin=False, theme=''):
        self.id = email
        self.admin = admin is True
        self.theme = theme

    @classmethod
    def get(cls, id):
        user_data = users_collection.find_one({"email": id})
        if user_data:
            return cls(user_data['email'], user_data.get('is_admin'), user_data.get('theme'))
        raise UserNotFoundError()

    @property
    def is_admin(self):
        return self.admin

class UserNotFoundError(Exception):
    pass

@login_manager.user_loader
def load_user(email):
    try:
        return User.get(email)
    except UserNotFoundError:
        return None

@app.route("/")
def index():
    recepti = recepti_collection.find({"status": "published"}).sort('datum', -1)
    return render_template("index.html", recepti=recepti)
