from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_bootstrap import Bootstrap5
from datetime import datetime, timezone
from pymongo import MongoClient
from bson.objectid import ObjectId
import gridfs
import markdown
from flask_login import UserMixin, LoginManager
from flask_login import login_required, current_user, login_user, logout_user
from forms import BlogPostForm, LoginForm, RegisterForm, ProfileForm, UserForm
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer

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

@login_manager.user_loader
def load_user(email):
    try:
        return User.get(email)
    except UserNotFoundError:
        return None

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

@app.route("/")
def index():
    recepti = recepti_collection.find({"status": "published"}).sort('datum', -1)
    return render_template("index.html", recepti=recepti)

@app.route("/recept/create", methods=["GET", "POST"])
@login_required
def recept_create():
    form = RecipeForm()
    if form.validate_on_submit():
        image_id = save_image_to_gridfs(request, fs)
        recept = {
            'naziv': form.naziv.data,
            'sastojci': form.sastojci.data,
            'upute': form.upute.data,
            'tip_jela': form.tip_jela.data,
            'vrijeme_pripreme': form.vrijeme_pripreme.data,
            'autor': current_user.get_id(),
            'status': form.status.data,
            'datum': datetime.combine(form.datum.data, datetime.min.time()),
            'slika_id': image_id,
            'datum_kreiranja': datetime.utcnow()
        }
        recepti_collection.insert_one(recept)
        flash("Recept je uspješno dodan!", "success")
        return redirect(url_for("index"))
    return render_template("recept_edit.html", form=form)

@app.route("/recept/<recept_id>")
def recept_view(recept_id):
    recept = recepti_collection.find_one({"_id": ObjectId(recept_id)})
    if not recept:
        flash("Recept nije pronađen!", "danger")
        return redirect(url_for("index"))
    return render_template("recept_view.html", recept=recept, edit_recept_permission=edit_recept_permission)

@app.route("/recept/edit/<recept_id>", methods=["GET", "POST"])
@login_required
def recept_edit(recept_id):
    permission = edit_recept_permission(recept_id)
    if not permission.can():
        abort(403, "Nemate dozvolu za uređivanje ovog recepta.")

    form = RecipeForm()
    recept = recepti_collection.find_one({"_id": ObjectId(recept_id)})

    if request.method == 'GET':
        form.naziv.data = recept['naziv']
        form.sastojci.data = recept['sastojci']
        form.upute.data = recept['upute']
        form.tip_jela.data = recept['tip_jela']
        form.vrijeme_pripreme.data = recept['vrijeme_pripreme']
        form.datum.data = recept['datum']
        form.status.data = recept['status']
    elif form.validate_on_submit():
        update_data = {
            'naziv': form.naziv.data,
            'sastojci': form.sastojci.data,
            'upute': form.upute.data,
            'tip_jela': form.tip_jela.data,
            'vrijeme_pripreme': form.vrijeme_pripreme.data,
            'datum': datetime.combine(form.datum.data, datetime.min.time()),
            'status': form.status.data,
            'datum_azuriranja': datetime.utcnow()
        }
        image_id = save_image_to_gridfs(request, fs)
        if image_id:
            update_data['slika_id'] = image_id
        recepti_collection.update_one({"_id": ObjectId(recept_id)}, {"$set": update_data})
        flash("Recept je ažuriran.", "success")
        return redirect(url_for("recept_view", recept_id=recept_id))
    return render_template("recept_edit.html", form=form)

@app.route("/recept/delete/<recept_id>", methods=["POST"])
@login_required
def delete_recept(recept_id):
    permission = edit_recept_permission(recept_id)
    if not permission.can():
        abort(403, "Nemate dozvolu za brisanje ovog recepta.")
    recepti_collection.delete_one({"_id": ObjectId(recept_id)})
    flash("Recept obrisan.", "success")
    return redirect(url_for("index"))

@app.route("/moji_recepti")
@login_required
def moji_recepti():
    recepti = recepti_collection.find({"autor": current_user.get_id()}).sort("datum", -1)
    return render_template("moji_recepti.html", recepti=recepti)

def save_image_to_gridfs(request, fs):
    if 'image' in request.files:
        image = request.files['image']
        if image.filename != '':
            return fs.put(image, filename=image.filename)
    return None

@app.template_filter('markdown')
def markdown_filter(text):
    return markdown.markdown(text)

class EditRecipeNeed:
    def __init__(self, recipe_id):
        super().__init__('edit_recipe', recipe_id)

def edit_recipe_permission(recipe_id):
    return Permission(EditRecipeNeed(str(ObjectId(recipe_id))))


