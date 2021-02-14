"""
Stability Evaluation
"""

import pickle
import re
from collections import OrderedDict
from statistics import stdev

import numpy as np
import pandas as pd
from keras.wrappers.scikit_learn import KerasClassifier
from lime.lime_text import LimeTextExplainer
from scipy.spatial.distance import cdist
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline

from DNN_base import TextsToSequences, Padder, create_model
from pre_processing import get_text_data

sequencer = TextsToSequences(num_words=35000)
padder = Padder(140)
myModel = KerasClassifier(build_fn=create_model, epochs=100)


def find_closest_k_sentences(sentences, ids, k, metric):
    # Needs at least 11 sentences to work
    index_list = ids
    final_idx_distances = list()
    sentences = [sentences[x] for x in ids]
    print(sentences)
    vectorizer = TfidfVectorizer()
    sentences_vectors = vectorizer.fit_transform(sentences).toarray()

    dictionary = dict(zip(index_list, sentences_vectors))
    distances = [[] for _ in range(len(sentences))]
    distances_dict = [dict() for _ in range(len(sentences))]
    cosine_distance_list = [[] for _ in range(len(sentences))]
    idx_distances = list()
    count = 0
    for idx in index_list:
        instance = dictionary.get(idx)
        instance = np.array(instance)

        for j in index_list:
            temp_state_sentence = dictionary.get(j)

            distances[count].append(
                cdist(instance.reshape(1, -1), temp_state_sentence.reshape(1, -1), metric='cosine').ravel())
            idx_distances.append(j)

        distances_dict[count] = dict(zip(idx_distances, distances[count]))
        distances_sorted = {k: v for k, v in sorted(distances_dict[count].items(), key=lambda x: x[1])}
        final_idxs, final_dists = zip(*list(distances_sorted.items()))
        final_idx_distances.append(final_idxs[1:k + 1])

        for j in range(1, closest_k + 1):
            print(j)
            cosine_distance_list[count].append((final_dists[j] - final_dists[0])[0])

        count += 1

    return index_list, final_idx_distances, cosine_distance_list


def get_jaccard_sim(str1, str2):
    a = set(str1.split())
    b = set(str2.split())
    c = a.intersection(b)
    return float(len(c)) / (len(a.union(b)))


def create_lime_explanation_words():
    top_lime_words = list()
    for i in loaded_ids:
        print(i)
        print(X[i])
        # print(y_original[i])
        split_expression = lambda s: re.split(r'\W+', s)
        explanation = explainer.explain_instance(X[i], c.predict_proba, num_features=5)
        print('Probability(neutral) =', c.predict_proba([X[i]])[0, 1])
        weights = OrderedDict(explanation.as_list())
        print(list(weights.keys()))
        top_lime_words.append(list(weights.keys()))
        lime_w = pd.DataFrame({'words': list(weights.keys()), 'weights': list(weights.values())})
        print(lime_w)

    print(top_lime_words)

    with open('data/' + datasetName + '_' + modelName + '_' + 'lime_top_words', 'wb') as f:
        pickle.dump(top_lime_words, f)


datasetName = "hate"  # 'polarity' or 'hate'
modelName = "RF"  # 'RF' or 'DNN'
method = "xspells"  # 'lime' or 'xspells'
closest_k = 10  # How big the neighborhood should be in sentences

_, X, _, y, _ = get_text_data('../data/' + datasetName + '_tweets.csv', datasetName)

print(X)
print(y)

# Load data from pickled dumps
with open('../data/' + datasetName + '_' + modelName + '_' + 'ids', 'rb') as f:
    loaded_ids = pickle.load(f)

with open('../data/' + datasetName + '_' + modelName + '_' + 'top_exemplar_words', 'rb') as f:
    loaded_top_exemplar_words = pickle.load(f)

'''Find closest k sentences for final experiment'''
index, closest_indexes, cosine_distance_list = (find_closest_k_sentences(X, loaded_ids,
                                                                         k=closest_k, metric='euclidean'))

print(closest_k)

closest_indexes_dict = dict(zip(index, closest_indexes))
pickled_black_box_filename = '../models/' + datasetName + '_saved_' + modelName + '_model.sav'
pickled_vectorizer_filename = '../models/' + datasetName + '_tfidf_vectorizer.pickle'
loaded_model = pickle.load(open(pickled_black_box_filename, 'rb'))
loaded_vectorizer = pickle.load(open(pickled_vectorizer_filename, 'rb'))

if modelName is 'DNN':
    # Use following if DNN
    c = loaded_model
else:
    # Use following if RF
    c = make_pipeline(loaded_vectorizer, loaded_model)

explainer = LimeTextExplainer()
# create_lime_explanation_words()

if method is 'xspells':
    top_words_dict = dict(zip(loaded_ids, loaded_top_exemplar_words))
else:
    with open('../data/' + datasetName + '_' + modelName + '_' + 'lime_top_words', 'rb') as f:
        loaded_top_lime_words = pickle.load(f)
    top_words_dict = dict(zip(loaded_ids, loaded_top_lime_words))

jaccard_distance_list = [[] for _ in range(len(loaded_ids))]
counter = 0

for i in loaded_ids:
    tempList = list()
    instance = ' '.join(map(str, top_words_dict.get(i)))

    for j in range(closest_k):
        listToStr = ' '.join(map(str, top_words_dict.get(closest_indexes_dict[i][j])))
        tempList.append(listToStr)

    for j in range(closest_k):
        jaccard_distance_list[counter].append(1 - get_jaccard_sim(instance, tempList[j]))

    counter += 1

instability_list = list()
for i in range(len(jaccard_distance_list)):
    v1 = jaccard_distance_list[i][0] / cosine_distance_list[i][0]
    vk = jaccard_distance_list[i][closest_k - 1] / cosine_distance_list[i][closest_k - 1]
    # v1 = jaccard_distance_list[i][0]
    # vk = jaccard_distance_list[i][closest_k - 1]
    instability_list.append(v1 / vk)

print('Average instability: ', (sum(instability_list) / len(instability_list)))
print('Standard Deviation: ', stdev(instability_list))
