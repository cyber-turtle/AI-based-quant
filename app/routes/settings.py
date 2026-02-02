from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import RiskSettings, Strategy, UserPreferences
from app.forms import RiskSettingsForm # Start using forms for robust handling? Or simplified for now.

settings = Blueprint('settings', __name__)

@settings.route('/strategies', methods=['GET', 'POST'])
@login_required
def strategies():
    user_strategies = Strategy.query.filter_by(user_id=current_user.id).all()
    # Simple Toggle Logic (POST)
    if request.method == 'POST':
        strat_id = request.form.get('strategy_id')
        strat = Strategy.query.get(strat_id)
        if strat and strat.user_id == current_user.id:
            strat.is_active = not strat.is_active
            db.session.commit()
            flash(f"Updated {strat.name}", "success")
            return redirect(url_for('settings.strategies'))
            
    return render_template('settings/strategies.html', strategies=user_strategies)

@settings.route('/risk', methods=['GET', 'POST'])
@login_required
def risk():
    risk_settings = RiskSettings.query.filter_by(user_id=current_user.id).first()
    if not risk_settings:
        # Create default if missing (should be handled by signal check but good to have here)
        risk_settings = RiskSettings(user_id=current_user.id)
        db.session.add(risk_settings)
        db.session.commit()

    if request.method == 'POST':
        # Update Settings
        try:
            risk_settings.max_drawdown_percent = float(request.form.get('max_drawdown'))
            risk_settings.daily_loss_limit_percent = float(request.form.get('daily_loss'))
            risk_settings.position_size_percent = float(request.form.get('position_size'))
            risk_settings.max_open_positions = int(request.form.get('max_positions'))
            risk_settings.require_stop_loss = 'require_stop_loss' in request.form
            
            db.session.commit()
            flash("Risk Settings Updated", "success")
        except ValueError:
            flash("Invalid Input", "danger")
        
        return redirect(url_for('settings.risk'))

    return render_template('settings/risk.html', risk=risk_settings)

@settings.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.session.add(prefs)
        db.session.commit()
        
    if request.method == 'POST':
        prefs.mt5_account = request.form.get('mt5_account')
        prefs.mt5_password = request.form.get('mt5_password')
        prefs.mt5_server = request.form.get('mt5_server')
        # Here we would verify connection
        db.session.commit()
        flash("Account Creds Saved", "success")
        return redirect(url_for('settings.account'))
        
    return render_template('settings/account.html', prefs=prefs)
