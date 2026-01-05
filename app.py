import sys
import os
import numpy as np
from flask import Flask, render_template, request, jsonify, url_for,flash,redirect,sessions
from forms import RegistrationForm,LoginForm
from models import db, User
from flask_login import LoginManager, login_user,logout_user,login_required,current_user
import random
import sqlite3

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)
app.config['SECRET_KEY'] = '1ee25c6972e25637de13505caf702cb1'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir,'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SQLALCHEMY_ECHO"] = True

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login if not authenticated

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register',methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    
    form = LoginForm()
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email):
            flash('Email is already linked to an account.','error')
            return redirect(url_for('register'))
        else:
            new_user = User(username=username,email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            flash(f'Successfuly registered {username}')
            return redirect(url_for('login'))
        
    return render_template('register.html',form=form)

@app.route('/login',methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    
    if request.method=='POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email)
        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Invalid username or password','error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out','info')
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    return render_template('profile.html',username=current_user.username)

@app.route('/planner')
def planner():
    return render_template('planner.html')

if __name__ == '__main__':
    app.secret_key = os.urandom(12)
    app.run(debug=True,host="0.0.0.0",port="80")