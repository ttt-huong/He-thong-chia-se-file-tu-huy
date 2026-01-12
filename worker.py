# Worker RabbitMQ - X\u1eed l\u00fd tin nh\u1eafn t\u1eeb queue
import pika
import json
import time
import boto3

# C\u1ea5u h\u00ecnh MinIO
s3 = boto3.client('s3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='admin',
    aws_secret_access_key='password123',
    config=boto3.session.Config(signature_version='s3v4')
)

# C\u1ea5u h\u00ecnh RabbitMQ
RABBITMQ_HOST = 'localhost'
RABBITMQ_QUEUE = 'file_processing'

def delete_file_from_minio(bucket, filename):
    """\u00d4a file t\u1eeb MinIO"""
    try:
        s3.delete_object(Bucket=bucket, Key=filename)
        print(f"\u2705 \u0110\u00e3 x\u00f3a file: {filename}")
        return True
    except Exception as e:
        print(f"\u274c L\u1ed7i x\u00f3a file: {e}")
        return False

def callback(ch, method, properties, body):
    """X\u1eed l\u00fd tin nh\u1eafn t\u1eeb queue"""
    try:
        message = json.loads(body)
        print(f"\ud83d\udce8 Nh\u1eadn tin nh\u1eafn: {message}")
        
        if message['action'] == 'schedule_delete':
            filename = message['filename']
            bucket = message['bucket']
            delete_after = message.get('delete_after_seconds', 3600)
            
            # \u0110\u1ee3i tr\u01b0\u1edbc khi x\u00f3a
            print(f"\u23f3 Ch\u1edd {delete_after} gi\u00e2y tr\u01b0\u1edbc khi x\u00f3a {filename}...")
            time.sleep(delete_after)
            
            # X\u00f3a file
            delete_file_from_minio(bucket, filename)
        
        # X\u00e1c nh\u1eadn \u0111\u00e3 x\u1eed l\u00fd xong
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except Exception as e:
        print(f"\u274c L\u1ed7i x\u1eed l\u00fd: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def start_worker():
    """Kh\u1edfi \u0111\u1ed9ng worker \u0111\u1ec3 l\u1eafng nghe queue"""
    credentials = pika.PlainCredentials('guest', 'guest')
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        credentials=credentials
    )
    
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    # T\u1ea1o queue n\u1ebfu ch\u01b0a c\u00f3
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    
    # C\u1ea5u h\u00ecnh l\u1ea5y 1 message m\u1ed7i l\u1ea7n
    channel.basic_qos(prefetch_count=1)
    
    # \u0110\u0103ng k\u00fd callback
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
    
    print('\ud83d\ude80 Worker b\u1eaft \u0111\u1ea7u l\u1eafng nghe queue...')
    channel.start_consuming()

if __name__ == '__main__':
    start_worker()
