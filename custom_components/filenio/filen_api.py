import aiohttp
import hashlib
import json
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
        encrypted_data = cipher.encrypt(pad(data, AES.block_size))

        encrypted_file = base64.b64encode(iv + encrypted_data).decode()

        headers = {"Authorization": self.token}
        async with self.session.post(f"{API_BASE}/upload", json={"file": encrypted_file, "name": file_name}, headers=headers) as resp:
            return await resp.json()

    async def close(self):
        """Close the session."""
        await self.session.close()
