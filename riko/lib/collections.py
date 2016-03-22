# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:expandtab
"""
riko.lib.collections
~~~~~~~~~~~~~~~~~~~~
Provides methods for creating riko pipes

Examples:
    basic usage::

        >>> from riko.lib.collections import SyncPipe
        >>> from riko import get_url
        >>>
        >>> url = {'value': get_url('gigs.json')}
        >>> fconf = {'url': url, 'path': 'value.items'}
        >>> str_conf = {'delimiter': '<br>'}
        >>> str_kwargs = {'field': 'description', 'emit': True}
        >>> sort_conf = {'rule': {'sort_key': 'title'}}
        >>>
        >>> (SyncPipe('fetchdata', conf=fconf)
        ...     .sort(conf=sort_conf)
        ...     .stringtokenizer(conf=str_conf, **str_kwargs)
        ...     .count().list)
        [{u'count': 169}]
        >>> (SyncPipe('fetchdata', conf=fconf, parallel=True)
        ...     .sort(conf=sort_conf)
        ...     .stringtokenizer(conf=str_conf, **str_kwargs)
        ...     .count().list)
        [{u'count': 169}]
        >>> (SyncPipe('fetchdata', conf=fconf, parallel=True, threads=False)
        ...     .sort(conf=sort_conf)
        ...     .stringtokenizer(conf=str_conf, **str_kwargs)
        ...     .count().list)
        [{u'count': 169}]
        >>> fconf['type'] = 'fetchdata'
        >>> sources = [{'url': {'value': get_url('feed.xml')}}, fconf]
        >>> len(SyncCollection(sources).list)
        56
        >>> len(SyncCollection(sources, parallel=True).list)
        56
"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals)

from functools import partial
from itertools import imap, izip, repeat
from importlib import import_module
from multiprocessing.dummy import Pool as ThreadPool
from multiprocessing import Pool, cpu_count

from builtins import *

from riko.lib.utils import multiplex, multi_try
from riko.lib.log import Logger

logger = Logger(__name__).logger


class PyPipe(object):
    """A riko module fetching object"""
    def __init__(self, name, parallel=False, **kwargs):
        self.name = name
        self.parallel = parallel
        self.kwargs = kwargs


class SyncPipe(PyPipe):
    """A synchronous Pipe object"""
    def __init__(self, name, source=None, workers=None, **kwargs):
        super(SyncPipe, self).__init__(name, **kwargs)
        chunksize = kwargs.get('chunksize')

        if kwargs.pop('listize', False) and source:
            self.source = list(source)
        else:
            self.source = source

        self.threads = kwargs.get('threads', True)
        self.reuse_pool = kwargs.get('reuse_pool', True)
        self.pool = kwargs.get('pool')
        self.module = import_module('riko.modules.pipe%s' % self.name)
        self.pipe = self.module.pipe
        self.processor = self.pipe.func_dict.get('sub_type') == 'processor'

        if self.parallel and self.processor:
            ordered = kwargs.get('ordered')
            length = lenish(self.source)
            def_pool = ThreadPool if self.threads else Pool

            self.workers = workers or get_worker_cnt(length, self.threads)
            self.chunksize = chunksize or get_chunksize(length, self.workers)
            self.pool = self.pool or def_pool(self.workers)
            self.map = self.pool.imap if ordered else self.pool.imap_unordered
        else:
            self.workers = workers
            self.chunksize = chunksize
            self.map = imap

    def __getattr__(self, name):
        kwargs = {
            'parallel': self.parallel,
            'threads': self.threads,
            'pool': self.pool if self.reuse_pool else None,
            'reuse_pool': self.reuse_pool,
            'workers': self.workers}

        return SyncPipe(name, source=self.output, **kwargs)

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self

    @property
    def output(self):
        pipeline = partial(self.pipe, **self.kwargs)

        if self.parallel and self.processor:
            zipped = izip(self.source, repeat(pipeline))
            mapped = self.map(listpipe, zipped, chunksize=self.chunksize)
        elif self.processor:
            mapped = self.map(pipeline, self.source)

        if self.parallel and self.processor and not self.reuse_pool:
            self.pool.close()
            self.pool.join()

        return multiplex(mapped) if self.processor else pipeline(self.source)

    @property
    def list(self):
        return list(self.output)


class PyCollection(object):
    """A riko bulk url fetching object"""
    def __init__(self, sources, parallel=False, workers=None, **kwargs):
        self.sources = sources
        self.parallel = parallel
        self.workers = workers
        self.sleep = kwargs.get('sleep', 0)
        self.zargs = izip(self.sources, repeat(self.sleep))
        self.length = lenish(self.sources)
        self.workers = workers or get_worker_cnt(self.length)


class SyncCollection(PyCollection):
    """A synchronous PyCollection object"""
    def __init__(self, *args, **kwargs):
        super(SyncCollection, self).__init__(*args, **kwargs)

        if self.parallel:
            self.chunksize = get_chunksize(self.length, self.workers)
            self.pool = ThreadPool(self.workers)
            self.map = self.pool.imap_unordered
        else:
            self.map = imap

    def fetch(self):
        """Fetch all source urls"""
        kwargs = {'chunksize': self.chunksize} if self.parallel else {}
        mapped = self.map(getpipe, self.zargs, **kwargs)
        return multiplex(mapped)

    @property
    def list(self):
        return list(self.fetch())


def get_chunksize(length, workers):
    return (length // (workers * 4)) or 1


def get_worker_cnt(length, threads=True):
    multiplier = 2 if threads else 1
    return min(length or 1, cpu_count() * multiplier)


def lenish(source, default=50):
    funcs = (len, lambda x: getattr(x, '__length_hint__')())
    errors = (TypeError, AttributeError)
    zipped = zip(funcs, errors)
    return multi_try(source, zipped, default)


def listpipe(args):
    source, pipeline = args
    return list(pipeline(source))


def getpipe(args, pipe=SyncPipe):
    source, sleep = args
    ptype = source.get('type', 'fetch')
    conf = {'sleep': sleep}
    conf.update(source)
    return pipe(ptype, conf=source).list
