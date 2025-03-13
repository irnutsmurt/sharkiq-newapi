#!/usr/bin/env python3
"""
Test script for the SharkNinja API authentication

This script tests both the old Ayla API and the new SharkNinja API
to determine which one works with your account.
"""

import asyncio
import argparse
import logging
import sys
from typing import List, Optional
try:
    from sharkiq.ayla_api import get_ayla_api
    from sharkiq.shark_auth import get_shark_auth_client
    from sharkiq.sharkiq import Properties, OperatingModes
    from sharkiq.shark_ninja_api import async_get_shark_ninja_vacuum
    from sharkiq.exc import SharkIqAuthError, SharkIqNotAuthedError
    # Add this line:
    from sharkiq.auth0_client import get_shark_token
except ImportError:
    # Adjust paths for local testing
    import sys
    import os
    sys.path.append(os.path.abspath(".."))
    from sharkiq.ayla_api import get_ayla_api
    from sharkiq.shark_auth import get_shark_auth_client
    from sharkiq.sharkiq import Properties, OperatingModes
    from sharkiq.shark_ninja_api import async_get_shark_ninja_vacuum
    from sharkiq.exc import SharkIqAuthError, SharkIqNotAuthedError
    # Add this line:
    from sharkiq.auth0_client import get_shark_token


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("shark_test")

# Import both APIs (will need to adjust import paths based on your installation)
try:
    from sharkiq.ayla_api import get_ayla_api
    from sharkiq.shark_auth import get_shark_auth_client
    from sharkiq.sharkiq import Properties, OperatingModes
    from sharkiq.shark_ninja_api import async_get_shark_ninja_vacuum
    from sharkiq.exc import SharkIqAuthError, SharkIqNotAuthedError
except ImportError:
    # Adjust paths for local testing
    import sys
    import os
    sys.path.append(os.path.abspath(".."))
    from sharkiq.ayla_api import get_ayla_api
    from sharkiq.shark_auth import get_shark_auth_client
    from sharkiq.sharkiq import Properties, OperatingModes
    from sharkiq.shark_ninja_api import async_get_shark_ninja_vacuum
    from sharkiq.exc import SharkIqAuthError, SharkIqNotAuthedError


async def test_ayla_api(email: str, password: str, europe: bool) -> bool:
    """Test the original Ayla API authentication"""
    logger.info("Testing Ayla API authentication...")
    try:
        ayla_api = get_ayla_api(email, password, europe=europe)
        await ayla_api.async_sign_in()
        devices = await ayla_api.async_get_devices()

        logger.info("Ayla API authentication successful!")
        logger.info(f"Found {len(devices)} devices:")

        for i, device in enumerate(devices):
            logger.info(f"  {i+1}. {device.name} (Model: {device.vac_model_number}, SN: {device.serial_number})")

            # Get some basic properties to verify connection
            battery = device.get_property_value(Properties.BATTERY_CAPACITY)
            error = device.error_text

            logger.info(f"     Battery: {battery}%")
            logger.info(f"     Error: {error if error else 'None'}")

        return True
    except SharkIqAuthError as e:
        logger.error(f"Ayla API authentication failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error with Ayla API: {e}")
        return False


async def test_shark_ninja_api(email: str, password: str, europe: bool) -> bool:
    """Test the new SharkNinja API authentication"""
    logger.info("Testing SharkNinja API authentication...")
    try:
        # First try the direct SharkNinja API
        logger.info("Trying SharkNinja direct API...")
        try:
            auth_client = get_shark_auth_client(email, password, europe=europe)
            await auth_client.async_sign_in()
            logger.info("Direct API authentication successful!")
        except Exception as e:
            logger.warning(f"Direct API authentication failed: {e}")

            # Fall back to Auth0 authentication
            logger.info("Trying Auth0 authentication...")
            try:
                from sharkiq.auth0_client import get_shark_token

                # Run synchronously in a thread since get_shark_token is not async
                loop = asyncio.get_event_loop()
                token_data = await loop.run_in_executor(
                    None, lambda: get_shark_token(email, password)
                )

                logger.info("Auth0 authentication successful!")
                logger.info(f"Token data: {token_data}")

                # Now create a pre-authenticated client
                auth_client = get_shark_auth_client(email, password, europe=europe)
                auth_client._access_token = token_data.get("token")
                auth_client._refresh_token = token_data.get("refresh_token")
                auth_client._is_authed = True

                # Set expiration if available
                if token_data.get("expires_in"):
                    from datetime import datetime, timedelta
                    auth_client._auth_expiration = datetime.now() + timedelta(
                        seconds=token_data.get("expires_in")
                    )
            except Exception as auth0_error:
                logger.error(f"Auth0 authentication also failed: {auth0_error}")
                raise e  # Re-raise the original error

        # Try to get devices
        logger.info("Getting devices...")
        try:
            devices = await async_get_shark_ninja_vacuum(auth_client)

            logger.info(f"Found {len(devices)} devices:")
            for i, device in enumerate(devices):
                logger.info(f"  {i+1}. {device.name} (SN: {device.serial_number})")

                # Get some basic properties to verify connection
                try:
                    battery = device.get_property_value(Properties.BATTERY_CAPACITY)
                    logger.info(f"     Battery: {battery}%")
                except Exception as e:
                    logger.warning(f"     Couldn't get battery: {e}")

                try:
                    error = device.error_text
                    logger.info(f"     Error: {error if error else 'None'}")
                except Exception as e:
                    logger.warning(f"     Couldn't get error: {e}")

        except Exception as e:
            logger.warning(f"Could not get devices: {e}")

        return True
    except Exception as e:
        logger.error(f"SharkNinja API authentication failed: {e}")
        return False

async def main():
    """Main function to run the tests"""
    parser = argparse.ArgumentParser(description="Test SharkIQ API authentication")
    parser.add_argument("--email", "-e", required=True, help="Email address for Shark account")
    parser.add_argument("--password", "-p", required=True, help="Password for Shark account")
    parser.add_argument("--europe", action="store_true", help="Use European endpoints")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Test both APIs
    ayla_success = await test_ayla_api(args.email, args.password, args.europe)
    shark_ninja_success = await test_shark_ninja_api(args.email, args.password, args.europe)

    # Print summary
    logger.info("\n=== RESULTS ===")
    logger.info(f"Ayla API: {'SUCCESS' if ayla_success else 'FAILED'}")
    logger.info(f"SharkNinja API: {'SUCCESS' if shark_ninja_success else 'FAILED'}")

    if shark_ninja_success:
        logger.info("\n✅ The new SharkNinja API works with your account!")
        logger.info("You should be able to use the updated integration.")
    elif ayla_success:
        logger.info("\n⚠ The original Ayla API works but the new SharkNinja API doesn't.")
        logger.info("You may not need to update your integration yet.")
    else:
        logger.info("\n❌ Neither API works with your account.")
        logger.info("Check your credentials and try again.")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
