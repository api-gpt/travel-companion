from flask import (
    Blueprint,
    url_for,
    session,
    redirect,
    current_app,
    abort,
    request
)
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from app.db.database import Database
import secrets

load_dotenv()

oauth_bp = Blueprint('oauth', __name__)
oauth = OAuth()
database = Database()

# Create user table if it doesn't exist
database.create_user_table()


def configure_oauth(app):
    oauth.init_app(app=app)
    providers = app.config['OAUTH2_PROVIDERS']

    for provider, config in providers.items():
        if provider == 'google':
            oauth.register(
                name=provider,
                client_id=config['client_id'],
                client_secret=config['client_secret'],
                access_token_url=config['token_url'],
                access_token_params=None,
                authorize_url=config['authorize_url'],
                authorize_params=None,
                api_base_url=config['api_base_url'],
                client_kwargs=config['client_kwargs'],
                jwks_uri=config['jwks_uri']
            )
        else:
            oauth.register(
                name=provider,
                client_id=config['client_id'],
                client_secret=config['client_secret'],
                access_token_url=config['token_url'],
                access_token_params=None,
                authorize_url=config['authorize_url'],
                authorize_params=None,
                api_base_url=config['api_base_url'],
                client_kwargs=config['client_kwargs']
            )


@oauth_bp.route('/login/<provider>')
def oauth2_login(provider):
    provider_data = current_app.config['OAUTH2_PROVIDERS'].get(provider)
    if provider_data is None:
        abort(404)

    # Generate random string for state parameter
    state = secrets.token_urlsafe(16)
    session['oauth2_state'] = state
    session['return_url'] = request.args.get('next') or url_for('web.home')

    # Dynamically create the client and authorize redirect
    redirect_uri = url_for('oauth.oauth2_authorize',
                           provider=provider, _external=True)
    return (oauth.create_client(provider)
            .authorize_redirect(redirect_uri, state=state))


##############################################
#
# Create the redirect authorization endpoint to show user profile
# Retrieve the token, profile, and store it in the session
#
##############################################
@oauth_bp.route('/authorize/<provider>')
def oauth2_authorize(provider):
    # Create the client to be used for authorization
    client = oauth.create_client(provider)
    if not client:
        abort(404)
    try:
        # Validate state parameter
        if request.args.get('state') != session.get('oauth2_state'):
            abort(403)
        token = client.authorize_access_token()
        session['token'] = token
        # Facebook uses /me as beginning of endpoint
        if provider == 'facebook':
            resp = client.get('me?fields=id,name,email', token=token)
        elif provider == 'google':
            resp = client.get('userinfo', token=token)
        else:
            resp = client.get('user', token=token)

        # Store the user profile in the session
        profile = resp.json()
        session['profile'] = profile
        
        # get user's 'name' and extract first and last name from it
        split_name = str.split(profile['name'], ' ')
        
        # Extract user data from profile
        user_data = {
            'provider': provider,
            'access_token': token['access_token'],
            'first_name': split_name[0] or profile.get('first_name', ''),
            'last_name': split_name[1] or profile.get('last_name', ''),
            'email': profile.get('email'),
            'url': profile.get('html_url', ''),
            'id': profile.get('sub') or profile.get('id')
        }
        
        # Insert data into 'users' table in database and store
        # id in session
        user_id = database.insert_user(user_data)
        session['id'] = user_id

        return_url = session.pop('return_url', url_for('web.home'))
        return redirect(return_url)
    except Exception as err:
        return f'Authorization failed: {err}', 400


@oauth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('web.home'))

# Resources Used:
# https://docs.authlib.org/en/latest/client/frameworks.html#frameworks-clients
# https://flask.palletsprojects.com/en/3.0.x/blueprints/
# https://docs.authlib.org/en/latest/client/frameworks.html
