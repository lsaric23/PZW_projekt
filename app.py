from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_bootstrap import Bootstrap5
from datetime import datetime, timezone
from pymongo import MongoClient
from bson.objectid import ObjectId
import gridfs
import markdown
from flask_login import UserMixin, LoginManager
from flask_login import login_required, current_user, login_user, logout_user
from forms import ReceptForm, LoginForm, RegisterForm, ProfileForm, UserForm
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

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
    form = ReceptForm()
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

    form = ReceptForm()
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

def save_image_to_gridfs(request, fs):
    if 'image' in request.files:
        image = request.files['image']
        if image.filename != '':
            image_id = fs.put(image, filename=image.filename)
        else:
            image_id = None
    else:
        image_id = None
    return image_id

@app.route('/image/<image_id>')
def serve_image(image_id):
    image = fs.get(ObjectId(image_id))
    return image.read(), 200, {'Content-Type': 'image/jpeg'}

@app.template_filter('markdown')
def markdown_filter(text):
    return markdown.markdown(text)

class EditRecipeNeed:
    def __init__(self, recipe_id):
        super().__init__('edit_recipe', recipe_id)

def edit_recept_permission(recept_id):
    return Permission(EditRecipeNeed(str(ObjectId(recept_id))))

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    if current_user.is_authenticated:
        identity.user = current_user
        identity.provides.add(UserNeed(current_user.id))
        identity.provides.add(RoleNeed('author'))
        if current_user.is_admin:
            identity.provides.add(RoleNeed('admin'))
        user_recepti = recepti_collection.find({"autor": current_user.get_id()})
        for recept in user_recepti:
            identity.provides.add(EditRecipeNeed(str(recept["_id"])))


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = request.form['email']
        password = request.form['password']
        user_data = users_collection.find_one({"email": email})

        if user_data is not None and check_password_hash(user_data['password'], password):
            if not user_data.get('is_confirmed', False):
                flash('Molimo potvrdite vašu e-mail adresu prije prijave.', category='warning')
                return redirect(url_for('login'))
            user = User(user_data['email'])
            login_user(user, form.remember_me.data)
            identity_changed.send(app, identity=Identity(user.id))
            next = request.args.get('next')
            if next is None or not next.startswith('/'):
                next = url_for('index')
            flash('Uspješno ste se prijavili!', category='success')
            return redirect(next)
        flash('Neispravno korisničko ime ili zaporka!', category='warning')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Odjavili ste se.', category='success')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = request.form['email']
        password = request.form['password']
        existing_user = users_collection.find_one({"email": email})

        if existing_user:
            flash('Korisnik već postoji', category='error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        users_collection.insert_one({
            "email": email,
            "password": hashed_password,
            "is_confirmed": False
        })
        send_confirmation_email(email)
        flash('Registracija uspješna. Sad se možete prijaviti', category='success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-confirmation-salt')

def confirm_token(token, expiration=3600):  # Token expires in 1 hour
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='email-confirmation-salt', max_age=expiration)
    except:
        return False
    return email

def send_confirmation_email(user_email):
    token = generate_confirmation_token(user_email)
    confirm_url = url_for('confirm_email', token=token, _external=True)
    html = render_template('email_confirmation.html', confirm_url=confirm_url)
    subject = "Molimo potvrdite email adresu"
    msg = Message(subject, recipients=[user_email], html=html)
    mail.send(msg)

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)
    except:
        flash('Link za potvrdu je neisprava ili je istekao.', 'danger')
        return redirect(url_for('unconfirmed'))

    user = users_collection.find_one({'email': email})
    if user['is_confirmed']:
        flash('Vaš račun je već potvrđen. Molimo prijavite se.', 'success')
    else:
        users_collection.update_one({'email': email}, {'$set': {'is_confirmed': True}})
        flash('Vaš račun je potvrđen. Hvala! Molimo prijavite se.', 'success')
    
    return redirect(url_for('login'))


def update_user_data(user_data, form):
    if form.validate_on_submit():
        db.users.update_one(
        {"_id": user_data['_id']},
        {"$set": {
            "first_name": form.first_name.data,
            "last_name": form.last_name.data,
            "bio": form.bio.data,
            "theme": form.theme.data
        }}
        )
        if form.image.data:
            # Pobrišimo postojeću ako postoji
            if hasattr(user_data, 'image_id') and user_data.image_id:
                fs.delete(user_data.image_id)
            
            image_id = save_image_to_gridfs(request, fs)
            if image_id != None:
                users_collection.update_one(
                {"_id": user_data['_id']},
                {"$set": {
                    'image_id': image_id,
                }}
            )
        flash("Podaci uspješno ažurirani!", "success")
        return True
    return False

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_data = users_collection.find_one({"email": current_user.get_id()})
    form = ProfileForm(data=user_data)
    title = "Vaš profil"
    if update_user_data(user_data, form):
        return redirect(url_for('profile'))
    return render_template('profile.html', form=form, image_id=user_data.get("image_id"), title=title)

@app.route('/user/<user_id>', methods=['GET', 'POST'])
@login_required
@admin_permission.require(http_exception=403)
def user_edit(user_id):
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    form = UserForm(data=user_data)
    title = "Korisnički profil"
    if update_user_data(user_data, form):
        return redirect(url_for('users'))
    return render_template('profile.html', form=form, image_id=user_data.get("image_id"), title=title)

@app.route("/my_recepti")
@login_required
def my_recepti():
    recepti = recepti_collection.find({"autor": current_user.get_id()}).sort("datum", -1)
    return render_template("my_recepti.html", recepti=recepti)

