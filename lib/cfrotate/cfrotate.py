#!/usr/bin/env python

import os
import sys
import tarfile
from datetime import datetime

import cloudfiles

class CloudFilesRotate(object):
    """ 
    >>> cfr = CloudFilesRotate("username", "apikey", "container", "auth_url")
    >>> cfr.rotate("/var/www/html", 7)
    >>> (123, 119)
    """
    def __init__(self, username, apikey, container,auth_url, snet=False, debug=False):
        self.DATE_FORMAT = "%Y-%m-%dT%H%M"
        self.debug = debug
        try:
            self.connection = cloudfiles.get_connection(username, 
                                                        apikey,
                                                        servicenet=snet,
                                                        authurl=auth_url,
                                                        timeout=15)
            self.container = self.connection.get_container(container)
        except cloudfiles.errors.AuthenticationFailed:
            print "Error authenticating with Cloud Files API"
            raise SystemExit(1)
        except cloudfiles.errors.NoSuchContainer:
            self.container = self.connection.create_container(container)

    def _compress(self, path, tempdir="/tmp"):
        if path == '/':
            filename = os.path.join(tempdir, 'root.tgz')
        elif path.endswith('/'):
            filename = os.path.join(tempdir, os.path.basename(path[:-1])
                                             + '.tgz')
        else:
            filename = os.path.join(tempdir, os.path.basename(path) + '.tgz')

        if self.debug:
            print "Creating %s" % filename
        zipped = tarfile.open(filename, 'w:gz')
        zipped.add(path)
        zipped.close()
        self.compressed = True

        return filename

    def _upload(self, path):
        upload_count = 0

        if getattr(path, '__iter__', False):
            for filename in path:
                self._upload(filename)
        elif os.path.isdir(path):
            filelist = []
            for root, subdirs, files in os.walk(path):
                for name in files:
                    filelist.append('/'.join([root, name]))
            self._upload(filelist)
        elif os.path.exists(path):
            if self.compressed:
                cloudpath = '/'.join([self.now, os.path.basename(path)])
            elif path[0] is not '/':
                cloudpath = '/'.join([self.now, path])
            else:
                cloudpath = ''.join([self.now, path])

            if self.debug:
                print "Uploading %s to %s" % (path, cloudpath)
            obj = self.container.create_object(cloudpath)
            obj.load_from_filename(path)
            upload_count += 1

        return upload_count
    
    def _rotate(self, count):
        delete_count = 0

        obj_list = self.container.list_objects(delimiter='/')
        n = (len(obj_list) > count) and len(obj_list) - count or 0
        oldest = sorted(obj_list)[:n]
        for prefix in oldest:
            old_objs = self.container.get_objects(prefix=prefix)
            for old_obj in old_objs:
                if self.debug:
                    print "Deleting %s" % old_obj
                self.container.delete_object(old_obj)
                delete_count += 1

        return delete_count

    def rotate(self, path, count):
        self.now = datetime.now().strftime(self.DATE_FORMAT)
        self.compressed = False
        path = self._compress(path)
        upload_count = self._upload(path)
        delete_count = self._rotate(count)

        if self.compressed:
            os.remove(path)

        return (upload_count, delete_count)
