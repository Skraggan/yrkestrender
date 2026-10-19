"""Text normalisation shared by extraction and vocabulary tools.

Ads are lowercased and split into word tokens. Hyphens and slashes split words
("B-körkort" -> "b körkort", "Python/Django" -> "python django"), so vocabulary
terms are written as space-separated tokens and matched as 1-3 word n-grams.
"""
import re

# Special forms that the tokenizer would otherwise destroy.
_SPECIAL = [
    (re.compile(r"(?<![\w])\.net(?![\w])", re.I), " dotnet "),
    (re.compile(r"(?<![\w])c\+\+", re.I), " cplusplus "),
    (re.compile(r"(?<![\w])c#", re.I), " csharp "),
    (re.compile(r"(?<![\w])f#", re.I), " fsharp "),
]
_TOKEN = re.compile(r"[0-9a-zà-öø-ÿ]+")


def normalise(text):
    for rx, repl in _SPECIAL:
        if rx.search(text):
            text = rx.sub(repl, text)
    return text.lower()


def tokens(text):
    return _TOKEN.findall(normalise(text))


def term_tokens(term):
    """Tokenise a vocabulary term the same way as ad text."""
    return tuple(tokens(term))
