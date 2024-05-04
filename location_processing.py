from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['FindPublicToilet']
restrooms = db['RestroomInfo']

# Fetch all documents that need updating
cursor = restrooms.find({})

# Update each document
for doc in cursor:
    longitude = doc['Longitude']
    latitude = doc['Latitude']
    # Update the document with the GeoJSON location
    restrooms.update_one(
        {'_id': doc['_id']},
        {'$set': {'Location': {'type': 'Point', 'coordinates': [longitude, latitude]}}}
    )

restrooms.create_index([("Location", "2dsphere")])