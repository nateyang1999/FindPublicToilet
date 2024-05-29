from flask import Flask, request, jsonify
from pymongo import MongoClient, errors
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import timedelta
import os

load_dotenv()

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)
# Setup MongoDB connection
mc = MongoClient(os.getenv('DATABASE_URL'))
db = mc[os.getenv('DB_NAME')]
user_col = db["UserAccount"]
restroom_col = db["RestroomInfo"]
rating_col = db["UserRating"]

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
    user = user_col.find_one({"Email": email}, {"_id": False})

    if user and check_password_hash(user['Password'], password):
        access_token = create_access_token(identity=user['UserID'], expires_delta=timedelta(days=1))
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

@app.route('/rate/<int:restroom_id>', methods=['POST'])
@jwt_required()
def post_rating(restroom_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    score = data.get('score')

    if not score:
        return jsonify({"error": "Score is required"}), 400

    existing_rating = rating_col.find_one({"UserID": user_id, "RestroomID": restroom_id})
    if existing_rating:
        return jsonify({"error": "User has already rated this restroom. Use the edit API to change the score."}), 401

    try:
        rating_col.insert_one({"UserID": user_id, "RestroomID": restroom_id, "Score": score})
        restroom_data = restroom_col.find_one({"RestroomID": restroom_id})
        new_rating = (restroom_data.get('Rating', 0) * restroom_data.get('RatingCount', 0) + score) / (restroom_data.get('RatingCount', 0) + 1)
        restroom_col.update_one({"RestroomID": restroom_id}, {"$set": {"Rating": new_rating, "RatingCount": restroom_data.get('RatingCount', 0) + 1}})
        return jsonify({"message": "Rating sent successfully!"}), 200
    except errors.PyMongoError as e:
        return jsonify({"error": "An error occurred while posting the rating"}), 500

@app.route('/edit_rating/<int:restroom_id>', methods=['PUT'])
@jwt_required()
def edit_rating(restroom_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    score = data.get('score')

    if not score:
        return jsonify({"error": "Score is required"}), 400

    existing_rating = rating_col.find_one({"UserID": user_id, "RestroomID": restroom_id})
    if not existing_rating:
        return jsonify({"error": "User has not rated this restroom yet. Use the post API to rate this restroom."}), 401

    try:
        rating_col.update_one({"UserID": user_id, "RestroomID": restroom_id}, {"$set": {"Score": score}})
        restroom_data = restroom_col.find_one({"RestroomID": restroom_id})
        new_rating = (restroom_data.get('Rating', 0) * restroom_data.get('RatingCount', 0) - existing_rating['Score'] + score) / restroom_data.get('RatingCount', 0)
        restroom_col.update_one({"RestroomID": restroom_id}, {"$set": {"Rating": new_rating}})
        return jsonify({"message": "Rating updated successfully!"}), 200
    except errors.PyMongoError as e:
        return jsonify({"error": "An error occurred while updating the rating"}), 500

def get_next_user_id():
    counters = db['Counters']
    result = counters.find_one_and_update({'Name': 'UserID'}, {'$inc': {'Seq': 1}}, return_document=True)
    return result['Seq']

@app.route('/has_rated/<int:restroom_id>', methods=['GET'])
@jwt_required()
def has_rated(restroom_id):
    user_id = get_jwt_identity()
    existing_rating = rating_col.find_one({"UserID": user_id, "RestroomID": restroom_id})
    if existing_rating:
        return jsonify({"HasRated": True}), 200
    else:
        return jsonify({"HasRated": False}), 200


if __name__ == "__main__":
    app.run(debug=True)
