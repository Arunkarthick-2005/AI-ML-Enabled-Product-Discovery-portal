from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["flipkart_db"]
products_collection = db["products"]
users_collection =db["users"]