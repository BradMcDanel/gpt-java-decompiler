# Copyright (c) Microsoft Corporation. 
# Licensed under the MIT license.

# -*- coding:utf-8 -*-
import argparse
import bleu
import weighted_ngram_match
import syntax_match
import dataflow_match
import json

parser = argparse.ArgumentParser()

parser.add_argument("--data-path", type=str, required=True, 
                        help="Data path")
parser.add_argument('--lang', type=str, default='java', 
                        choices=['java','js','c_sharp','php','go','python','ruby'],
                        help='programming language')
parser.add_argument('--params', type=str, default='0.25,0.25,0.25,0.25',
                        help='alpha, beta and gamma')

args = parser.parse_args()

lang = args.lang
alpha,beta,gamma,theta = [float(x) for x in args.params.split(',')]

tools = ['Procyon','CFR','JADX','Fernflower','Krakatau']

for tool in tools:

    # preprocess inputs
    references = []
    hypothesis = []

    #load data
    with open(args.data_path, 'r') as f:
        for line in f:
            references.append(json.loads(line)["Gold"]["java_source"])
            hypothesis.append(json.loads(line)[tool]["java_source"])

    hypothesis = ["" if h is None else h for h in hypothesis]
    references = [[r] for r in references]


    # calculate ngram match (BLEU)
    tokenized_hyps = [x.split() for x in hypothesis]
    tokenized_refs = [[x.split() for x in reference] for reference in references]

    ngram_match_score = bleu.corpus_bleu(tokenized_refs,tokenized_hyps)

    # calculate weighted ngram match
    keywords = [x.strip() for x in open('keywords/'+args.lang+'.txt', 'r', encoding='utf-8').readlines()]
    def make_weights(reference_tokens, key_word_list):
        return {token:1 if token in key_word_list else 0.2 \
                for token in reference_tokens}
    tokenized_refs_with_weights = [[[reference_tokens, make_weights(reference_tokens, keywords)]\
                for reference_tokens in reference] for reference in tokenized_refs]

    weighted_ngram_match_score = weighted_ngram_match.corpus_bleu(tokenized_refs_with_weights,tokenized_hyps)

    # calculate syntax match
    syntax_match_score = syntax_match.corpus_syntax_match(references, hypothesis, args.lang)

    # calculate dataflow match
    dataflow_match_score = dataflow_match.corpus_dataflow_match(references, hypothesis, args.lang)

    print('ngram match: {0}, weighted ngram match: {1}, syntax_match: {2}, dataflow_match: {3}'.\
                        format(ngram_match_score, weighted_ngram_match_score, syntax_match_score, dataflow_match_score))

    code_bleu_score = alpha*ngram_match_score\
                    + beta*weighted_ngram_match_score\
                    + gamma*syntax_match_score\
                    + theta*dataflow_match_score

    print(tool +' CodeBLEU score: ', code_bleu_score)




