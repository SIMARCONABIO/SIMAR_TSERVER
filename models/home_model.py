# -*- coding: utf-8 -*-
import os
import csv
import time
import datetime
import psycopg2
import configparser

from io import StringIO
from psycopg2.extras import RealDictCursor

from flask import request, make_response, render_template

from flask_restful import Resource, reqparse

parser = reqparse.RequestParser()


class BuoyModel:

    def __init__(self):
        try:
            config = configparser.ConfigParser()
            dirname = os.path.abspath(os.path.dirname(__file__))
            config_path = os.path.join(dirname, '../.config.ini')
            config.read(config_path)
            host = config.get('dbsettings', 'db_host')
            user = config.get('dbsettings', 'db_user')
            passwd = config.get('dbsettings', 'db_passwd')
            dbname = config.get('dbsettings', 'db_dbname')
            self.db = psycopg2.connect(database=dbname, user=user, password=passwd, host=host)
        except Exception as err:
            raise Exception('Could not connect to db ', err)

    def get_param(self, param):
        try:
            cur = self.db.cursor(cursor_factory=RealDictCursor)
            query = """SELECT "value" FROM config WHERE param = '{p}';""".format(p=param)
            cur.execute(query)
            row = cur.fetchone()
            cur.close()
            if row:
                return row['value']
            else:
                return None
        except psycopg2.Error as err:
            self.db.rollback()
            raise Exception(err)

    def __del__(self):
        if self.db:
            self.db.close()


class Root(Resource):

    def __init__(self):
        self.model = BuoyModel()

    def get(self):
        try:
            headers = {'Content-Type': 'text/html'}
            e = self.model.get_param('contact_email')
            return make_response(render_template('index.html', email=e), 200, headers)
        except Exception as error:
            return {"success": False, "message": str(error)}


class ApiRoot(Resource):

    def __init__(self):
        self.model = BuoyModel()

    def get(self):
        try:
            headers = {'Content-Type': 'text/html'}
            e = self.model.get_param('contact_email')
            return make_response(render_template('index.html', email=e), 200, headers)
        except Exception as error:
            print(error)
            return {"success": False, "message": str(error)}
