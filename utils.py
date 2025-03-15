from ics import Calendar, Event
from flask import Response
import dateutil.parser
import requests
from urllib.parse import urlparse, urlunparse, urljoin, parse_qsl, urlencode
from flask import current_app

def return_ics_Response(response_body):
    return Response(
        response_body,
        mimetype='text/calendar',
        headers={'Content-Disposition': 'attachment'}
    )

def build_ics_urls(ics_url):
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
    cal = Calendar()
    # Use extra to add custom iCalendar properties
    cal.extra.append("PRODID:-//Andrew Mussey//GroupMe-to-ICS 0.1//EN")
    cal.extra.append("VERSION:2.0")
    cal.extra.append("CALSCALE:GREGORIAN")
    cal.extra.append("METHOD:PUBLISH")
    cal.extra.append(f"X-WR-CALNAME:GroupMe: {current_app.groupme_calendar_name}")
    cal.extra.append(f"X-WR-TIMEZONE:{current_app.calendar_timezone}")

    for json_blob in groupme_json['response']['events']:
        if 'deleted_at' not in json_blob:
            event = Event()
            event.uid = json_blob['event_id']
            event.begin = dateutil.parser.parse(json_blob['start_at'])
            if json_blob.get('end_at'):
                event.end = dateutil.parser.parse(json_blob['end_at'])
            event.name = json_blob['name']
            event.description = json_blob.get('description', '')
            if json_blob.get('location'):
                location = json_blob.get('location', {})

                if json_blob.get('description'):
                    event.description += '\n\n'
                event.description += 'Location:\n'

                if location.get('name') and location.get('address'):
                    event.location = "{}, {}".format(location.get('name'), location.get('address').strip().replace("\n", ", "))
                    event.description += location.get('name')
                    event.description += '\n'
                    event.description += location.get('address')
                elif location.get('name'):
                    event.location = location.get('name')
                    event.description += location.get('name')
                elif location.get('address'):
                    event.location = location.get('address').strip().replace("\n", ", ")
                    event.description += location.get('address')

                if location.get('lat') and location.get('lng'):
                    location_url = 'https://www.google.com/maps?q={},{}'.format(location.get('lat'), location.get('lng'))
                    if not event.location:
                        event.location = location_url
                    else:
                        event.description += '\n'
                    event.description += location_url

            if json_blob.get('updated_at'):
                event.last_modified = dateutil.parser.parse(json_blob.get('updated_at'))
            cal.events.add(event)

    return cal.serialize()

def groupme_ics_error(error_text, static_name=None):
    cal = Calendar()
    # Use extra to add custom iCalendar properties
    cal.extra.append("PRODID:-//Andrew Mussey//GroupMe-to-ICS 0.1//EN")
    cal.extra.append("VERSION:2.0")
    cal.extra.append("CALSCALE:GREGORIAN")
    cal.extra.append("METHOD:PUBLISH")
    cal.extra.append(f"X-WR-CALNAME:GroupMe: {current_app.groupme_calendar_name} ({error_text})")
    cal.extra.append("X-WR-TIMEZONE:America/Chicago")

    return cal.serialize()
