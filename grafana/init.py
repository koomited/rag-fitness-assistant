import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Grafana configuration
GRAFANA_URL = "http://localhost:3000"
GRAFANA_USER = os.getenv("GRAFANA_ADMIN_USER")
GRAFANA_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD")

# PostgreSQL configuration
PG_HOST = "postgres"  # Assuming the service is named 'postgres' in Docker Compose
PG_DB = os.getenv("POSTGRES_DB")
PG_USER = os.getenv("POSTGRES_USER")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD")
PG_PORT = os.getenv("POSTGRES_PORT")

def create_api_key():
    auth = (GRAFANA_USER, GRAFANA_PASSWORD)
    headers = {"Content-Type": "application/json"}

    # Step 1: Create a service account
    service_account_payload = {
        "name": "ProgrammaticServiceAccount",
        "role": "Admin",
        "isDisabled": False
    }
    response = requests.post(
        f"{GRAFANA_URL}/api/serviceaccounts",
        auth=auth,
        headers=headers,
        json=service_account_payload
    )

    if response.status_code == 201:
        print("Service account created successfully")
        service_account_id = response.json().get("id")
    elif response.status_code in [400, 409]:  # Handle both 400 and 409 for existing service account
        print("Service account already exists, checking for existing account...")
        response = requests.get(f"{GRAFANA_URL}/api/serviceaccounts/search", auth=auth, headers=headers)
        if response.status_code == 200:
            for sa in response.json().get("serviceAccounts", []):
                if sa["name"] == "ProgrammaticServiceAccount":
                    service_account_id = sa["id"]
                    print(f"Found existing service account with ID: {service_account_id}")
                    break
            else:
                print("Failed to find existing service account")
                return None
        else:
            print(f"Failed to search for service accounts: {response.status_code} - {response.text}")
            return None
    else:
        print(f"Failed to create service account: {response.status_code} - {response.text}")
        return None

    # Step 2: Create a token for the service account
    token_payload = {
        "name": "ProgrammaticKey"
    }
    response = requests.post(
        f"{GRAFANA_URL}/api/serviceaccounts/{service_account_id}/tokens",
        auth=auth,
        headers=headers,
        json=token_payload
    )

    if response.status_code in [200, 201]:  # Handle both 200 and 201 for success
        print("Token created successfully")
        token_key = response.json().get("key")
        if token_key:
            return token_key
        else:
            print("Token created but no key found in response")
            return None
    elif response.status_code == 409:
        print("Token already exists, deleting and recreating...")
        tokens_response = requests.get(
            f"{GRAFANA_URL}/api/serviceaccounts/{service_account_id}/tokens",
            auth=auth,
            headers=headers
        )
        if tokens_response.status_code == 200:
            for token in tokens_response.json():
                if token["name"] == "ProgrammaticKey":
                    delete_response = requests.delete(
                        f"{GRAFANA_URL}/api/serviceaccounts/{service_account_id}/tokens/{token['id']}",
                        auth=auth
                    )
                    if delete_response.status_code == 200:
                        print("Existing token deleted")
                        return create_api_key()  # Recursively retry
            print("Failed to find existing token")
            return None
        else:
            print(f"Failed to list tokens: {tokens_response.status_code} - {tokens_response.text}")
            return None
    else:
        print(f"Failed to create token: {response.status_code} - {response.text}")
        return None

def create_or_update_datasource(api_key):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    datasource_payload = {
        "name": "PostgreSQL",
        "type": "postgres",
        "url": f"{PG_HOST}:{PG_PORT}",
        "access": "proxy",
        "user": PG_USER,
        "database": PG_DB,
        "basicAuth": False,
        "isDefault": True,
        "jsonData": {"sslmode": "disable", "postgresVersion": 1300},
        "secureJsonData": {"password": PG_PASSWORD},
    }

    print("Datasource payload:")
    print(json.dumps(datasource_payload, indent=2))

    response = requests.get(
        f"{GRAFANA_URL}/api/datasources/name/{datasource_payload['name']}",
        headers=headers,
    )

    if response.status_code == 200:
        existing_datasource = response.json()
        datasource_id = existing_datasource["id"]
        print(f"Updating existing datasource with id: {datasource_id}")
        response = requests.put(
            f"{GRAFANA_URL}/api/datasources/{datasource_id}",
            headers=headers,
            json=datasource_payload,
        )
    else:
        print("Creating new datasource")
        response = requests.post(
            f"{GRAFANA_URL}/api/datasources", headers=headers, json=datasource_payload
        )

    print(f"Response status code: {response.status_code}")
    print(f"Response headers: {response.headers}")
    print(f"Response content: {response.text}")

    if response.status_code in [200, 201]:
        print("Datasource created or updated successfully")
        return response.json().get("datasource", {}).get("uid") or response.json().get("uid")
    else:
        print(f"Failed to create or update datasource: {response.text}")
        return None

def create_dashboard(api_key, datasource_uid):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    dashboard_file = "dashboard.json"

    try:
        with open(dashboard_file, "r") as f:
            dashboard_json = json.load(f)
    except FileNotFoundError:
        print(f"Error: {dashboard_file} not found.")
        return
    except json.JSONDecodeError as e:
        print(f"Error decoding {dashboard_file}: {str(e)}")
        return

    print("Dashboard JSON loaded successfully.")

    panels_updated = 0
    for panel in dashboard_json.get("panels", []):
        if isinstance(panel.get("datasource"), dict):
            panel["datasource"]["uid"] = datasource_uid
            panels_updated += 1
        elif isinstance(panel.get("targets"), list):
            for target in panel["targets"]:
                if isinstance(target.get("datasource"), dict):
                    target["datasource"]["uid"] = datasource_uid
                    panels_updated += 1

    print(f"Updated datasource UID for {panels_updated} panels/targets.")

    dashboard_json.pop("id", None)
    dashboard_json.pop("uid", None)
    dashboard_json.pop("version", None)

    dashboard_payload = {
        "dashboard": dashboard_json,
        "overwrite": True,
        "message": "Updated by Python script",
    }

    print("Sending dashboard creation request...")

    response = requests.post(
        f"{GRAFANA_URL}/api/dashboards/db", headers=headers, json=dashboard_payload
    )

    print(f"Response status code: {response.status_code}")
    print(f"Response content: {response.text}")

    if response.status_code == 200:
        print("Dashboard created successfully")
        return response.json().get("uid")
    else:
        print(f"Failed to create dashboard: {response.text}")
        return None

def delete_service_account_and_token():
    auth = (GRAFANA_USER, GRAFANA_PASSWORD)
    headers = {"Content-Type": "application/json"}

    response = requests.get(f"{GRAFANA_URL}/api/serviceaccounts/search", auth=auth, headers=headers)
    if response.status_code != 200:
        print(f"Failed to search for service accounts: {response.status_code} - {response.text}")
        return False

    service_account_id = None
    for sa in response.json().get("serviceAccounts", []):
        if sa["name"] == "ProgrammaticServiceAccount":
            service_account_id = sa["id"]
            print(f"Found service account 'ProgrammaticServiceAccount' with ID: {service_account_id}")
            break

    if not service_account_id:
        print("Service account 'ProgrammaticServiceAccount' not found")
        return True

    tokens_response = requests.get(
        f"{GRAFANA_URL}/api/serviceaccounts/{service_account_id}/tokens",
        auth=auth,
        headers=headers
    )
    if tokens_response.status_code == 200:
        for token in tokens_response.json():
            if token["name"] == "ProgrammaticKey":
                delete_response = requests.delete(
                    f"{GRAFANA_URL}/api/serviceaccounts/{service_account_id}/tokens/{token['id']}",
                    auth=auth
                )
                if delete_response.status_code == 200:
                    print(f"Deleted token 'ProgrammaticKey' with ID {token['id']}")
                else:
                    print(f"Failed to delete token {token['id']}: {delete_response.text}")
    else:
        print(f"Failed to list tokens: {tokens_response.text}")

    response = requests.delete(f"{GRAFANA_URL}/api/serviceaccounts/{service_account_id}", auth=auth)
    if response.status_code == 200:
        print("Service account deleted successfully")
        return True
    else:
        print(f"Failed to delete service account: {response.status_code} - {response.text}")
        return False

def delete_datasource():
    auth = (GRAFANA_USER, GRAFANA_PASSWORD)
    headers = {"Content-Type": "application/json"}

    response = requests.get(f"{GRAFANA_URL}/api/datasources/name/PostgreSQL", auth=auth)
    if response.status_code == 200:
        datasource_id = response.json().get("id")
        print(f"Found datasource 'PostgreSQL' with ID: {datasource_id}")
        delete_response = requests.delete(f"{GRAFANA_URL}/api/datasources/{datasource_id}", auth=auth)
        if delete_response.status_code == 200:
            print("Datasource 'PostgreSQL' deleted successfully")
            return True
        else:
            print(f"Failed to delete datasource: {delete_response.status_code} - {delete_response.text}")
            return False
    elif response.status_code == 404:
        print("Datasource 'PostgreSQL' not found")
        return True
    else:
        print(f"Failed to find datasource: {response.status_code} - {response.text}")
        return False

def delete_dashboard():
    auth = (GRAFANA_USER, GRAFANA_PASSWORD)
    headers = {"Content-Type": "application/json"}

    dashboard_file = "dashboard.json"
    try:
        with open(dashboard_file, "r") as f:
            dashboard_json = json.load(f)
            dashboard_title = dashboard_json.get("title")
            dashboard_uid = dashboard_json.get("uid")
            print(f"Dashboard title from file: {dashboard_title}")
    except FileNotFoundError:
        print(f"Error: {dashboard_file} not found, cannot determine dashboard to delete")
        return False
    except json.JSONDecodeError as e:
        print(f"Error decoding {dashboard_file}: {str(e)}")
        return False

    if dashboard_uid:
        response = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}", auth=auth)
        if response.status_code == 200:
            print(f"Found dashboard with UID: {dashboard_uid}")
            delete_response = requests.delete(f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}", auth=auth)
            if delete_response.status_code == 200:
                print("Dashboard deleted successfully")
                return True
            else:
                print(f"Failed to delete dashboard: {delete_response.status_code} - {response.text}")
                return False
        elif response.status_code == 404:
            print(f"Dashboard with UID {dashboard_uid} not found")
            return True
    else:
        response = requests.get(f"{GRAFANA_URL}/api/search?query={dashboard_title}", auth=auth)
        if response.status_code == 200:
            for item in response.json():
                if item["title"] == dashboard_title and item["type"] == "dash-db":
                    dashboard_uid = item["uid"]
                    print(f"Found dashboard '{dashboard_title}' with UID: {dashboard_uid}")
                    delete_response = requests.delete(f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}", auth=auth)
                    if delete_response.status_code == 200:
                        print("Dashboard deleted successfully")
                        return True
                    else:
                        print(f"Failed to delete dashboard: {delete_response.status_code} - {delete_response.text}")
                        return False
            print(f"Dashboard with title '{dashboard_title}' not found")
            return True
        else:
            print(f"Failed to search for dashboard: {response.status_code} - {response.text}")
            return False

def delete_all():
    print("Starting cleanup process...")
    success = True

    if not delete_service_account_and_token():
        success = False
        print("Failed to delete service account or token")

    if not delete_datasource():
        success = False
        print("Failed to delete datasource")

    if not delete_dashboard():
        success = False
        print("Failed to delete dashboard")

    if success:
        print("Cleanup completed successfully")
    else:
        print("Cleanup completed with errors")

def main():
    print("Starting resource creation process...")
    # Delete existing resources first
    delete_all()

    api_key = create_api_key()
    if not api_key:
        print("API key creation failed")
        return

    datasource_uid = create_or_update_datasource(api_key)
    print(f"Datasource UID: {datasource_uid}")
    if not datasource_uid:
        print("Datasource creation failed")
        return

    create_dashboard(api_key, datasource_uid)

if __name__ == "__main__":
    main()