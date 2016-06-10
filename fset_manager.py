"""
The class here will act as a base/interface for what takes a window
into the document and creates feature sets for training/classifying.

"""


from collections import deque, namedtuple
import os
import re

import nltk
from nltk.corpus import brown, names

import ps


TAGGED = 'training_passages/tagged_text/'

FeatureContext = namedtuple('FeatureContext',
                            ['history', 'current', 'lookahead'])
TaggedToken = namedtuple('TaggedToken', ['token', 'tag', 'start', 'end'])


def tagged_token(token_span):
    """This takes an input of ((TOKEN, TAG), (START, END)) and returns
    a TaggedToken."""
    ((token, tag), (start, end)) = token_span
    return TaggedToken(token, tag, start, end)


def split_sentences(text, tokenizer=None, offset=0):
    """\
    Splits text into lists of lists. Each list contains a sentence, which is a
    list of normalized tokens, including the token's indexes in the original
    text.

    """

    if tokenizer is None:
        tokenizer = nltk.load('tokenizers/punkt/{0}.pickle'.format('english'))
    for start, end in tokenizer.span_tokenize(text):
        sent = text[start:end]
        sent_tokens = []
        matches = re.finditer(
            r'\w+|[\'\"\/^/\,\-\:\.\;\?\!\(0-9]', sent
        )
        for match in matches:
            mstart, mend = match.span()
            seg_start = start + offset
            sent_tokens.append(
                (match.group(0).lower().replace('_', ''),
                 (mstart+seg_start, mend+seg_start))
            )
        yield sent_tokens


def tag_token_spans(sentences, tagger):
    """\
    This uses tagger to split apart tokens (token, span) and returns ((token,
    tag), span). Each sentence is a list of these tokens.
    """
    tagged_sents = []
    for sent in sentences:
        to_tag = [token for (token, _) in sent]
        spans = [span for (_, span) in sent]
        tagged = tagger.tag(to_tag)
        tagged_sents.append(list(zip(tagged, spans)))
    return tagged_sents


def build_trainer(tagged_sents, default_tag='DEFAULT'):
    """Return a trained POS tagger."""
    name_tagger = [
        nltk.DefaultTagger('PN').tag([
            name.lower() for name in names.words()
        ])
    ]
    punctuation_tags = [[('^', '^'), ('"', '"')]]
    patterns = [
        (r'.*ing$', 'VBG'),               # gerunds
        (r'.*ed$', 'VBD'),                # simple past
        (r'.*es$', 'VBZ'),                # 3rd singular present
        (r'.*ould$', 'MD'),               # modals
        (r'.*\'s$', 'NN$'),               # possessive nouns
        (r'.*s$', 'NNS'),                 # plural nouns
        (r'^-?[0-9]+(.[0-9]+)?$', 'CD'),  # cardinal numbers
        (r'.*ly$', 'RB'),                       # adverbs
        # comment out the following line to raise to the surface all
        # the words being tagged by this last, default tag when you
        # run debug.py.
        (r'.*', 'NN')                     # nouns (default)
    ]

    # Right now, nothing will get to the default tagger, because the
    # regex taggers last pattern essentially acts as a default tagger,
    # tagging everything as NN.
    tagger0 = nltk.DefaultTagger(default_tag)
    regexp_tagger = nltk.RegexpTagger(patterns, backoff=tagger0)
    punctuation_tagger = nltk.UnigramTagger(
        punctuation_tags, backoff=regexp_tagger
    )
    tagger1 = nltk.UnigramTagger(tagged_sents, backoff=punctuation_tagger)
    tagger2 = nltk.BigramTagger(tagged_sents, backoff=tagger1)
    tagger3 = nltk.UnigramTagger(name_tagger, backoff=tagger2)

    return tagger3


# TODO: Change so `text` is POS-tagged.
def tag_quotes(text, is_quote):
    """\
    Takes a list of sentence tokens (lists of pairs of tokens and span indexes)
    and returns each sentence in a tuple pair with whether it is currently in a
    quote or not.

    """

    return [(s, False) for s in text]


class AQuoteProcess:

    def make_context(self, window):
        """This makes a FeatureContext from a window of tokens (which
        will become TaggedTokens.)"""
        raise NotImplementedError()

    def get_features(self, context):
        """This returns the feature set for the data in the current window."""
        raise NotImplementedError()

    def get_tag(self, features, context):
        """This returns the tag for the feature set to train against."""
        raise NotImplementedError()

    def get_training_features(self, tagged_tokens, feature_history=0):
        """This returns a sequence of feature sets and tags to train against for
        the input tokens."""
        raise NotImplementedError()

    # [[((TOKEN, TAG), (START, END))]] -> [???]
    def get_all_training_features(self, tagged_tokens):
        """This takes tokenized, segmented, and tagged files and gets
        training features."""
        raise NotImplementedError()

    def build_trainer(self, tagged_sents, default_tag='DEFAULT'):
        """This builds a tagger from a corpus."""
        return build_trainer(tagged_sents, default_tag)

    def windows(self, seq, window_size):
        """This iterates over window_size chunks of seq."""
        window = deque()
        for item in seq:
            window.append(item)
            if len(window) > window_size:
                window.popleft()
            yield list(window)

    # FileName -> [[((TOKEN, TAG), (START, END))]]
    def get_tagged_tokens(self, corpus=TAGGED, testing=False):
        """This tokenizes, segments, and tags all the files in a directory."""
        if testing:
            # train against a smaller version of the corpus so that it
            # doesn't take years during testing.
            tagger = build_trainer(brown.tagged_sents(categories='news'))
        else:
            tagger = build_trainer(brown.tagged_sents())
        tokens_and_spans = self.tokenize_corpus(corpus)
        tagged_spanned_tokens = tag_token_spans(
            tokens_and_spans,
            tagger,
        )
        return tagged_spanned_tokens

    # Override:
    # This needs to call ps.find_quoted_quotes to divide up each file by
    # quotes, then it can use `span_tokenizer` to identify the sentences.
    def tokenize_corpus(self, corpus):
        """Read the corpus a list sentences, each of which is a list of
        tokens and the spans in which they occur in the text."""
        if os.path.isdir(corpus):
            corpus_dir = corpus
            corpus = [
                os.path.join(corpus_dir, fn) for fn in os.listdir(corpus_dir)
            ]
        else:
            corpus = [corpus]

        tokenizer = nltk.load('tokenizers/punkt/{0}.pickle'.format('english'))

        for filename in corpus:
            with open(filename) as fin:
                data = fin.read()

            for start, end in tokenizer.span_tokenize(data):
                sent = data[start:end]
                sent_tokens = []
                matches = re.finditer(
                    r'\w+|[\'\"\/^/\,\-\:\.\;\?\!\(0-9]', sent
                )
                for match in matches:
                    mstart, mend = match.span()
                    sent_tokens.append(
                        (match.group(0).lower().replace('_', ''),
                         (mstart+start, mend+start))
                    )
                yield sent_tokens


class QuotePoint(AQuoteProcess):
    """\
    This looks at the document as a quote-point following a token. The
    classifier is trained on the tag and token for the quote point and
    history_size preceding tokens.

    """

    def __init__(self, is_context, is_target, history_size=2):
        self.is_context = is_context
        self.is_target = is_target
        self.history_size = history_size

    def make_context(self, window):
        return FeatureContext(
            [tagged_token(t) for t in window[:-self.history_size]],
            tagged_token(window[-2]),
            tagged_token(window[-1]),
        )

    def get_features(self, context):
        featureset = {
            'token0': context.current[0],
            'tag0': context.current[1],
        }
        history = reversed(list(context.history))
        for (offset, (token, tag, _start, _end)) in enumerate(history):
            featureset['token{}'.format(offset+1)] = token
            featureset['tag{}'.format(offset+1)] = tag

        return featureset

    def get_tag(self, _features, context):
        return self.is_context(context)

    # [((TOKEN, TAG), (START, END))]
    # -> [(FEATURES :: dict, SPAN :: (Int, Int), TAG :: Bool)]
    def get_training_features(self, tagged_tokens):
        window_size = self.history_size + 2
        for window in self.windows(tagged_tokens, window_size):
            # window :: [((TOKEN, TAG), (START, END))]
            if len(window) < 2:
                continue
            # make sure that make_context and get_features can work
            # context :: FeatureContext
            context = self.make_context(window)
            if self.is_target(context):
                # features :: dict
                features = self.get_features(context)
                # span :: (Int, Int)
                span = (context.current.start, context.current.end)
                # tag :: Bool
                tag = self.get_tag(features, context)
                yield (features, span, tag)

    # [[((TOKEN, TAG), (START, END))]] -> [???]
    def get_all_training_features(self, tagged_tokens):
        """This takes tokenized, segmented, and tagged files and gets
        training features."""
        training_features = []
        for sent in tagged_tokens:
            training_features += self.get_training_features(
                sent
            )
        return training_features


class InternalStyle(AQuoteProcess):
    """ Assumes that we understand speech, at least in part, as a
    characteristic of the whole internal content of quotation marks. Rather
    than speech being signaled by a quotation mark and a quality of its
    immediately following words, it's a quality shared by all those words and
    marked by style in some way.

    The other processes defined in this file create `FeatureContext` objects.
    This one won't.

    Training tags are:

        * 1 = quoted
        * 0 = not-quoted

    """

    def __init__(self, is_quote, is_word):
        self.is_quote = is_quote
        self.is_word = is_word

    # So I want the feature histories to be longer…but how much longer? Start
    # with 10. Eric do I need to relist the .is_target and whatnot here if they
    # haven't changed? I think that I do because it will only call down or
    # overwrite methods in full. Is that right?

    # def make_context(self, window):
    #     return FeatureContext(
    #         [tagged_token(t) for t in window[:-self.history_size]],
    #         tagged_token(window[-2]),
    #         tagged_token(window[-1]),
    #     )

    def get_training_features(self, tagged_tokens, feature_history=0):
        feature_set = {}
        spans = []
        # tag = any(
        #     self.is_quote(token_tag) for (token_tag, _) in tagged_tokens
        # )
        tag = False

        for (token_tag, span) in tagged_tokens:
            tag |= self.is_quote(token_tag)
            if self.is_quote(token_tag):
                continue

            feature_set['{}/{}'.format(*token_tag)] = True
            spans.append(span)

            # TODO: This isn't right. It needs to also consider whether the
            # previous sentences were quotes or not. If the previous one is a
            # quotation, then this one should default to being a quotation
            # also. Or if the previous sentence is a quotation and this one
            # returns true for `is_quote`, then we need to mark the next one as
            # not a quote.

        return (feature_set, spans, tag)

    # * Windows were based on a sliding window of N tokens.
    # * Windows now are sentences.
    # * Each window has one tag.
    # * Each window creates one feature set, which will be the vector of
    #   word/pos-tag in the sentence.

    # [[((TOKEN, TAG), (START, END))]]
    # -> [ (FEATURES :: (TOKEN/POS_TAG) -> Int
    #    , SPAN :: (Int, Int)
    #    , TAG :: Bool)
    #    ]
    def get_all_training_features(self, tagged_tokens):
        """This takes tokenized, segmented, and tagged files and gets
        training features."""
        features = []

        for sent in tagged_tokens:
            features.append(self.get_training_features(sent))

        return features

    def tokenize_corpus(self, corpus):
        """Read the corpus a list sentences, each of which is a list of
        tokens and the spans in which they occur in the text."""
        if os.path.isdir(corpus):
            corpus_dir = corpus
            corpus = [
                os.path.join(corpus_dir, fn) for fn in os.listdir(corpus_dir)
            ]
        else:
            corpus = [corpus]

        tokenizer = nltk.load('tokenizers/punkt/{0}.pickle'.format('english'))

        for filename in corpus:
            with open(filename) as fin:
                print(filename)
                data = fin.read()

            segment_start = 0

            for span in ps.split_quoted_quotes(data):
                for sent_tokens in split_sentences(span, tokenizer,
                                                   segment_start):
                    yield sent_tokens
                segment_start += len(span)


Current = InternalStyle


if __name__ == '__main__':
    import doctest
    doctest.testfile('fset_manager.md')
