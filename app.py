from flask import Flask, request, jsonify
from pymongo import MongoClient
from flask_jwt_extended import JWTManager, create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)
# Setup MongoDB connection
mc = MongoClient(os.getenv('DATABASE_URL'))
db = mc["FindPublicToilet"]
user_col = db["UserAccount"]
restroom_col = db["RestroomInfo"]

@app.route('/register', methods=['POST'])
def register():
    email = request.json['email']
    password = request.json['password']

    if user_col.find_one({"Email": email}):
        return jsonify({"error": "Email already exists"}), 409

    user_id = get_next_user_id()
    hashed_password = generate_password_hash(password)
    user_data = {
        "UserID": user_id,
        "Email": email,
        "Password": hashed_password
    }
    user_col.insert_one(user_data)
    return jsonify({"message": "User registered successfully!"}), 201

@app.route('/login', methods=['POST'])
def login():
    email = request.json['email']
    password = request.json['password']
    user = user_col.find_one({"email": email}, {"_id": False})

    if user and check_password_hash(user['Password'], password):
        access_token = create_access_token(identity=email)
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401

@app.route('/nearby_toilet', methods=['POST'])
def nearby_toilet():
    user_long = request.json['longitude']
    user_lat = request.json['latitude']
    # Find the 10 nearest restrooms
    query = {
        'Location': {
            '$near': {
                '$geometry': {
                    'type': "Point",
                    'coordinates': [user_long, user_lat]
                },
                '$maxDistance': 1000  # 1000 meters
            }
        }
    }
    nearby_restroom = restroom_col.find(query, {"_id": False}).limit(10)
    result = list(nearby_restroom)
    for r in result:
        if not r.get('Rating'):
            r['Rating'] = 0
            r['RatingCount'] = 0
    return jsonify(result)

def get_next_user_id():
    counters = db['Counters']
    result = counters.find_one_and_update({'Name': 'UserID'}, {'$inc': {'Seq': 1}}, return_document=True)
    return result['Seq']


if __name__ == "__main__":
    app.run(debug=True)
