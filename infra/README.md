# `infra` Directory

The `infra` directory contains infrastructure-as-code configurations for setting up and managing the monitoring, logging, and tracing (MLT) stack for the VMLC backend. It leverages various open-source tools to provide comprehensive observability into the application's performance and behavior.

## Key Configuration Files and Their Roles

-   **`alloy.alloy`**: This file likely contains the configuration for the **Grafana Agent** in "Alloy" mode. Grafana Agent is a metrics, logs, and traces collector that can scrape data from various sources and send it to Prometheus, Loki, and Tempo. The `.alloy` extension suggests a declarative configuration format for the agent, defining pipelines for collecting and routing telemetry data.
-   **`loki.yml`**: Configuration for **Loki**, Grafana's horizontally-scalable, highly-available, multi-tenant log aggregation system. This file defines aspects such as:
    -   Where Loki stores log data (e.g., local disk, S3).
    -   Ingestion rules and how log streams are processed.
    -   Retention policies for log data.
-   **`otel.yml`**: Configuration for the **OpenTelemetry Collector**. This component is crucial for vendor-agnostic collection, processing, and exporting of telemetry data (metrics, logs, and traces). This file specifies:
    -   Receivers: How data is ingested (e.g., from applications instrumented with OpenTelemetry SDKs).
    -   Processors: How data is transformed (e.g., batching, filtering, attribute modification).
    -   Exporters: Where processed data is sent (e.g., to Prometheus, Loki, Tempo).
    -   Pipelines: The flow of data through receivers, processors, and exporters.
-   **`prometheus.yml`**: Configuration for **Prometheus**, the leading open-source monitoring system for time series data. This file typically includes:
    -   `scrape_configs`: Definitions of targets (e.g., application instances, node exporters) that Prometheus should scrape for metrics, along with intervals and labels.
    -   `rule_files`: Paths to alerting and recording rules.
    -   `alerting`: Configuration for Alertmanager integration.
-   **`stack.base.yml`**: A base Docker Compose file that defines the common services (e.g., Prometheus, Loki, Tempo, Grafana, OpenTelemetry Collector, Grafana Agent) for the MLT stack. It sets up the core components without environment-specific overrides.
-   **`stack.prod.yml`**: A Docker Compose override file for the **production environment**. This file extends `stack.base.yml` and applies production-specific configurations, such as:
    -   Resource limits and requests for containers.
    -   Persistent volume configurations for data storage.
    -   Network settings and security considerations for production deployment.
    -   Specific image versions or build contexts for production.
-   **`stack.staging.yml`**: Similar to `stack.prod.yml`, this is a Docker Compose override file for the **staging environment**. It extends `stack.base.yml` and applies staging-specific settings, which might differ from production (e.g., fewer replicas, different storage configurations, or debug settings).
-   **`tempo.yml`**: Configuration for **Tempo**, Grafana's open-source, highly scalable distributed tracing backend. This file specifies:
    -   Storage backend: Where traces are stored (e.g., local disk, S3, Cassandra).
    -   Ingestion protocols: How traces are received (e.g., OpenTelemetry, Jaeger, Zipkin).
    -   Retention policies for trace data.

## `grafana/` Subdirectory

This subdirectory specifically manages configurations for **Grafana**, the open-source platform for monitoring and observability.

-   **`grafana/dashboards.yml`**: A Grafana provisioning file that tells Grafana where to find and load dashboard definitions. It typically points to a directory containing JSON files that define the dashboards.
-   **`grafana/datasources.yml`**: A Grafana provisioning file that defines connections to various data sources. For this stack, it would include configurations for:
    -   Prometheus (for metrics).
    -   Loki (for logs).
    -   Tempo (for traces).
    -   Potentially other data sources.
-   **`grafana/dashboards/`**: This directory is intended to store the actual Grafana dashboard definitions. These are usually JSON files that describe the panels, queries, and layout of each dashboard, allowing for easy version control and provisioning.

## Interconnections and Overall Purpose

The files in the `infra` directory work together to establish a comprehensive observability stack:

-   **OpenTelemetry Collector (`otel.yml`)** gathers telemetry data from the VMLC application.
-   **Grafana Agent (`alloy.alloy`)** collects logs, metrics, and traces, potentially acting as an intermediary for OpenTelemetry Collector or directly scraping data.
-   **Prometheus (`prometheus.yml`)** stores and queries metrics.
-   **Loki (`loki.yml`)** stores and queries logs.
-   **Tempo (`tempo.yml`)** stores and queries distributed traces.
-   **Grafana (configurations in `grafana/`)** visualizes all this data through dashboards, allowing developers and operations teams to monitor the application's health, performance, and troubleshoot issues.
-   The `stack.*.yml` files orchestrate the deployment of these services using Docker Compose, adapting the setup for different environments (base, staging, production).

This setup provides a robust foundation for understanding and maintaining the operational health of the VMLC backend.