# gopro-streetview
This script uploads 360 photos or videos to the Street View Publish API.

When uploading photos, the Google Maps API is used to associate the photo with a
place.

As of 2019-02-17, uploading photo sequences is only available for alpha testers,
therefore it is expected that the GCP project specified by the `developer_key`
has been whitelisted to use photo sequences.

For more information about the Street View Publish API, visit
https://developers.google.com/streetview/publish/

## Requirements

To install the requirements, run the following command:

```
$ pip3 install googlemaps httplib2 numpy google-auth \
               google-auth-httplib2 google-api-python-client tqdm
```

## Example usage for photo specifying the coordinates:

```
$ python3 streetview_uploader.py \
    --client_secrets=/path/to/client_secrets \
    --googlemaps_key=GOOGLE_MAPS_API_KEY \
    --developer_key=API_KEY_OF_THE_GCP_PROJECT \
    --photo=/path/to/photo_file \
    --lat=LATITUDE \
    --lon=LONGITUDE
```

## Example usage for photo specifying the coordinates:

```
$ python3 streetview_uploader.py \
    --client_secrets=/path/to/client_secrets \
    --googlemaps_key=GOOGLE_MAPS_API_KEY \
    --developer_key=API_KEY_OF_THE_GCP_PROJECT \
    --photo=/path/to/photo_file \
    --query="Googleplex Mountain View, CA"
```

## Example usage for video:

```
$ python3 streetview_uploader.py \
    --client_secrets=/path/to/client_secrets \
    --googlemaps_key=GOOGLE_MAPS_API_KEY \
    --developer_key=API_KEY_OF_THE_GCP_PROJECT \
    --video=/path/to/video_file
```
