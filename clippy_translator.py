#!/usr/bin/python

import os
import re
import sys
import random

LANGUAGES = ('english', 'binary', 'klingon', 'parseltongue', 'hodor')
KLINGON_PHRASES = ["yI'el", "pe'el", "nuqneH", "bIpIv'a'", "jIpIv", "bIpIv'a'",
                    "qaleghqa'mo'", "jIQuch", "qaleghqa'neS", "nuq 'oH ponglIj'e'",
                    "jIH 'oH pongwIj'e'", "munglIj nuq", "mungwIj", "qaqIHneS", "qaqIHmo' jIQuch",
                    "maj ram", "yInajchu'", "Qapla'", "'IwlIj jachjaj", "yISop", "peSop", "jIyaj",
                    "jIyajbe'", "jISovbe'", "QIt yIjatlh", "'e' yIjatlhqa'", "'e' yIghItlh",
                    "tlhIngan Hol Dajatlh'a'", "HIja'", "loQ vIjatlhlaH",
                    "tlhIngan Hol vIjatlhtaHvIS,  chay'", "vIjatlh", "Huch 'ar DaneH", "qatlho'",
                    "nuqDaq 'oH puchpa''e'", "Hoch DIl [loD/be']vam", "mamI' DaneH'a'",
                    "nItebHa' mamI' DaneH'a'", "qamuSHa'",
                    "tugh bIpIvchoHjaj", "naDevvo' yIghoS", "naDevvo' peghoS", "HIQaH QaH",
                    "qul", "mev", "'avwI' tIghuHmoH"]

KLINGON_BY_LENGTH = dict()
for phrase in KLINGON_PHRASES:
    KLINGON_BY_LENGTH.setdefault(len(phrase), list()).append(phrase)
CHOICE_BY_LENGTH = dict.fromkeys(KLINGON_BY_LENGTH.keys(), 0)

def _replace_binary(match):
    if random.randint(0, 100) == 0:
        # and I think I saw a two!
        return '2'
    return '1' if random.randint(0, 1) else '0'

def _replace_klingon(match):
    word = match.group(0)
    word_length = len(word)
    if word_length < 3:
        word_length = 3
    if word_length == 4:
        word_length = 5
    while word_length > 0 and word_length not in CHOICE_BY_LENGTH:
        word_length -= 1
    if word_length not in KLINGON_BY_LENGTH:
        return "Qapla'"
    words = KLINGON_BY_LENGTH.get(word_length)
    choice = CHOICE_BY_LENGTH[word_length]
    word = words[choice]
    CHOICE_BY_LENGTH[word_length] = (choice + 1) % len(words)
    return word

def _replace_parseltongue(match):
    word = match.group(0)
    word_len = len(word)
    if random.randint(0, 2) == 0:
        new_word = 'hiss'
        if word_len > 4:
            new_word += 's' * (word_len - 4)
    else:
        new_word = 's' * word_len
    if word[0].isupper():
        new_word = new_word.capitalize()
    return new_word

def _replace_hodor(match):
    word = match.group(0)
    word_len = len(word)
    new_word = 'hodor'
    if word_len > 6:
        ohs = 'o' * (word_len - 5)
        new_word = 'hod' + ohs + 'r'
    if word[0].isupper():
        new_word = new_word.capitalize()
    return new_word

def translate_binary(msg):
    return re.sub('[a-zA-Z0-9]', _replace_binary, msg)

def translate_klingon(msg):
    return re.sub('[a-zA-Z0-9]+', _replace_klingon, msg)

def translate_parseltongue(msg):
    return re.sub('[a-zA-Z0-9]+', _replace_parseltongue, msg)

def translate_hodor(msg):
    return re.sub('[a-zA-Z0-9]+', _replace_hodor, msg)

def translate(language, msg):
    if language == 0:
        return msg
    if language == 1:
        return translate_binary(msg)
    if language == 2:
        return translate_klingon(msg)
    if language == 3:
        return translate_parseltongue(msg)
    if language == 4:
        return translate_hodor(msg)
    raise ValueError('Invalid language: ' + str(language))

def main():
    print translate(LANGUAGES.index(sys.argv[1].lower()), sys.argv[2])

if __name__ == '__main__':
    main()
