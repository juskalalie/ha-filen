import aiohttp
import hashlib
import base64
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

API_BASE = "https://api.filen.io/v1"
MAX_RETRIES = 3
TIMEOUT = 10  # Timeout for network requests

_LOGGER = logging.getLogger(__name__)

class FilenClient:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.token = None
        self.session = aiohttp.ClientSession()

    async def login(self):
        """Authenticate and get a session token with retries."""
        password_hash = hashlib.sha512(self.password.encode()).hexdigest()
        retries = 0

        while retries < MAX_RETRIES:
            try:
                async with self.session.post(
                    f"{API_BASE}/auth/login", 
                    json={"email": self.email, "password": password_hash}, 
                    timeout=TIMEOUT
                ) as resp:
                    data = await resp.json()
                    if resp.status == 200 and data.get("status"):
                        self.token = data["data"]["token"]
                        _LOGGER.info("Login successful")
                        return True
                    _LOGGER.warning("Login failed: %s", data.get("message", "Unknown error"))
            except asyncio.TimeoutError:
                _LOGGER.error("Login request timed out")
            except aiohttp.ClientError as e:
                _LOGGER.error("Network error during login: %s", e)

            retries += 1
            await asyncio.sleep(2)  # Retry delay

        _LOGGER.error("Login failed after %d attempts", MAX_RETRIES)
        return False

    async def make_request(self, method, endpoint, payload=None):
        """Generic API request handler with improved error handling and retries."""
        headers = {"Authorization": self.token}
        retries = 0

        while retries < MAX_RETRIES:
            try:
                async with self.session.request(
                    method, f"{API_BASE}/{endpoint}", json=payload, headers=headers, timeout=TIMEOUT
                ) as resp:
                    data = await resp.json()

                    # Handle expired token
                    if resp.status == 401:
                        _LOGGER.warning("Session expired. Attempting to reauthenticate...")
                        if await self.login():
                            headers["Authorization"] = self.token
                            continue  # Retry the request with the new token
                        else:
                            _LOGGER.error("Reauthentication failed")
                            return None

                    # Return data if successful
                    if resp.status == 200 and data.get("status"):
                        return data

                    _LOGGER.warning("Request to %s failed: %s", endpoint, data.get("message", "Unknown error"))
                    return None
            except asyncio.TimeoutError:
                _LOGGER.error("Request to %s timed out", endpoint)
            except aiohttp.ClientError as e:
                _LOGGER.error("Network error: %s", e)

            retries += 1
            await asyncio.sleep(2)  # Retry delay

        _LOGGER.error("Request to %s failed after %d attempts", endpoint, MAX_RETRIES)
        return None
        
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
        """Move a file with improved error handling."""
        payload = {"file_id": file_id, "destination_folder_id": destination_folder_id}
        return await self.make_request("POST", "files/move", payload)

    async def move_folder(self, folder_id, destination_folder_id):
        """Move a folder with improved error handling."""
        payload = {"folder_id": folder_id, "destination_folder_id": destination_folder_id}
        return await self.make_request("POST", "folders/move", payload)
            
    async def close(self):
        """Close the session."""
        await self.session.close()
