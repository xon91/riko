# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:expandtab
"""
riko.modules.pipestrtransform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides functions for performing string transformations on text, e.g.,
capitalize, uppercase, etc.

Examples:
    basic usage::

        >>> from riko.modules.pipestrtransform import pipe
        >>> conf = {'rule': {'transform': 'title'}}
        >>> pipe({'content': 'hello world'}, conf=conf).next()['strtransform']
        u'Hello World'

Attributes:
    OPTS (dict): The default pipe options
    DEFAULTS (dict): The default parser options
"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals)

from builtins import *
from twisted.internet.defer import inlineCallbacks, returnValue

from . import processor
from riko.lib.log import Logger
from riko.twisted import utils as tu

OPTS = {
    'listize': True, 'ftype': 'text', 'field': 'content', 'extract': 'rule'}

DEFAULTS = {}
logger = Logger(__name__).logger

ATTRS = {
    'capitalize', 'lower', 'upper', 'swapcase', 'title', 'strip', 'rstrip',
    'lstrip', 'zfill', 'replace', 'count', 'find'}


def reducer(word, rule):
    if rule.transform in ATTRS:
        args = rule.args.split(',') if rule.args else []
        result = getattr(unicode, rule.transform)(word, *args)
    else:
        logger.warning('Invalid transformation: %s', rule.transform)
        result = word

    return result


@inlineCallbacks
def asyncParser(word, rules, skip, **kwargs):
    """ Asynchronously parses the pipe content

    Args:
        word (str): The string to transform
        rules (List[obj]): the parsed rules (Objectify instances).
        skip (bool): Don't parse the content
        kwargs (dict): Keyword arguments

    Kwargs:
        assign (str): Attribute to assign parsed content (default: strtransform)
        feed (dict): The original item

    Returns:
        Deferred: twisted.internet.defer.Deferred Tuple of (item, skip)

    Examples:
        >>> from twisted.internet.task import react
        >>> from riko.lib.utils import Objectify
        >>>
        >>> def run(reactor):
        ...     callback = lambda x: print(x[0])
        ...     item = {'content': 'hello world'}
        ...     conf = {'rule': {'transform': 'title'}}
        ...     rule = Objectify(conf['rule'])
        ...     kwargs = {'feed': item, 'conf': conf}
        ...     d = asyncParser(item['content'], [rule], False, **kwargs)
        ...     return d.addCallbacks(callback, logger.error)
        >>>
        >>> try:
        ...     react(run, _reactor=tu.FakeReactor())
        ... except SystemExit:
        ...     pass
        ...
        Hello World
    """
    if skip:
        value = kwargs['feed']
    else:
        value = yield tu.coopReduce(reducer, rules, word)

    result = (value, skip)
    returnValue(result)


def parser(word, rules, skip, **kwargs):
    """ Parses the pipe content

    Args:
        word (str): The string to transform
        rules (List[obj]): the parsed rules (Objectify instances).
        skip (bool): Don't parse the content
        kwargs (dict): Keyword arguments

    Kwargs:
        assign (str): Attribute to assign parsed content (default: strtransform)
        feed (dict): The original item

    Returns:
        Tuple(dict, bool): Tuple of (item, skip)

    Examples:
        >>> from riko.lib.utils import Objectify
        >>>
        >>> item = {'content': 'hello world'}
        >>> conf = {'rule': {'transform': 'title'}}
        >>> rule = Objectify(conf['rule'])
        >>> kwargs = {'feed': item, 'conf': conf}
        >>> parser(item['content'], [rule], False, **kwargs)[0]
        u'Hello World'
    """
    value = kwargs['feed'] if skip else reduce(reducer, rules, word)
    return value, skip


@processor(DEFAULTS, async=True, **OPTS)
def asyncPipe(*args, **kwargs):
    """A processor module that asynchronously performs string transformations
    on the field of a feed item.

    Args:
        item (dict): The entry to process
        kwargs (dict): The keyword arguments passed to the wrapper

    Kwargs:
        conf (dict): The pipe configuration. Must contain the key 'rule'.

            rule (dict): can be either a dict or list of dicts. Must contain
                the key 'transform'. May contain the key 'args'

                transform (str): The string transformation to apply. Must be
                    one of: 'capitalize', 'lower', 'upper', 'swapcase',
                    'title', 'strip', 'rstrip', 'lstrip', 'zfill', 'replace',
                    'count', or 'find'

                args (str): A comma separated list of arguments to supply the
                    transformer.

        assign (str): Attribute to assign parsed content (default: strtransform)
        field (str): Item attribute from which to obtain the first number to
            operate on (default: 'content')

    Returns:
       Deferred: twisted.internet.defer.Deferred item with transformed content

    Examples:
        >>> from twisted.internet.task import react
        >>>
        >>> def run(reactor):
        ...     callback = lambda x: print(x.next()['strtransform'])
        ...     conf = {'rule': {'transform': 'title'}}
        ...     d = asyncPipe({'content': 'hello world'}, conf=conf)
        ...     return d.addCallbacks(callback, logger.error)
        >>>
        >>> try:
        ...     react(run, _reactor=tu.FakeReactor())
        ... except SystemExit:
        ...     pass
        ...
        Hello World
    """
    return asyncParser(*args, **kwargs)


@processor(**OPTS)
def pipe(*args, **kwargs):
    """A processor that performs string transformations on the field of a feed
    item.

    Args:
        item (dict): The entry to process
        kwargs (dict): The keyword arguments passed to the wrapper

    Kwargs:
        conf (dict): The pipe configuration. Must contain the key 'rule'.

            rule (dict): can be either a dict or list of dicts. Must contain
                the key 'transform'. May contain the key 'args'

                transform (str): The string transformation to apply. Must be
                    one of: 'capitalize', 'lower', 'upper', 'swapcase',
                    'title', 'strip', 'rstrip', 'lstrip', 'zfill', 'replace',
                    'count', or 'find'

                args (str): A comma separated list of arguments to supply the
                    transformer.

        assign (str): Attribute to assign parsed content (default: strtransform)
        field (str): Item attribute from which to obtain the first number to
            operate on (default: 'content')

    Yields:
        dict: an item with transformed content

    Examples:
        >>> conf = {'rule': {'transform': 'title'}}
        >>> pipe({'content': 'hello world'}, conf=conf).next()['strtransform']
        u'Hello World'
        >>> rules = [
        ...     {'transform': 'lower'}, {'transform': 'count', 'args': 'g'}]
        >>> conf = {'rule': rules}
        >>> kwargs = {'conf': conf, 'field': 'title', 'assign': 'result'}
        >>> pipe({'title': 'Greetings'}, **kwargs).next()['result']
        2
    """
    return parser(*args, **kwargs)
