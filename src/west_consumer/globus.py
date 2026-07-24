import json
import logging
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import jsonpatch

from esgf_core_utils.models.kafka.events import (
    Auth,
    Error,
    KafkaErrorEvent,
    KafkaSuccessEvent,
    Metadata,
    OriginalEvent,
    Publisher,
    ResultData,
    ResultPayload,
)
from globus_sdk import (
    ClientCredentialsAuthorizer,
    ConfidentialAppAuthClient,
    SearchClient,
)
from globus_sdk.scopes import SearchScopes
from globus_sdk.services.search.errors import SearchAPIError


class ConsumerSearchClient:
    def __init__(self, credentials, search_index, error_producer, success_producer):
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
        self.success_producer = success_producer

    def _item_id(self, payload):
        return payload.get("item_id") or (payload.get("item") or {}).get("id")

    def _method(self, payload):
        method = payload.get("method")
        if method == "JSON_PATCH":
            return "PATCH"
        return method

    def _result_data(self, message_data):
        payload = message_data["data"]["payload"]
        return ResultData(
            type="STAC",
            payload=ResultPayload(
                collection_id=payload["collection_id"],
                method=self._method(payload),
                item_id=self._item_id(payload),
            ),
        )

    def _result_metadata(self, message_data):
        original_metadata = message_data["metadata"]
        return Metadata(
            auth=Auth.model_validate(original_metadata["auth"]),
            event_id=original_metadata["event_id"],
            publisher=Publisher(package="west-consumer", version=version("west-consumer")),
            request_id=original_metadata["request_id"],
            time=original_metadata["time"],
            schema_version=original_metadata["schema_version"],
        )

    def success_event(self, message_data, partition, offset) -> KafkaSuccessEvent:
        """Build a KafkaSuccessEvent for a successfully processed transaction."""
        original_metadata = message_data["metadata"]
        return KafkaSuccessEvent(
            data=self._result_data(message_data),
            metadata=self._result_metadata(message_data),
            original_event=OriginalEvent(
                event_id=original_metadata["event_id"],
                offset=offset,
                partition=partition,
            ),
        )

    def error_event(
        self,
        message_data,
        partition,
        offset,
        *,
        detail,
        status,
        title,
        type,
    ) -> KafkaErrorEvent:
        """Build a KafkaErrorEvent for a failed transaction."""
        payload = message_data["data"]["payload"]
        item_id = self._item_id(payload)
        original_metadata = message_data["metadata"]
        return KafkaErrorEvent(
            data=self._result_data(message_data),
            metadata=self._result_metadata(message_data),
            original_event=OriginalEvent(
                event_id=original_metadata["event_id"],
                offset=offset,
                partition=partition,
            ),
            error=Error(
                detail=detail,
                instance=original_metadata["request_id"],
                status=status,
                title=title,
                type=type,
            ),
        )

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

    def post(self, message_data, partition, offset):
        payload = message_data.get("data").get("payload")
        collection_id = payload.get("collection_id")
        item = payload.get("item")
        item_id = item.get("id")
        try:
            globus_response = self.search_client.get_subject(self.esgf_index, item_id)
        except SearchAPIError as e:
            if e.http_status == 404:
                now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                item["properties"]["created"] = now
                item["properties"]["updated"] = now
                assets = item.get("assets")
                for asset in assets.values():
                    asset["created"] = now
                    asset["updated"] = now
                item["assets"] = self.normalize_assets(assets)
                return self.gmetaentry(item)
            logging.error(f"Error when getting item {item_id} from Globus Search: {e}")
            sys.exit(1)

        if globus_response.data:
            detail = {
                "code": "ItemAlreadyExistsError",
                "description": f"Item {item_id} in collection {collection_id} already exists"
            }
            logging.warn(detail)
            event = self.error_event(
                message_data,
                partition,
                offset,
                detail=json.dumps(detail),
                status=409,
                title=f"{item_id} already exists",
                type="ItemAlreadyExists",
            )
            self.error_producer.produce(
                key=item_id,
                value=event.model_dump_json(),
            )
        return None

    def json_patch(self, message_data, partition, offset):
        metadata = message_data.get("metadata")
        payload = message_data.get("data").get("payload")
        item_id = payload.get("item_id")
        collection_id = payload.get("collection_id")
        logging.debug(f"Applying JSON patch to item: {item_id}")
        try:
            globus_response = self.search_client.get_subject(self.esgf_index, item_id)
        except SearchAPIError as e:
            if e.http_status == 404:
                detail = {
                    "code": "ItemNotFound",
                    "description": f"Item {item_id} does not exist in collection {collection_id}"
                }
                logging.warn(detail)
                event = self.error_event(
                    message_data,
                    partition,
                    offset,
                    detail=json.dumps(detail),
                    status=404,
                    title=f"{item_id} not found",
                    type="ItemNotFound",
                )
                self.error_producer.produce(
                    key=event.data.payload.item_id,
                    value=event.model_dump_json(),
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
            detail = {
                "code": "BadRequest",
                "description": f"Error when applying JSON patch to item {item_id}: {e}"
            }
            logging.error(detail)
            logging.error(f"Patch operations: {patch_operations}")
            event = self.error_event(
                message_data,
                partition,
                offset,
                detail=json.dumps(detail),
                status=400,
                title=f"Error when applying JSON patch to item {item_id}",
                type="BadRequest",
            )
            self.error_producer.produce(
                key=event.data.payload.item_id,
                value=event.model_dump_json(),
            )
            return None

        now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
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
        return None

    def process_message(self, message_data, partition, offset):
        try:
            payload = message_data.get("data").get("payload")
            method = payload.get("method")
            logging.info(
                f"Processing B message method={method} partition={partition} offset={offset}"
            )
            if method == "POST":
                print(f"Processing POST message: {message_data}")
                return self.post(message_data, partition, offset)
            if method == "PUT":
                return self.put(message_data, partition, offset)
            if method == "JSON_PATCH" or method == "PATCH":
                return self.json_patch(message_data, partition, offset)
            return None
        except Exception as e:
            logging.error(
                f"Error processing message partition={partition} offset={offset}: {e}"
            )
            return None

    def process_messages(self, messages_data):
        pending = []
        for message_data, partition, offset in messages_data:
            entry = self.process_message(message_data, partition, offset)
            if entry:
                pending.append((entry, message_data, partition, offset))
        if not pending:
            return True

        gmeta = [entry for entry, _, _, _ in pending]
        gmetalist = {"ingest_type": "GMetaList", "ingest_data": {"gmeta": gmeta}}

        r = self.search_client.ingest(self.esgf_index, gmetalist)
        task_id = r.get("task_id")
        logging.info("Submitted ingest task successfully, waiting for task to complete...")

        while True:
            r = self.search_client.get_task(task_id)
            state = r.get("state")
            if state == "SUCCESS":
                logging.info(f"Ingestion task {task_id} completed successfully")
                for _, message_data, partition, offset in pending:
                    event = self.success_event(message_data, partition, offset)
                    self.success_producer.produce(
                        key=event.data.payload.item_id,
                        value=event.model_dump_json(),
                    )
                return True
            if state == "FAILED":
                logging.error(f"Ingestion task {task_id} failed")
                logging.error(r.text)
                sys.exit(1)
            time.sleep(1)
        return True
