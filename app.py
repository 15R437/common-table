import sys
import os
import numpy as np
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, render_template, request, jsonify, url_for,flash,redirect,sessions
from forms import RegistrationForm,LoginForm
from logic.optimisers import SimAnnealer
from logic.models import generate_similarity_matrix
import random
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = '1ee25c6972e25637de13505caf702cb1'

def connect():
    connection = sqlite3.connect()
    cursor = connection.cursor()
    return connection,cursor

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/planner')
def planner():
    return render_template('planner.html')

@app.route('/register',methods=['GET'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        flash(f"Welcome {form.first_name.data}!",'success')
        return redirect(url_for('index'))
    return render_template('register.html',title='Register',form=form)

@app.route('/register', methods=['POST'])
def process_register():
    request.form
    



@app.route('/login')
def login():
    form = LoginForm()
    return render_template('login.html',title='Login',form=form)

if __name__ == '__main__':
    app.secret_key = os.urandom(12)
    app.run(debug=True,host="0.0.0.0",port="80")