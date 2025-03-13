"""
Updated Shark IQ API client to work with the SharkNinja authentication system
"""
import enum
import logging
from typing import Optional, List, Dict, Any

from .shark_auth import SharkAuthClient
from .sharkiq import SharkIqVacuum, Properties, OperatingModes, PropertyName, PropertyValue

_LOGGER = logging.getLogger(__name__)

# The new SharkNinja API endpoints
SHARK_API_URL = "https://api.iot-sharkninja.com/v1"
EU_SHARK_API_URL = "https://api.eu.iot-sharkninja.com/v1"

class SharkNinjaVacuum(SharkIqVacuum):
    """
    Updated SharkIQ vacuum class that works with the SharkNinja API instead of Ayla Networks

    This extends the original SharkIqVacuum class but uses the new API endpoints
    """

    def __init__(self, auth_client: SharkAuthClient, device_data: Dict, europe: bool = False):
        """Initialize a SharkNinja vacuum instance"""
        # Initialize the base class with the device data
        # We'll override the methods that interact with the API
        self.auth_client = auth_client
        self._dsn = device_data['dsn']
        self._key = device_data.get('key', '')
        self._oem_model_number = device_data.get('oem_model', '')
        self._vac_model_number = None
        self._vac_serial_number = None
        self._properties_full = {}
        self.property_values = {}  # We'll populate this differently
        self._settable_properties = None
        self.europe = europe

        # API base URL
        self._api_base = EU_SHARK_API_URL if europe else SHARK_API_URL

        # Properties from the device data
        self._name = device_data.get('product_name', f"Shark Vacuum {self._dsn}")
        self._error = None

    @property
    def update_url(self) -> str:
        """API endpoint to fetch updated device properties"""
        return f"{self._api_base}/robots/{self._dsn}/properties"

    @property
    def metadata_endpoint(self) -> str:
        """Endpoint for device metadata"""
        return f"{self._api_base}/robots/{self._dsn}/metadata"

    def set_property_endpoint(self, property_name: PropertyName) -> str:
        """Get the API endpoint for setting a property"""
        if isinstance(property_name, enum.Enum):
            property_name = property_name.value
        return f"{self._api_base}/robots/{self._dsn}/properties/{property_name}"

    def update(self, property_list: Optional[List[str]] = None):
        """Update the known device state"""
        params = {"names[]": property_list} if property_list else None

        resp = self.auth_client.request("get", self.update_url, params=params)
        if resp.status_code != 200:
            _LOGGER.error(f"Failed to update device properties: {resp.status_code}")
            return

        # Process the response based on the new API format
        properties = resp.json()
        self._process_properties(properties)

    async def async_update(self, property_list: Optional[List[str]] = None):
        """Update the known device state asynchronously"""
        params = {"names[]": property_list} if property_list else None

        async with await self.auth_client.async_request("get", self.update_url, params=params) as resp:
            if resp.status != 200:
                _LOGGER.error(f"Failed to update device properties: {resp.status}")
                return

            properties = await resp.json()

        self._process_properties(properties)

    def _process_properties(self, properties: Dict[str, Any]):
        """Process properties from the new API format"""
        # The structure will likely be different from the Ayla API
        # This is a placeholder - adjust based on actual API response
        self._properties_full = properties

        # Extract values into a simplified dictionary
        self.property_values = {k: v.get("value") for k, v in properties.items()}

    def get_property_value(self, property_name: PropertyName) -> Any:
        """Get the value of a property"""
        if isinstance(property_name, enum.Enum):
            property_name = property_name.value
        return self.property_values.get(property_name)

    def set_property_value(self, property_name: PropertyName, value: PropertyValue):
        """Set a property value"""
        if isinstance(property_name, enum.Enum):
            property_name = property_name.value
        if isinstance(value, enum.Enum):
            value = value.value

        endpoint = self.set_property_endpoint(property_name)
        data = {"value": value}

        resp = self.auth_client.request("put", endpoint, json=data)
        if resp.status_code != 200:
            _LOGGER.error(f"Failed to set property {property_name}: {resp.status_code}")
            return

        # Update local state
        self.property_values[property_name] = value

    async def async_set_property_value(self, property_name: PropertyName, value: PropertyValue):
        """Set a property value asynchronously"""
        if isinstance(property_name, enum.Enum):
            property_name = property_name.value
        if isinstance(value, enum.Enum):
            value = value.value

        endpoint = self.set_property_endpoint(property_name)
        data = {"value": value}

        async with await self.auth_client.async_request("put", endpoint, json=data) as resp:
            if resp.status != 200:
                _LOGGER.error(f"Failed to set property {property_name}: {resp.status}")
                return

        # Update local state
        self.property_values[property_name] = value

    # The rest of the methods (clean_rooms, get_room_list, etc.) should work with minimal changes
    # since they mostly use get_property_value and set_property_value


def get_shark_ninja_vacuum(auth_client: SharkAuthClient, update: bool = True) -> List[SharkNinjaVacuum]:
    """Get SharkNinja vacuum devices for the account"""
    # This function needs to fetch the list of devices from the new API
    # As a fallback, we can try using the existing list_devices method
    devices = []

    try:
        device_list = auth_client.list_devices()
        devices = [SharkNinjaVacuum(auth_client, d, europe=auth_client.europe) for d in device_list]

        if update:
            for device in devices:
                device.update()
    except Exception as e:
        _LOGGER.error(f"Failed to get devices: {e}")

    return devices


async def async_get_shark_ninja_vacuum(auth_client: SharkAuthClient, update: bool = True) -> List[SharkNinjaVacuum]:
    """Get SharkNinja vacuum devices for the account asynchronously"""
    devices = []

    try:
        device_list = await auth_client.async_list_devices()
        devices = [SharkNinjaVacuum(auth_client, d, europe=auth_client.europe) for d in device_list]

        if update:
            for device in devices:
                await device.async_update()
    except Exception as e:
        _LOGGER.error(f"Failed to get devices: {e}")

    return devices
