import json
import logging

import boto3
import urllib3


def get_secret(config):
    client = boto3.client("secretsmanager", region_name=config.get("region_name"))
    try:
        response = client.get_secret_value(SecretId=config.get("secret_name"))
        if "SecretString" in response:
            secret = response["SecretString"]
        else:
            secret = response["SecretBinary"]
        secret_dict = json.loads(secret)
        return secret_dict
    except Exception as e:
        logging.errort(f"Error retrieving secret: {e}")
        raise e


def load_access_control_policy(url):
    parsed = urllib3.util.parse_url(url)
    if parsed.scheme == "file":
        with open(parsed.path) as file:
            print("Access Control Policy loaded")
            return json.load(file)

    http = urllib3.PoolManager()
    response = http.request("GET", url)
    if response.status == 200:
        logging.info("Access Control Policy loaded")
        return json.loads(response.data.decode("utf-8"))
    else:
        return {}
