import argparse
import googlemaps
import httplib2
import numpy
import os
import sys
import requests
from apiclient.discovery import build
from oauth2client import tools
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage

_PARSER = argparse.ArgumentParser(
    description='Street View Uploader.', parents=[tools.argparser])
_PARSER.add_argument('--googlemaps_key', required=True, type=str)
_PARSER.add_argument('--lat', required=False, type=float, default=0.0)
_PARSER.add_argument('--lon', required=False, type=float, default=0.0)
_PARSER.add_argument('--query', required=False, type=str)
_PARSER.add_argument(
    '--photo', required=True, type=str, help='Full path to photo file.')
_PARSER.add_argument(
    '--client_secrets',
    required=True,
    help='Full path of the client_secrets.json file.')
_PARSER.add_argument(
    '--developer_key', help='Developer key of the GCP project.')


_GOOGLE_MAPS_API = None
_RADIUS_NEARBY_LOOKUP_IN_METERS = 10

_API_NAME = 'streetviewpublish'
_API_VERSION = 'v1'
_SCOPES = 'https://www.googleapis.com/auth/streetviewpublish'
_APPLICATION_NAME = 'Street View Publish API Python'
_STREET_VIEW_PUBLISH_API = None
_CREDENTIALS_DIRECTORY_NAME = '.credentials'
_CREDENTIALS_FILENAME = 'streetviewpublish_credentials.json'

def _get_credentials(args):
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, _CREDENTIALS_DIRECTORY_NAME)
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, _CREDENTIALS_FILENAME)
    storage = Storage(credential_path)
    credentials = storage.get()
    if not credentials or credentials.invalid:
        flow = flow_from_clientsecrets(args.client_secrets,
                               scope=_SCOPES,
                               redirect_uri='http://localhost')
        flow.user_agent = _APPLICATION_NAME
        credentials = tools.run_flow(flow, storage, args)
    return credentials


def _pick_place(results):
    if len(results) == 1:
        name = results[0]['name']
        address = results[0]['formatted_address']
        print(f'Place: {name}, {address}')
        input('Press enter to continue or Ctrl-C to exit')
        return results[0]['place_id']
    elif len(results) > 1:
        for counter, place in enumerate(results):
            name = place['name']
            print(f'{counter}: {name}')
        choice = input('Enter option: ')
        return results[int(choice)]['place_id']
    else:
        return None


def _find_place(query=None, lat=0.0, lon=0.0):
    global _GOOGLE_MAPS_API
    if query is not None:
        places = _GOOGLE_MAPS_API.places(query=query, type="establishment")
        place_id = _pick_place(places['results'])
        if place_id is None:
            print('Place not found')
        return place_id
    elif not numpy.isclose(lat, 0.0) and not numpy.isclose(lon, 0.0):
            places = _GOOGLE_MAPS_API.places_nearby(
                location=(lat,lon), radius=_RADIUS_NEARBY_LOOKUP_IN_METERS, type="establishment")
            place_id = _pick_place(places['results'])
            if place_id is None:
                print('Place not found')
            return place_id
    else:
        print('Either a query or a lat/lon must be provided.')
        return None


def _init_street_view_publish_api(args):
    global _STREET_VIEW_PUBLISH_API
    credentials = _get_credentials(args)
    http = httplib2.Http()
    http = credentials.authorize(http)
    _STREET_VIEW_PUBLISH_API = build(_API_NAME, _API_VERSION, http=http)


def _get_headers(credentials, photo_size):
  """Returns a list of header parameters in HTTP header format.

  Args:
    credentials: The credentials object returned from the _get_credentials
      method.
    photo_size: The size of the photo.

  Returns:
    A dict of header parameters.
  """
  headers = {
      'Content-Type': 'image/jpeg',
      'Authorization': 'Bearer ' + credentials.access_token,
      'X-Goog-Upload-Protocol': 'raw',
      'X-Goog-Upload-Content-Length': str(photo_size)
  }
  return headers

def main():
    args = _PARSER.parse_args()
    global _GOOGLE_MAPS_API
    global _STREET_VIEW_PUBLISH_API
    _init_street_view_publish_api(args)

    _GOOGLE_MAPS_API = googlemaps.Client(key=args.googlemaps_key)
    place_id = _find_place(args.query, args.lat, args.lon)
    if place_id is not None:
        print(f'Place id: {place_id}')

    start_upload_response = _STREET_VIEW_PUBLISH_API.photo().startUpload(
        body={}).execute()
    upload_url = str(start_upload_response['uploadUrl'])
    with open(args.photo, 'rb') as f:
        raw_data = f.read()
        try:
            requests.post(
                upload_url,
                data=raw_data,
                headers=_get_headers(_get_credentials(args), len(raw_data)))
            print('Upload successful: %s' % f.name)
        except requests.exceptions.RequestException as e:
            print('Failed to upload: %s' % f.name)
            print(e)
            sys.exit(1)

    photo_request = {
            'uploadReference': {'uploadUrl': upload_url},
            'places': {'placeId': place_id}}
    photo_response = _STREET_VIEW_PUBLISH_API.photo().create(
        body=photo_request).execute()
    print('Photo created successfully: %s' % photo_response)


if __name__ == '__main__':
    main()
