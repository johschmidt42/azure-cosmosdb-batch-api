import logging
import sys
from enum import Enum
from typing import List, Optional, Type

from azure.monitor.opentelemetry.exporter import (ApplicationInsightsSampler,
                                                  AzureMonitorLogExporter,
                                                  AzureMonitorTraceExporter)
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import (LoggerProvider, LoggingHandler,
                                     LogRecordProcessor)
from opentelemetry.sdk._logs._internal.export import (BatchLogRecordProcessor,
                                                      ConsoleLogExporter,
                                                      LogExporter)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, Tracer, TracerProvider
from opentelemetry.sdk.trace.export import (BatchSpanProcessor,
                                            ConsoleSpanExporter, SpanExporter)
from opentelemetry.trace import set_tracer_provider
from pydantic_settings import BaseSettings


class LogLevels(str, Enum):
    DEBUG: str = "DEBUG"
    INFO: str = "INFO"
    WARNING: str = "WARNING"
    ERROR: str = "ERROR"
    CRITICAL: str = "CRITICAL"


class ConfigApplicationInsights(BaseSettings):
    APPLICATIONINSIGHTS_CONNECTION_STRING: str
    LOGGING_LEVEL: LogLevels = LogLevels.INFO
    LOGGING_ENABLED: bool = True


class LoggingService:
    """
    LoggingService.

    Create a single instance of the LoggingService per app or script.
    Examples can be found here: https://github.com/be-media-co/be-id-opentelemetry
    """

    def __init__(
        self,
        service_name: str,
        service_instance_name: str,
        config: Optional[ConfigApplicationInsights] = None,
        console_log_exporter: bool = False,
        console_span_exporter: bool = False,
        console_logger: bool = True,
        formatter: Optional[logging.Formatter] = None,
        log_record_processor: Type[LogRecordProcessor] = BatchLogRecordProcessor,
        span_processor: Type[SpanProcessor] = BatchSpanProcessor,
        sampling_ratio: float = 1.0,
    ) -> None:
        """

        Args:
            config: Pydantic BaseSettings class for logging configuration
            console_log_exporter: Whether to send OTLP formatted log events
            to console (only for diagnostics)
            console_span_exporter: Whether to send OTLP formatted span events
            to console (only for diagnostics)
            console_logger: Whether to send logs to console
            formatter: Python logging formatter
            service_name: This will appear as `cloud_RoleName`
            in Azure Application Insights
            service_instance_name: This will appear as `cloud_RoleInstance`
            in Azure Application Insights
            log_record_processor: The processor class to use for processing log records
            span_processor: The processor class to use for processing spans
            sampling_ratio: The sampling rate to use for sampling
        """
        self.config: ConfigApplicationInsights = (
            config if config else ConfigApplicationInsights()
        )
        self.console_log_exporter: bool = console_log_exporter
        self.console_span_exporter: bool = console_span_exporter
        self.console_logger: bool = console_logger
        self.formatter: logging.Formatter = (
            formatter
            if formatter
            else logging.Formatter(
                "%(levelname)s [%(asctime)s] {%(module)s} %(message)s"
            )
        )
        self.service_name: str = service_name
        self.service_instance_name: str = service_instance_name
        self.log_record_processor: Type[LogRecordProcessor] = log_record_processor
        self.span_processor: Type[SpanProcessor] = span_processor

        self.loggers: List[str] = []

        self.logger_provider: Optional[LoggerProvider] = None
        self.tracer_provider: Optional[TracerProvider] = None

        self.sampling_ratio: float = sampling_ratio

    def setup_logger_provider(
        self,
    ) -> LoggerProvider:
        """
        Initialize Azure Monitor logging pipeline with open telemetry.
        Run this only once.

        Returns: OpenTelemetry logging provider

        """

        # init logger_provider
        resource: Resource = Resource.create(
            {
                "service.name": self.service_name,
                "service.instance.id": self.service_instance_name,
            }
        )
        # `service.name` = `cloud_RoleName` in azure application insights
        # `service.instance.id` = `cloud_RoleInstance` in azure application insights
        logger_provider: LoggerProvider = LoggerProvider(resource=resource)

        # init log_exporters
        log_exporters: List[LogExporter] = []
        log_records_processors: List[LogRecordProcessor] = []

        if self.console_log_exporter:
            # for diagnostics, we can emit the log records in OTLP format to console
            console_log_exporter: ConsoleLogExporter = self._init_console_log_exporter()
            log_exporters.append(console_log_exporter)

        # this is the exporter for Azure Monitor
        azure_log_exporter: AzureMonitorLogExporter = self._init_azure_log_exporter(
            self.config
        )
        log_exporters.append(azure_log_exporter)

        # init log_records_processors
        for log_exporter in log_exporters:
            log_records_processors.append(
                self.log_record_processor(exporter=log_exporter)
            )

        # add log_record_processors to log_provider
        for log_records_processor in log_records_processors:
            logger_provider.add_log_record_processor(
                log_record_processor=log_records_processor
            )

        # make the logger provider the global one
        # (there should only be one for your app/script)
        set_logger_provider(logger_provider)

        self.logger_provider: LoggerProvider = logger_provider

        return logger_provider

    def setup_tracer_provider(self, sampling_ratio: float = 1.0) -> TracerProvider:
        """

        Initialize the logging tracer pipeline with open telemetry.

        Args:
            sampling_ratio: The sampling rate

        Returns: The tracer provider instance

        """

        # init tracer_provider
        resource: Resource = Resource.create(
            {
                "service.name": self.service_name,
                "service.instance.id": self.service_instance_name,
            }
        )
        # `service.name` = `cloud_RoleName` in azure application insights
        # `service.instance.id` = `cloud_RoleInstance` in azure application insights

        tracer_provider: TracerProvider = TracerProvider(
            sampler=ApplicationInsightsSampler(sampling_ratio=sampling_ratio),
            resource=resource,
        )

        # init trace_exporters
        span_exporters: List[SpanExporter] = []
        span_processors: List[SpanProcessor] = []

        if self.console_span_exporter:
            # for diagnostics, we can emit the spans in OTLP format to console
            console_span_exporter: ConsoleSpanExporter = (
                self._init_console_span_exporter()
            )
            span_exporters.append(console_span_exporter)

        if self.config.LOGGING_ENABLED:
            # this is the exporter for Azure Monitor
            azure_span_exporter: AzureMonitorTraceExporter = (
                self._init_azure_span_exporter(self.config)
            )
            span_exporters.append(azure_span_exporter)

        # init log_records_processors
        for span_exporter in span_exporters:
            span_processors.append(self.span_processor(span_exporter=span_exporter))

        # add span_processors to trace_provider
        for span_processor in span_processors:
            tracer_provider.add_span_processor(span_processor=span_processor)

        # make the tracer provider the global one
        # (there should only be one for your app/script)
        set_tracer_provider(tracer_provider)

        self.tracer_provider: TracerProvider = tracer_provider

        return tracer_provider

    @staticmethod
    def _init_azure_log_exporter(
        config: ConfigApplicationInsights,
    ) -> AzureMonitorLogExporter:
        return AzureMonitorLogExporter(
            connection_string=config.APPLICATIONINSIGHTS_CONNECTION_STRING
        )

    @staticmethod
    def _init_azure_span_exporter(
        config: ConfigApplicationInsights,
    ) -> AzureMonitorTraceExporter:
        return AzureMonitorTraceExporter(
            connection_string=config.APPLICATIONINSIGHTS_CONNECTION_STRING
        )

    @staticmethod
    def _init_console_log_exporter():
        return ConsoleLogExporter()

    @staticmethod
    def _init_console_span_exporter():
        return ConsoleSpanExporter()

    def _initialize_console_log_handler(self) -> logging.StreamHandler:
        """
        Initializes the console log handler

        Returns: A Python logging handler

        """
        console_logging_handler: logging.StreamHandler = logging.StreamHandler(
            stream=sys.stdout
        )
        console_logging_handler.name = "Console Handler"
        console_logging_handler.setFormatter(self.formatter)
        console_logging_handler.setLevel(self.config.LOGGING_LEVEL.value)
        return console_logging_handler

    def get_logger(
        self,
        logger_name: str,
        additional_loggers: Optional[List[logging.Logger]] = None,
    ) -> logging.Logger:
        """

        Args:
            logger_name: the logger name
            additional_loggers: Additional loggers to which the handlers
            should be added to.

        Returns: A Python Logger

        """

        # do not return the root logger because of recursive behaviour:
        # https://github.com/Azure/azure-sdk-for-python/issues/34787
        if logger_name == "":
            issue_url: str = (
                "https://github.com/Azure/azure-sdk-for-python/issues/34787"
            )
            raise ValueError(
                f"Don't use the root logger. For more information, see: {issue_url}"
            )

        if logger_name in self.loggers:
            return logging.getLogger(logger_name)

        # logger
        logger: logging.Logger = logging.getLogger(logger_name)

        handlers: List[logging.Handler] = []

        # console logging handler
        if self.console_logger:
            console_logging_handler: logging.StreamHandler = (
                self._initialize_console_log_handler()
            )
            handlers.append(console_logging_handler)

        # azure logging handler
        if self.config.LOGGING_ENABLED:
            if not self.logger_provider:
                self.logger_provider: LoggerProvider = self.setup_logger_provider()

            # create the logging_handler that triggers the log_provider
            azure_logging_handler: LoggingHandler = LoggingHandler(
                logger_provider=self.logger_provider,
                level=self.config.LOGGING_LEVEL.value,
            )
            azure_logging_handler.name = "Azure Monitor Handler"
            handlers.append(azure_logging_handler)

        logger.setLevel(self.config.LOGGING_LEVEL.value)
        for handler in handlers:
            logger.addHandler(handler)

        self.loggers.append(logger_name)

        if additional_loggers is not None:
            for additional_logger in additional_loggers:
                additional_logger.setLevel(self.config.LOGGING_LEVEL.value)
                for handler in handlers:
                    additional_logger.addHandler(handler)

        return logger

    def get_tracer(self, module_name: str) -> Tracer:
        """
        This will create a tracer from the tracer provider.

        Args:
            module_name: module name used by the tracer

        Returns: A Tracer object that can be used to
        correlate logs to Azure Application Insights

        """
        if not self.tracer_provider:
            self.tracer_provider: TracerProvider = self.setup_tracer_provider(
                self.sampling_ratio
            )

        tracer: Tracer = self.tracer_provider.get_tracer(
            instrumenting_module_name=module_name
        )

        return tracer
