from prometheus_client import Gauge

bot_counter = Gauge(
    name="onchebot_bot_count",
    documentation="Total number of bots",
)

watched_topic_counter = Gauge(
    name="onchebot_watched_topic_count",
    documentation="Number of topic being watched",
)

posted_msg_counter = Gauge(
    name="onchebot_posted_message_count",
    documentation="Number of messages posted",
)

msg_counter = Gauge(
    name="onchebot_total_message_count",
    documentation="Number of messages fetched",
)

topic_counter = Gauge(
    name="onchebot_total_topic_count",
    documentation="Number of topics fetched",
)
