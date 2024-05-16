from typing import Optional

from azure.cosmos import ContainerProxy, CosmosClient, DatabaseProxy
from azure.identity import DefaultAzureCredential
from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APPLICATIONINSIGHTS_CONNECTION_STRING: str
    COSMOSDB_ACCOUNT_NAME: str
    COSMOSDB_CONTAINER_NAME: str
    COSMOSDB_DATABASE_NAME: str
    COSMOSDB_PARTITION_KEY: str
    COSMOSDB_ACCESS_KEY: Optional[str] = None

    @computed_field
    @property
    def host(self) -> str:
        return f"https://{self.COSMOSDB_ACCOUNT_NAME}.documents.azure.com:443/"


class DB:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings: Settings = settings if settings else Settings()
        self._init_connection()

    def _init_connection(self):
        self.cosmos_client: CosmosClient = CosmosClient(
            url=self.settings.host,
            credential=(
                self.settings.COSMOSDB_ACCESS_KEY
                if self.settings.COSMOSDB_ACCESS_KEY
                else DefaultAzureCredential()
            ),
        )
        self.database_client: DatabaseProxy = (
            self.cosmos_client.get_database_client(  # noqa: E501
                database=self.settings.COSMOSDB_DATABASE_NAME  # noqa: E501
            )
        )
        self.container_client: ContainerProxy = (
            self.database_client.get_container_client(
                container=self.settings.COSMOSDB_CONTAINER_NAME
            )
        )
