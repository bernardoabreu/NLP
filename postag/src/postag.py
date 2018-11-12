#!/usr/bin/env python3
# coding: utf-8

# # Trabalho Prático 2
# ## Processamento de Linguagem Natural - 2018/2
# ### Bernardo de Almeida Abreu - 2018718155

# In[57]:


import numpy as np
import pandas as pd
# import re
import gensim
# import nltk
import keras
# import matplotlib.pyplot as plt
from keras.models import model_from_json

# In[2]:


paths = {
    'train': '../macmorpho-v3/macmorpho-train.txt',
    'test': '../macmorpho-v3/macmorpho-test.txt',
    'dev': '../macmorpho-v3/macmorpho-dev.txt',
    'word2vec': '../data/skip_s100.txt'
}


# ## Embedding - Word2Vec
w2v_model = gensim.models.KeyedVectors.load_word2vec_format(paths['word2vec'])

# ### Adiciona vetores extras
w2v_model.add(['<PAD>','<OOV>'], [[0.1]*100,[0.2]*100])


# ## Leitura do texto
def read_text(filename):
    with open(filename, 'r') as f:
        return f.readlines()


train_text = read_text(paths['train'])
test_text = read_text(paths['test'])
dev_text = read_text(paths['dev'])


# ### Separação de palavras e tags
def split_word_tags(text):
    word_lines = []
    tag_lines = []
    for line in text:
        words, tags = zip(*[tagged_word.split('_')
                            for tagged_word in line.split()])
        word_lines.append([w.lower() for w in words])
        tag_lines.append(list(tags))
    return word_lines, tag_lines


train_words, train_tags = split_word_tags(train_text)
print(train_words[0])
print(train_tags[0])

test_words, test_tags = split_word_tags(test_text)
dev_words, dev_tags = split_word_tags(dev_text)


def flat_list(l):
    return [item for sublist in l for item in sublist]

id2tag = ['<PAD>'] + list(set(flat_list(train_tags)).union(set(flat_list(test_tags))).union(set(flat_list(dev_tags))))
tag2id = {}
for i, tag in enumerate(id2tag):
    tag2id[tag] = i

# ## Pad the words

# ### Analyse sentence size distribution
df_train = pd.DataFrame(columns=['words', 'tags'])
df_test = pd.DataFrame(columns=['words', 'tags'])
df_dev = pd.DataFrame(columns=['words', 'tags'])

df_train['words'] = train_words
df_train['tags'] = train_tags

df_test['words'] = test_words
df_test['tags'] = test_tags

df_dev['words'] = dev_words
df_dev['tags'] = dev_tags


df_sentences = pd.concat([df_train, df_test, df_dev], axis=0)

MAX_SENTENCE_LENGTH = int(df_sentences['words'].map(len).describe()['75%'])


def fill_sentence(sentence):
    tokens_to_fill = int(MAX_SENTENCE_LENGTH - len(sentence))
    sentence.extend(['<PAD>'] * tokens_to_fill)
    return sentence[:MAX_SENTENCE_LENGTH]


df_train["words"] = df_train["words"].map(fill_sentence)
df_train["tags"] = df_train["tags"].map(fill_sentence)

df_test["words"] = df_test["words"].map(fill_sentence)
df_test["tags"] = df_test["tags"].map(fill_sentence)

df_dev["words"] = df_dev["words"].map(fill_sentence)
df_dev["tags"] = df_dev["tags"].map(fill_sentence)


print(len(w2v_model.vocab))
print(MAX_SENTENCE_LENGTH)
print(len(df_train))
w2v_model.vocab['<OOV>'].index
print(len(df_train['words']))


pretrained_weights = w2v_model.vectors
vocab_size, emdedding_size = pretrained_weights.shape
print('Result embedding shape:', pretrained_weights.shape)


def word2idx(word):
    return w2v_model.vocab[word].index


def idx2word(idx):
    return w2v_model.index2word[idx]


def prepare_words(sentences):
    sentences_x = np.zeros([len(sentences), MAX_SENTENCE_LENGTH],
                           dtype=np.int32)

    oov_index = word2idx('<OOV>')
    for i, sentence in enumerate(sentences):
        for t, word in enumerate(sentence):
            try:
                sentences_x[i, t] = word2idx(word)
            except KeyError:
                sentences_x[i, t] = oov_index
    return sentences_x


def prepare_tags(tag_sentences, tag2index):
    tags_y = np.zeros([len(tag_sentences), MAX_SENTENCE_LENGTH],
                      dtype=np.int32)
    for i, sentence in enumerate(tag_sentences):
        for t, tag in enumerate(sentence):
            tags_y[i, t] = tag2index[tag]
    return tags_y


print('\nPreparing the train data for LSTM...')
train_sentences_X = prepare_words(df_train['words'])
print('train_x shape:', train_sentences_X.shape)

print('\nPreparing the test data for LSTM...')
test_sentences_X = prepare_words(df_test['words'])
print('train_x shape:', test_sentences_X.shape)

print('\nPreparing the validation data for LSTM...')
dev_sentences_X = prepare_words(df_dev['words'])
print('train_x shape:', dev_sentences_X.shape)


print('\nPreparing the train tags for LSTM...')
train_tags_y = prepare_tags(df_train['tags'], tag2id)
print('train_y shape:', train_tags_y.shape)

print('\nPreparing the test data for LSTM...')
test_tags_y = prepare_tags(df_test['tags'], tag2id)
print('train_y shape:', test_tags_y.shape)

print('\nPreparing the validation data for LSTM...')
dev_tags_y = prepare_tags(df_dev['tags'], tag2id)
print('train_y shape:', dev_tags_y.shape)

print()

cat_train_tags_y = keras.utils.to_categorical(train_tags_y,
                                              num_classes=len(id2tag),
                                              dtype='int32')
cat_test_tags_y = keras.utils.to_categorical(test_tags_y,
                                             num_classes=len(id2tag),
                                             dtype='int32')
cat_dev_tags_y = keras.utils.to_categorical(dev_tags_y,
                                            num_classes=len(id2tag),
                                            dtype='int32')


# ## Arquitetura do modelo

model = keras.models.Sequential()

# ### Adiciona camada de embedding
model.add(
    keras.layers.Embedding(
        input_dim=len(w2v_model.vocab),
        output_dim=emdedding_size,
        input_length=MAX_SENTENCE_LENGTH,
        weights=[pretrained_weights]
    )
)


model.add(
    keras.layers.Bidirectional(keras.layers.LSTM(256, return_sequences=True)))
model.add(keras.layers.Dropout(0.2))
model.add(keras.layers.TimeDistributed(keras.layers.Dense(len(tag2id))))
model.add(keras.layers.Dropout(0.2))
model.add(keras.layers.Activation('softmax'))

model.compile(loss='categorical_crossentropy',
              optimizer=keras.optimizers.Adam(0.001),
              metrics=['accuracy'])

model.summary()


csv_logger = keras.callbacks.CSVLogger('training.log')
model.fit(train_sentences_X, cat_train_tags_y, batch_size=64, epochs=10,
          # validation_split=0.2,
          validation_data=(dev_sentences_X, cat_dev_tags_y),
          callbacks=[csv_logger])

print('Evaluate model:')
scores = model.evaluate(test_sentences_X, cat_test_tags_y)
print("%s: %.2f%%" % (model.metrics_names[1], scores[1] * 100))

# ## Save model

# ### serialize model to JSON
model_json = model.to_json()
with open("model.json", "w") as json_file:
    json_file.write(model_json)

# ### serialize weights to HDF5
model.save_weights("model.h5")
print("Saved model to disk")