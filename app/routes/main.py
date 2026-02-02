from flask import Blueprint, render_template

main = Blueprint('main', __name__)
auth = Blueprint('auth', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/dashboard')
def dashboard():
    return render_template('dashboard/index.html')

@auth.route('/login')
def login():
    return render_template('auth/login.html')
