import requests
import json
import base64
import time

def get_shark_token(email, password):
    """Authenticate with SharkNinja using Auth0"""

    # Auth0 parameters
    auth0_domain = "login.sharkninja.com"
    client_id = ""

    # Step 1: Get Auth0 token using Resource Owner Password flow
    token_url = f"https://{auth0_domain}/oauth/token"
    token_payload = {
        "grant_type": "password",
        "username": email,
        "password": password,
        "client_id": client_id,
        "scope": "openid profile email"
    }

    token_headers = {
        "Content-Type": "application/json"
    }

    print(f"Authenticating with Auth0 at {token_url}")
    response = requests.post(token_url, json=token_payload, headers=token_headers)

    if response.status_code != 200:
        raise Exception(f"Auth0 authentication failed: {response.text}")

    auth0_tokens = response.json()
    access_token = auth0_tokens.get("access_token")
    id_token = auth0_tokens.get("id_token")

    print(f"Successfully obtained Auth0 tokens")

    # The error message suggests we need a key=value format
    # Try these alternative Authorization header formats
    auth_headers = [
        {"Authorization": f"Bearer {id_token}"},
        {"Authorization": f"id_token={id_token}"},  # Try key=value format
        {"Authorization": f"token={id_token}"},     # Try key=value format
        {"Authorization": f"access_token={access_token}"}  # Try key=value format
    ]

    # Try with different URLs
    urls = [
        "https://idp.iot-sharkninja.com/v1/token",
        "https://api.iot-sharkninja.com/v1/auth/token",
        "https://idp.iot-sharkninja.com/v1/me",  # Try a user info endpoint
        "https://api.iot-sharkninja.com/v1/me"   # Try a user info endpoint
    ]

    # Try different HTTP methods
    for url in urls:
        for headers in auth_headers:
            print(f"Trying URL: {url} with headers: {headers}")
            try:
                # Try GET
                response = requests.get(url, headers=headers)
                print(f"GET response: {response.status_code} - {response.text[:100]}")

                if response.status_code == 200:
                    try:
                        data = response.json()
                        print("Successfully exchanged token!")
                        return {
                            "token": data.get("access_token", data.get("token", id_token)),
                            "refresh_token": data.get("refresh_token", auth0_tokens.get("refresh_token")),
                            "expires_in": data.get("expires_in", auth0_tokens.get("expires_in", 3600))
                        }
                    except:
                        # If not JSON, just use the original Auth0 token
                        pass

                # Try POST
                response = requests.post(url, headers=headers)
                print(f"POST response: {response.status_code} - {response.text[:100]}")

                if response.status_code == 200:
                    try:
                        data = response.json()
                        print("Successfully exchanged token!")
                        return {
                            "token": data.get("access_token", data.get("token", id_token)),
                            "refresh_token": data.get("refresh_token", auth0_tokens.get("refresh_token")),
                            "expires_in": data.get("expires_in", auth0_tokens.get("expires_in", 3600))
                        }
                    except:
                        # If not JSON, just use the original Auth0 token
                        pass
            except Exception as e:
                print(f"Error with {url} and {headers}: {e}")

    # Since we couldn't find the right endpoint/header combination,
    # let's just return the Auth0 token and hope it works directly with the API
    print("Couldn't find the right token exchange endpoint - using Auth0 token directly")
    return {
        "token": id_token,  # Use the ID token as it likely contains user info
        "refresh_token": auth0_tokens.get("refresh_token"),
        "expires_in": auth0_tokens.get("expires_in", 3600)
    }
