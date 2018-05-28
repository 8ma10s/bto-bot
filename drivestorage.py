import random
from collections import OrderedDict
from functools import lru_cache

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import error
import os

class DriveStorage:

    def __init__(self,root, onHeroku):
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

        # variables
        self.drive = GoogleDrive(gauth)
        self.dirTree = {'root':{'id':root, 'isDir': True, 'subdir':{}}}
        self.dataCache = OrderedDict()
        self.cacheSize = 0


    # upload the file to the specific location
    def upload(self, data, location, filename):
        targetPath = location
        curDir = self.dirTree['root']
        for dir in targetPath:
            if dir in curDir['subdir']:
                if not curDir['subdir'][dir]['isDir']:
                    raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                curDir = curDir['subdir'][dir]
            else:
                self.__refreshDir(curDir['id'], curDir)
                if dir in curDir['subdir']:
                    if not curDir['subdir'][dir]['isDir']:
                        raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                    curDir = curDir['subdir'][dir]
                else:
                    # create new folder
                    newFolder = self.drive.CreateFile(
                        {'title':dir,
                        'parents':[{'id': curDir['id']}],
                        "mimeType": "application/vnd.google-apps.folder"
                        })
                    newFolder.Upload()
                    curDir['subdir'][dir] = {'isDir': True, 'id': newFolder['id'], 'subdir': {}}
                    curDir = curDir['subdir'][dir]
        
        
        self.__refreshDir(curDir['id'], curDir)
        # update file
        if filename in curDir['subdir']:
            gFile = self.drive.CreateFile(
                {'title':filename, 
                'id': curDir['subdir'][filename]['id'],
                'parents':[{'kind': 'drive#fileLink', 'id': curDir['id']}]
                })
            
        else:
            gFile = self.drive.CreateFile(
                {'title':filename,
                'parents':[{'kind': 'drive#fileLink', 'id': curDir['id']}]
                })


        gFile.content = data
        gFile.Upload()
        self.__reduceCache()
        if gFile['id'] in self.dataCache:
            self.cacheSize -= self.dataCache[gFile['id']].getbuffer().nbytes
            self.dataCache[gFile['id']].close()
        self.dataCache[gFile['id']] = data
        self.cacheSize += data.getbuffer().nbytes
        self.__listFiles.cache_clear()
        curDir['subdir'][filename] = {'id': gFile['id'], 'isDir':False, 'subdir':{}}
        return data

    def download(self, location, filenames):
        targetPath = location
        curDir = self.dirTree['root']
        for dir in targetPath:
            if dir in curDir['subdir']:
                if not curDir['subdir'][dir]['isDir']:
                    raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                curDir = curDir['subdir'][dir]
            else:

                self.__refreshDir(curDir['id'], curDir)
                if dir in curDir['subdir']:
                    if not curDir['subdir'][dir]['isDir']:
                        raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                    curDir = curDir['subdir'][dir]
                else:
                    raise error.DirectoryNotFoundError('The specified directory: "' +  dir + '" was not found')

        # if cached, no need to connect to Google
        if filenames: 
            for key in list(curDir['subdir'].keys()):
                matchObj = curDir['subdir'][key]
                if all(filename in key for filename in filenames) and not matchObj['isDir'] and matchObj['id'] in self.dataCache:
                    self.dataCache.move_to_end(matchObj['id'])
                    print('cached, no list load')
                    return (key, self.dataCache[matchObj['id']])

        gFiles = self.drive.ListFile({'q': "'" + curDir['id'] + "' in parents and trashed=false"}).GetList()
        gFiles = list(filter(lambda x: all(y in x['title'] for y in filenames), gFiles))

        if not gFiles:
            raise error.FileNotFoundError('Could not find a file that matches all queries')
        # choose exact match if exists. If not, choose a random file among the ones that matched the query
        gFile = None
        if len(filenames) == 1:
            for match in gFiles:
                print(match['title'])
                if os.path.splitext(match['title'])[0] == os.path.splitext(filenames[0])[0]:
                    gFile = match
        if not gFile:
            gFile = random.choice(gFiles)
        
        # if cached, return cache
        if gFile['id'] in self.dataCache:
            self.dataCache.move_to_end(gFile['id'])
            print('cached, list load')
            return (gFile['title'], self.dataCache[gFile['id']])
        else:
            gFile.FetchContent()
            self.__reduceCache()
            self.dataCache[gFile['id']] = gFile.content
            self.cacheSize += gFile.content.getbuffer().nbytes

            curDir['subdir'][gFile['title']] = {'id': gFile['id'], 'isDir':False, 'subdir':{}}
            print('not cached')
            return (gFile['title'], gFile.content)
    
    def listFiles(self, location):
        return self.__listFiles(tuple(location))

    @lru_cache()
    def __listFiles(self, location):
        targetPath = list(location)
        curDir = self.dirTree['root']
        for dir in targetPath:
            if dir in curDir['subdir']:
                if not curDir['subdir'][dir]['isDir']:
                    raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                curDir = curDir['subdir'][dir]
            else:

                self.__refreshDir(curDir['id'], curDir)
                if dir in curDir['subdir']:
                    if not curDir['subdir'][dir]['isDir']:
                        raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                    curDir = curDir['subdir'][dir]
                else:
                    raise error.DirectoryNotFoundError('The specified directory: "' +  dir + '" was not found')
        
        print("'" + curDir['id'] + "' in parents and trashed=false")
        gFiles = self.drive.ListFile({'q': "'" + curDir['id'] + "' in parents and trashed=false"}).GetList()
        return [gFile['title'] for gFile in gFiles]




    
    def __refreshDir(self, id, curDir):
        ## make a dictionary of subdirectories, with key being the title, and values being dict of id, isDir, and empty subDir
        ## then set it equal to current folder's subdirectory
        curDir['subdir'] = { result['title']:{'id':result['id'], 
        'isDir':(True if result['mimeType'] == 'application/vnd.google-apps.folder' else False), 
        'subdir': {} if result['title'] not in curDir['subdir'] else curDir['subdir'][result['title']]['subdir']} 
        for result in self.drive.ListFile({'q': "'" + id + "' in parents and trashed=false"}).GetList() }

    def __reduceCache(self):
        if self.cacheSize > 262144000:
            for _ in range(50):
                bio = self.dataCache.pop(last = False)
                self.cacheSize -= bio.getbuffer.nbytes
                bio.close()
        else:
            return
    
