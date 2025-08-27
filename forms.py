from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DateField, FileField, SubmitField, RadioField, PasswordField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from datetime import datetime
from flask_wtf.file import FileAllowed

class RecipeForm(FlaskForm):
    title = StringField('Naziv recepta', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Kratki opis', validators=[Length(max=300)])
    ingredients = TextAreaField('Sastojci', render_kw={"placeholder": "Npr. 200g brašna, 2 jaja, 1 žlica šećera..."}, validators=[DataRequired()])
    instructions = TextAreaField('Upute za pripremu', render_kw={"id": "markdown-editor"}, validators=[DataRequired()])
    category = SelectField('Kategorija', choices=[
        ('predjelo', 'Predjelo'),
        ('glavno_jelo', 'Glavno jelo'),
        ('desert', 'Desert'),
        ('napitak', 'Napitak'),
        ('ostalo', 'Ostalo')
    ])
    date = DateField('Datum dodavanja', default=datetime.today)
    status = RadioField('Status', choices=[('draft', 'Skica'), ('published', 'Objavljeno')], default='draft')
    tags = StringField('Oznake', render_kw={"id": "tags"})
    image = FileField('Fotografija recepta', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Samo slike!')])
    submit = SubmitField('Spremi recept')

class LoginForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired(), Length(1, 64), Email()])
    password = PasswordField('Zaporka', validators=[DataRequired()])
    remember_me = BooleanField('Ostani prijavljen')
    submit = SubmitField('Prijava')

class RegisterForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired(), Length(3, 64), Email()])
    password = PasswordField('Zaporka', validators=[DataRequired(), EqualTo('password2', message='Zaporke moraju biti jednake.')])
    password2 = PasswordField('Potvrdi zaporku', validators=[DataRequired()])
    submit = SubmitField('Registracija')

class ProfileForm(FlaskForm):
    first_name = StringField("Ime", validators=[DataRequired(), Length(max=50)])
    last_name = StringField("Prezime", validators=[DataRequired(), Length(max=50)])
    bio = TextAreaField("O meni", validators=[Length(max=1000)], render_kw={"id": "markdown-editor"})
    theme = SelectField('Tema', choices=[
        ('', ''),
        ('cerulean', 'Cerulean'),
        ('cosmo', 'Cosmo'),
        ('cyborg', 'Cyborg'),
        ('darkly', 'Darkly'),
        ('flatly', 'Flatly'),
        ('journal', 'Journal'),
        ('litera', 'Litera'),
        ('lumen', 'Lumen'),
        ('lux', 'Lux'),
        ('materia', 'Materia'),
        ('minty', 'Minty'),
        ('morph', 'Morph'),
        ('pulse', 'Pulse'),
        ('quartz', 'Quartz'),
        ('sandstone', 'Sandstone'),
        ('simplex', 'Simplex'),
        ('sketchy', 'Sketchy'),
        ('slate', 'Slate'),
        ('solar', 'Solar'),
        ('spacelab', 'Spacelab'),
        ('superhero', 'Superhero'),
        ('united', 'United'),
        ('vapor', 'Vapor'),
        ('yeti', 'Yeti'),
        ('zephyr', 'Zephyr')
    ])
    image = FileField('Vaša slika', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Samo slike!')])
    submit = SubmitField("Spremi")

class UserForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Length(3, 64), Email()])
    first_name = StringField("Ime", validators=[DataRequired(), Length(max=50)])
    last_name = StringField("Prezime", validators=[DataRequired(), Length(max=50)])
    is_confirmed = BooleanField('Potvrđen')
    bio = TextAreaField("O korisniku", validators=[Length(max=1000)], render_kw={"id": "markdown-editor"})
    theme = SelectField('Tema', choices=[
        ('', ''),
        ('cerulean', 'Cerulean'),
        ('cosmo', 'Cosmo'),
        ('cyborg', 'Cyborg'),
        ('darkly', 'Darkly'),
        ('flatly', 'Flatly'),
        ('journal', 'Journal'),
        ('litera', 'Litera'),
        ('lumen', 'Lumen'),
        ('lux', 'Lux'),
        ('materia', 'Materia'),
        ('minty', 'Minty'),
        ('morph', 'Morph'),
        ('pulse', 'Pulse'),
        ('quartz', 'Quartz'),
        ('sandstone', 'Sandstone'),
        ('simplex', 'Simplex'),
        ('sketchy', 'Sketchy'),
        ('slate', 'Slate'),
        ('solar', 'Solar'),
        ('spacelab', 'Spacelab'),
        ('superhero', 'Superhero'),
        ('united', 'United'),
        ('vapor', 'Vapor'),
        ('yeti', 'Yeti'),
        ('zephyr', 'Zephyr')
    ])
    image = FileField('Slika', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Samo slike!')])
    submit = SubmitField("Spremi")