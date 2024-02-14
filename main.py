from flask import Flask , render_template, request, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import SearchField, SelectField, StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Email
import pandas as pd
import requests
import flask_login
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap4
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get('FLASK_KEY', 'nothingspecial')
# To generate your own key run: python -c 'import secrets; print(secrets.token_hex())'
login_manager = LoginManager()
login_manager.init_app(app)
bootstrap = Bootstrap4(app)

# create the extension
db = SQLAlchemy()
# configure the SQLite database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DB_URI', 'sqlite:///books.db')
# initialize the app with the extension
db.init_app(app)

# Tables in Databasse
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=False)
    name = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=False)
    address = db.Column(db.String)
    orders = relationship('Order', back_populates='user')


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String, nullable=False)
    volume_id = db.Column(db.String, nullable=False)
    user_id = db.Column(db.Integer, ForeignKey('users.id'))
    user = relationship("User", back_populates='orders')

#creating tables
with app.app_context():
    db.create_all()

#login manager for user management
@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.Select(User).where(User.id == user_id)).scalar()

#reading the data
data = pd.read_csv('static/main_dataset.csv')
data.dropna()
data['price'] = pd.to_numeric(data['price'])
data['price'] = data['price']*83
data['price'] = data['price'].round()
data.isbn = pd.to_numeric(data.isbn)

def get_formatted_list(r):
    sbook = []
    img_url = r['volumeInfo']['imageLinks']['thumbnail']
    sbook.append(img_url)
    sbook.append(r['volumeInfo']['title'])
    sbook.append(r['volumeInfo']['authors'][0])
    sbook.append(r['volumeInfo']['printType'])
    try:
        sbook.append(r['volumeInfo']['averageRating'])
    except:
        sbook.append(0)
    sbook.append(r['saleInfo']['listPrice']['amount'])
    sbook.append(r['saleInfo']['listPrice']['currencyCode'])
    sbook.append(0)
    sbook.append(r['volumeInfo']['industryIdentifiers'][0]['identifier'])
    sbook.append(r['volumeInfo']['categories'][0])
    sbook.append(sbook[0])
    return sbook


#html forms to display on website using wtforms
class SearchForm(FlaskForm):
    q = SearchField('Search', render_kw={"placeholder": "Search..."}, validators=[DataRequired()])
    category = SelectField('Category', choices=['All', 'Fiction', 'Non-Fiction'])


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    login = SubmitField('Log in')

class RegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    login = SubmitField('Sign up')

class SearchFilter(FlaskForm):
    ebook_type = SelectField('Ebook Type', choices=['free', 'paid', 'PaperBack'])
    language = SelectField('Language', choices=['English'], render_kw={"placeholder": "All"})
    order_by = SelectField('Order by', choices=['Relevance', 'Newest'])
    show = SubmitField('Apply Filters')

#Making the routes for webpages
@app.route('/')
def home():
    sform = SearchForm()
    s_books = data.sample(4).values.tolist()
    #getting cover images from google books api and volume id
    for b in s_books:
        try:
            r = requests.get('https://www.googleapis.com/books/v1/volumes', params={'q': b[8]}).json()
            img_url = r['items'][0]['volumeInfo']['imageLinks']['thumbnail']
            volume_id = r['items'][0]['id']
            b.append(volume_id)
            b[0] = img_url
        except:
            continue
    return render_template('index.html', books=s_books, sform=sform)

@app.route('/book')
def book():
    sform = SearchForm()
    volume_id = request.args.get('volume_id')
    isbn = int(request.args.get('isbn'))
    r = requests.get(f'https://www.googleapis.com/books/v1/volumes/{volume_id}').json()
    sbook = data.loc[data.isbn==isbn].values.tolist()
    return render_template('book.html', book=r, sbook=sbook[0], sform=sform)

@app.route('/book_info')
def book_info():
    sform = SearchForm()
    volume_id = request.args.get('volume_id')
    
    r = requests.get(f'https://www.googleapis.com/books/v1/volumes/{volume_id}').json()
    #making a copy of sbook instance
    sbook = get_formatted_list(r)

    return render_template('book.html', book=r, sbook=sbook, sform=sform)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if not flask_login.current_user.is_authenticated:
        return redirect(url_for('login'))
    #storing user response for orders
    if request.method=='POST':
        address={
                'First_Name':request.form.get('firstName'),
                'Last_Name':request.form.get('lastName'),
                'email':request.form.get('email'),
                'Address':request.form.get('address'),
                'Address2':request.form.get('address2'),
                'Country':request.form.get('country'),
                'Pin':request.form.get('zip'),
                'State':request.form.get('state')
            }
        volume_id = request.args.get('volume_id')
        new_order = Order(
            address=json.dumps(address),
            volume_id=volume_id,
            user=flask_login.current_user
        )
        db.session.add(new_order)
        db.session.commit()
        return redirect(url_for('home'))
    sform = SearchForm()
    volume_id = request.args.get('volume_id')
    r = requests.get(f'https://www.googleapis.com/books/v1/volumes/{volume_id}').json()
    sbook = get_formatted_list(r)
    return render_template('checkout.html', book=sbook, sform=sform)

@app.route('/search', methods=['GET', 'POST'])
def search():
    sform = SearchForm()
    sfilter = SearchFilter()
    q = request.form.get('q', 'Fiction')
    params = {'langRestrict' : 'en'}

    #To filter user searches and show relevant data
    if sfilter.validate_on_submit():
        if sfilter.ebook_type.data != 'PaperBack':
            params['filter'] =  f'{sfilter.ebook_type.data}-ebooks'
        if sfilter.order_by.data:
            params['order_by'] = sfilter.order_by.data
        params['q'] = request.args.get('q')
    else:
        params['q'] = q
    books_sdata = requests.get('https://www.googleapis.com/books/v1/volumes', params=params).json()
    return render_template('search.html',q=q, sform=sform, bdata=books_sdata, form = sfilter)

@app.route('/login', methods=['GET', 'POST'])
def login():
    sform = SearchForm()
    login_form = LoginForm()
    #login form check
    if login_form.validate_on_submit:
        email = login_form.email.data
        password = login_form.password.data
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('home'))
            else:
                return render_template("login.html",sform=sform, lform=login_form)
    return render_template('login.html', sform=sform, lform=login_form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    sform = SearchForm()
    rform = RegisterForm()
    #registering the user
    if rform.validate_on_submit():
        name=rform.name.data
        email=rform.email.data
        new_user=User(
            name=name,
            email=email,
            password=generate_password_hash(rform.password.data, method="pbkdf2:sha256", salt_length=6)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('orders'))
    return render_template('register.html', sform=sform, rform = rform)

@login_required
@app.route('/orders')
def orders():
    sform=SearchForm()
    orders=flask_login.current_user.orders
    orders_data=[]
    i=0
    for order in orders:
        r = requests.get(f'https://www.googleapis.com/books/v1/volumes/{order.volume_id}').json()
        orders_data.append(r)
        orders_data[i]['order_data']=order
        i+=1
    return render_template('orders.html', sform=sform, odata=orders_data, )

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run()
