from uuid import uuid4

from flask import (Blueprint, render_template, current_app, request,
                   flash, url_for, redirect, session, abort)
from flask.ext.mail import Message
from flask.ext.babel import gettext as _
from flask.ext.login import login_required, login_user, current_user, logout_user, confirm_login, login_fresh

from ..extensions import db, mail, login_manager

from .models import User
from .forms import SignupForm, LoginForm, RecoverPasswordForm, ReauthForm, ChangePasswordForm

user = Blueprint('user', __name__)


@user.route('/users')
def index():
    if current_user.is_authenticated():
        return redirect(url_for('user.index'))

    page = int(request.args.get('page', 1))
    pagination = User.query.paginate(page=page, per_page=10)
    return render_template('user/index.html', pagination=pagination)


@user.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated():
        return redirect(url_for('admin.admin_dash'))

    form = LoginForm(login=request.args.get('login', None),
                     next=request.args.get('next', None))

    if form.validate_on_submit():
        user, authenticated = User.authenticate(form.login.data,
                                                form.password.data)

        if user and authenticated:
            remember = request.form.get('remember') == 'y'
            if login_user(user, remember=remember):
                flash(_("Logged in"), 'success')
            return redirect(form.next.data or url_for('admin.admin_dash'))
        else:
            flash(_('Sorry, invalid login'), 'warning')

    return render_template('user/login.html', form=form)


@user.route('/reauth', methods=['GET', 'POST'])
@login_required
def reauth():
    form = ReauthForm(next=request.args.get('next'))

    if request.method == 'POST':
        user, authenticated = User.authenticate(current_user.name,
                                                form.password.data)
        if user and authenticated:
            confirm_login()
            flash(_('Reauthenticated.'), 'success')
            return redirect('/change_password')

        flash(_('Password is wrong.'), 'warning')
    return render_template('user/reauth.html', form=form)


@user.route('/logout')
@login_required
def logout():
    logout_user()
    flash(_('Logged out'), 'success')
    return redirect(url_for('admin.index'))


@user.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated():
        return redirect(url_for('admin.admin_dash'))

    form = SignupForm(next=request.args.get('next'))

    if form.validate_on_submit():
        user = User()
        form.populate_obj(user)

        db.session.add(user)
        db.session.commit()

        if login_user(user):
            return redirect(form.next.data or url_for('user.index'))

    return render_template('user/signup.html', form=form)


@user.route('/change_password', methods=['GET', 'POST'])
def change_password():
    user = None
    if current_user.is_authenticated():
        if not login_fresh():
            return login_manager.needs_refresh()
        user = current_user
    elif 'activation_key' in request.values and 'email' in request.values:
        activation_key = request.values['activation_key']
        email = request.values['email']
        user = User.query.filter_by(activation_key=activation_key) \
                         .filter_by(email=email).first()

    if user is None:
        abort(403)

    form = ChangePasswordForm(activation_key=user.activation_key)

    if form.validate_on_submit():
        user.password = form.password.data
        user.activation_key = None
        db.session.add(user)
        db.session.commit()

        flash(_("Your password has been changed, please log in again"),
              "success")
        return redirect(url_for("user.login"))

    return render_template("user/change_password.html", form=form)


@user.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    form = RecoverPasswordForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            flash(_('Please see your email for instructions on how to access your account'), 'success')

            user.activation_key = str(uuid4())
            db.session.add(user)
            db.session.commit()

            url = url_for('user.change_password', email=user.email, activation_key=user.activation_key, _external=True)
            html = render_template('macros/_reset_password.html', project=current_app.config['PROJECT'], username=user.name, url=url)
            message = Message(subject='Reset your password in ' + current_app.config['PROJECT'], html=html, recipients=[user.email])
            mail.send(message)

            return render_template('user/reset_password.html', form=form)
        else:
            flash(_('Sorry, no user found for that email address'), 'error')

    return render_template('user/reset_password.html', form=form)


@user.route('/lang/', methods=['POST'])
def lang():
    session['language'] = request.form['language']
    new_language = current_app.config['ACCEPT_LANGUAGES'][request.form['language']]
    flash(_('Language changed to ')+new_language, 'success')
    return redirect(url_for('admin.admin_dash'))