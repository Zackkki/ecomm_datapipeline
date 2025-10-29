from airflow import DAG
from airflow.providers.google.cloud.sensors.gcs import GCSObjectsWithPrefixExistenceSensor
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator, BigQueryCheckOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
from google.cloud import storage

# Configuration
PROJECT_ID = 'ecommdatapipeline'
DATASET_ID = 'ecommerce_data'
GCS_BUCKET = 'e_comm_de'
GCS_ORDER_PREFIX = 'landing/orders/'

default_args = {
    'owner': 'data-eng',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'order_processing_incremental',
    default_args=default_args,
    description='Process incoming order files every 15 minutes',
    schedule_interval='*/15 * * * *',  # Every 15 minutes
    start_date=days_ago(1),
    catchup=False,
    tags=['orders', 'incremental'],
)

# Task 1: Check for new order files
check_new_files = GCSObjectsWithPrefixExistenceSensor(
    task_id='check_new_order_files',
    bucket=GCS_BUCKET,
    prefix=GCS_ORDER_PREFIX,
    google_cloud_conn_id='google_cloud_default',
    dag=dag,
    poke_interval=60,  # Check every 60 seconds
    timeout=600,  # Timeout after 10 minutes
    mode='poke',
)

# Task 2: Load orders to staging
load_to_staging = GCSToBigQueryOperator(
    task_id='load_orders_to_staging',
    bucket=GCS_BUCKET,
    source_objects=[f'{GCS_ORDER_PREFIX}*.json'],
    destination_project_dataset_table=f'{PROJECT_ID}.{DATASET_ID}.staging_orders',
    source_format='NEWLINE_DELIMITED_JSON',
    write_disposition='WRITE_APPEND',
    autodetect=False,
    schema_fields=[
        {'name': 'order_id', 'type': 'STRING', 'mode': 'REQUIRED'},
        {'name': 'customer_id', 'type': 'STRING', 'mode': 'REQUIRED'},
        {'name': 'order_timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
        {'name': 'items', 'type': 'RECORD', 'mode': 'REPEATED', 'fields': [
            {'name': 'product_id', 'type': 'STRING'},
            {'name': 'quantity', 'type': 'INTEGER'},
            {'name': 'unit_price', 'type': 'FLOAT'},
        ]},
        {'name': 'total_amount', 'type': 'FLOAT', 'mode': 'REQUIRED'},
        {'name': 'payment_status', 'type': 'STRING'},
        {'name': 'shipping_address', 'type': 'RECORD', 'mode': 'NULLABLE', 'fields': [
            {'name': 'street', 'type': 'STRING'},
            {'name': 'city', 'type': 'STRING'},
            {'name': 'state', 'type': 'STRING'},
            {'name': 'zipcode', 'type': 'STRING'},
            {'name': 'country', 'type': 'STRING'},
        ]},
    ],
    dag=dag,
)

# Task 3: Data Quality Check - Duplicate Orders
check_duplicates = BigQueryCheckOperator(
    task_id='check_duplicate_orders',
    sql=f'''
        SELECT COUNT(*) = 0
        FROM (
            SELECT order_id, COUNT(*) as cnt
            FROM `{PROJECT_ID}.{DATASET_ID}.staging_orders`
            WHERE DATE(order_timestamp) = CURRENT_DATE()
            GROUP BY order_id
            HAVING cnt > 1
        )
    ''',
    use_legacy_sql=False,
    dag=dag,
)

# Task 4: Data Quality Check - Amount Mismatch
check_amount_mismatch = BigQueryInsertJobOperator(
    task_id='check_amount_mismatch',
    configuration={
        'query': {
            'query': f'''
                INSERT INTO `{PROJECT_ID}.{DATASET_ID}.data_quality_checks`
                (check_id, check_timestamp, check_type, order_id, issue_description, severity)
                SELECT
                    GENERATE_UUID() as check_id,
                    CURRENT_TIMESTAMP() as check_timestamp,
                    'amount_mismatch' as check_type,
                    order_id,
                    CONCAT('Calculated: ', calculated_total, ' vs Recorded: ', total_amount) as issue_description,
                    'warning' as severity
                FROM (
                    SELECT
                        order_id,
                        total_amount,
                        ROUND((SELECT SUM(quantity * unit_price) FROM UNNEST(items)), 2) as calculated_total
                    FROM `{PROJECT_ID}.{DATASET_ID}.staging_orders`
                    WHERE DATE(order_timestamp) = CURRENT_DATE()
                )
                WHERE ABS(calculated_total - total_amount) > 0.01
            ''',
            'useLegacySql': False,
        }
    },
    dag=dag,
)

# Task 5: Transform to fact_orders
transform_to_fact = BigQueryInsertJobOperator(
    task_id='transform_to_fact_orders',
    configuration={
        'query': {
            'query': f'''
                INSERT INTO `{PROJECT_ID}.{DATASET_ID}.fact_orders`
                (order_id, customer_id, customer_tier, order_timestamp, order_date, order_hour,
                 product_id, product_name, category, quantity, unit_price, line_total, 
                 total_amount, payment_status, city, state, country, region)
                SELECT
                    o.order_id,
                    o.customer_id,
                    COALESCE(c.customer_tier, 'bronze') as customer_tier,
                    o.order_timestamp,
                    DATE(o.order_timestamp) as order_date,
                    EXTRACT(HOUR FROM o.order_timestamp) as order_hour,
                    item.product_id,
                    p.product_name,
                    p.category,
                    item.quantity,
                    item.unit_price,
                    item.quantity * item.unit_price as line_total,
                    o.total_amount,
                    o.payment_status,
                    o.shipping_address.city as city,
                    o.shipping_address.state as state,
                    o.shipping_address.country as country,
                    CASE 
                        WHEN o.shipping_address.state IN ('CA', 'OR', 'WA') THEN 'West'
                        WHEN o.shipping_address.state IN ('NY', 'NJ', 'PA') THEN 'East'
                        WHEN o.shipping_address.state IN ('TX', 'AZ', 'NM') THEN 'South'
                        ELSE 'Other'
                    END as region
                FROM `{PROJECT_ID}.{DATASET_ID}.staging_orders` o
                LEFT JOIN UNNEST(o.items) as item
                LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.dim_customers` c ON o.customer_id = c.customer_id
                LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.dim_products` p ON item.product_id = p.product_id
                WHERE DATE(o.order_timestamp) = CURRENT_DATE()
                    AND NOT EXISTS (
                        SELECT 1 FROM `{PROJECT_ID}.{DATASET_ID}.fact_orders` f
                        WHERE f.order_id = o.order_id
                    )
            ''',
            'useLegacySql': False,
        }
    },
    dag=dag,
)

# Task 6: Update hourly aggregations
update_hourly_agg = BigQueryInsertJobOperator(
    task_id='update_hourly_aggregations',
    configuration={
        'query': {
            'query': f'''
                MERGE `{PROJECT_ID}.{DATASET_ID}.agg_hourly_metrics` T
                USING (
                    SELECT
                        TIMESTAMP_TRUNC(order_timestamp, HOUR) as metric_hour,
                        COUNT(DISTINCT order_id) as total_orders,
                        SUM(total_amount) as total_revenue,
                        AVG(total_amount) as avg_order_value,
                        COUNT(DISTINCT customer_id) as unique_customers
                    FROM `{PROJECT_ID}.{DATASET_ID}.fact_orders`
                    WHERE DATE(order_timestamp) = CURRENT_DATE()
                    GROUP BY metric_hour
                ) S
                ON T.metric_hour = S.metric_hour
                WHEN MATCHED THEN
                    UPDATE SET
                        total_orders = S.total_orders,
                        total_revenue = S.total_revenue,
                        avg_order_value = S.avg_order_value,
                        unique_customers = S.unique_customers,
                        updated_at = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN
                    INSERT (metric_hour, total_orders, total_revenue, avg_order_value, unique_customers, updated_at)
                    VALUES (S.metric_hour, S.total_orders, S.total_revenue, S.avg_order_value, S.unique_customers, CURRENT_TIMESTAMP())
            ''',
            'useLegacySql': False,
        }
    },
    dag=dag,
)

# Task 7: Archive processed files
def archive_files(**context):
    """Move processed files to archive folder"""
    from datetime import datetime
    
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    
    blobs = bucket.list_blobs(prefix=GCS_ORDER_PREFIX)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for blob in blobs:
        if blob.name.endswith('.json'):
            new_name = blob.name.replace('landing/', f'archive/{timestamp}/')
            bucket.rename_blob(blob, new_name)
            print(f'Archived: {blob.name} -> {new_name}')

archive_files_task = PythonOperator(
    task_id='archive_processed_files',
    python_callable=archive_files,
    dag=dag,
)

# Define task dependencies
check_new_files >> load_to_staging >> [check_duplicates, check_amount_mismatch]
[check_duplicates, check_amount_mismatch] >> transform_to_fact >> update_hourly_agg >> archive_files_task