"""
SharkNinja Identity Provider (IDP) API client.

This replaces the Ayla Networks authentication previously used by SharkIQ devices.
"""

import aiohttp
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional

from .exc import SharkIqAuthError, SharkIqAuthExpiringError, SharkIqNotAuthedError
from .const import (
    DEVICE_URL,
    EU_DEVICE_URL,
    SHARK_APP_ID,
    SHARK_APP_SECRET,
    EU_SHARK_APP_ID,
    EU_SHARK_APP_SECRET
)

# New SharkNinja IDP endpoints
SHARK_IDP_URL = "https://idp.iot-sharkninja.com/v1/login-message-shark"
EU_SHARK_IDP_URL = "https://idp.eu.iot-sharkninja.com/v1/login-message-shark"


class SharkAuthClient:
    """Authentication client for the SharkNinja IDP"""

    def __init__(
            self,
            email: str,
            password: str,
            app_id: str,
            app_secret: str,
            websession: Optional[aiohttp.ClientSession] = None,
            europe: bool = False):
        self._email = email
        self._password = password
        self._access_token = None  # type: Optional[str]
        self._refresh_token = None  # type: Optional[str]
        self._auth_expiration = None  # type: Optional[datetime]
        self._is_authed = False  # type: bool
        self._app_id = app_id
        self._app_secret = app_secret
        self.websession = websession
        self.europe = europe
        self._device_url = EU_DEVICE_URL if europe else DEVICE_URL
        self._auth_url = EU_SHARK_IDP_URL if europe else SHARK_IDP_URL

    async def ensure_session(self) -> aiohttp.ClientSession:
        """Ensure that we have an aiohttp ClientSession"""
        if self.websession is None:
            self.websession = aiohttp.ClientSession()
        return self.websession

    @property
    def _login_data(self) -> Dict:
        """Authentication payload for the SharkNinja IDP"""
        return {
            "email": self._email,
            "password": self._password,
            "client_id": self._app_id,
            "client_secret": self._app_secret
        }

    def _set_credentials(self, status_code: int, login_result: Dict):
        """Update the internal credentials from the login response"""
        if status_code == 404:
            raise SharkIqAuthError(f"Authentication endpoint not found. Status: {status_code}")
        elif status_code == 401:
            raise SharkIqAuthError(f"Authentication failed. Status: {status_code}")
        elif status_code != 200:
            raise SharkIqAuthError(f"Unexpected authentication response. Status: {status_code}")

        # Extract tokens from the new SharkNinja IDP response format
        # Adjust these field names based on the actual response format
        try:
            self._access_token = login_result["token"]
            self._refresh_token = login_result.get("refresh_token")

            # Set expiration - default to 1 hour if not specified
            expires_in = login_result.get("expires_in", 3600)
            self._auth_expiration = datetime.now() + timedelta(seconds=expires_in)

            self._is_authed = True
        except KeyError as e:
            raise SharkIqAuthError(f"Missing expected field in authentication response: {e}")

    def sign_in(self):
        """Authenticate to SharkNinja IDP synchronously"""
        login_data = self._login_data
        resp = requests.post(self._auth_url, json=login_data)
        self._set_credentials(resp.status_code, resp.json())

    async def async_sign_in(self):
        """Authenticate to SharkNinja IDP asynchronously"""
        session = await self.ensure_session()
        login_data = self._login_data
        async with session.post(self._auth_url, json=login_data) as resp:
            self._set_credentials(resp.status, await resp.json())

    def refresh_auth(self):
        """Refresh authentication synchronously"""
        if not self._refresh_token:
            # If no refresh token available, perform a full sign-in
            self.sign_in()
            return

        refresh_data = {"refresh_token": self._refresh_token}
        # Note: Adjust the refresh endpoint URL as needed
        refresh_url = f"{self._auth_url}/refresh"
        resp = requests.post(refresh_url, json=refresh_data)
        self._set_credentials(resp.status_code, resp.json())

    async def async_refresh_auth(self):
        """Refresh authentication asynchronously"""
        if not self._refresh_token:
            # If no refresh token available, perform a full sign-in
            await self.async_sign_in()
            return

        session = await self.ensure_session()
        refresh_data = {"refresh_token": self._refresh_token}
        # Note: Adjust the refresh endpoint URL as needed
        refresh_url = f"{self._auth_url}/refresh"
        async with session.post(refresh_url, json=refresh_data) as resp:
            self._set_credentials(resp.status, await resp.json())

    def _clear_auth(self):
        """Clear authentication state"""
        self._is_authed = False
        self._access_token = None
        self._refresh_token = None
        self._auth_expiration = None

    def sign_out(self):
        """Sign out and invalidate the access token"""
        # Implement sign-out if the API supports it
        # Otherwise just clear local auth state
        self._clear_auth()

    async def async_sign_out(self):
        """Sign out and invalidate the access token"""
        # Implement sign-out if the API supports it
        # Otherwise just clear local auth state
        self._clear_auth()

    @property
    def auth_expiration(self) -> Optional[datetime]:
        """When does the auth expire"""
        if not self._is_authed:
            return None
        elif self._auth_expiration is None:
            raise SharkIqNotAuthedError("Invalid state. Please reauthorize.")
        else:
            return self._auth_expiration

    @property
    def token_expired(self) -> bool:
        """Return true if the token has already expired"""
        if self.auth_expiration is None:
            return True
        return datetime.now() > self.auth_expiration

    @property
    def token_expiring_soon(self) -> bool:
        """Return true if the token will expire soon"""
        if self.auth_expiration is None:
            return True
        return datetime.now() > self.auth_expiration - timedelta(seconds=600)

    def check_auth(self, raise_expiring_soon=True):
        """Confirm authentication status"""
        if not self._access_token or not self._is_authed or self.token_expired:
            self._is_authed = False
            raise SharkIqNotAuthedError()
        elif raise_expiring_soon and self.token_expiring_soon:
            raise SharkIqAuthExpiringError()

    @property
    def auth_header(self) -> Dict[str, str]:
        """Get the authentication header for API requests"""
        self.check_auth()
        # Adjust the header format based on the SharkNinja API requirements
        return {"Authorization": f"Bearer {self._access_token}"}

    def _get_headers(self, fn_kwargs) -> Dict[str, str]:
        """
        Extract the headers element from fn_kwargs, removing it if it exists
        and updating with self.auth_header.
        """
        try:
            headers = fn_kwargs['headers']
        except KeyError:
            headers = {}
        else:
            del fn_kwargs['headers']
        headers.update(self.auth_header)
        return headers

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make an authenticated HTTP request"""
        headers = self._get_headers(kwargs)
        return requests.request(method, url, headers=headers, **kwargs)

    async def async_request(self, http_method: str, url: str, **kwargs):
        """Make an authenticated HTTP request asynchronously"""
        session = await self.ensure_session()
        headers = self._get_headers(kwargs)
        return session.request(http_method, url, headers=headers, **kwargs)

    def list_devices(self) -> list:
        """List devices associated with the account"""
        # The endpoint might be different in the new API
        device_url = f"{self._device_url}/apiv1/devices.json"
        resp = self.request("get", device_url)
        devices = resp.json()
        if resp.status_code == 401:
            raise SharkIqAuthError("Authentication failed when listing devices")
        return [d["device"] for d in devices]

    async def async_list_devices(self) -> list:
        """List devices associated with the account asynchronously"""
        # The endpoint might be different in the new API
        device_url = f"{self._device_url}/apiv1/devices.json"
        async with await self.async_request("get", device_url) as resp:
            devices = await resp.json()
            if resp.status == 401:
                raise SharkIqAuthError("Authentication failed when listing devices")
        return [d["device"] for d in devices]


def get_shark_auth_client(username: str, password: str, websession: Optional[aiohttp.ClientSession] = None, europe: bool = False):
    """Get a SharkAuthClient object"""
    if europe:
        return SharkAuthClient(username, password, EU_SHARK_APP_ID, EU_SHARK_APP_SECRET, websession=websession, europe=europe)
    else:
        return SharkAuthClient(username, password, SHARK_APP_ID, SHARK_APP_SECRET, websession=websession)
