from flask import (
    Flask
)

from pymongo import MongoClient
from pyArango.connection import *

import logging

import os
from hunabku._version import get_version
from shutil import rmtree
from distutils.dir_util import copy_tree
import subprocess
import glob
import time
import pathlib
import sys
import importlib
import json


class Hunabku:
    """
    Class to serve papers information store in a mongodb database throught an API using flask.

    example:
    http://0.0.0.0:5000/data/redalyc?init=1&end&apikey=pl0ok9ij8uh7yg
    """

    def __init__(
            self,
            apikey,
            dburi='mongodb://localhost:27017/',
            arangouri="http://localhost:8529",
            ip='127.0.0.1',
            port=8080,
            log_file='hunabku.log',
            info_level=logging.DEBUG):
        """
        Contructor to initialize configuration options.

        Args:
            apikey: apikey to access the data
            ip (str): ip to start the server
            port (int): port for the server
            info_level (logging.DEBUG/INFO etc..): enable/disable debug mode with extra messages output.
        """
        self.dburi = dburi
        self.arangouri=arangouri
        self.dbclient = MongoClient(dburi)
        self.arangoclient=Connection(arangoURL=arangouri,username="root", password="poioiulkj")
        self.ip = ip
        self.port = port
        self.colav_db=self.dbclient["colombia"]
        self.arangodb=self.arangoclient["colombia"]
        self.info_level = info_level
        self.apikey = apikey
        self.apidoc_dir = 'hunabku_website'
        self.apidoc_static_dir = self.apidoc_dir + '/static'
        self.apidoc_output_dir = self.apidoc_dir + '/static/apidoc'
        self.apidoc_templates_dir = self.apidoc_dir + '/templates'
        self.apidoc_config_dir = self.apidoc_dir + '/config'
        self.apidoc_config_data = {}
        self.apidoc_config_data['url'] = 'http://' + \
            ip + ':' + str(port) + '/apidoc'
        self.apidoc_config_data['sampleUrl'] = 'http://' + ip + ':' + str(port)
        self.apidoc_config_data['header'] = {}
        self.apidoc_config_data['header']['filename'] = self.apidoc_config_dir + \
            '/apidoc-header.md'
        self.apidoc_config_data['version'] = get_version()
        self.pkg_config_dir = str(
            pathlib.Path(__file__).parent.absolute()) + '/config/'
        self.pkg_templates_dir = str(
            pathlib.Path(__file__).parent.absolute()) + '/templates/'
        self.plugins = []
        self.log_file = log_file
        self.logger = logging.getLogger(__name__)
        self.set_info_level(info_level)
        self.app = Flask(
            'hanubku',
            static_folder=self.apidoc_static_dir,
            static_url_path='/',
            template_folder=self.apidoc_templates_dir)
        self.apidoc_setup()
        self.load_plugins()
        self.generate_doc()

    def apidoc_setup(self):
        """
        creates an ApiDoc folder to dump configuration and documentation of the APIs
        """
        try:
            os.makedirs(self.apidoc_dir, exist_ok=True)
            print(" * ApidDoc Directory ", self.apidoc_dir, " created ")
        except FileExistsError:
            # Is this is happening then restart the microservices in the folder
            print(
                " * Warning! ApidDoc Directory ",
                self.apidoc_dir,
                " already exists")

        try:
            os.mkdir(self.apidoc_static_dir)
            print(
                " * ApiDoc Static Directory ",
                self.apidoc_static_dir,
                " created ")
        except FileExistsError:
            # Is this is happening then restart the microservices in the folder
            print(
                " * Warning! ApiDoc Static Directory ",
                self.apidoc_static_dir,
                " already exists")

        try:
            os.mkdir(self.apidoc_output_dir)
            print(" * ApiDoc Static Output Directory ",
                  self.apidoc_output_dir, " created ")
        except FileExistsError:
            # Is this is happening then restart the microservices in the folder
            print(
                " * Warning! ApiDoc Static Output Directory ",
                self.apidoc_output_dir,
                " already exists")

        try:
            os.mkdir(self.apidoc_templates_dir)
            print(
                " * ApiDoc Templates Directory ",
                self.apidoc_templates_dir,
                " created ")
        except FileExistsError:
            # Is this is happening then restart the microservices in the folder
            print(
                " * Warning! ApiDoc Templates Directory ",
                self.apidoc_templates_dir,
                " already exists")

        try:
            os.mkdir(self.apidoc_config_dir)
            print(
                " * ApiDoc Config Directory ",
                self.apidoc_static_dir,
                " created ")
        except FileExistsError:
            # Is this is happening then restart the microservices in the folder
            print(
                " * Warning! ApiDoc Static Directory ",
                self.apidoc_static_dir,
                " already exists")

        copy_tree(self.pkg_config_dir, self.apidoc_config_dir)
        apidoc_config_data = {}
        with open(self.apidoc_config_dir + '/apidoc.json') as json_file:
            apidoc_config_data = json.load(json_file)

        apidoc_config_data.update(self.apidoc_config_data)
        with open(self.apidoc_config_dir + '/apidoc.json', 'w') as json_file:
            json.dump(apidoc_config_data, json_file)

        copy_tree(self.pkg_templates_dir, self.apidoc_templates_dir)

    def set_info_level(self, info_level):
        """
        Information level for debug or verbosity of the application (https://docs.python.org/3.1/library/logging.html)
        """
        if info_level != logging.DEBUG:
            logging.basicConfig(filename=self.log_file, level=info_level)
        self.info_level = info_level

    def load_plugins(self):
        """
        This method return the plugins found in the folder plugins.
        """
        self.logger.warning('-----------------------')
        self.logger.warning('------ Loagind Plugins:')
        for path in glob.glob(
                str(pathlib.Path(__file__).parent.absolute()) + "/plugins/*.py"):
            name = path.split(os.path.sep)[-1].replace('.py', '')
            print('------ Loading plugin: ' + name)
            spec = importlib.util.spec_from_file_location(name, path)
            module = spec.loader.load_module()
            plugin_class = getattr(module, name)
            instance = plugin_class(self)
            instance.register_endpoints()
            plugin = {}
            plugin['name'] = name
            plugin['path'] = path
            plugin['spec'] = spec
            plugin['instance'] = instance
            self.plugins.append(plugin)

    def check_apidoc_syntax(self, plugin_file):
        """
        Allows to check in the syntaxis in the docstring comment is right
        for apidoc  files generation.
        The the syntax is wrong, the Hunabku server can not start.
        """
        args = ['apidoc', '-c', self.apidoc_config_dir, '-i',
                str(pathlib.Path(__file__).parent.absolute()) + '/plugins/',
                '--simulate',
                '-f',
                plugin_file]
        process = subprocess.run(args,
                                 stdout=subprocess.PIPE)
        if process.returncode != 0:
            self.logger.error('------ERROR: parsing docstring for apidocs in plugin ' + plugin_file)
            self.logger.error('             server can not start until apidocs syntax is fixed')
            sys.exit(1)

    def generate_doc(self, timeout=1, maxtries=5):
        """
        this method allows to generated apidocs documentation parsing plugin files
        """
        self.logger.warning('-----------------------')
        self.logger.warning('------ Creating documentation')

        rmtree(self.apidoc_static_dir, ignore_errors=True)
        args = ['apidoc', '-c', self.apidoc_config_dir, '-i',
                str(pathlib.Path(__file__).parent.absolute()) + '/plugins/']

        for plugin in self.plugins:
            self.check_apidoc_syntax(plugin['path'])
            args.append('-f')
            args.append(plugin['path'])
        args.append('-o')
        args.append(self.apidoc_output_dir)
        process = subprocess.Popen(args,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        counter = 0
        while process.poll() is None:
            time.sleep(timeout)
            counter = counter + 1
            if counter == maxtries:
                process.kill()
                break
        self.logger.warning(
            '------ Apidocs at http://{}:{}/apidoc/index.html'.format(self.ip, self.port))

    def start(self):
        """
        Method to start server
        """
        self.app.run(host=self.ip, port=self.port, debug=True)
