import logging
from datetime import datetime

from azure.core.settings import settings
from azure.core.tracing.ext.opentelemetry_span import OpenTelemetrySpan
from azure.cosmos import PartitionKey, exceptions
from opentelemetry.sdk.trace import Tracer

from db import DB
from logging_service import LoggingService

if __name__ == "__main__":
    db: DB = DB()

    # container
    partition_key: PartitionKey = PartitionKey(path="/partitionKey")
    partition: str = "partition1"
    container = db.database_client.create_container_if_not_exists(
        id=db.settings.COSMOSDB_CONTAINER_NAME, partition_key=partition_key
    )

    # instrument azure
    settings.tracing_implementation = OpenTelemetrySpan

    service_name: str = "ServiceName"
    service_instance_name: str = "ServiceInstanceName"
    logger_name: str = "LoggerName"
    module_name: str = "ModuleName"
    context_name: str = f"{datetime.now().isoformat()}: {service_name}"

    logging_service: LoggingService = LoggingService(
        service_name=service_name, service_instance_name=service_instance_name
    )

    logger: logging.Logger = logging_service.get_logger(logger_name)
    tracer: Tracer = logging_service.get_tracer(module_name=module_name)

    with tracer.start_as_current_span(context_name):
        logger.info(
            "COSMOSDB",
            extra={"service_name": service_name},
        )
        # Transactional Batch operations look very similar to the singular operations apis,
        # and are tuples containing (operation_type_string, args_tuple, batch_operation_kwargs_dictionary)

        item_1 = {"id": "123", "partitionKey": partition}
        item_2 = {"id": "456", "partitionKey": partition}
        item_operation1 = ("upsert", (item_1,), {})
        item_operation2 = ("upsert", (item_2,), {})
        item_operation3 = ("read", ("123",), {})
        item_operation4 = ("read", ("456",), {})

        batch_operations = [
            item_operation1,
            item_operation2,
            item_operation3,
            item_operation4,
        ]

        try:
            batch_results = db.container_client.execute_item_batch(
                batch_operations=batch_operations, partition_key=partition
            )
            # Batch results are returned as a list of item operation results - or raise a CosmosBatchOperationError if
            # one of the operations failed within your batch request.
            print(f"\nResults for the batch operations: {batch_results}\n")
        except exceptions.CosmosBatchOperationError as e:
            error_operation_index = e.error_index
            error_operation_response = e.operation_responses[error_operation_index]
            error_operation = batch_operations[error_operation_index]
            print(
                f"\nError operation: {error_operation}, error operation response: {error_operation_response}\n"
            )
