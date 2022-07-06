import argparse
import os
import json
import random

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=str, required=True, help="Input directory")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory")
    parser.add_argument("--train-percentage", type=float, default=0.85, help="Percentage of Java files to use for training")
    parser.add_argument("--seed", type=int, default=0, help="Random seed")
    args = parser.parse_args()

    # make sure output directory exists
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    all_data = []
    for filename in os.listdir(args.input_dir):
        with open(os.path.join(args.input_dir, filename), 'r') as f:
            all_data.extend(json.load(f))


    # shuffle data
    random.seed(args.seed)
    random.shuffle(all_data)

    # split data
    train_data = all_data[:int(len(all_data) * args.train_percentage)]
    test_data = all_data[int(len(all_data) * args.train_percentage):]

    print("Train data: {}".format(len(train_data)))
    print("Test data: {}".format(len(test_data)))

    # write data
    with open(os.path.join(args.output_dir, 'train.json'), 'w') as f:
        for dict in train_data:
            f.write(json.dumps(dict) + '\n')

    with open(os.path.join(args.output_dir, 'test.json'), 'w') as f:
        for dict in test_data:
            f.write(json.dumps(dict) + '\n')
