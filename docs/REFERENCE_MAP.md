# Reference map — design references (not runtime validation)

| Concern | Reference | Adopt | Defer |
|---|---|---|---|
| Rate limiting | https://github.com/mjpieters/aiolimiter | bounded quotas, measured backoff | asynchronous rewrite |
| Cache | https://github.com/tkem/cachetools | TTL + bounded LRU + source timestamp | Redis deployment |
| Dead-letter queue | https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html | replay IDs, bounded retries, poison-message isolation | managed SQS |
| Circuit breaker | https://github.com/danielfm/pybreaker | closed/open/half-open + cooldown | broad global breaker |
| Metrics | https://prometheus.io/docs/instrumenting/clientlibs/ | counters, latency, run ID | new server |
| ETL validation | https://github.com/unionai-oss/pandera | schema, type, null, reject evidence | full dataframe migration |

These are architectural references only. Integrate after confirming real caller behavior and adding tests. Market-data rate limits and agent CLI timeouts are separate fault domains.
