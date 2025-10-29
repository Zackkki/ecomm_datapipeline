# generate_orders.py
import json
import random
from datetime import datetime, timedelta
import uuid

def generate_orders(num_orders=50, output_file='orders_sample.json'):
    """Generate sample order data"""
    
    categories = ['Electronics', 'Clothing', 'Home & Garden', 'Books', 'Sports']
    statuses = ['completed', 'pending', 'failed']
    cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix']
    states = ['NY', 'CA', 'IL', 'TX', 'AZ']
    
    orders = []
    
    for _ in range(num_orders):
        num_items = random.randint(1, 5)
        items = []
        total = 0
        
        for _ in range(num_items):
            unit_price = round(random.uniform(10, 500), 2)
            quantity = random.randint(1, 3)
            items.append({
                'product_id': f'PROD-{random.randint(1000, 9999)}',
                'quantity': quantity,
                'unit_price': unit_price
            })
            total += unit_price * quantity
        
        city_idx = random.randint(0, len(cities)-1)
        
        order = {
            'order_id': str(uuid.uuid4()),
            'customer_id': f'CUST-{random.randint(1000, 5000)}',
            'order_timestamp': (datetime.now() - timedelta(minutes=random.randint(0, 60))).isoformat(),
            'items': items,
            'total_amount': round(total, 2),
            'payment_status': random.choice(statuses),
            'shipping_address': {
                'street': f'{random.randint(100, 9999)} Main St',
                'city': cities[city_idx],
                'state': states[city_idx],
                'zipcode': f'{random.randint(10000, 99999)}',
                'country': 'USA'
            }
        }
        orders.append(order)
    
    with open(output_file, "w") as f:
        for row in orders:
            f.write(json.dumps(row) + "\n")
    
    print(f'Generated {num_orders} orders in {output_file}')

if __name__ == '__main__':
    generate_orders()