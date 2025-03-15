from flask import Flask, current_app, render_template, request
import os
import datetime
import pytz  # For timezone validation

import utils

app = Flask(__name__)
with app.app_context():
    # Validate timezone
    calendar_timezone = os.environ.get('GROUPME_CALENDAR_TIMEZONE', 'America/Chicago')
    try:
        pytz.timezone(calendar_timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        app.logger.error(f"Invalid timezone: {calendar_timezone}. Falling back to America/Chicago.")
        calendar_timezone = 'America/Chicago'
    current_app.calendar_timezone = calendar_timezone

    current_app.groupme_calendar_name = 'GroupMe Calendar'
    static_name = os.environ.get('GROUPME_STATIC_NAME', None)
    if static_name and static_name.strip():
        current_app.groupme_calendar_name = static_name

@app.route('/')
def index():
    try:
        last_cache = getattr(current_app, 'last_cache', datetime.datetime(year=2000, month=1, day=1))
        cache_duration = int(os.environ.get('CACHE_DURATION', 60))

        groupme_group_id = os.environ.get('GROUPME_GROUP_ID', None)
        if not groupme_group_id:
            app.logger.error("GROUPME_GROUP_ID is not set.")
            return 'ERROR: The GROUPME_GROUP_ID is not set.', 500

        if datetime.datetime.now() - last_cache > datetime.timedelta(minutes=cache_duration) or cache_duration == 0:
            app.logger.info('Cache miss.')

            # Perform a recache.
            groupme_api_key = os.environ.get('GROUPME_API_KEY', None)
            if not groupme_api_key:
                app.logger.error("GROUPME_API_KEY is not set.")
                return 'ERROR: The GROUPME_API_KEY is not set.', 500

            successfully_load_json = utils.load_groupme_json(app=app, groupme_api_key=groupme_api_key, groupme_group_id=groupme_group_id)
            if not successfully_load_json:
                app.logger.error("Failed to load GroupMe JSON.")
                return 'There was a critical error loading the GroupMe Calendar. Please investigate.', 500
            current_app.ics_cache = utils.groupme_json_to_ics(groupme_json=current_app.groupme_calendar_json_cache)
            current_app.last_cache = datetime.datetime.now()
        else:
            app.logger.info('Cache hit. Time remaining: {}'.format(datetime.timedelta(minutes=cache_duration) - (datetime.datetime.now() - last_cache)))

        # Use urllib.parse for URL parsing in Python 3
        from urllib.parse import urlparse, urljoin
        ics_url = os.environ.get('GROUPME_PROXY_URL', None)
        if not ics_url:
            ics_url = urljoin(request.url, 'calendar.ics')
            if request.url.endswith('/'):
                ics_url = urljoin(request.url, 'calendar.ics')

        ics_url_http, ics_url_webcal, ics_url_google = utils.build_ics_urls(ics_url)

        params = {
            'title': getattr(current_app, 'groupme_calendar_name', 'GroupMe'),
            'groupme_id': groupme_group_id,
            'ics_url_http': ics_url_http,
            'ics_url_webcal': ics_url_webcal,
            'ics_url_google': ics_url_google,
            'calendar_timezone': current_app.calendar_timezone,
        }

        # Return a template, but also some basic info about the latest cache time.
        return render_template('index.html', **params)
    except Exception as e:
        app.logger.error(f"Error in index route: {str(e)}")
        return f"Internal Server Error: {str(e)}", 500

@app.route('/calendar.ics')
def full_ics():
    try:
        last_cache = getattr(current_app, 'last_cache', datetime.datetime(year=2000, month=1, day=1))
        cache_duration = int(os.environ.get('CACHE_DURATION', 60))
        if datetime.datetime.now() - last_cache > datetime.timedelta(minutes=cache_duration) or cache_duration == 0:
            app.logger.info('Cache miss.')

            # Perform a recache.
            groupme_api_key = os.environ.get('GROUPME_API_KEY', None)
            groupme_group_id = os.environ.get('GROUPME_GROUP_ID', None)
            if not groupme_api_key:
                app.logger.error("GROUPME_API_KEY is not set.")
                return utils.return_ics_Response(util
