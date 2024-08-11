from flask import Flask, session
from flask_session import Session
from auth.oauth import oauth_bp, configure_oauth
from routes.web import web_bp, fetch_weather_update
from dotenv import load_dotenv
import threading

load_dotenv()

notification_update = {}


def start_notification_thread():
    notification_thread = threading.Thread(target=fetch_weather_update)
    notification_thread.start()


app = Flask(__name__)
app.config.from_object('config.DevelopmentConfig')

app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Initialize OAuth2.0 providers configurations
configure_oauth(app)

# Initialize OAuth and register blueprints
app.register_blueprint(oauth_bp)
app.register_blueprint(web_bp, url_prefix='/')

# Start the notification thread
start_notification_thread()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
