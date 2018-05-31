import io
import os
from sys import exit

from configobj import ConfigObj
from validate import Validator

import drivestorage
import error


class DataContainer:
    """A wrapper for ConfigObj which keeps track of all config files"""

    def __init__(self):
        """load config, their last modified times, initialize Google Drive Connection."""
        self.onHeroku = ('DYNO' in os.environ)
        self.keys = self.__setKeys()
        self.drive = drivestorage.DriveStorage(self.keys['DRIVE_ROOT'], self.onHeroku)
        self.__fileList = {} 
        self.__setup()

    def save(self, filename):
        """Declares that the file has been modified (and thus needs to be pushed to Google Drive on the next push().
        Note that this method does NOT actually push the contents on the server. This is done by calling push()."""
        if filename in self.__fileList:
            self.__fileList[filename]['obj'] = self.__dict__[filename]

    def push(self, filename=None):
        """Pushes modified config files onto Google Drive. If filename is not specified, pushes everything that
        is marked as modified. If specified, only the specified file is pushed."""

        result = False
        if not filename:
            for entry in self.__fileList.values():
                if self.__push(entry):
                    result = True
        elif filename in self.__fileList:
            result = self.__push(self.__fileList[filename])
        else:
            raise error.FileNotFoundError('A config file named "' + filename + '" does not exist.')

        return result

    def __push(self, entry):
        """Internal function that takes entry in __fileList and uploads them if needed."""
        if entry['obj'] != None:
            data = io.BytesIO()
            entry['obj'].write(data)
            self.drive.upload(data, entry['path'], entry['filename'])
            entry['obj'] = None
            return True
        else:
            return False
        


    def __setKeys(self):
        """ retrieve the keys/secrets and set them to self.keys. """
        join = os.path.join
        keynames = ConfigObj(infile=join('config', 'keysspec.ini'))
        if self.onHeroku:
            keys = {}
            for keyname in keynames:
                try:
                    keys[keyname] = os.environ.get(keyname)
                except KeyError:
                    print('The required key "' + keyname + '" does not exist. Exiting')
                    exit
            keys = ConfigObj(infile=keys, configspec=join('config','keysspec.ini'))
        else:
            keys = ConfigObj(infile=join('config','keys.ini'), indent_type='\t', configspec=join('config', 'keysspec.ini'))
        if not keys.validate(Validator()):
            print('The key config format is invalid. Exiting')
            exit
        return keys


    def __setup(self):
        """Load files.ini to get a list of necessary config files to load. Then, set each config file 
        as a member variable of this class, with names of those files being the member variable name"""
        join = os.path.join
        self.entries = ConfigObj(infile=join('config', 'files.ini'), configspec=join('config', 'filesspec.ini'))
        self.entries.validate(Validator())
        # set names written on files.ini as member variables of this class
        for entryname, entry in self.entries.items():
            print(entry)
            path = entry['path']
            filename = entry['filename']
            spec = join(*path, entry['spec']) if entry['spec'] else None


            _ , data = self.drive.download(path, [filename], exact=True)
            self.__dict__[entryname] = ConfigObj(data, indent_type='\t', configspec=spec)

            if self.__dict__[entryname].configspec != None and not self.__dict__[entryname].validate(Validator()):
                print('File format validation for "' + filename + '" failed. Exiting')
                exit()
            # index as dict
            self.__fileList[entryname] = {'obj':None, 'path':path, 'filename':filename}
