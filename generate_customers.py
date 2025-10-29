import csv
import random
from datetime import datetime, timedelta

def generate_customers(num_customers=1000, output_file='customers_sample.csv'):
    """Generate sample customer data"""
    
    tiers = ['bronze', 'silver', 'gold']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['customer_id', 'name', 'email', 'registration_date', 'customer_tier'])
        
        for i in range(1000, 1000 + num_customers):
            reg_date = datetime.now() - timedelta(days=random.randint(1, 365))
            writer.writerow([
                f'CUST-{i}',
                f'Customer {i}',
                f'customer{i}@example.com',
                reg_date.strftime('%Y-%m-%d'),
                random.choice(tiers)
            ])
    
    print(f'Generated {num_customers} customers in {output_file}')

if __name__ == '__main__':
    generate_customers()
