"""
Home Assistant integration for Filen.io cloud storage.
This integration allows you to upload and download files from your Filen.io account
with proper encryption and decryption.
"""
import asyncio
import logging
import os
import voluptuous as vol
import hashlib
import base64
import json
import time
import aiohttp
import secrets
import tempfile
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN = "filen"
SCAN_INTERVAL = timedelta(minutes=30)

# Configuration schema
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_EMAIL): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Services
SERVICE_UPLOAD_FILE = "upload_file"
SERVICE_DOWNLOAD_FILE = "download_file"
SERVICE_LIST_FILES = "list_files"

ATTR_LOCAL_PATH = "local_path"
ATTR_REMOTE_PATH = "remote_path"
ATTR_FOLDER_UUID = "folder_uuid"
ATTR_FILE_NAME = "file_name"

SERVICE_UPLOAD_FILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LOCAL_PATH): cv.string,
        vol.Required(ATTR_FOLDER_UUID): cv.string,
        vol.Optional(ATTR_FILE_NAME): cv.string,
    }
)

SERVICE_DOWNLOAD_FILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_REMOTE_PATH): cv.string,
        vol.Required(ATTR_LOCAL_PATH): cv.string,
    }
)

SERVICE_LIST_FILES_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_FOLDER_UUID): cv.string,
    }
)

# Chunk size for file uploads (10MB)
CHUNK_SIZE = 10 * 1024 * 1024

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Filen component."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in config:
        return True

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Filen from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    filen = FilenApi(hass, email, password)
    try:
        await filen.login()
    except Exception as err:
        _LOGGER.error("Failed to login to Filen.io: %s", err)
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = filen

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPLOAD_FILE,
        filen.handle_upload_file,
        schema=SERVICE_UPLOAD_FILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DOWNLOAD_FILE,
        filen.handle_download_file,
        schema=SERVICE_DOWNLOAD_FILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_FILES,
        filen.handle_list_files,
        schema=SERVICE_LIST_FILES_SCHEMA,
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Filen config entry."""
    # Unregister services
    for service in [SERVICE_UPLOAD_FILE, SERVICE_DOWNLOAD_FILE, SERVICE_LIST_FILES]:
        hass.services.async_remove(DOMAIN, service)

    hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True

class FilenApi:
    """Wrapper for the Filen.io API."""

    def __init__(self, hass: HomeAssistant, email: str, password: str):
        """Initialize the API client."""
        self.hass = hass
        self.email = email
        self.password = password
        self.auth_token = None
        self.master_key = None
        self.session = aiohttp.ClientSession()
        self.api_base_url = "https://gateway.filen.io/v3/auth/info"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    def _hash_password(self, password: str) -> str:
        """Hash the password using SHA512."""
        return hashlib.sha512(password.encode()).hexdigest()

    def _derive_master_key(self, password: str, salt: str) -> bytes:
        """Derive the master key from password and salt."""
        return PBKDF2(password, salt.encode(), dkLen=32, count=100000)

    def _decrypt_master_key(self, encrypted_master_key: str, derived_key: bytes) -> str:
        """Decrypt the master key using the derived key."""
        try:
            encrypted_data = base64.b64decode(encrypted_master_key)
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]
            
            cipher = AES.new(derived_key, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
            
            return decrypted.decode('utf-8')
        except Exception as e:
            _LOGGER.error(f"Error decrypting master key: {e}")
            raise

    def _encrypt_file_key(self, file_key: str, master_key: str) -> str:
        """Encrypt the file key using the master key."""
        try:
            file_key_bytes = file_key.encode('utf-8')
            master_key_bytes = base64.b64decode(master_key)
            
            iv = secrets.token_bytes(16)
            cipher = AES.new(master_key_bytes, AES.MODE_CBC, iv)
            padded_data = pad(file_key_bytes, AES.block_size)
            ciphertext = cipher.encrypt(padded_data)
            
            encrypted_data = iv + ciphertext
            return base64.b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            _LOGGER.error(f"Error encrypting file key: {e}")
            raise

    def _decrypt_file_key(self, encrypted_file_key: str, master_key: str) -> str:
        """Decrypt the file key using the master key."""
        try:
            encrypted_data = base64.b64decode(encrypted_file_key)
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]
            
            master_key_bytes = base64.b64decode(master_key)
            cipher = AES.new(master_key_bytes, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
            
            return decrypted.decode('utf-8')
        except Exception as e:
            _LOGGER.error(f"Error decrypting file key: {e}")
            raise

    async def _encrypt_file(self, file_path: str) -> Tuple[str, str, List[bytes]]:
        """
        Encrypt a file for uploading to Filen.
        Returns the file key, metadata, and encrypted chunks.
        """
        try:
            # Generate a random key for file encryption
            file_key = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
            file_key_bytes = base64.b64decode(file_key)
            
            # Read the file and split into chunks
            file_size = os.path.getsize(file_path)
            chunks = []
            
            with open(file_path, 'rb') as f:
                chunk_count = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
                
                for _ in range(chunk_count):
                    chunk_data = f.read(CHUNK_SIZE)
                    if not chunk_data:
                        break
                    
                    # Encrypt chunk
                    iv = secrets.token_bytes(16)
                    cipher = AES.new(file_key_bytes, AES.MODE_CBC, iv)
                    padded_data = pad(chunk_data, AES.block_size)
                    encrypted_chunk = iv + cipher.encrypt(padded_data)
                    
                    chunks.append(encrypted_chunk)
            
            # Create metadata
            file_name = os.path.basename(file_path)
            metadata = {
                "name": file_name,
                "size": file_size,
                "mime": self._get_mime_type(file_path),
            }
            
            metadata_json = json.dumps(metadata)
            
            # Encrypt metadata
            iv = secrets.token_bytes(16)
            cipher = AES.new(file_key_bytes, AES.MODE_CBC, iv)
            padded_metadata = pad(metadata_json.encode('utf-8'), AES.block_size)
            encrypted_metadata = base64.b64encode(iv + cipher.encrypt(padded_metadata)).decode('utf-8')
            
            return file_key, encrypted_metadata, chunks
        except Exception as e:
            _LOGGER.error(f"Error encrypting file: {e}")
            raise

    async def _decrypt_file(self, encrypted_chunks: List[bytes], file_key: str, output_path: str) -> None:
        """
        Decrypt file chunks and save to output path.
        """
        try:
            file_key_bytes = base64.b64decode(file_key)
            
            with open(output_path, 'wb') as f:
                for chunk in encrypted_chunks:
                    iv = chunk[:16]
                    ciphertext = chunk[16:]
                    
                    cipher = AES.new(file_key_bytes, AES.MODE_CBC, iv)
                    decrypted_chunk = unpad(cipher.decrypt(ciphertext), AES.block_size)
                    
                    f.write(decrypted_chunk)
        except Exception as e:
            _LOGGER.error(f"Error decrypting file: {e}")
            raise

    def _get_mime_type(self, file_path: str) -> str:
        """Get the MIME type of a file."""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"

    async def login(self) -> None:
        """Log in to Filen.io and get an auth token."""
        hashed_password = self._hash_password(self.password)

        login_data = {
            "email": self.email,
            "password": hashed_password,
            "twoFactorCode": None,  # Optional 2FA code
            "authVersion": 2
        }

        try:
            response = await self.session.post(
                f"{self.api_base_url}/v3/login",
                json=login_data
            )
            data = await response.json()

            if not data.get("status"):
                raise Exception(data.get("message", "Unknown login error"))

            self.auth_token = data.get("data", {}).get("apiKey")
            
            # Handle master key decryption
            encrypted_master_keys = data.get("data", {}).get("masterKeys")
            user_email = data.get("data", {}).get("email")
            user_salt = data.get("data", {}).get("salt")
            
            if encrypted_master_keys and user_email and user_salt:
                # Use the first master key
                encrypted_master_key = encrypted_master_keys.split(",")[0]
                
                # Derive key from password and salt
                derived_key = self._derive_master_key(self.password, user_salt)
                
                # Decrypt master key
                self.master_key = self._decrypt_master_key(encrypted_master_key, derived_key)
                
                _LOGGER.info("Successfully decrypted master key")
            else:
                raise Exception("Could not retrieve master key data")
            
            _LOGGER.info("Successfully logged in to Filen.io")
        except Exception as err:
            _LOGGER.error("Failed to login to Filen.io: %s", err)
            raise

    async def handle_upload_file(self, call: ServiceCall) -> None:
        """Handle the file upload service call."""
        local_path = call.data[ATTR_LOCAL_PATH]
        folder_uuid = call.data[ATTR_FOLDER_UUID]
        file_name = call.data.get(ATTR_FILE_NAME)
        
        try:
            if not os.path.exists(local_path):
                raise Exception(f"Local file not found: {local_path}")
                
            await self.upload_file(local_path, folder_uuid, file_name)
            _LOGGER.info("Successfully uploaded file %s to Filen.io", local_path)
        except Exception as err:
            _LOGGER.error("Failed to upload file to Filen.io: %s", err)

    async def handle_download_file(self, call: ServiceCall) -> None:
        """Handle the file download service call."""
        remote_path = call.data[ATTR_REMOTE_PATH]
        local_path = call.data[ATTR_LOCAL_PATH]
        
        try:
            await self.download_file(remote_path, local_path)
            _LOGGER.info("Successfully downloaded file %s from Filen.io to %s", remote_path, local_path)
        except Exception as err:
            _LOGGER.error("Failed to download file from Filen.io: %s", err)

    async def handle_list_files(self, call: ServiceCall) -> None:
        """Handle the list files service call."""
        folder_uuid = call.data.get(ATTR_FOLDER_UUID, "base")
        
        try:
            files = await self.list_files(folder_uuid)
            
            # Create a readable list of files
            file_list = []
            for file in files:
                file_list.append({
                    "name": file.get("name", "Unknown"),
                    "uuid": file.get("uuid", ""),
                    "size": self._format_size(file.get("size", 0)),
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S', 
                                             time.localtime(file.get("timestamp", 0)))
                })
            
            _LOGGER.info("Files in folder %s: %s", folder_uuid, file_list)
            
            # Create a persistent notification with the file list
            file_names = "\n".join([f"- {file['name']} ({file['size']}, {file['timestamp']})" 
                                    for file in file_list])
            
            self.hass.components.persistent_notification.create(
                f"Files in folder {folder_uuid}:\n{file_names}",
                title="Filen.io Files",
                notification_id=f"filen_files_{folder_uuid}"
            )
        except Exception as err:
            _LOGGER.error("Failed to list files from Filen.io: %s", err)

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    async def upload_file(self, local_path: str, folder_uuid: str, custom_file_name: str = None) -> Dict[str, Any]:
        """Upload a file to Filen.io with encryption."""
        if not self.auth_token or not self.master_key:
            await self.login()

        file_name = custom_file_name or os.path.basename(local_path)
        file_size = os.path.getsize(local_path)
        
        # Encrypt the file
        _LOGGER.info("Encrypting file for upload: %s", file_name)
        file_key, encrypted_metadata, encrypted_chunks = await self._encrypt_file(local_path)
        
        # Encrypt the file key with the master key
        encrypted_file_key = self._encrypt_file_key(file_key, self.master_key)
        
        # Step 1: Get upload info
        upload_info_data = {
            "apiKey": self.auth_token,
            "uuid": folder_uuid,
            "name": file_name,
            "size": file_size,
            "chunks": len(encrypted_chunks),
            "mime": self._get_mime_type(local_path)
        }
        
        response = await self.session.post(
            f"{self.api_base_url}/v3/upload/prepare",
            json=upload_info_data
        )
        
        upload_info = await response.json()
        if not upload_info.get("status"):
            raise Exception(upload_info.get("message", "Upload preparation failed"))
        
        upload_key = upload_info["data"]["uploadKey"]
        
        # Step 2: Upload each chunk
        _LOGGER.info("Uploading file in %d chunks", len(encrypted_chunks))
        
        for i, chunk in enumerate(encrypted_chunks):
            chunk_number = i + 1
            
            form = aiohttp.FormData()
            form.add_field("uploadKey", upload_key)
            form.add_field("chunk", str(chunk_number))
            
            # Create a temporary file for the chunk
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(chunk)
                temp_name = temp_file.name
                
            try:
                # Add the file field after the temp file is closed
                form.add_field("file", 
                               open(temp_name, 'rb'),
                               filename=f"{file_name}.chunk{chunk_number}",
                               content_type="application/octet-stream")
                
                _LOGGER.info("Uploading chunk %d/%d", chunk_number, len(encrypted_chunks))
                response = await self.session.post(
                    f"{self.api_base_url}/v3/upload",
                    data=form
                )
                
                data = await response.json()
                if not data.get("status"):
                    raise Exception(data.get("message", f"File upload failed for chunk {chunk_number}"))
            finally:
                # Remove the temporary file
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        
        # Step 3: Finish the upload by submitting the file metadata
        finish_data = {
            "apiKey": self.auth_token,
            "uploadKey": upload_key,
            "uuid": folder_uuid,
            "name": file_name,
            "size": file_size,
            "chunks": len(encrypted_chunks),
            "mime": self._get_mime_type(local_path),
            "metadata": encrypted_metadata,
            "key": encrypted_file_key,
            "rm": "none"  # No redundancy
        }
        
        response = await self.session.post(
            f"{self.api_base_url}/v3/upload/done",
            json=finish_data
        )
        
        result = await response.json()
        if not result.get("status"):
            raise Exception(result.get("message", "Failed to complete upload"))
        
        _LOGGER.info("Upload completed successfully")
        return result

    async def download_file(self, file_uuid: str, local_path: str) -> None:
        """Download and decrypt a file from Filen.io."""
        if not self.auth_token or not self.master_key:
            await self.login()
            
        # Get file metadata
        file_info_data = {
            "apiKey": self.auth_token,
            "uuid": file_uuid
        }
        
        response = await self.session.post(
            f"{self.api_base_url}/v3/file/info",
            json=file_info_data
        )
        
        file_info = await response.json()
        if not file_info.get("status"):
            raise Exception(file_info.get("message", "Could not get file info"))
        
        file_data = file_info.get("data", {})
        encrypted_file_key = file_data.get("key")
        
        if not encrypted_file_key:
            raise Exception("Could not retrieve file encryption key")
        
        # Decrypt the file key using the master key
        file_key = self._decrypt_file_key(encrypted_file_key, self.master_key)
        
        # Get download link
        download_data = {
            "apiKey": self.auth_token,
            "uuid": file_uuid
        }
        
        response = await self.session.post(
            f"{self.api_base_url}/v3/download/file",
            json=download_data
        )
        
        download_info = await response.json()
        if not download_info.get("status"):
            raise Exception(download_info.get("message", "Could not get download link"))
        
        # Download the encrypted file
        download_url = download_info["data"]["downloadURL"]
        chunks = []
        
        # Create a temporary file for the download
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_name = temp_file.name
            
        try:
            # Download to the temporary file
            async with self.session.get(download_url) as response:
                with open(temp_name, 'wb') as f:
                    chunk_size = 8192  # 8KB chunks for download
                    while True:
                        chunk = await response.content.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
            
            # Read and process the encrypted file
            file_size = os.path.getsize(temp_name)
            
            # For simplicity, we'll treat the whole file as a single chunk here
            # In a more complete implementation, you'd handle multiple chunks as needed
            with open(temp_name, 'rb') as f:
                encrypted_data = f.read()
                chunks.append(encrypted_data)
            
            # Ensure the directory exists for the output file
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            
            # Decrypt the file
            _LOGGER.info("Decrypting downloaded file")
            await self._decrypt_file(chunks, file_key, local_path)
            
            _LOGGER.info("File successfully downloaded and decrypted")
        
        finally:
            # Remove the temporary file
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    async def list_files(self, folder_uuid: str = "base") -> List[Dict[str, Any]]:
        """List files in a folder."""
        if not self.auth_token:
            await self.login()
            
        list_data = {
            "apiKey": self.auth_token,
            "uuid": folder_uuid,
            "skipCache": True
        }
        
        response = await self.session.post(
            f"{self.api_base_url}/v3/dir/content",
            json=list_data
        )
        
        data = await response.json()
        if not data.get("status"):
            raise Exception(data.get("message", "Could not list files"))
        
        files = data.get("data", {}).get("files", [])
        
        # For each file, try to decrypt its metadata to get the real name
        decrypted_files = []
        
        for file in files:
            try:
                if self.master_key and file.get("key") and file.get("metadata"):
                    # Decrypt the file key
                    file_key = self._decrypt_file_key(file["key"], self.master_key)
                    
                    # Decrypt metadata
                    encrypted_metadata = base64.b64decode(file["metadata"])
                    iv = encrypted_metadata[:16]
                    ciphertext = encrypted_metadata[16:]
                    
                    file_key_bytes = base64.b64decode(file_key)
                    cipher = AES.new(file_key_bytes, AES.MODE_CBC, iv)
                    decrypted_metadata = unpad(cipher.decrypt(ciphertext), AES.block_size)
                    
                    metadata = json.loads(decrypted_metadata.decode('utf-8'))
                    
                    # Update file with decrypted metadata
                    file.update(metadata)
            except Exception as e:
                _LOGGER.warning(f"Could not decrypt metadata for file {file.get('uuid')}: {e}")
                
            decrypted_files.append(file)
        
        return decrypted_files
