# generate_products.py
import csv
import random

def generate_products(num_products=100, output_file='products_sample.csv'):
    """Generate sample product catalog"""
    
    categories = ['Electronics', 'Clothing', 'Home & Garden', 'Books', 'Sports']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['product_id', 'product_name', 'category', 'price', 'stock_level'])
        
        for i in range(1000, 1000 + num_products):
            category = random.choice(categories)
            writer.writerow([
                f'PROD-{i}',
                f'{category} Product {i}',
                category,
                round(random.uniform(10, 500), 2),
                random.randint(0, 1000)
            ])
    
    print(f'Generated {num_products} products in {output_file}')

if __name__ == '__main__':
    generate_products()