#!/usr/bin/env python3
# coding: utf-8


import codecs
import collections
import itertools
import operator
import os
import re
import sys
import unicodedata

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.path as path

import numpy as np

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer


CORPUS = 'corpus'


def read_text(filename):
    """Read in the text from the file."""
    with codecs.open(filename, 'r', 'utf8') as f:
        return f.read()


def clean_text(input_text):
    """Clean the text by lowercasing and removing newlines."""
    return input_text.replace('\n', ' ').lower()


def clean_and_read_text(input_text):
    return clean_text(read_text(input_text))


def quotations_check(filename):
    text = clean_and_read_text(filename)
    """Checks if a file has an even number of quotes."""
    if len(list(re.finditer(r'"', text))) % 2 != 0:
        print("%(filename)s has an odd number of quotation marks." % locals())
        pause()
    elif percent_quoted(filename) > 30:
        print("%(filename)s has a high percentage of quoted text." % locals())
        pause()
    else:
        return


def print_matches_for_debug(filename):
    """Takes a file, finds its matches and prints them out to a new file
    'debug.txt' for debugging."""
    text = clean_and_read_text(filename)
    quotes = find_quoted_quotes(text)
    debug = open('debug.txt', 'w')
    counter = 0
    for match in quotes:
        debug.write("Match %(counter)i: " % locals() + match.group(0) + "\n")
        counter += 1
    debug.close


def find_quoted_quotes(input_text):
    """This returns the regex matches from finding the quoted quotes."""
    return list(re.finditer(r'"[^"]+"', input_text))


def create_location_histogram(file, bin_count=500):
    """\
    This takes the regex matches and produces a histogram of where they
    occurred in the document.
    """
    text = clean_and_read_text(file)
    matches = find_quoted_quotes(text)
    locations = [m.start() for m in matches]
    n, bins = np.histogram(locations, bin_count)

    fig, ax = plt.subplots()

    left = np.array(bins[:-1])
    right = np.array(bins[1:])
    bottom = np.zeros(len(left))
    top = bottom + n

    XY = np.array([[left, left, right, right], [bottom, top, top, bottom]]).T

    barpath = path.Path.make_compound_path_from_polys(XY)

    patch = patches.PathPatch(
        barpath, facecolor='blue', edgecolor='gray', alpha=0.8,
        )
    ax.add_patch(patch)

    ax.set_xlim(left[0], right[-1])
    ax.set_ylim(bottom.min(), top.max())

    plt.show()


def take_while(pred, input_str):
    """This returns the prefix of a string that matches pred,
    and the suffix where the match stops."""
    for (i, c) in enumerate(input_str):
        if not pred(c):
            return (input_str[:i], input_str[i:])
    else:
        return (input_str, "")


def is_punct(c):
    """Since `unicode` doesn't have a punctuation predicate..."""
    return unicodedata.category(c)[0] == 'P'


def get_unicode_category(unichars, prefix):
    """\
    This returns a generator over the unicode characters with a given major
    category.
    """
    return (c for c in unichars if unicodedata.category(c)[0] == prefix)


def make_token_re():
    unichars = [chr(c) for c in range(sys.maxunicode)]
    punct_chars = re.escape(''.join(get_unicode_category(unichars, 'P')))
    word_chars = re.escape(''.join(get_unicode_category(unichars, 'L')))
    number_chars = re.escape(''.join(get_unicode_category(unichars, 'N')))

    re_token = re.compile(r'''
            (?P<punct>  [{}]  ) |
            (?P<word>   [{}]+ ) |
            (?P<number> [{}]+ ) |
            (?P<trash>  .     )
        '''.format(punct_chars, word_chars, number_chars),
        re.VERBOSE,
        )
    return re_token


def tokenize(input_str, token_re=make_token_re()):
    """This returns an iterator over the tokens in the string."""
    return (
        m.group() for m in token_re.finditer(input_str) if not m.group('trash')
        )


def frequencies(corpus):
    """This takes a list of tokens and returns a `Counter`."""
    return collections.Counter(
        itertools.ifilter(lambda t: not (len(t) == 1 and is_punct(t)),
                          itertools.chain.from_iterable(corpus)))


def find_quotes(doc, start_quote='“', end_quote='”'):
    """\
    This takes a tokenized document (with punctuation maintained) and returns
    tuple pairs of the beginning and ending indexes of the quoted quotes.
    """
    start = 0
    while start <= len(doc):
        try:
            start_quote_pos = doc.index(start_quote, start)
            end_quote_pos = doc.index(end_quote, start_quote_pos + 1)
        except ValueError:
            return
        yield (start_quote_pos, end_quote_pos + 1)
        start = end_quote_pos + 1


def tokenize_file(filename):
    text = clean_and_read_text(filename)
    return list(tokenize(text))


def pause():
    """\
    Pauses between each text when processing groups of texts together for
    debugging, mostly, but also to analyze the sometimes really long output.
    """
    input("Paused. Type any key to continue.")


def calc_number_of_quotes(file):
    # Working here next time. you need to figure out a way to convert the
    # matches into a big string for processing.
    text = clean_and_read_text(file)
    matches = find_quoted_quotes(text)
    text_string = ""
    for match in matches:
        text_string = text_string + match.group(0)
    count = len(text_string)
    return count


def calc_number_of_characters(file):
    text = clean_and_read_text(file)
    text = text.replace('\\', '')
    count = len(text)
    return count


def list_number_of_quotes(file, count):
    print("Number of quoted sentences in {}: {}".format(file, count))


def percent_quoted(file):
    number_of_quotes = calc_number_of_quotes(file)
    number_of_chars = calc_number_of_characters(file)
    percent = 100 * (number_of_quotes / number_of_chars)
    number_of_characters = calc_number_of_characters(file)
    percent = 100 * (number_of_quotes / number_of_characters)
    print("The percentage of {} that occurs in quoted text is {}"
          .format(file, percent))


def list_percentage(file):
    percent = percent_quoted(file)
    print("The percentage of {} that occurs in quoted text is {}".format(
        file, percent))


def all_files(dirname):
    for (root, _, files) in os.walk(dirname):
        for fn in files:
            yield os.path.join(root, fn)


def top_items(vectorizer, array, n=10):
    inv_vocab = dict((v, k) for (k, v) in vectorizer.vocabulary_.items())
    for row in array:
        indexes = list(enumerate(row))
        indexes.sort(key=operator.itemgetter(1), reverse=True)
        top = [(i, inv_vocab[i], c) for (i, c) in indexes[:n]]
        yield top


def vectorizer_report(title, klass, filenames, **kwargs):
    if 'titles' in kwargs:
        titles = kwargs.pop('titles')
    else:
        titles = filenames

    params = {
        'input': 'filename',
        'tokenizer': tokenize,
        'stop_words': 'english',
        }
    params.update(kwargs)
    v = klass(**params)
    corpus = v.fit_transform(filenames)
    a = corpus.toarray()

    print('# {}\n'.format(title))
    for (fn, top) in zip(titles, top_items(v, a)):
        print('## {}\n'.format(fn))
        for (i, row) in enumerate(top):
            print('{0:>3}. {1[0]:>6}. {1[1]:<12}\t{1[2]:>5}'.format(i, row))
        print()

def concatenate_quotes(filename):
    text = clean_and_read_text(filename)
    quotes = find_quoted_quotes(text)
    counter = 0
    concatenated_quotes = ""
    for match in quotes:
        concatenated_quotes += quotes[counter].group(0)
        counter += 1
    return concatenated_quotes


def get_corpus_quotes(filenames):
    all_quotes = []

    for filename in filenames:
        with open(filename) as f:
            quotes = '\n'.join(
                m.group() for m in find_quoted_quotes(f.read())
                )
            all_quotes.append(quotes)

    return all_quotes


def main():
    files = list(all_files(CORPUS))
    quoted = get_corpus_quotes(files)
    remove_short = lambda s: filter(lambda x: len(x) > 1, tokenize(s))

    vectorizer_report(
        'Raw Frequencies', CountVectorizer, quoted, tokenizer=remove_short,
        input='content', titles=files,
        )
    vectorizer_report('Tf-Idf', TfidfVectorizer, quoted,
                      tokenizer=remove_short, input='content', titles=files)


if __name__ == '__main__':
    main()

# To do:
# percent_quoted seems to be working now, though 69% quoted for Night and Day
# seems crazy high.

# You'll eventually want to calculate non-speech vs speech
# percentages as well.

# also note that you get one funky match at the end - match='"i shall go and
# talk to him.  i shall say goodnig>, and you're losing the next quote.

# Refactoring ideas: make it so that the os.path, etc. thing is simplified.
# Also make sure, once all the functions are written, that you don't have
# redundant cleaning of texts and looping through the corpus.

# It's currently preserving \s for every quote. Do we want to keep that?
# Presumably? It's going to throw off the percentages though.
