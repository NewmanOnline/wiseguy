# -*- coding: utf-8 -*-

import collections, copy, functools, contextlib

import lxml.html


class Transform(object):
    def __init__(self, keys, action):
        if isinstance(keys, basestring):
            self.keys = set([keys])
        else:
            self.keys = set(keys)
        self.action = action
        self.applied = False
        self.context = dict()

    def __repr__(self):
        return "<Transform %s>" % self.keys

    def apply(self, context):
        for key in list(self.keys):
            if key in context:
                self.context[key] = context[key]
                self.keys.remove(key)
        if not self.keys:
            self.applied = True


class TemplateMeta(type):
    applied_transforms = []

    def keys(self):
        keys = set()
        for transform in self.transforms:
            keys = keys | transform.keys
        return keys

    def apply(self, context):
        for transform in list(self.transforms):
            transform.apply(context)
            if transform.applied:
                transform.action(template=self, **transform.context)
                self.transforms.remove(transform)
                self.applied_transforms.append(transform)

    def copy(self):
        return TemplateMeta(
            'Template',
            (Template,),
            dict(
                element=copy.deepcopy(self.element),
                transforms=copy.deepcopy(self.transforms)))

    def extend(self, template):
        self.transforms.extend(template.transforms)
        self.apply(template(dict()))

    def add_widget(self, path, template):
        self.element.add(path, template.element)
        self.transforms.extend(template.transforms)

    def render_lxml(self, kwargs):
        template = self.copy()
        template.apply(kwargs)
        return template.element

    def render(self, **kwargs):
        html = self.render_lxml(kwargs)
        return lxml.html.tostring(html, pretty_print=True)

    def __call__(self, kwargs):
        return self.render_lxml(kwargs)


class Template(object):
    __metaclass__ = TemplateMeta


class SubTemplateMeta(TemplateMeta):
    def __init__(self, cls_name, bases, cls_dict):
        self.keys = [k for k in cls_dict if not k.startswith("_")]
        self.transforms = []
        for value in cls_dict.itervalues():
            if hasattr(value, 'transforms'):
                self.transforms.extend(value.transforms)

    def __call__(self, context):
        return dict(
            (k, getattr(self, k)(context)) for k in self.keys)


class SubTemplate(object):
    __metaclass__ = SubTemplateMeta


def bound_template(adder_func):
    class BoundTemplateMeta(TemplateMeta):
        def __init__(cls, cls_name, bases, cls_dict):
            adder_func(cls)

    class BoundTemplate(Template):
        __metaclass__ = BoundTemplateMeta

    return BoundTemplate

def register(collection):
    def _register(func):
        collection[func.__name__] = func
        return func
    return _register


# Utils

def extends(template):
    def _decorator(wrapped_template):
        new_template = template.copy()
        new_template.extend(
            wrapped_template)
        return new_template
    return _decorator

def set_attr(path, attr, content_func):
    def _set_attr(template, **kwargs):
        template.element.set_attr(
            path,
            attr,
            content_func(**kwargs))
    return _set_attr

def set_text(path, content_func):
    def _set_text(template, **kwargs):
        for el in template.element.cssselect(path):
            el.text = content_func(**kwargs)
    return _set_text

def replace(path, content_func):
    def _replace(template, **kwargs):
        template.element.replace(
            path,
            content_func(**kwargs))
    return _replace

def add(path, content_func, index=None):
    def _add(template, **kwargs):
        template.element.add(
            path,
            content_func(**kwargs),
            index=index)
    return _add
