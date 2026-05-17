import logging
import sys
import time
from datetime import datetime, timezone
import json
import jsonpatch
from jsonpointer import JsonPointerException

from globus_sdk import (
    ClientCredentialsAuthorizer,
    ConfidentialAppAuthClient,
    SearchClient,
)
from globus_sdk.scopes import SearchScopes
from globus_sdk.services.search.errors import SearchAPIError


class ConsumerSearchClient:
    def __init__(self, credentials, search_index, error_producer):
        confidential_client = ConfidentialAppAuthClient(
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret"),
        )
        authorizer = ClientCredentialsAuthorizer(
            confidential_client,
            scopes=SearchScopes.all,
        )
        self.search_client = SearchClient(authorizer=authorizer)
        self.esgf_index = search_index
        self.error_producer = error_producer

    def normalize_assets(self, assets):
        normalized_assets = []
        for key, value in assets.items():
            normalized_assets.append({"name": key} | value)
        for asset in normalized_assets:
            if "alternate" in asset:
                if asset.get("alternate"):
                    asset["alternate"] = self.normalize_assets(asset["alternate"])
                else:
                    del asset["alternate"]
        return normalized_assets

    def denormalize_assets(self, assets):
        denormalized_assets = {}
        for asset in assets:
            try:
                name = asset.pop("name")
            except AttributeError as e:
                logging.error(f"Error when denormalizing assets: {e}")
                logging.error(f"{asset}")
                logging.error(f"{json.dumps(assets, indent=2, sort_keys=True)}")
                sys.exit(1)
            if "alternate" in asset:
                asset["alternate"] = self.denormalize_assets(asset["alternate"])
            else:
                asset["alternate"] = {}
            denormalized_assets[name] = asset
        return denormalized_assets

    def gmetaentry(self, item):
        return {
            "subject": item.get("id"),
            "visible_to": [
                "public",
            ],
            "content": item,
        }

    def get_index(self):
        return self.search_client.get_index(self.esgf_index)

    def search(self, query):
        return self.search_client.search(self.esgf_index, query)

    def post(self, message_data):
        item = message_data.get("data").get("payload").get("item")
        try:
            globus_response = self.search_client.get_subject(self.esgf_index, item.get("id"))
        except SearchAPIError as e:
            if e.http_status == 404:
                now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
                item["properties"]["created"] = now
                item["properties"]["updated"] = now
                item["assets"] = self.normalize_assets(item.get("assets"))
                gmeta_entry = self.gmetaentry(item)
                return gmeta_entry

        if globus_response.data:
            logging.warn(f"Item with ID {item.get('id')} already exists in the index.")
            self.error_producer.produce(
                key=item.get("id"),
                value=f"Item with ID {item.get('id')} already exists in the index.",
            )
            return None
        return None

    def json_patch(self, message_data):
        payload = message_data.get("data").get("payload")
        item_id = payload.get("item_id")
        logging.debug(f"Applying JSON patch to item: {item_id}")
        try:
            globus_response = self.search_client.get_subject(self.esgf_index, item_id)
        except SearchAPIError as e:
            if e.http_status == 404:
                logging.warn(f"Item with ID {item_id} does not exist in the index.")
                self.error_producer.produce(
                    key=item_id,
                    value=f"Item with ID {item_id} does not exist in the index.",
                )
                return None
            logging.error(f"Error when getting item {item_id} from Globus Search: {e}")
            sys.exit(1)
        item = globus_response.data.get("entries")[0].get("content")
        item["assets"] = self.denormalize_assets(item.get("assets"))

        try:
            patch_operations = payload.get("patch")
            if isinstance(patch_operations, dict):
                patch_operations = patch_operations.get("operations")
            patched_item = jsonpatch.apply_patch(item, patch_operations)
        except Exception as e:
            logging.error(f"Error when applying JSON patch to item {item_id}: {e}")
            logging.error(f"Patch operations: {patch_operations}")
            return None

        now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
        patched_item["properties"]["updated"] = now
        patched_item["assets"] = self.normalize_assets(patched_item.get("assets"))
        gmeta_entry = self.gmetaentry(patched_item)
        logging.debug(f"Patched entry: {gmeta_entry}")
        return gmeta_entry

    def delete(self, subject):
        globus_response = self.search_client.get_subject(self.esgf_index, subject)
        if globus_response.data:
            self.search_client.delete_subject(self.esgf_index, subject)
            return True
        logging.warn(f"Item with ID {subject} does not exist in the index.")
        self.error_producer.produce(
            key=subject,
            value=f"Item with ID {subject} does not exist in the index.",
        )
        return None

    def process_message(self, message_data):
        try:
            payload = message_data.get("data").get("payload")
            method = payload.get("method")
            logging.info(f"Processing message with method: {method}")
            if method == "POST":
                return self.post(message_data)
            if method == "PUT":
                return self.put(message_data)
            if method == "JSON_PATCH" or method == "PATCH":
                return self.json_patch(message_data)
            return None
        except Exception as e:
            logging.error(f"Error processing message data: {e}")
            self.error_producer.produce(
                key=message_data.get("data").get("payload").get("item").get("id"),
                value=str(e),
            )
            return None

    def process_messages(self, messages_data):
        gmeta = []
        for message_data in messages_data:
            entry = self.process_message(message_data)
            if entry:
                gmeta.append(entry)
        if not gmeta:
            return True

        gmetalist = {"ingest_type": "GMetaList", "ingest_data": {"gmeta": gmeta}}

        r = self.search_client.ingest(self.esgf_index, gmetalist)
        task_id = r.get("task_id")
        logging.info("Submitted ingest task successfully, waiting for task to complete...")

        while True:
            r = self.search_client.get_task(task_id)
            state = r.get("state")
            if state == "SUCCESS":
                logging.info(f"Ingestion task {task_id} completed successfully")
                return True
            if state == "FAILED":
                logging.error(f"Ingestion task {task_id} failed")
                logging.error(r.text)
                sys.exit(1)
            time.sleep(1)
        return True
