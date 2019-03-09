import os
import random
from collections import OrderedDict
import json
from io import BytesIO

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

import error


class DriveStorage:

    def __init__(self,root, onHeroku):

        # variables
        self.drive = self.__setupDrive(onHeroku)
        results = self.drive.ListFile({'q': "'" + root + "' in parents and trashed=false"}).GetList()
        self.dirIndex = {}
        self.indexName = 'index.json'
        self.dataCache = OrderedDict()
        self.cacheSize = 0
        for result in results:
            if result['title'] == self.indexName:
                gFile = self.drive.CreateFile({'id': result['id'] })
                gFile.FetchContent()
                self.dirIndex = json.loads(gFile.content.getvalue().decode('UTF-8', 'strict'))
                break
        
        if not self.dirIndex:
            print('Loading and indexing entries...')
            self.dirIndex = {'root':{'id':root, 'entries':self.__makeEntries(root) }}
            print('Done!')
            self.uploadIndex()



    # upload the file to the specific location
    def upload(self, data, location, filename):

        # find (if not, create) the directory the file is supposed to be uploaded.
        curDir = self.__getDirectory(location, self.dirIndex['root'], create=True)

        # prepare to update / upload the file
        if filename in curDir['entries']:
            gFile = self.drive.CreateFile(
                {'title':filename, 
                'id': curDir['entries'][filename]['id'],
                'parents':[{'kind': 'drive#fileLink', 'id': curDir['id']}]
                })
        else:
            gFile = self.drive.CreateFile(
                {'title':filename,
                'parents':[{'kind': 'drive#fileLink', 'id': curDir['id']}]
                })
        
        # upload
        gFile.content = data
        gFile.Upload()
        print('Filename "' + filename + '" uploaded to Drive')
        
        #maintenance
        self.__addToCache(gFile)
        curDir['entries'][filename] = {'id': gFile['id'], 'entries':None}
        return data


    def download(self, location, filenames=[], exact=False):
        if exact and len(filenames) != 1:
            raise error.InvalidParametersError('if exact=True, there must only be 1 filename argument')
    
        curDir = self.__getDirectory(location, self.dirIndex['root'])

        name = None
        id = None
        # if specified, get specified file
        if not filenames:
            files = [(entryname, entry['id']) for entryname, entry in curDir['entries'].items() if entry['entries'] == None]
            name, id = random.choice(files)
        # if file not specified, choose a random file
        else:
            for entryname, entry in curDir['entries'].items():
                if (exact and  entry['entries'] == None and os.path.splitext(entryname)[0] == os.path.splitext(filenames[0])[0]) \
                or (not exact and entry['entries'] == None and all(filename in entryname for filename in filenames)):
                    name = entryname
                    id = entry['id']
                    break

        # if no file is found, throw an error
        if name == None or id == None:
            raise error.FileNotFoundError('A file with name ' + str(filenames) + ' is not found in "' + os.path.join(*location) + '".')


        # if file is cached, load from cache. If not, download and add to cache
        if id in self.dataCache:
            self.dataCache.move_to_end(id)
            print('File "' + name + '" loaded from cache')
        else:
            gFile = self.drive.CreateFile({'id': id})
            gFile.FetchContent()
            print('File "' + name + '" downloaded from Google Drive')
            self.__addToCache(gFile)

        self.dataCache[id].seek(0)
        return (name, self.dataCache[id])

    def uploadIndex(self):
        indexStr = json.dumps(self.dirIndex)
        data = BytesIO(indexStr.encode('UTF-8', errors='strict'))
        self.upload(data, [], self.indexName)

    def listFiles(self, location, filenames=[]):
        curDir = self.__getDirectory(location, self.dirIndex['root'])
        return [name for name in curDir['entries'] if all(filename in name for filename in filenames)]


    def __reduceCache(self):
        if self.cacheSize > 262144000:
            print('Reducing cache for DriveStorage')
            while self.cacheSize > 131072000:
                bio = self.dataCache.pop(last = False)
                self.cacheSize -= bio.getbuffer.nbytes
                bio.close()
            print('Size of cache reduced to ' + self.cacheSize)
        else:
            return

    def __addToCache(self, gFile):
        if gFile['id'] in self.dataCache:
            self.cacheSize -= self.dataCache[gFile['id']].getbuffer().nbytes
            self.dataCache[gFile['id']].close()
            print('Filename "' + gFile['title'] + '" deleted in cache')

        self.dataCache[gFile['id']] = gFile.content
        self.cacheSize += gFile.content.getbuffer().nbytes
        self.__reduceCache()
        print('Filename "' + gFile['title'] + '" added in cache')

    def __getDirectory(self, targetPath, curDir, create=False):
        """Traverse and get the content (entries) of the specified directory.
        If a directory within a path is nonexistent, it creates that directory (if create=True), or throw and error if False."""
        if targetPath == []:
            return curDir

        dir = targetPath[0]
        if dir not in curDir['entries']:
            if create:
                newFolder = self.drive.CreateFile(
                    {'title':dir,
                    'parents':[{'id': curDir['id']}],
                    "mimeType": "application/vnd.google-apps.folder"
                    })
                newFolder.Upload()
                curDir['entries'][dir] = {'id': newFolder['id'], 'entries': {}}
                return self.__getDirectory(targetPath[1:], curDir['entries'][dir], create=create)
            else:
                raise error.DirectoryNotFoundError('The directory called "' + targetPath[0] + '" was not found.')
        else:
            if curDir['entries'][dir]['entries'] == None:
                raise error.NotADirectoryError('An entry named "' + dir + '" is not a directory.')
            else:
                return self.__getDirectory(targetPath[1:], curDir['entries'][dir], create=create)


    def __makeEntries(self, id):
        """A recursive function that retrieves the structure of every files/directories under a directory with id, and returns a dict
        representing that structure."""
        results = self.drive.ListFile({'q': "'" + id + "' in parents and trashed=false"}).GetList()
        return { result['title']:{'id':result['id'], 
        'entries': self.__makeEntries(result['id']) if result['mimeType'] == 'application/vnd.google-apps.folder' else None} 
        for result in results if not result['title'].startswith('.')}

    def __setupDrive(self, onHeroku):
        gauth = GoogleAuth()
        if onHeroku:
            from oauth2client.client import Credentials
            import os
            import oauth2client.clientsecrets as clientsecrets
            # load credentials from env
            gauth.credentials = Credentials.new_from_json(os.environ.get('MYCREDS'))
            # set client_config from env, and change backend to settings to tell it to load from settings in the future
            _, client_info = clientsecrets.loads(os.environ.get('CLIENT_SECRETS'))
            client_info['revoke_uri'] = client_info.get('revoke_uri')
            client_info['redirect_uri'] = client_info['redirect_uris'][0]
            gauth.settings['client_config_backend'] = 'settings'
            gauth.settings['client_config'] = client_info
        else:
            gauth.LoadCredentialsFile('mycreds.json') # replace with loadEnv if heroku
        if gauth.credentials is None:
            # Authenticate if they're not there
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            # Refresh them if expired
            gauth.Refresh()
        else:
            # Initialize the saved creds
            gauth.Authorize()
        # Save the current credentials to a file
        if onHeroku:
            os.environ['MYCREDS'] = Credentials.to_json(gauth.credentials)
        else:
            gauth.SaveCredentialsFile('mycreds.json') # replace with saveToEnv if heroku

        return GoogleDrive(gauth)
