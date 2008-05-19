# -*- coding: utf-8 -*-

from pprint import pprint
from datetime import datetime
from calendar import timegm

import couchdb
from couchdb.client import Server, ResourceNotFound

from couchdb.schema import Document, TextField, IntegerField, DateTimeField, ListField, FloatField, DictField, Schema, Field, SchemaMeta

from utils import simple_decorator

@simple_decorator
def revisioned_save(save_func):
    """Adds the current data (except revisions) into revisions before saving"""
    def revisioned_func(*args, **kwargs):
        # If it's already been saved then create a revision
        # (No need to revise)
        save_revision = kwargs.pop("save_revision", False)
        self = args[0]
        if self.rev and save_revision:
            print "\n\n\n\nsaving revision\n\n\n\n"
            print self.rev
            revisions = self._data.setdefault('revisions', [])
            data = {'date_revised':datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'}
            data.update(self._orig_data)
            del data['revisions']
            revisions.append(data)
        return save_func(*args, **kwargs)
    return revisioned_func

class Query(object):
    """A callable holder for a few attributes of a query"""
    def __init__(self, name, code, wrapper, parent_class, unique=True):
        self.name = name
        self.code = code
        self.wrapper = wrapper
        self.parent_class = parent_class
        self._unique = unique
    
    def __call__(self, key, db=None):
        "Returns the first item from the query"
        db = db or self.parent_class.meta.db
        results = db.query(self.code, wrapper=self.wrapper)[key]
        if self._unique:
            if len(results):
                return list(results)[0]
            else:
                return []
        else:
            return results


class SchemaMetaData(object):
    """A placeholder for bits of data about the schema"""
    def __init__(self, metadata):
        self.db = getattr(metadata, 'db', None)
        self.id_default_column = getattr(metadata, 'id_default_column', None)
        self.content_type = getattr(metadata, 'content_type', None)
        self.revisioned = getattr(metadata, 'revisioned', False)


class PicardDocumentMeta(SchemaMeta):
    def __new__(cls, name, bases, d):
        meta = SchemaMetaData(d.get('meta', None))
        if meta.revisioned:
            date_revised = DateTimeField(default=datetime.now)
            d['date_revised'] = date_revised
            def revisions(self):
                revs = self._data.setdefault('revisions', [])
                return [self.wrap(rev) for rev in revs]
            d['revisions'] = property(revisions)
            d['save'] = revisioned_save(bases[0].save)
        pd_class = SchemaMeta.__new__(cls, name, bases, d)
        pd_class.meta = meta
        
        queries = {}
        for attrname, field in pd_class._fields.items():
            for query_type in ['get_by', 'by']:
                if query_type == 'get_by':
                    unique = True
                if getattr(field, 'keyable', False):
                    code = """
                    function(doc) {
                      if (doc.content_type == "%s") {
                        map(doc.%s, doc);
                      }
                    }
                    """ % (pd_class.meta.content_type, attrname)
                    query_name = "%s_%s" % (query_type, attrname)
                    query = Query(query_name, code, pd_class.init_from_row, parent_class=pd_class, unique=unique)
                    queries[query_name] = query
                    setattr(pd_class, query_name, query)
        setattr(pd_class, '_queries', queries)
            
        return pd_class
    


class PicardDocument(Document):
    """A version of Couchdb document with some utility methods"""
    
    __metaclass__ = PicardDocumentMeta
        
    def __init__(self, *args, **kwargs):
        super(PicardDocument, self).__init__(**kwargs)
        self._data['content_type'] = self.meta.content_type
        for query_name, query in self._queries.items():
            query.db = self.meta.db
    
    def __delitem__(self, name):
        if hasattr(self, name):
            del self.name
        else:
            del self._data[name]

    def __getitem__(self, name):
        if hasattr(self, name):
            return getattr(self, name)
        else:
            return self._data[name]

    def __setitem__(self, name, value):
        if hasattr(self, name):
            self.name = value
        else:
            self._data[name] = value
    
    @classmethod
    def by_id(cls, id):
        item = cls.load(id)
        if item is None:
            raise ResourceNotFound()
        return item
    
    def save(self, db=None):
        """Save the document to the given or default database.  Use `id_default_column` if set"""
        db = db or self.meta.db
        id = self.id or getattr(self, self.meta.id_default_column) or None
        if id:
            db[id] = self._data
        else:
            docid = db.create(self._data)
            self._data = db[docid]
        return self
    
    @classmethod
    def load(cls, id, db=None):
        """Load a specific document from the given database."""
        db = db or cls.meta.db
        item = db.get(id)
        if item is None:
            raise ResourceNotFound()
        return cls.wrap(item)
    
    @classmethod
    def delete(cls, id, db=None):
        db = db or cls.meta.db
        del db[id]

    @classmethod
    def wrap(cls, data):
        instance = cls()
        instance._data.update(data)
        instance._orig_data = data
        return instance
    
    @classmethod
    def init_from_row(cls, row):
        """initialises an item from a view result row"""
        return cls.wrap(row.value)

    @classmethod
    def get_all(cls, db=None):
        db = db or cls.meta.db
        """Fetches all documents that match the classes content_type"""
        code = """
        function(doc) {
          if (doc.content_type == "%s") {
            map(null, doc);
          }
        }
        """ % cls.meta.content_type
        return db.query(code, wrapper=cls.init_from_row)
    
    