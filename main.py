import base64
import os
import urllib2
import json
import wikipedia
import requests

from flask import Flask, redirect, render_template, request
from google.cloud import datastore
from google.cloud import storage
from google.cloud import vision



app = Flask(__name__)


@app.route('/')
def homepage():
    # Create a Cloud Datastore client.
    datastore_client = datastore.Client()

    # Use the Cloud Datastore client to fetch information from Datastore about
    # each photo.
    query = datastore_client.query(kind='Photos')
    image_entities = list(query.fetch())    

    # Return a Jinja2 HTML template.
    return render_template('homepage.html', image_entities=image_entities, count=3)

@app.route('/upload_photo', methods=['GET', 'POST'])
def upload_photo():
    # Create a Cloud Storage client.
    storage_client = storage.Client()

    # Get the Cloud Storage bucket that the file will be uploaded to.
    bucket = storage_client.get_bucket(os.environ.get('CLOUD_STORAGE_BUCKET'))

    # Create a new blob and upload the file's content to Cloud Storage.
    photo = request.files['file']
    blob = bucket.blob(photo.filename)
    blob.upload_from_string(
            photo.read(), content_type=photo.content_type)

    # Make the blob publicly viewable.
    blob.make_public()
    image_public_url = blob.public_url
    
    # Create a Cloud Vision client.
    vision_client = vision.ImageAnnotatorClient()

    # Retrieve a Vision API response for the photo stored in Cloud Storage
    source_uri = 'gs://{}/{}'.format(os.environ.get('CLOUD_STORAGE_BUCKET'), blob.name)
    response = vision_client.annotate_image({
        'image': {'source': {'image_uri': source_uri}},
    })
    labels = response.label_annotations
    faces = response.face_annotations
    web_entities = response.web_detection.web_entities

    # Create a Cloud Datastore client
    datastore_client = datastore.Client()

    # The kind for the new entity
    kind = 'Photos'

    # The name/ID for the new entity
    name = blob.name

    # Create the Cloud Datastore key for the new entity
    key = datastore_client.key(kind, name)

    # Construct the new entity using the key. Set dictionary values for entity
    # keys image_public_url and label.
    entity = datastore.Entity(key)
    entity['image_public_url'] = image_public_url
    entity['label'] = labels[0].description

    # Save the new entity to Datastore
    datastore_client.put(entity)

    pictures = getPictures(web_entities[0].description)
    restaraunts = getRestaraunts(web_entities[0].description)


    #mapSource = constructMapSource(restaraunts, getCurrentLocation())


    searchMapSource = constructSearchMap(getCurrentLocation(), web_entities[0].description)
    shortSummary = wikipedia.summary(web_entities[0].description, sentences=4)

    # Redirect to the home page.
    return render_template('homepage.html', web_entity=web_entities[0], public_url=image_public_url, pics=pictures, summary=shortSummary, rests=restaraunts, map=searchMapSource)


def constructSearchMap(curr, item):
    baseURL = "https://www.google.com/maps/embed/v1/search?key=<GOOGLE_SEARCH_API_KEY>&q="

    item = item.replace(' ','+')

    baseURL += item + "+in+" + str(curr[0]) +"+" + str(curr[1])

    print(baseURL)

    return baseURL


def constructMapSource(restaraunts, currentLocation):

    baseURL = "https://www.google.com/maps/embed/v1/directions?key=<GOOGLE_MAPS_API_KEY"
    origin = "&origin=" + repr(currentLocation[0]) + "," + repr(currentLocation[1])
    print(restaraunts[0])
    destination = "&destination=" + repr(restaraunts[0]['latitude']) + "," + repr(restaraunts[0]['longitude'])
    waypoints = "&waypoints="

    for i in range(1, len(restaraunts) - 1):
        waypoints += ( repr(restaraunts[i]['latitude']) + "," + repr(restaraunts[i]['longitude']) + "|")

    finalURL = baseURL + origin + destination + waypoints[:-1]
    #print(finalURL)

    return finalURL


def getCurrentLocation():
    send_url = 'http://freegeoip.net/json'
    r = requests.get(send_url)
    j = json.loads(r.text)
    lat = j['latitude']
    lon = j['longitude']


    city = j['city']
    state = j['region_code']
    #return [lat, lon]
    return [city,state]

def getPictures(subject):
    baseURL = "https://www.googleapis.com/customsearch/v1?q="
    formatedSubject = subject.replace(" ", "+")
    cx = "<GOOGLE_SEARCH_CX>"

    # DELETE THIS
    API_KEY = "<GOOGLE_SEARCH_API_KEY>"

    # construct the query URL
    baseURL += (formatedSubject + "&cx=" + cx + "&searchType=image&key=" + API_KEY)

    print(baseURL)
    resp = urllib2.urlopen(baseURL)
    d = json.load(resp)

    pictures = []

    for i in d['items']:
        pictures.append(i['link'])

    return pictures

def getRestaraunts(subject):
    baseURL = "https://api.yelp.com/v3/businesses/search"
    currentLocation = getCurrentLocation()
    formatedSubject = subject.replace(" ", "+")


    # construct the query URL
    baseURL += ("?term=" + formatedSubject + "&location=" + currentLocation[0] + "+" + currentLocation[1])

    print(baseURL)

    header = {'Authorization': '<YELP_API_KEY>'}

    req = requests.get(baseURL, headers=header)

    d = req.json()

    restaraunts = []

    for i in d['businesses']:
        restaraunts.append(i['coordinates'])

    return restaraunts

@app.errorhandler(500)
def server_error(e):
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500


if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)