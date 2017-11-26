import logging
import itertools
import os

from functools import lru_cache
from . import dataset_transformations
from . import sql
from .database import Database
from .typecast import Typecast
from .file import File
from .utility import read_yml, mkdir, list_wrap

BATCH_SIZE = 1000
    
@lru_cache()
def datasets():
    """Returns a dictionary with all defined datasets"""
    return read_yml(os.path.join(os.path.dirname(__file__), 'datasets.yml'))


class Dataset:
    """Information about a dataset"""

    def __init__(self, dataset_name, args=None):
        self.name = dataset_name
        self.args = args
        self.db = None
        #self.db = Database(self.args, table_name=self.name)
        if self.args:
            self.root_dir = self.args.root_dir
        else:
            self.root_dir = './data'

        self.dataset = datasets()[dataset_name]
        # self.typecast = Typecast(self)
        self.files = self._files()

        self.schemas = list_wrap(self.dataset['schema'])
        # self.import_file = None

    def _files(self):
        return [ File(file_dict, folder=self.name, root_dir=self.root_dir) for file_dict in self.dataset['files'] ]


    def download_files(self):
        for f in self.files:
            f.download()


    def db_import(self):
        """
        inserts the dataset in the postgres
        output:  True | Throws
        """
        self.setup_db()
        self.create_schema()

        for schema in self.schemas:
            self.import_schema(schema)

        self.sql_files()


    def transform(self, schema):
        """ 
        Calls the function in dataset_transformation with the same name
        as the dataset
        input: dict
        output: generator
        """
        tc = Typecast(schema)
        return tc.cast_rows(getattr(dataset_transformations, schema['table_name'])(self))
    

    def import_schema(self, schema):
        rows = self.transform(schema)
        
        while True:
            batch = list(itertools.islice(rows, 0, BATCH_SIZE))
            if len(batch) == 0:
                break
            else:
                self.db.insert_rows(batch, table_name=schema['table_name'])

    def create_schema(self):
        create_table = lambda name, fields: self.db.sql(sql.create_table(name, fields))

        for s in self.schemas:
            create_table(s['table_name'], s['fields'])

    def sql_files(self):
        if 'sql' in self.dataset:
            for f in self.dataset['sql']:
                self.db.execute_sql_file(f)

    def setup_db(self):
        if self.db is None:
            self.db = Database(self.args, table_name=self.name)


