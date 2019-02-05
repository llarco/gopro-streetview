import argparse
import googlemaps
import httplib2
import numpy
import os
import subprocess
import sys
import requests
from apiclient import discovery
from oauth2client import client
from oauth2client import file
from oauth2client import tools

_PARSER = argparse.ArgumentParser(
    description='Street View Uploader.', parents=[tools.argparser])
_PARSER.add_argument('--googlemaps_key', required=True, type=str)
_PARSER.add_argument('--lat', required=False, type=float, default=0.0)
_PARSER.add_argument('--lon', required=False, type=float, default=0.0)
_PARSER.add_argument('--query', required=False, type=str)
_PARSER.add_argument(
    '--photo', required=False, type=str, default=None,
    help='Full path to photo file.')
_PARSER.add_argument(
    '--video', required=False, type=str, default=None,
    help = 'Full path of stitched video file including GPMF track.')
_PARSER.add_argument(
    '--client_secrets',
    required=True,
    help='Full path of the client_secrets.json file.')
_PARSER.add_argument(
    '--developer_key', help='Developer key of the GCP project.')


_IMAGE_CONTENT_TYPE = 'image/jpeg'
_VIDEO_CONTENT_TYPE = 'video/mp4'

_GOOGLE_MAPS_API = None
_RADIUS_NEARBY_LOOKUP_IN_METERS = 10
_LABEL = "ALPHA_TESTER"

_API_NAME = 'streetviewpublish'
_API_VERSION = 'v1'
_SCOPES = 'https://www.googleapis.com/auth/streetviewpublish'
_DISCOVERY_SERVICE_URL = "https://%s.googleapis.com/$discovery/rest?version=%s"
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
    storage = file.Storage(credential_path)
    credentials = storage.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(args.client_secrets,
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


def _get_discovery_service_url(args):
  """Returns the discovery service url."""
  discovery_service_url = _DISCOVERY_SERVICE_URL % (_API_NAME, _API_VERSION)
  if args.developer_key is not None:
    discovery_service_url += "&key=%s" % args.developer_key
  if _LABEL is not None:
    discovery_service_url += "&labels=%s" % _LABEL
  return discovery_service_url


def _init_street_view_publish_api(args):
    global _STREET_VIEW_PUBLISH_API
    credentials = _get_credentials(args)
    http = credentials.authorize(httplib2.Http())
    _STREET_VIEW_PUBLISH_API = discovery.build(
        _API_NAME,
        _API_VERSION,
        developerKey=args.developer_key,
        discoveryServiceUrl=_get_discovery_service_url(args),
        http=http,
        cache_discovery=False)


def _init_google_maps_api(args):
    global _GOOGLE_MAPS_API
    _GOOGLE_MAPS_API = googlemaps.Client(key=args.googlemaps_key)


def _get_headers(credentials, photo_size, contentType):
  """Returns a list of header parameters in HTTP header format.

  Args:
    credentials: The credentials object returned from the _get_credentials
      method.
    photo_size: The size of the photo.

  Returns:
    A dict of header parameters.
  """
  headers = {
      'Content-Type': contentType,
      'Authorization': 'Bearer ' + credentials.access_token,
      'X-Goog-Upload-Protocol': 'raw',
      'X-Goog-Upload-Content-Length': str(photo_size)
  }
  return headers


def _upload_file_resumable(args, uploadUrl, contentType):
    access_token = _get_credentials(args).access_token
    fileSize = os.stat(args.video).st_size
    headers = {
        'Authorization': 'Bearer ' + access_token,
        'Content-Length': '0',
        'X-Goog-Upload-Protocol': 'resumable',
        'X-Goog-Upload-Header-Content-Length': str(fileSize),
        'X-Goog-Upload-Header-Content-Type': contentType,
        'X-Goog-Upload-Command': 'start'
    }
    resumableUrl = requests.post(uploadUrl, headers=headers)
    resumableUrl = resumableUrl.headers['X-Goog-Upload-URL']

    chunk_size = 20 * 1024 * 1024 # 20 MiB
    offset = 0
    f = open(args.video, 'rb')
    while (offset < (fileSize - chunk_size)):
        headers = {
            'Authorization': 'Bearer ' + access_token,
            'Content-Length': str(chunk_size),
            'X-Goog-Upload-Command': 'upload',
            'X-Goog-Upload-Offset': str(offset)
        }
        f.seek(offset)
        data = f.read(chunk_size)
        chunk_response = requests.post(resumableUrl, data=data, headers=headers)
        if (chunk_response.status_code != 200):
            print ('Error: %s' % chunk_response.headers)
            sys.exit()
        offset = offset + chunk_size
        print ("Done {0:.2f}%".format(offset / fileSize * 100), end="\r")

    last_chunk = fileSize - offset
    headers = {
        'Authorization': 'Bearer ' + access_token,
        'Content-Length': str(last_chunk),
        'X-Goog-Upload-Command': 'upload, finalize',
        'X-Goog-Upload-Offset': str(offset)
    }
    f.seek(offset)
    data = f.read(last_chunk)
    chunk_response = requests.post(resumableUrl, data=data, headers=headers)
    if (chunk_response.status_code != 200):
        print ('Error: %s' % chunk_response.headers)
        sys.exit()
    print ('Done uploading!')
    print ('Upload URL: %s' % uploadUrl)


def _upload_file(args, uploadUrl, contentType):
    with open(args.photo, 'rb') as f:
        raw_data = f.read()
        try:
            requests.post(
                upload_url,
                data=raw_data,
                headers=_get_headers(
                    _get_credentials(args), len(raw_data), contentType))
            print('Upload successful: %s' % f.name)
        except requests.exceptions.RequestException as e:
            print('Failed to upload: %s' % f.name)
            print(e)
            sys.exit(1)


def _upload_photo(args):
    placeId = _find_place(args.query, args.lat, args.lon)
    if placeId is not None:
        print(f'Place id: {placeId}')

    startUploadResponse = _STREET_VIEW_PUBLISH_API.photo().startUpload(
        body={}).execute()
    uploadUrl = str(startUploadResponse['uploadUrl'])

    _upload_file(args, uploadUrl, _IMAGE_CONTENT_TYPE)

    photoRequest = {
            'uploadReference': {'uploadUrl': uploadUrl},
            'places': {'placeId': placeId}}
    photoResponse = _STREET_VIEW_PUBLISH_API.photo().create(
        body=photoRequest).execute()
    print('Photo created successfully: %s' % photoResponse)


def _upload_photo_sequence(args):
    startUploadResponse = _STREET_VIEW_PUBLISH_API.photoSequence().startUpload(
        body={}).execute()
    uploadUrl = str(startUploadResponse['uploadUrl'])

    _upload_file_resumable(args, uploadUrl, _VIDEO_CONTENT_TYPE)

    # photoSequenceRequest = {
    #         'uploadReference': {'uploadUrl': uploadUrl},
    # }
    # photoSequenceResponse = _STREET_VIEW_PUBLISH_API.photoSequence().create(
    #     body=photoSequenceRequest, inputType="VIDEO").execute()
    # print('Photo sequence created: %s' % photoSequenceResponse['name'])


def main():
    args = _PARSER.parse_args()
    global _GOOGLE_MAPS_API
    global _STREET_VIEW_PUBLISH_API
    _init_google_maps_api(args)
    _init_street_view_publish_api(args)

    if (args.photo is not None and args.video is not None):
        print('Either a photo or a photo sequence can be uploaded, '
              'but not both.')
        sys.exit(1)

    if (args.photo is not None):
        _upload_photo(args)
    elif(args.video is not None):
        _upload_photo_sequence(args)
    else:
        print('Either a photo or a photo sequence must be provided.')


if __name__ == '__main__':
    main()
