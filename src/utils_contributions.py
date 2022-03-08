#@title Utilities


import numpy as np
import itertools
import torch
import matplotlib.pyplot as plt
import pandas as pd
import json
import random
random.seed(10)

from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers import AutoTokenizer, AutoModelForMaskedLM
from ipywidgets import IntProgress
import torch.nn.functional as F


from src.contributions import ModelWrapper, ClassificationModelWrapperCaptum, LMModelWrapperCaptum
import matplotlib
#matplotlib.use('Agg')

from captum.attr import visualization

try:
    from IPython.core.display import HTML, display

    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False

color_name = 'color{}'
define_color = '\definecolor{{{}}}{{HTML}}{{{}}}'
box = '\\mybox{{{}}}{{\strut{{{}}}}}'

device = "cuda" if torch.cuda.is_available() else "cpu"



def load_model_data(model_name,dataset_name=None):
    """Load model and datasets."""

    print('Loading',model_name,'...')
    print('Loading',dataset_name,'...')

    if dataset_name == 'sst2':
        dataset = load_dataset('glue', 'sst2',split='test')
        if model_name == 'bert':
            tokenizer = AutoTokenizer.from_pretrained("textattack/bert-base-uncased-SST-2")
            model = AutoModelForSequenceClassification.from_pretrained("textattack/bert-base-uncased-SST-2")
        elif model_name == 'distilbert':
            tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased-finetuned-sst-2-english")
            model = AutoModelForSequenceClassification.from_pretrained("distilbert-base-uncased-finetuned-sst-2-english")
        elif model_name == 'roberta':
            tokenizer = AutoTokenizer.from_pretrained("textattack/roberta-base-SST-2")
            model = AutoModelForSequenceClassification.from_pretrained("textattack/roberta-base-SST-2")
        else:
            print('please select bert, distilbert or roberta')
            return -1

    elif dataset_name == 'imdb':
        dataset = load_dataset("imdb",split='test')
        if model_name == 'bert':
            tokenizer = AutoTokenizer.from_pretrained("textattack/bert-base-uncased-imdb")
            model = AutoModelForSequenceClassification.from_pretrained("textattack/bert-base-uncased-imdb")
        elif model_name == 'distilbert':
            tokenizer = AutoTokenizer.from_pretrained("textattack/distilbert-base-uncased-imdb")
            model = AutoModelForSequenceClassification.from_pretrained("textattack/distilbert-base-uncased-imdb")
        elif model_name == 'roberta':
            tokenizer = AutoTokenizer.from_pretrained("textattack/roberta-base-imdb")
            model = AutoModelForSequenceClassification.from_pretrained("textattack/roberta-base-imdb")
    else:
        if dataset_name == 'sva':
            data_file = open("data/lgd_dataset.tsv",encoding="utf8")
            dataset = data_file.readlines()
        else:
            print('No dataset provided, loading pre-trained models and no dataset')
            dataset = None
        
        if model_name == 'bert':
            tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
            model = AutoModelForMaskedLM.from_pretrained("bert-base-uncased")

        elif model_name == 'distilbert':
            tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
            model = AutoModelForMaskedLM.from_pretrained("distilbert-base-uncased")

        elif model_name == 'roberta':
            tokenizer = AutoTokenizer.from_pretrained("roberta-base")
            model = AutoModelForMaskedLM.from_pretrained("roberta-base")
        else:
            print('please select bert, distilbert or roberta')
            return -1
        

    model.to(device)
    model.zero_grad()
    return model, tokenizer, dataset


def get_cos_mean(model_name,dataset_name,num_samples = 500):
    """Compute the average cosine similarity between random samples of token representations
        and of transformer vectors."""

    model, tokenizer, dataset_partition = load_model_data(model_name,dataset_name)
    try:
        num_layers = model.config.num_hidden_layers
    except:
        num_layers = model.config.n_layers

    t_cos_layer = {}
    cos_layer = {}
    for layer in range(num_layers+1):
        cos_layer[layer] = []
        if layer < num_layers:
            t_cos_layer[layer] = []


    if dataset_name == 'sva':
        out_fn = f'cos_results/{model_name}_sva_cos_results.json'   
        for i,line in enumerate(open("data/lgd_dataset.tsv",encoding="utf8")):
            na,_,masked,good,bad = line.strip().split("\t")
            if i == num_samples:
                break
            # Add Ġ to word if using RoBERTa
            if model_name == 'roberta':
                good = '\u0120' + good
                bad = '\u0120' + bad
            text = masked.replace('***mask***',tokenizer.mask_token)
            pt_batch = tokenizer(text, return_tensors="pt").to(device)
            target_idx = (pt_batch['input_ids'][0] == tokenizer.mask_token_id).nonzero(as_tuple=True)
            target_idx = target_idx[0].item()
            good_verb_id = tokenizer.convert_tokens_to_ids(good)
            wrong_verb_id = tokenizer.convert_tokens_to_ids(bad)
            model_wrapped = ModelWrapper(model)
            prediction_scores, hidden_states, attentions, transformed_vectors_norm_model, contributions, transformed_vectors = model_wrapped(pt_batch)
            #transformed_vectors = transformed_vectors[:,1:-1,1:-1,:]
            embeddings = torch.stack(hidden_states, dim=0).squeeze()#[:,1:-1,:]
            for layer in range(num_layers+1):
                samples = random.sample(range(0,transformed_vectors.size(2)), k=2)
                cos_sim_samples = F.cosine_similarity(embeddings[layer,samples[0]], embeddings[layer,samples[1]], dim=-1)
                cos_layer[layer].append(cos_sim_samples.cpu().detach().numpy())
                if layer < num_layers:
                    t_cos_sim_samples = F.cosine_similarity(transformed_vectors[layer,:,samples[0]], transformed_vectors[layer,:,samples[1]], dim=-1)
                    t_cos_layer[layer].append(t_cos_sim_samples.cpu().detach().numpy())
    
    elif dataset_name == 'sst2':
        out_fn = f'cos_results/{model_name}_sst2_cos_results.json'            
        for i in range(0,num_samples):    
            model_wrapped = ModelWrapper(model)
            sentence = dataset_partition[i]
            text = sentence['sentence']
            pt_batch = tokenizer(text, return_tensors="pt").to(device)
            prediction_scores, hidden_states, attentions, transformed_vectors_norm_model, contributions, transformed_vectors = model_wrapped(pt_batch)
            #transformed_vectors = transformed_vectors[:,1:-1,1:-1,:]
            embeddings = torch.stack(hidden_states, dim=0).squeeze()#[:,1:-1,:]
            for layer in range(num_layers+1):
                samples = random.sample(range(0,transformed_vectors.size(2)), k=2)
                cos_sim_samples = F.cosine_similarity(embeddings[layer,samples[0]], embeddings[layer,samples[1]], dim=-1)
                cos_layer[layer].append(cos_sim_samples.cpu().detach().numpy())
                if layer < num_layers:
                    t_cos_sim_samples = F.cosine_similarity(transformed_vectors[layer,:,samples[0]], transformed_vectors[layer,:,samples[1]], dim=-1)
                    t_cos_layer[layer].append(t_cos_sim_samples.cpu().detach().numpy())


    mean_cos_transformed = { f'layer_{layer}' : -1 for layer in range(num_layers) }
    mean_cos_embeddings = { f'layer_{layer}' : -1 for layer in range(num_layers) }

    for layer in range(num_layers):
        mean_cos_transformed[f'layer_{layer}'] = str(np.concatenate(t_cos_layer[layer]).mean())

    for layer in range(num_layers+1):
        mean_cos_embeddings[f'layer_{layer}'] = str(np.array(cos_layer[layer]).mean())

    
    with open(out_fn, 'w') as f:
            json.dump({
            'mean cosine similarity transformed vectors' : mean_cos_transformed,
            'mean cosine similarity embeddings' : mean_cos_embeddings
            }, f)

def normalize_attribution_visualization(attributions):
    """Applies min-max normalization for visualization purposes."""

    min_importance_matrix = attributions.min(0, keepdim=True)[0]
    max_importance_matrix = attributions.max(0, keepdim=True)[0]
    attributions = (attributions - min_importance_matrix) / (max_importance_matrix - min_importance_matrix)
    return attributions

def normalize_contributions(model_contributions,scaling='minmax',resultant_norm=None):
    """Normalization of the matrix of contributions/weights extracted from the model."""

    normalized_model_contributions = torch.zeros(model_contributions.size())
    for l in range(0,model_contributions.size(0)):

        if scaling == 'min_max':
            ## Min-max normalization
            min_importance_matrix = model_contributions[l].min(-1, keepdim=True)[0]
            max_importance_matrix = model_contributions[l].max(-1, keepdim=True)[0]
            normalized_model_contributions[l] = (model_contributions[l] - min_importance_matrix) / (max_importance_matrix - min_importance_matrix)
            normalized_model_contributions[l] = normalized_model_contributions[l] / normalized_model_contributions[l].sum(dim=-1,keepdim=True)

        elif scaling == 'sum_one':
            normalized_model_contributions[l] = model_contributions[l] / model_contributions[l].sum(dim=-1,keepdim=True)
            #normalized_model_contributions[l] = normalized_model_contributions[l].clamp(min=0)

        # For l1 distance between resultant and transformer vectors we apply min_sum
        elif scaling == 'min_sum':
            if resultant_norm == None:
                min_importance_matrix = model_contributions[l].min(-1, keepdim=True)[0]
                normalized_model_contributions[l] = model_contributions[l] + torch.abs(min_importance_matrix)
                normalized_model_contributions[l] = normalized_model_contributions[l] / normalized_model_contributions[l].sum(dim=-1,keepdim=True)
            else:
                normalized_model_contributions[l] = model_contributions[l] + torch.abs(resultant_norm[l].unsqueeze(1))
                normalized_model_contributions[l] = torch.clip(normalized_model_contributions[l],min=0)
                normalized_model_contributions[l] = normalized_model_contributions[l] / normalized_model_contributions[l].sum(dim=-1,keepdim=True)
        else:
            print('No normalization selected!')
    return normalized_model_contributions

def plot_histogram(input_tensor,text):
    """Helper function to make bar plots."""

    input_tensor = input_tensor.cpu().detach().numpy()
    # Creating plot
    fig = plt.figure(figsize =(20,4))
    ax = fig.add_subplot(111)
    ax.bar(range(0,input_tensor.size),input_tensor)
    plt.xticks(ticks = range(0,input_tensor.size) ,labels = text, rotation = 45)

def get_raw_att_relevance(full_att_mat, layer=-1,token_pos=0):
    att_sum_heads =  full_att_mat.sum(axis=1)/full_att_mat.shape[1]
    return att_sum_heads[layer][token_pos,:]

def spearmanr(x, y):
    """Compute Spearman rank's correlation bertween two attribution vectors.
        https://github.com/samiraabnar/attention_flow/blob/master/compute_corel_distilbert_sst.py"""

    x = pd.Series(x)
    y = pd.Series(y)
    assert x.shape == y.shape
    rx = x.rank(method='dense')
    ry = y.rank(method='dense')
    d = rx - ry
    dsq = np.sum(np.square(d))
    n = x.shape[0]
    coef = 1. - (6. * dsq) / (n * (n**2 - 1.))
    return [coef]

def get_normalized_rank(x):
    """Compute normalized [0,1] ranks. The higher the value, the higher the rank."""
    
    length_tok_sentence = x.shape
    x = pd.Series(x)
    rank = x.rank(method='dense')
    rank_normalized = rank/length_tok_sentence
    return rank_normalized

def add_attributions_to_visualizer(attributions, tokens, pred, pred_ind, label, delta, vis_data_records):    
    # storing couple samples in an array for visualization purposes
    vis_data_records.append(visualization.VisualizationDataRecord(
                            attributions,
                            pred,
                            pred_ind,
                            label,
                            "label",
                            attributions.sum(),       
                            tokens[:len(attributions)],
                            delta))
                        

def format_special_tokens(token):
    if token.startswith("<") and token.endswith(">"):
        return "#" + token.strip("<>")
    return token

def _get_color(attr):
    # clip values to prevent CSS errors (Values should be from [-1,1])
    attr = max(-1, min(1, attr))
    if attr > 0:
        hue = 207
        sat = 75
        lig = 100 - int(40 * attr)
    else:
        hue = 0
        sat = 75
        lig = 100 - int(-40 * attr)
    return "hsl({}, {}%, {}%)".format(hue, sat, lig)

def format_word_importances(words, importances):
    if importances is None or len(importances) == 0:
        return "<td></td>"
    assert len(words) <= len(importances)
    tags = ["<td>"]
    for word, importance in zip(words, importances[: len(words)]):
        word = format_special_tokens(word)
        color = _get_color(importance)
        unwrapped_tag = '<mark style="background-color: {color}; opacity:1.0; \
                    line-height:1.75"><font color="black"> {word}\
                    </font></mark>'.format(
            color=color, word=word
        )
        tags.append(unwrapped_tag)
    tags.append("</td>")
    return "".join(tags)


def latex_colorize(text, weights):
    """https://github.com/ucinlp/facade/blob/facade/util/generate_colorize.py"""

    s = ''
    for w, x in zip(text, weights):
        w = w.replace('#','\#')
        color = np.digitize(x, np.arange(0, 0.9, 0.1)) - 1
        s += ' ' + box.format(color_name.format(color), w)
    return s

def prepare_colorize():
    """ Define scale of colors for macros.tex."""

    with open('latex_saliency/colorize.tex', 'w') as f:
        cmap = plt.cm.get_cmap('Blues')
        for i, x in enumerate(np.arange(0, 0.9, 0.1)):
            rgb = matplotlib.colors.rgb2hex(cmap(x)[:3])
            # convert to upper to circumvent xcolor bug
            rgb = rgb[1:].upper() if x > 0 else 'FFFFFF'
            f.write(define_color.format(color_name.format(i), rgb))
            f.write('\n')
        f.write('''\\newcommand*{\mybox}[2]{\\tikz[anchor=base,baseline=0pt,rounded corners=0pt, inner sep=0.2mm] \\node[fill=#1!60!white] (X) {#2};}''')
        f.write('\n')
        f.write('''\\newcommand*{\mybbox}[2]{\\tikz[anchor=base,baseline=0pt,inner sep=0.2mm,] \\node[draw=black,thick,fill=#1!60!white] (X) {#2};}''')


def figure_saliency(attributions_list, tokenized_text, methods_list):
    """ Creates rows of paper's tables by adding the corresponding color to the text."""

    methods_dict = {0:'$\\text{Grad}_{l2}$', 1:'Grad $\\cdot$ input', 2:'Integrated Gradients', 3:'Attn Rollout', 4:'Norm Rollout', 5:'Ours'}


    words_weights = []
    for i in methods_list:
        attr = attributions_list[i]
        # We need to replace RoBERTa's special character
        words_weights.append((tokenized_text[i].replace('\u0120',''), element.item()) for i, element in enumerate(attr))
    
    
    with open('latex_saliency/figure.tex', 'w') as f:
        for i, ww in enumerate(words_weights):
            method_latex = methods_dict[methods_list[i]]
            f.write('''\multicolumn{1}{l}{''' + method_latex + '''}\\\ \n''')
            words, weights = list(map(list, zip(*ww)))
            f.write(latex_colorize(words, weights)+'\\\\\n')
            if i == len(words_weights)-1:
                f.write('''\\bottomrule''')
            else:
                f.write('''\\addlinespace\n''')


def compute_joint_attention(att_mat):
    """ Compute attention rollout given contributions or attn weights + residual."""

    aug_att_mat =  att_mat
    device = att_mat.device
    joint_attentions = torch.zeros(aug_att_mat.size()).to(device)

    layers = joint_attentions.shape[0]
    joint_attentions[0] = aug_att_mat[0]
    #joint_attentions[0] = joint_attentions[0] / joint_attentions[0].sum(dim=-1,keepdim=True)
    
        
    for i in np.arange(1,layers):
        joint_attentions[i] = torch.matmul(aug_att_mat[i],joint_attentions[i-1])
        
        
    return joint_attentions


def compute_rollout(att_mat):
    """ Compute rollout method for raw attention weights."""

    # Add residual connection
    res_att_mat = att_mat + np.eye(att_mat.shape[1])[None,...]
    # Normalize to sum 1
    res_att_mat = res_att_mat / res_att_mat.sum(axis=-1)[...,None]
    res_att_mat_torch = torch.tensor(res_att_mat,dtype=torch.float32)
    joint_attentions = compute_joint_attention(res_att_mat_torch) # (num_layers,src_len,src_len)
    return joint_attentions

