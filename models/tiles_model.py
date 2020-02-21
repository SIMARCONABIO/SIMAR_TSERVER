import os
import yaml
import json
import subprocess
import psycopg2

from psycopg2.extras import RealDictCursor

from flask import request

from flask_restful import Resource, reqparse

from mapproxy.config.config import load_default_config, load_config
from mapproxy.util.ext.dictspec.validator import validate, ValidationError
from mapproxy.config.loader import ProxyConfiguration, ConfigurationError
from mapproxy.wsgiapp import MapProxyApp
from webtest import TestApp as TestApp_

from mapproxy.seed.seeder import seed
from mapproxy.seed.config import SeedingConfiguration, SeedConfigurationError, ConfigurationError
from mapproxy.seed.spec import validate_seed_conf
from mapproxy.config.loader import ProxyConfiguration
from mapproxy.config.spec import validate_options
from mapproxy.config.config import load_default_config, load_config
from mapproxy.seed import seeder
from mapproxy.seed import util

parser = reqparse.RequestParser()

mapserver_bin = '/usr/lib/cgi-bin/mapserv'
mapserver_url = 'http://simar.conabio.gob.mx:8085/cgi-bin/mapserv?'


def get_mapproxy_conf(tileset, layer, title):
    '''
        Default para productos SATMO
    '''
    return json.dumps({
        'services': {
            'wms': {'image_formats': ['image/png'],
                'md': {'abstract': 'Djmp', 'title': 'Djmp'},
                'srs': ['EPSG:4326', 'EPSG:3857'],
                'versions': ['1.1.1']},
            'wmts': {
                'restful': True,
                'restful_template':
                '/{Layer}/{TileMatrixSet}/{TileMatrix}/{TileCol}/{TileRow}.png',
                },
            'tms': {
                'origin': 'nw',
                },
            'demo': None
        },
        'layers':  [{
            "name": layer,
            "title": title,
            "sources":["tileset_cache"]
        }],
        'caches': {
            "tileset_cache":{
                "grids":["webmercator"],
                "sources":["tileset_source"],
                "cache": {
                    'type': 'file',
                    'directory': tileset.directory,
                    'directory_layout': 'tms'
                }
            }
        },
        'sources': {
            'tileset_source': {
                'type' : 'mapserver',
                'req': {
                    'layers': 'raster',
                    'transparent': 'true',
                    'map': tileset.map
                },
                'mapserver': {
                    'binary': tileset.mapserver_binary,
                    'working_dir': '/tmp'
                },
                'coverage': {
                    'bbox': '-170,-90,-30,90',
                    'bbox_srs': 'EPSG:4326',
                }
            }
        },  
        'grids': {
            'webmercator': {
                'base': 'GLOBAL_WEBMERCATOR'
            },
        },
        'globals': {
            'image': {
                'resampling_method': 'nearest',
                'paletted': tileset.paletted,
            }
        }
    })


def get_coverage(tileset):
    return {
        "bbox": [tileset.bbox_x0, tileset.bbox_x1, tileset.bbox_y0, tileset.bbox_y1],
        "srs": "EPSG:3857"
    }


def seed_seeds(tileset):
    if tileset.layer_zoom_start > tileset.layer_zoom_stop:
        raise ConfigurationError('invalid configuration - zoom start is greater than zoom stop')
    return {
        "refresh_before": {
            "minutes": 0
        },
        "caches": [
            "tileset_cache"
        ],
        "levels": {
            "from": tileset.layer_zoom_start,
            "to": tileset.layer_zoom_stop
        },
        "coverages": ["tileset_geom"]
    }

def get_seed_conf(tileset):
    seed_conf = {
        'coverages': {
            "tileset_geom": get_coverage(tileset)
        },
        'seeds': {
            "tileset_seed": seed_seeds(tileset)
        }
    }
    return json.dumps(seed_conf)

def generate_confs(tileset, layer, title, ignore_warnings=True, renderd=False):
    """
    Default para productos SATMO
    Takes a Tileset object and returns mapproxy and seed config files
    """
    # Start with a sane configuration using MapProxy's defaults
    mapproxy_config = load_default_config()

    tileset_conf_json = get_mapproxy_conf(tileset, layer, title)
    tileset_conf = yaml.safe_load(tileset_conf_json)

    #print tileset_conf_json

    # merge our config
    load_config(mapproxy_config, config_dict=tileset_conf)

    seed_conf_json = get_seed_conf(tileset)
    seed_conf = yaml.safe_load(seed_conf_json)

    errors, informal_only = validate_options(mapproxy_config)
    if not informal_only or (errors and not ignore_warnings):
        raise ConfigurationError('invalid configuration - {}'.format(', '.join(errors)))

    mapproxy_cf = ProxyConfiguration(mapproxy_config, seed=seed, renderd=renderd)

    errors, informal_only = validate_seed_conf(seed_conf)
    if not informal_only:
        raise SeedConfigurationError('invalid seed configuration - {}'.format(', '.join(errors)))
    seed_cf = SeedingConfiguration(seed_conf, mapproxy_conf=mapproxy_cf)

    return mapproxy_cf, seed_cf

def get_mapproxy(tileset, layer, title):
    """Creates a mapproxy config for a given layer-like object.
       Compatible with django-registry and GeoNode.
       Default para productos SATMO
    """
    mapproxy_cf, seed_cf = generate_confs(tileset, layer, title)
    # Create a MapProxy App
    app = MapProxyApp(mapproxy_cf.configured_services(), mapproxy_cf.base_config)
    # Wrap it in an object that allows to get requests by path as a string.
    return TestApp(app), mapproxy_cf

class TileModel:

    def __init__(self, db):
        self.db = db       

    def get_raster(self, composition, sensor, product_date):
        try:
            c = composition
            if c == 'nsst':
                c = 'day'

            cur = self.db.cursor(cursor_factory=RealDictCursor)
            query = """SELECT r."rid", r.filename FROM "public"."ocean_color_satmo_nc" AS c 
            INNER JOIN "public"."ocean_color_satmo_nc_rs" AS r ON c."rid" = r."ridNc" AND r.format = 'mapserver' 
            WHERE c.product_date = '%s' and c.sensor = '%s' and c.composition = '%s';""" % (product_date, sensor, c)

            cur.execute(query)
            row = cur.fetchone()
            cur.close()
            if row:
                return row
            else:
                return None
        except psycopg2.Error as err:
            raise Exception(err)

    def get_cache_dir(self, composition, sensor, product_date):
        base_dir = '/mnt/d/xamp/tmp/tiles'
        cache_dir = None
        if composition == 'nsst':
            cache_dir = os.path.join(base_dir, sensor, composition, product_date)

        return cache_dir


class Tiles(Resource):

    def __init__(self, db):
        self.model = TileModel(db)

    def get(self, composition, sensor, product_date, z, x, y):
        try:
            c_dir = self.model.get_cache_dir(composition, sensor, product_date)
            if c_dir:
                r = self.model.get_raster(composition, sensor, product_date)
                if r:
                    l_name = 'raster'
                    tileset = type('Tileset', (object,), 
                    {
                        'id': r['rid'], 
                        'name': l_name, 
                        'map': r['filename'], 
                        'cache_type': 'file', 
                        'directory': c_dir,
                        'directory_layout':'', 
                        'source_type': 'mapserver',
                        'mapserver_binary': mapserver_bin,
                        'bbox_x0': -123,
                        'bbox_x1': -59,
                        'bbox_y0': 33,
                        'bbox_y1': 1,
                        'layer_name': l_name, # needs to be updated
                        'layer_zoom_start': 0,
                        'layer_zoom_stop': 12,
                        'paletted': False,
                    })()

                    print(tileset)

                    mp, yaml_config = get_mapproxy(tileset, layer=composition, title="")

                    path_info = '/%s/%s/%s' % (str(z), str(x), str(y))

                    params = {}
                    headers = {
                        'X-Script-Name': str(path_info.replace(path_info.lstrip('/'), '')),
                        'X-Forwarded-Host': request.META['HTTP_HOST'],
                        'HTTP_HOST': request.META['HTTP_HOST'],
                        'SERVER_NAME': request.META['SERVER_NAME'],
                    }
                    mp_response = mp.get(path_info, params, headers)

                    print(mp_response)

                # print(c_dir)
            return {"success": False}
        except Exception as error:
            print(error)
            return {"success": False, "message": str(error)}
