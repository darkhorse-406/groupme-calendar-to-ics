print("Starting to load utils.py")  # Debug print

try:
    from icalendar import Calendar, Event
    from flask import Response
    import dateutil.parser
    import requests
    from urllib.parse import urlparse, urlunparse, urljoin, parse_qsl, urlencode
    from flask import current_app
except Exception as e:
    print(f"Import error in utils.py: {str(e)}")
    raise

print("Successfully loaded imports in utils.py")  # Debug print

def return_ics_Response(response_body):
    return Response(
        response_body,
        mimetype='text/calendar',
        headers={'Content-Disposition': 'attachment'}
    )

def build_ics_urls(ics_url):
    print("Starting build_ics_urls")  # Debug print
    google_calendar_url_base = 'http://www.google.com/calendar/render?cid='

    # Parse the URL into [scheme, netloc, path, params, query, fragment]
    parsed_ics_url = list(urlparse(ics_url))
    if parsed_ics_url[0] != 'https':
        parsed_ics_url[0] = 'http'
    ics_url_http = urlunparse(parsed_ics_url)

    parsed_ics_url[0] = 'webcal'
    ics_url_webcal = urlunparse(parsed_ics_url)

    parsed_google_url = list(urlparse(google_calendar_url_base))
    parsed_google_url[4] = dict(parse_qsl(parsed_google_url[4]))
    parsed_google_url[4]['cid'] = ics_url_webcal
    parsed_google_url[4] = urlencode(parsed_google_url[4])
    ics_url_google = urlunparse(parsed_google_url)

    return ics_url_http, ics_url_webcal, ics_url_google

def load_groupme_json(app, groupme_api_key, groupme_group_id):
    print("Starting load_groupme_json")  # Debug print
    url_group_info = 'https://api.groupme.com/v3/groups/{groupme_group_id}'.format(groupme_group_id=groupme_group_id)
    url_calendar = 'https://api.groupme.com/v3/conversations/{groupme_group_id}/events/list'.format(groupme_group_id=groupme_group_id)
    headers = {'X-Access-Token': groupme_api_key}

    response = requests.get(url_calendar, headers=headers)
    if response.status_code != 200:
        current_app.groupme_load_successfully = False
        current_app.groupme_calendar_json_cache = {}
        app.logger.error('{}: {}'.format(response.status_code, response.text))
        return False

    current_app.groupme_calendar_json_cache = response.json()

    response = requests.get(url_group_info, headers=headers)
    if response.status_code == 200:
        if response.json().get('response', {}).get('name', None):
            current_app.groupme_calendar_name = response.json().get('response', {}).get('name')

    current_app.groupme_load_successfully = True
    return True

def groupme_json_to_ics(groupme_json, static_name=None):
    print("Starting groupme_json_to_ics")  # Debug print
    cal = Calendar()
    # Use dictionary-style assignment for iCalendar properties
    cal['PRODID'] = '-//Andrew Mussey//GroupMe-to-ICS 0.1//EN'
    cal['VERSION'] = '2.0'
    cal['CALSCALE'] = 'GREGORIAN'
    cal['METHOD'] = 'PUBLISH'
    cal['X-WR-CALNAME'] = f"GroupMe: {current_app.groupme_calendar_name}"
    cal['X-WR-TIMEZONE'] = current_app.calendar_timezone

    for json_blob in groupme_json['response']['events']:
        if 'deleted_at' not in json_blob:
            event = Event()
            event['UID'] = json_blob['event_id']
            event['DTSTART'] = dateutil.parser.parse(json_blob['start_at'])
            if json_blob.get('end_at'):
                event['DTEND'] = dateutil.parser.parse(json_blob['end_at'])
            event['SUMMARY'] = json_blob['name']
            event['DESCRIPTION'] = json_blob.get('description', '')
            if json_blob.get('location'):
                location = json_blob.get('location', {})

                if json_blob.get('description'):
                    event['DESCRIPTION'] = event['DESCRIPTION'] + '\n\n'
                event['DESCRIPTION'] = event['DESCRIPTION'] + 'Location:\n'

                if location.get('name') and location.get('address'):
                    event['LOCATION'] = "{}, {}".format(location.get('name'), location.get('address').strip().replace("\n", ", "))
                    event['DESCRIPTION'] = event['DESCRIPTION'] + location.get('name') + '\n' + location.get('address')
                elif location.get('name'):
                    event['LOCATION'] = location.get('name')
                    event['DESCRIPTION'] = event['DESCRIPTION'] + location.get('name')
                elif location.get('address'):
                    event['LOCATION'] = location.get('address').strip().replace("\n", ", ")
                    event['DESCRIPTION'] = event['DESCRIPTION'] + location.get('address')

                if location.get('lat') and location.get('lng'):
                    location_url = 'https://www.google.com/maps?q={},{}'.format(location.get('lat'), location.get('lng'))
                    if 'LOCATION' not in event:
                        event['LOCATION'] = location_url
                    else:
                        event['DESCRIPTION'] = event['DESCRIPTION'] + '\n'
                    event['DESCRIPTION'] = event['DESCRIPTION'] + location_url

            if json_blob.get('updated_at'):
                event['LAST-MODIFIED'] = dateutil.parser.parse(json_blob.get('updated_at'))
            cal.add_component(event)

    return cal.to_ical().decode('utf-8')

def groupme_ics_error(error_text, static_name=None):
    print("Starting groupme_ics_error")  # Debug print
    cal = Calendar()
    # Use dictionary-style assignment for iCalendar properties
    cal['PRODID'] = '-//Andrew Mussey//GroupMe-to-ICS 0.1//EN'
    cal['VERSION'] = '2.0'
    cal['CALSCALE'] = 'GREGORIAN'
    cal['METHOD'] = 'PUBLISH'
    cal['X-WR-CALNAME'] = f"GroupMe: {current_app.groupme_calendar_name} ({error_text})"
    cal['X-WR-TIMEZONE'] = 'America/Chicago'

    return cal.to_ical().decode('utf-8')
