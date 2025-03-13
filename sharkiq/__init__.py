"""Python API for Shark IQ vacuum robots"""
from .ayla_api import get_ayla_api, AylaApi
from .exc import (
    SharkIqError,
    SharkIqAuthExpiringError,
    SharkIqNotAuthedError,
    SharkIqAuthError,
    SharkIqReadOnlyPropertyError,
)
from .sharkiq import OperatingModes, PowerModes, Properties, SharkIqVacuum
# Add these new imports
from .shark_auth import get_shark_auth_client, SharkAuthClient
from .shark_ninja_api import get_shark_ninja_vacuum, async_get_shark_ninja_vacuum, SharkNinjaVacuum

__version__ = '1.0.3'  # Increment the version number since we're adding new functionality
