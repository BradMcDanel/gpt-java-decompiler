"""
Fetches the Java source code from BigQuery and writes it to .json files.
"""

import argparse
import json
import os

import tqdm

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--table-path', type=str, required=True, help='BigQuery table path')
    parser.add_argument('--output-dir', type=str, required=True, help='Output directory')
    parser.add_argument('--batch-size', type=int, default=100000, help='Batch size')
    args = parser.parse_args()

    num_rows_query = f'''bq --format=json query "SELECT COUNT(*) FROM {args.table_path}"'''
    num_rows = os.popen(num_rows_query).read().strip()
    num_rows = int(json.loads(num_rows)[0]["f0_"])

    query = '''bq --format=json query -n={} "SELECT * FROM {} LIMIT {} OFFSET {}"'''
    chunk = 0
    for i in tqdm.tqdm(range(0, num_rows, args.batch_size), desc='Fetching'):
        rows = min(args.batch_size, num_rows - i)
        query_str = query.format(rows, args.table_path, args.batch_size, i)
        output_path = os.path.join(args.output_dir, f'{chunk}.json')
        os.system(query_str + ' > ' + output_path)
        chunk += 1
