# Azure CosmosDB Batch API

This repository explores the Azure CosmosDB Batch API capabilities (2024-04-28) that are summarized here:

- https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/transactional-batch?tabs=python

## Prerequisites

- CosmosDB
    - cosmosDB database (NoSQL API)
    - read/write access to the database via access key
      OR [RBAC](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-setup-rbac#permission-model)
- Application Insights
    - Connection String
- .env configuration file from [.env.sample](.env.sample)

## Distributed Tracing with OpenTelemetry & Application Insights

By instrumenting Azure with:

```python
from azure.core.settings import settings
from azure.core.tracing.ext.opentelemetry_span import OpenTelemetrySpan

settings.tracing_implementation = OpenTelemetrySpan
```

and setting up the Azure Monitor Trace Exporter (azure-monitor-opentelemetry), here
with [logging_service.py](logging_service.py),

we can see that what normally would require multiple requests to the cosmosDB can be reduced to a single request using
the
batch API.

TODO: add image

## Limitations

- The Azure Cosmos DB request size limit constrains the size of the Transactional Batch payload to not exceed 2 MB, and
  the maximum execution time is 5 seconds.
- There's a current limit of 100 operations per Transactional Batch to ensure the performance is as expected and within
  SLAs.
- [Cross-partition executions are not allowed](https://learn.microsoft.com/en-us/answers/questions/1426290/how-to-batch-items-with-different-partition-keys-i).

## Run

```shell
python main.py
```

## Notes

- If there is an error on any of the operations, nothing is committed.
- If there are multiple read operations and there is at least one missing document, the data is not returned.
- If there are multiple read operations with multiple missing documents, only the first 404 is reported, not all of
  them.
