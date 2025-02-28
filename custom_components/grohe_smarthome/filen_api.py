import aiohttp
import hashlib
import base64
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

API_BASE = "https://api.filen.io/v1"

class FilenClient:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.token = None
        self.session = aiohttp.ClientSession()

    async def login(self):
        """Authenticate and get a session token."""
        password_hash = hashlib.sha512(self.password.encode()).hexdigest()
        async with self.session.post(f"{API_BASE}/auth/login", json={"email": self.email, "password": password_hash}) as resp:
            data = await resp.json()
            if resp.status == 200 and data.get("status"):
                self.token = data["data"]["token"]
                return True
        return False

    async def get_storage_info(self):
        """Retrieve used and total storage."""
        headers = {"Authorization": self.token}
        async with self.session.get(f"{API_BASE}/user/storage", headers=headers) as resp:
            return await resp.json()

    async def upload_file(self, file_path):
        """Encrypt and upload a file to Filen.io."""
        file_name = os.path.basename(file_path)
        key = hashlib.sha256(self.password.encode()).digest()  # Generate encryption key
        iv = os.urandom(16)

        with open(file_path, "rb") as f:
            data = f.read()

        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted_data

    async def create_folder(self, folder_name, parent_folder_id=None):
        """Create a new folder in Filen.io."""
        headers = {"Authorization": self.token}
        payload = {
            "name": folder_name,
            "parent": parent_folder_id or "root"
        }
        async with self.session.post(f"{API_BASE}/folders/create", json=payload, headers=headers) as resp:
            return await resp.json()

    async def list_folders(self):
        """Retrieve a list of folders in Filen.io."""
        headers = {"Authorization": self.token}
        async with self.session.get(f"{API_BASE}/folders/list", headers=headers) as resp:
            return await resp.json()

    async def delete_folder(self, folder_id):
        """Delete a folder from Filen.io."""
        headers = {"Authorization": self.token}
        payload = {"id": folder_id}
        async with self.session.post(f"{API_BASE}/folders/delete", json=payload, headers=headers) as resp:
            return await resp.json()

    async def move_file(self, file_id, destination_folder_id):
        """Move a file to another folder."""
        headers = {"Authorization": self.token}
        payload = {
            "file_id": file_id,
            "destination_folder_id": destination_folder_id
        }
        async with self.session.post(f"{API_BASE}/files/move", json=payload, headers=headers) as resp:
            return await resp.json()

    async def move_folder(self, folder_id, destination_folder_id):
        """Move a folder into another folder."""
        headers = {"Authorization": self.token}
        payload = {
            "folder_id": folder_id,
            "destination_folder_id": destination_folder_id
        }
        async with self.session.post(f"{API_BASE}/folders/move", json=payload, headers=headers) as resp:
            return await resp.json()
            
    async def close(self):
        """Close the session."""
        await self.session.close()
