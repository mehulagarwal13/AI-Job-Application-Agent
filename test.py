from app.core.qdrant_client import client, COLLECTION_NAME
info = client.get_collection(COLLECTION_NAME)
print(info.points_count)