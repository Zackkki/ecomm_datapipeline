# ecomm_datapipeline
An ELT (Extract, Load, Transform) data pipeline built on Google Cloud Platform for processing e-commerce order data in real-time and generating business intelligence insights.
## 🎯 Project Overview

This project demonstrates end-to-end data engineering capabilities by building an automated pipeline that:
- Processes incoming order data every 15 minutes
- Maintains a star schema data warehouse in BigQuery
- Performs automated data quality checks
- Generates real-time analytics and daily business reports
- Orchestrates complex workflows using Apache Airflow

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Sources                             │
│  • Orders (JSON) - Every 15 minutes                         │
│  • Products (CSV) - Daily updates                           │
│  • Customers (CSV) - Daily updates                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Cloud Storage (GCS)                            │
│  Landing Zone → Staging → Archive                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          Cloud Composer (Apache Airflow)                    │
│  • Incremental Pipeline (15 min)                            │
│  • Daily Batch Jobs                                         │
│  • Data Quality Checks                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  BigQuery Data Warehouse                    │
│                                                             │
│  Staging Layer:                                             │
│  ├── staging_orders                                         │
│  ├── staging_products                                       │
│  └── staging_customers                                      │
│                                                             │
│  Core Layer (Star Schema):                                  │
│  ├── fact_orders (Fact Table)                               │
│  ├── dim_products (Dimension)                               │
│  ├── dim_customers (Dimension)                              │
│  └── agg_hourly_metrics (Aggregation)                       │
│                                                             │
│  Data Quality Layer:                                        │
│  └── data_quality_checks                                    │
└─────────────────────────────────────────────────────────────┘
```

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| **Cloud Platform** | Google Cloud Platform (GCP) |
| **Orchestration** | Apache Airflow (Cloud Composer) |
| **Data Warehouse** | BigQuery |
| **Data Lake** | Cloud Storage (GCS) |
| **Programming** | Python 3.11, SQL |
| **Data Processing** | BigQuery SQL, Airflow Operators |

## 📊 Data Model

### Star Schema Design

**Fact Table:**
- `fact_orders` - Grain: One row per product per order
  - Captures: order details, customer info, product info, pricing, location

**Dimension Tables:**
- `dim_customers` - Customer master data with tier information
- `dim_products` - Product catalog with pricing and inventory

**Aggregation Tables:**
- `agg_hourly_metrics` - Pre-aggregated metrics for dashboard performance
- `agg_category_revenue` - Revenue metrics by product category

## 🔄 Pipeline Workflows

### 1. Incremental Order Processing (Every 15 Minutes)

**DAG: `order_processing_incremental`**

```
1. Sensor Task → Detect new order files in GCS
2. Load Task → Load JSON to staging_orders
3. Quality Checks → 
   ├── Check for duplicate orders
   └── Validate order amounts
4. Transform Task → Flatten & enrich data to fact_orders
5. Aggregation Task → Update hourly metrics
6. Archive Task → Move processed files to archive
```

**Key Features:**
- Idempotent processing (prevents duplicate processing)
- Automatic retry on failure (2 retries with 5-min delay)
- Partitioned by date, clustered by customer_id for query performance

### 2. Daily Batch Processing (Midnight)

**DAG: `daily_batch_processing`**

```
1. Load dimensions → Update product & customer data
2. Generate Reports →
   ├── Inactive customers (30+ days no orders)
   ├── Low stock alerts (high demand + low inventory)
   └── Revenue trends by region
3. Data Quality Audit → Summary statistics
```

## 🎯 Data Quality Framework

Automated checks at every stage:

| Check Type | Description | Action |
|------------|-------------|--------|
| **Duplicate Detection** | Identifies duplicate order_id | Fail pipeline |
| **Amount Validation** | Verifies total = sum(item prices) | Log warning |
| **Schema Validation** | Ensures required fields present | Fail task |
| **Missing References** | Checks customer/product exists | Log to audit table |

All quality issues logged to `data_quality_checks` table with severity levels.

## 📈 Business Intelligence Outputs

### Real-Time Dashboard Metrics (15-min refresh)
- Orders per hour
- Revenue by product category
- Top 10 selling products
- Average order value by customer tier
- Geographic distribution

### Daily Reports
1. **Customer Churn Risk** - Customers inactive 30+ days
2. **Inventory Alerts** - Products with high sales but low stock
3. **Revenue Trends** - 90-day trends by region and category

## 🚀 Setup Instructions

### Prerequisites
- GCP Account with billing enabled
- `gcloud` CLI installed and configured
- Python 3.12

### 1. Clone Repository
```bash
git clone https://github.com/zackkki/ecomm_datapipeline.git
cd ecommerce-data-pipeline
```

### 2. Set Up GCP Resources

```bash
# Set project
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Create GCS bucket
gsutil mb -l us-central1 gs://${PROJECT_ID}-data-pipeline

# Create bucket structure
gsutil mkdir gs://${PROJECT_ID}-data-pipeline/landing/orders
gsutil mkdir gs://${PROJECT_ID}-data-pipeline/landing/products
gsutil mkdir gs://${PROJECT_ID}-data-pipeline/landing/customers
gsutil mkdir gs://${PROJECT_ID}-data-pipeline/archive

# Create BigQuery dataset
bq mk --location=asia-southeast1 ecommerce_data
```

### 3. Create BigQuery Tables

```bash
# Run the schema creation script
bq query --use_legacy_sql=false < sql/create_tables.sql
```

### 4. Set Up Cloud Composer

```bash
# Create Composer environment
gcloud composer environments create ecommerce-pipeline \
    --location asia-southeast1 \
    --image-version composer-3-airflow-2.10.5 \

# Get DAGs folder
export DAGS_FOLDER=$(gcloud composer environments describe ecommerce-pipeline \
    --location asia-southeast1 \
    --format="get(config.dagGcsPrefix)")
```

### 5. Deploy Airflow DAGs

```bash
# Upload DAGs
gsutil cp dags/*.py $DAGS_FOLDER/

# Grant permissions to Composer service account
export COMPOSER_SA=$(gcloud composer environments describe ecommerce-pipeline \
    --location asia-southeast1 \
    --format="get(config.nodeConfig.serviceAccount)")

gsutil iam ch serviceAccount:${COMPOSER_SA}:objectAdmin \
    gs://${PROJECT_ID}-data-pipeline
```

### 6. Generate and Upload Sample Data

```bash
# Generate sample data
python scripts/generate_orders.py
python scripts/generate_products.py
python scripts/generate_customers.py

# Upload to GCS
gsutil cp data/orders_sample.json \
    gs://${PROJECT_ID}-data-pipeline/landing/orders/orders_$(date +%Y%m%d_%H%M%S).json
gsutil cp data/products_sample.csv \
    gs://${PROJECT_ID}-data-pipeline/landing/products/products_latest.csv
gsutil cp data/customers_sample.csv \
    gs://${PROJECT_ID}-data-pipeline/landing/customers/customers_latest.csv
```

### 7. Enable DAGs in Airflow UI

1. Access Airflow UI:
```bash
gcloud composer environments describe ecommerce-pipeline \
    --location asia-southeast1 \
    --format="get(config.airflowUri)"
```

2. Toggle ON the DAGs:
   - `order_processing_incremental`
   - `daily_batch_processing` (create this based on requirements)

3. Manually trigger for testing

## 📁 Project Structure

```
ecommerce-datapipeline/
├── dags/
│   └── order_processing_incremental.py    # 15-min incremental pipeline
│   
├── scripts/
│   ├── generate_orders.py                 # Sample data generator
│   ├── generate_products.py
│   └── generate_customers.py
└── README.md


## 📊 Monitoring & Observability

- **Airflow UI**: Task status, logs, execution times
- **BigQuery Audit Logs**: Query performance, slot usage
- **Cloud Monitoring**: Set up alerts for:
  - Pipeline failures
  - Data quality check failures
  - Processing time anomalies
  - Cost thresholds

## 🎓 Key Learnings & Design Decisions

### Why ELT over ETL?
- Leverages BigQuery's distributed processing power
- Keeps raw data intact for reprocessing
- Enables faster iteration on transformations
- Scales better with data volume growth

### Why Star Schema?
- Optimized for analytical queries
- Denormalized structure improves query performance
- Intuitive for business users
- Supports both detailed and aggregated analysis

### Why 15-Minute Increments?
- Balances freshness with cost
- Reduces API calls vs real-time streaming
- Allows batch processing optimizations
- Sufficient for business decision-making

## 🔮 Future Enhancements

- [ ] Add dbt for transformation layer management
- [ ] Implement CDC (Change Data Capture) for real-time updates
- [ ] Add data lineage tracking with Apache Atlas
- [ ] Create Looker/Data Studio dashboards
- [ ] Implement data versioning and time travel
- [ ] Add machine learning predictions (demand forecasting)
- [ ] Set up automated data profiling with Great Expectations

## 📝 License

MIT License - feel free to use this project for learning and portfolio purposes.

## 🙏 Acknowledgments

- Built as part of data engineering learning journey
- Inspired by real-world e-commerce analytics requirements
- Thanks to the open-source community for amazing tools

---

**⭐ If you find this project helpful, please give it a star!**
