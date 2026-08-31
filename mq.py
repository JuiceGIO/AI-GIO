"""消息队列客户端（升级3：审批超时提醒 → RabbitMQ 延迟消息）

职责：报销单进入「待审批」状态时，往 RabbitMQ 发一条「delay_ms 后再检查」的延迟消息。
真正提醒由 Java 消费端（expense-approval .../mq/OverdueConsumer）按状态幂等处理；
Python 与 Java 双侧发送，重复消息在消费端被忽略，不影响正确性。

降级策略：pika 未安装 / RabbitMQ 不可达 / 发送失败，全部静默降级——
超时提醒仍由 Java 的 @Scheduled 定时兜底扫描负责，功能不丢。

环境变量：
  RABBIT_URL（可选）或 RABBITMQ_HOST/PORT/USER/PASSWORD（默认 127.0.0.1:5672 guest/guest）
  OVERDUE_DELAY_MS  默认 172800000（48 小时）
"""
import logging
import os

logger = logging.getLogger("mq")

RABBIT_URL = os.getenv("RABBIT_URL", "amqp://guest:guest@127.0.0.1:5672")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "127.0.0.1")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
OVERDUE_DELAY_MS = int(os.getenv("OVERDUE_DELAY_MS", str(48 * 60 * 60 * 1000)))

EXCHANGE = "expenseai.exchange"
DELAY_ROUTING_KEY = "overdue.delay"


def _connect():
    """建连接并强制加超时，Rabbit 不可达时快速失败，避免请求线程长时间卡住"""
    import pika

    url = os.getenv("RABBIT_URL")
    if url:
        params = pika.URLParameters(url)
        params.connection_attempts = 1
        params.socket_timeout = 2
        params.blocked_connection_timeout = 3
        return pika.BlockingConnection(params)
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    return pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        socket_timeout=2,
        connection_attempts=1,
        blocked_connection_timeout=3,
    ))


def publish_delayed_overdue_check(form_id: int, delay_ms: int = None) -> bool:
    """发布一条延迟消息：delay_ms 后消费端检查该报销单是否仍待审批。
    返回是否成功发送（失败不影响主流程，由定时兜底覆盖）。"""
    delay_ms = delay_ms or OVERDUE_DELAY_MS
    try:
        connection = _connect()
        try:
            channel = connection.channel()
            # 与 Java 端 RabbitConfig 声明保持一致（声明是幂等的）
            channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
            channel.queue_declare(queue="expenseai.overdue.delay", durable=True,
                                  arguments={
                                      "x-dead-letter-exchange": "expenseai.dlx",
                                      "x-dead-letter-routing-key": "overdue.dead",
                                  })
            channel.basic_publish(
                exchange=EXCHANGE,
                routing_key=DELAY_ROUTING_KEY,
                body=str(form_id).encode(),
                properties=pika.BasicProperties(
                    delivery_mode=2,          # 持久化，防重启丢消息
                    expiration=str(delay_ms), # 单条消息 TTL：到期进死信 → 消费端检查
                ),
            )
        finally:
            connection.close()
        logger.info("已发送延迟检查消息 form_id=%s delay_ms=%s", form_id, delay_ms)
        return True
    except Exception as e:
        logger.warning("RabbitMQ 不可用，延迟提醒降级给定时兜底：%s", e)
        return False
