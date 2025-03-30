from motor.motor_asyncio import AsyncIOMotorClient
import logging
import os
from dotenv import load_dotenv

class MongoAsyncClient:

    def __init__(self, db_name: str) -> None:
        load_dotenv()
        try:
            self.client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
            self.db = self.client[db_name]
            logging.info(f"Connected to MongoDB: {db_name}")
        
        except Exception as e:
            logging.error(f"Error connecting to MongoDB: {e}")
            raise e
    
    async def close(self) -> None:
        if self.client:
            await self.client.close()
            logging.info("MongoDB connection closed")

    async def insert_one(self, collection_name: str, document: dict):
        try:
            result = await self.db[collection_name].insert_one(document)
            return result.inserted_id
        except Exception as e:
            logging.error(f"Error inserting document: {e}")
            raise
            
    async def find_one(self, collection_name: str, query: dict):
        try:
            return await self.db[collection_name].find_one(query)
        except Exception as e:
            logging.error(f"Error finding document: {e}")
            raise
            
    async def find_many(self, collection_name: str, query: dict, limit: int = 0):
        try:
            cursor = self.db[collection_name].find(query)
            if limit > 0:
                cursor.limit(limit)
            return await cursor.to_list(length=None)
        except Exception as e:
            logging.error(f"Error finding documents: {e}")
            raise
            
    async def update_one(self, collection_name: str, query: dict, update: dict):
        try:
            result = await self.db[collection_name].update_one(query, {'$set': update})
            return result.modified_count
        except Exception as e:
            logging.error(f"Error updating document: {e}")
            raise
            
    async def delete_one(self, collection_name: str, query: dict):
        try:
            result = await self.db[collection_name].delete_one(query)
            return result.deleted_count
        except Exception as e:
            logging.error(f"Error deleting document: {e}")
            raise
            
    async def count_documents(self, collection_name: str, query: dict):
        try:
            return await self.db[collection_name].count_documents(query)
        except Exception as e:
            logging.error(f"Error counting documents: {e}")
            raise
