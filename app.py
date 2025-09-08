from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, abort
from datetime import datetime
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
from flask_principal import Principal, Permission, RoleNeed, Identity, identity_changed, identity_loaded, UserNeed, Need

app = Flask(__name__)
app.secret_key = "supersecretkey123"

app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

client = MongoClient(os.getenv('MONGODB_CONNECTION_STRING'))
db = client['kuharica_database']
recepti_collection = db['recepti']
users_collection = db['users']
fs = gridfs.GridFS(db)
mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

principal = Principal(app)
admin_permission = Permission(RoleNeed('admin'))
author_permission = Permission(RoleNeed('author'))

class User(UserMixin):
    def __init__(self, email, admin=False, theme=''):
        self.id = email
        self.admin = admin is True
        self.theme = theme

    @classmethod
    def get(cls, user_id):
        user_data = users_collection.find_one({"email": user_id})
        if user_data:
            return cls(user_data['email'], user_data.get('is_admin'), user_data.get('theme'))
        raise UserNotFoundError()

    @property
    def is_admin(self):
        return self.admin

class UserNotFoundError(Exception):
    pass

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.get(user_id)
    except UserNotFoundError:
        return None


def edit_recept_permission(recept_id):
    return Permission(Need('edit_recept', str(ObjectId(recept_id))))


@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    if current_user.is_authenticated:
        identity.user = current_user
        identity.provides.add(UserNeed(current_user.id))
        identity.provides.add(RoleNeed('author'))

        if getattr(current_user, 'is_admin', False):
            identity.provides.add(RoleNeed('admin'))

        user_recepti = recepti_collection.find({"user_id": current_user.get_id()})
        for recept in user_recepti:
            recept_id = recept.get("_id")
            if recept_id:
                # Kreiranje Need direktno, bez nasljeđivanja
                identity.provides.add(Need('edit_recept', str(recept_id)))
                print(f" Dodano pravo za recept ID: {recept_id}")
            else:
                print(" Recept bez _id, preskačem...")

            
@app.route("/")
def index():
    recepti = recepti_collection.find().sort("date", -1)
    return render_template("index.html", recepti=recepti)

@app.route("/recept/create", methods=["GET", "POST"])
@login_required
def recept_create():
    form = ReceptForm()
    if form.validate_on_submit():
        recept = {
            "title": form.title.data,
            "description": form.description.data,
            "ingredients": form.ingredients.data,
            "instructions": form.instructions.data,
            "category": form.category.data,
            "vrijeme_pripreme": form.vrijeme_pripreme.data,
            "date": datetime.combine(form.date.data, datetime.min.time()) if form.date.data else None,
            "status": form.status.data,
            "tags": form.tags.data,
            "user_id": current_user.id,
            "created_at": datetime.utcnow()
        }

        image_id = save_image_to_gridfs(request, fs)
        if image_id:
            recept["image_id"] = image_id

        print("Spremljeni recept:", recept)  # DEBUG
        recepti_collection.insert_one(recept)
        flash("Recept uspješno dodan!", "success")
        return redirect(url_for("index"))
    else:
        if request.method == "POST":
            print(" Forma nije prošla validaciju")
            print(" POST data:", request.form)
            print(" Form errors:", form.errors)
    return render_template("recept_edit.html", form=form)


@app.route("/recept/<recept_id>")
def recept_view(recept_id):
    recept = recepti_collection.find_one({"_id": ObjectId(recept_id)})
    if not recept:
        flash("Recept nije pronađen!", "danger")
        return redirect(url_for("index"))
    return render_template("recept_view.html", recept=recept, edit_recept_permission=edit_recept_permission)

@app.route('/recept/edit/<recept_id>', methods=['GET', 'POST'])
@login_required
def recept_edit(recept_id):
    recept = recepti_collection.find_one({"_id": ObjectId(recept_id)})
    if not recept:
        flash("Recept ne postoji", "danger")
        return redirect(url_for('my_recepti'))

    permission = edit_recept_permission(recept_id)
    if not permission.can():
        flash("Nemate pravo uređivanja ovog recepta", "danger")
        return redirect(url_for('my_recepti'))

    form = ReceptForm(data={
        "title": recept.get("title"),
        "description": recept.get("description"),
        "ingredients": recept.get("ingredients"),
        "instructions": recept.get("instructions"),
        "category": recept.get("category"),
        "vrijeme_pripreme": recept.get("vrijeme_pripreme"),
        "date": recept.get("date"),
        "status": recept.get("status"),
        "tags": recept.get("tags"),
    })

    if form.validate_on_submit():
        update_data = {
            "title": form.title.data,
            "description": form.description.data,
            "ingredients": form.ingredients.data,
            "instructions": form.instructions.data,
            "category": form.category.data,
            "vrijeme_pripreme": form.vrijeme_pripreme.data,
            "date": datetime.combine(form.date.data, datetime.min.time()) if form.date.data else None,
            "status": form.status.data,
            "tags": form.tags.data,
            "updated_at": datetime.utcnow()
        }

        image_id = save_image_to_gridfs(request, fs)
        if image_id:
            update_data["image_id"] = image_id

        recepti_collection.update_one({"_id": ObjectId(recept_id)}, {"$set": update_data})
        flash("Recept je uspješno ažuriran", "success")
        return redirect(url_for('my_recepti'))

    return render_template("recept_edit.html", form=form, recept=recept)

@app.route('/recept/delete', methods=['POST'])
@login_required
def delete_recept():
    data = request.get_json()
    recept_id = data.get('recept_id')
    if not recept_id:
        return jsonify({"error": "Nema ID recepta"}), 400

   
    permission = edit_recept_permission(recept_id)
    if not permission.can():
        return jsonify({"error": "Nemate pravo brisanja ovog recepta"}), 403

    recepti_collection.delete_one({"_id": ObjectId(recept_id)})
    return jsonify({"success": True}), 200

def save_image_to_gridfs(request, fs):
    if 'image' in request.files:
        image = request.files['image']
        if image.filename:
            return fs.put(image, filename=image.filename, content_type=image.content_type)
    return None

@app.route('/image/<image_id>')
def serve_image(image_id):
    image = fs.get(ObjectId(image_id))
    return image.read(), 200, {'Content-Type': image.content_type}


@app.template_filter('markdown')
def markdown_filter(text):
    return markdown.markdown(text)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = request.form['email']
        password = request.form['password']
        user_data = users_collection.find_one({"email": email})

        if user_data and check_password_hash(user_data['password'], password):
            #if not user_data.get('is_confirmed', False):
            #    #flash('Molimo potvrdite vašu e-mail adresu prije prijave.', category='warning')
            #    return redirect(url_for('login'))
            user = User(user_data['email'], user_data.get('is_admin', False))
            login_user(user, form.remember_me.data)
            identity_changed.send(app, identity=Identity(user.id))
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('index')
            flash('Uspješno ste se prijavili!', category='success')
            return redirect(next_page)
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
        #send_confirmation_email(email)
        flash('Registracija uspješna. Sad se možete prijaviti', category='success')
        return redirect(url_for('login'))


    return render_template('register.html', form=form)

def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-confirmation-salt')

def confirm_token(token, expiration=3600):
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
    email = confirm_token(token)
    if not email:
        flash('Link za potvrdu je neispravan ili je istekao.', 'danger')
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
        users_collection.update_one(
            {"_id": user_data['_id']},
            {"$set": {
                "first_name": form.first_name.data,
                "last_name": form.last_name.data,
                "bio": form.bio.data,
                "theme": form.theme.data
            }}
        )
        if form.image.data:
            if "image_id" in user_data and user_data["image_id"]:
                fs.delete(user_data["image_id"])
            image_id = save_image_to_gridfs(request, fs)
            if image_id:
                users_collection.update_one(
                    {"_id": user_data['_id']},
                    {"$set": {"image_id": image_id}}
                )
        flash("Podaci uspješno ažurirani!", "success")
        return True
    return False

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_data = users_collection.find_one({"email": current_user.get_id()})
    form = ProfileForm(data=user_data)
    if update_user_data(user_data, form):
        return redirect(url_for('profile'))
    return render_template('profile.html', form=form, image_id=user_data.get("image_id"), title="Vaš profil")

@app.route('/user/<user_id>', methods=['GET', 'POST'])
@login_required
@admin_permission.require(http_exception=403)
def user_edit(user_id):
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    form = UserForm(data=user_data)
    if update_user_data(user_data, form):
        return redirect(url_for('users'))
    return render_template('profile.html', form=form, image_id=user_data.get("image_id"), title="Korisnički profil")

@app.route("/my_recepti")
@login_required
def my_recepti():
    recepti = recepti_collection.find({"user_id": current_user.get_id()}).sort("date", -1)
    return render_template("my_recepti.html", recepti=recepti)

@app.route('/users')
@login_required
@admin_permission.require(http_exception=403)
def users():
    users = users_collection.find().sort("email")
    return render_template('users.html', users=users)

def localize_status(status):
    return {"draft": "Skica", "published": "Objavljen"}.get(status, status)

app.jinja_env.filters['localize_status'] = localize_status

@app.errorhandler(403)
def access_denied(e):
    return render_template('403.html', description=e.description), 403