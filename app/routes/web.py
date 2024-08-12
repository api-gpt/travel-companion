
from flask import (Blueprint, render_template, abort, request, jsonify,
                   session, url_for, redirect)
from jinja2 import TemplateNotFound
import requests
import os
# import threading
import json

web_bp = Blueprint('web', __name__,
                   static_folder='../web/static',
                   template_folder='templates')

ERROR_MESSAGE_400 = {"Error": "The request body is invalid"}

notification_update = {}
get_itinerary_data = {}
get_weather_data = {}

PROMPT_SVC_URL = os.getenv('PROMPT_SVC_URL')


@web_bp.route('/', methods=['GET'])
def home():
    try:
        # simulate log-in as test_user_id
        # session['id'] = 'test_user_id'
        return render_template('index.html')
    except TemplateNotFound:
        abort(404)


@web_bp.route('/plan-a-trip', methods=['GET'])
def plan_a_trip():
    try:
        return render_template('plan-a-trip.html')
    except TemplateNotFound:
        abort(404)


# routed from "Get Itinerary" button (bottom-left) on Plan a Trip page
@web_bp.route('/plan-a-trip', methods=['POST'])
def plan_a_trip_post():

    global get_itinerary_data

    # Get form data
    content = request.form.to_dict()
    destination = content.get('destination')

    # Contact prompt-svc for trip planning
    gpt_response = promptServiceInitialReq(content)

    # returns trip_id
    trip_id = gpt_response['trip_id']
    gpt_message = gpt_response['gpt-message']
    itinerary_data_out = generate_itinerary_data(gpt_message)

    # Fetch weather update for the destination
    fetch_weather_update(destination)

    # Binds trip_id to plan-a-trip.html
    return render_template('plan-a-trip.html',
                           notification_update=notification_update,
                           itinerary_data=itinerary_data_out,
                           trip_id=trip_id)


# renders a trip by trip_id with most recent itinerary
@web_bp.route('/plan-a-trip/<int:trip_id>', methods=['GET'])
def plan_a_trip_get(trip_id):

    global get_itinerary_data

    # Contact prompt-svc to retrieve trip's most recent itinerary
    gpt_response = promptServiceGetTrip(trip_id)

    # returns trip_id
    gpt_message = gpt_response['gpt-message']
    destination = gpt_response['destination']
    itinerary_data_out = generate_itinerary_data(gpt_message)

    # Fetch weather update for the destination
    fetch_weather_update(destination)

    # Binds trip_id to plan-a-trip.html
    return render_template('plan-a-trip.html',
                           notification_update=notification_update,
                           itinerary_data=itinerary_data_out,
                           trip_id=trip_id)


# routed from "Send" button (bottom-right) on Plan a Trip page
@web_bp.route('/chat-plan-a-trip/<int:trip_id>', methods=['POST'])
def plan_a_trip_chat(trip_id):
    content = request.get_json()
    message = content.get('message')

    print(f"routed to chat-plan-a-trip for trip_id: {trip_id}")

    if not message:
        return jsonify(ERROR_MESSAGE_400), 400

    # Contact prompt-svc to chat trip itinerary
    gpt_message = promptServiceChat({"message": message,
                                     "trip_id": trip_id})

    # extract messages from response
    gpt_chat_response = gpt_message['messages']

    return jsonify({'gpt_chat_response': gpt_chat_response})


# routed from "Update Itinerary" button (top of chat box) on Plan a Trip page
@web_bp.route('/update-plan-a-trip/<int:trip_id>', methods=['POST'])
def plan_a_trip_update(trip_id):

    print(f"routed to update-plan-a-trip for trip_id: {trip_id}")

    # Contact prompt-svc to update trip itinerary
    gpt_response = promptServiceUpdate({"trip_id": trip_id})

    # extract messages from response, then jsonify it
    gpt_message = gpt_response['gpt-message']
    destination = gpt_response['destination']
    itinerary_data_out = generate_itinerary_data(gpt_message)

    # weather service
    fetch_weather_update(destination)

    # Binds trip_id to plan-a-trip.html
    return render_template('plan-a-trip.html',
                           notification_update=notification_update,
                           itinerary_data=itinerary_data_out,
                           trip_id=trip_id)


@web_bp.route('/recommendations', methods=['GET'])
def recommendations():
    try:
        weather_data = generate_weather_data(get_weather_data)
        return render_template('recommendations.html',
                               notification_update=notification_update,
                               weather_data=weather_data,
                               itinerary_data=get_itinerary_data,
                               promptUrl=promptSvcUrl())
    except TemplateNotFound:
        abort(404)


@web_bp.route('/login-method', methods=['GET'])
def login_method():
    try:
        return render_template('login-method.html')
    except TemplateNotFound:
        abort(404)


@web_bp.route('/profile', methods=['GET'])
def profile():
    try:
        p = promptServiceGetProfile()

        if p is None or 'error' in p:
            return render_template('profile.html')
        else:
            return render_template('profile.html',
                                   age=p.get('age'),
                                   travelStyle=p.get('travelStyle'),
                                   travelPriorities=p.get('travelPriorities'),
                                   travelAvoidances=p.get('travelAvoidances'),
                                   dietaryRestrictions=p.get(
                                       'dietaryRestrictions'),
                                   accomodations=p.get('accomodations'))
    except TemplateNotFound:
        abort(404)


@web_bp.route('/profile', methods=['POST'])
def profile_post():

    # Get form data
    content = request.form
    age = content.get('age')
    travelStyle = content.get('travel-style')
    travelPriorities = content.get('travel-priorities')
    travelAvoidances = content.get('travel-avoidances')
    dietaryRestrictions = content.get('dietary-restrictions')
    accomodations = content.get('accomodations')

    # Update profile
    response = promptServiceUpdateProfile(content)

    try:
        if response is None or 'error' in response:
            return render_template('profile.html')

        return render_template('profile.html',
                               age=age,
                               travelStyle=travelStyle,
                               travelPriorities=travelPriorities,
                               travelAvoidances=travelAvoidances,
                               dietaryRestrictions=dietaryRestrictions,
                               accomodations=accomodations)
    except TemplateNotFound:
        abort(404)


@web_bp.route('/get-notification', methods=['GET'])
def get_notification():
    return jsonify(notification_update)


# renders history page
@web_bp.route('/history', methods=['GET'])
def get_history():

    response = promptServiceGetHistory()
    print("recieved response from promptServiceGetHistory")
    return response


###########################################################
#
#  Route to use promt-svc's initial GPT request route
#
#  Receives:
#   - content:  variables from UI's form
#
#  Returns:
#   - gpt_message:  string
#
###########################################################
def promptServiceInitialReq(content):

    # Attach user_id to content
    if 'id' in session:
        content['user_id'] = session['id']
    else:
        content['user_id'] = None

    r = requests.post(f'{promptSvcUrl()}/v1/prompt/initial-trip-planning-req',
                      json=content)
    response = r.json()
    return response


# when user update itinerary
def promptServiceUpdate(content):

    r = requests.post(f'{promptSvcUrl()}/v1/prompt/trip-planning-update',
                      json=content)
    response = r.json()
    return response


# when user chats with GPT
def promptServiceChat(content):

    r = requests.post(f'{promptSvcUrl()}/v1/prompt/trip-planning-chat',
                      json=content)
    response = r.json()
    return response


# get a trip by trip_id
def promptServiceGetTrip(trip_id):

    # Attach user_id to content
    if 'id' in session:
        headers = {'Authorization': 'Bearer {}'.format(session['id'])}
    else:
        headers = {}

    r = requests.get(f'{promptSvcUrl()}/v1/prompt/get-trip/{trip_id}',
                     headers=headers)
    response = r.json()
    return response


# get history (all trips of a user)
def promptServiceGetHistory():

    # Attach user_id to content
    if 'id' in session:
        headers = {'Authorization': 'Bearer {}'.format(session['id'])}
    else:
        return redirect(url_for('web.home'))

    r = requests.get(f'{promptSvcUrl()}/v1/prompt/get-trip-history',
                     headers=headers)
    response = r.json()

    # insert URL for each response
    for trip in response['history']:
        trip['url'] = url_for('web.plan_a_trip_get',
                              trip_id=trip['trip_id'],
                              _external=True)

    print(response)
    return response


# when user updates the profile
def promptServiceUpdateProfile(content):

    # Attach user_id to content
    if 'id' in session:
        headers = {'Authorization': 'Bearer {}'.format(session['id'])}
    else:
        return None

    r = requests.post(f'{promptSvcUrl()}/v1/prompt/profile',
                      json=content,
                      headers=headers)
    response = r.json()
    print(response)
    return response


# when user gets their profile
def promptServiceGetProfile():

    # Attach user_id to content
    if 'id' in session:
        headers = {'Authorization': 'Bearer {}'.format(session['id'])}
    else:
        return None

    r = requests.get(f'{promptSvcUrl()}/v1/prompt/profile',
                     headers=headers)
    response = r.json()
    print(response)
    return response


def fetch_weather_update(location):
    global notification_update
    global get_weather_data

    weather_payload = {"location": location}

    url = f'{promptSvcUrl()}/v1/prompt/weather'

    r = requests.post(url, json=weather_payload)

    if r.status_code == 200:
        data = r.json()
        location = data.get("location", "Unknown location")
        get_weather_data = data.get("weather-update",
                                    "No weather update available")
        notification_update = {
            'message': f"{get_weather_data}",
            'link': '/recommendations'
        }


def promptSvcUrl():
    return PROMPT_SVC_URL


def generate_weather_data(weather_data):
    return json.loads(f"{weather_data}")


def generate_itinerary_data(agenda_data):
    return json.loads(f"{agenda_data}")

# Resource(s) Used:
# https://flask.palletsprojects.com/en/3.0.x/blueprints/
