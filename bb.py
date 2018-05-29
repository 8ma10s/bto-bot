import asyncio
import configparser
import io
import os
import random
import sys

import aiohttp
import discord
import numpy as np
from configobj import ConfigObj

import datacontainer
import error
import utilities

# load config / google drive
dc = datacontainer.DataContainer()
keys = dc.keys
configs = dc.configs
stats = dc.stats
ds = dc.drive

# set up discord client
client = discord.Client()

# load utilities function
utils = utilities.Utilities(client,dc)

# set global variables
sleep = False
rubyLock = True

# How to use

@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

@client.event
async def on_message(message):
    global sleep
    global rubyLock
    if client.user == message.author:
        return
    
    #detect a command
    if message.content.startswith(';'):
        isStamp = False
        addStamp = False
        msg = message.content.split()
        
        #stamp command
        command = msg[0][1:]
        if command.startswith(';'):
            isStamp = True
            command = command[1:]
            if command.endswith('+'):
                addStamp = True
                command = command[0:-1]
                if command == 'list':
                    await client.send_message(message.channel, 'listって名前のフォルダは作れません')
                    return


        if len(msg) >= 2:
            args = msg[1:]
        else:
            args = []
        
        #during sleep, only accepts wakeup command
        if sleep:
            if command == 'wakeup' and not isStamp:
                if await utils.isAuthorized(message, '今日は何日？'):
                    sleep = False
                    await client.send_message(message.channel, 'ぽきた')
                    return
                else:
                    await client.send_message(message.channel, 'なーんだじゃぁ寝ちゃおーっと')
                    return
            else:
                return

        # adding stamp
        elif addStamp:
            config = configs['stamps']
            # preprocessing
            if any(x in command for x in ['..', '/', '\\']):
                await client.send_message(message.channel, '悪用禁止')
                return
            
            if not args or '.' not in args[0]:
                await client.send_message(message.channel, 'ファイル名を拡張子込みでうちこめ')
                return
            elif args[0].startswith('list'):
                await client.send_message(message.channel, '\'list\'っていう名前は使えない仕様だよ')
                return
            # get specified message
            if len(args) > 1:
                try:
                    imgMsg = await client.get_message(message.channel, args[1])
                except discord.NotFound:
                    await client.send_message(message.channel, 'そんなIDねーよ')
                    return
                except discord.HTTPException:
                    await client.send_message(message.channel, 'そんなIDねーよ')
                    return
            
            # save the picture
            else:
                await client.send_message(message.channel, 'よしいいぞ、' + 'フォルダ' + command + 'に' + args[0] + 'として登録したいファイルをよこせ')
                imgMsg = await client.wait_for_message(timeout = 60, author=message.author, channel=message.channel)

            if imgMsg.attachments:
                async with aiohttp.ClientSession() as session:
                    async with session.get(imgMsg.attachments[0]['url']) as resp:
                        attachment = await resp.read()
                        pic = io.BytesIO(attachment)
                        ds.upload(pic, config['DIR'] + [command], args[0])
                        pic.seek(0)
                        await client.send_file(message.channel, pic, filename=args[0], content='フォルダ' + command + 'に' + args[0] + 'を追加')
                        pic.seek(0)
            else:
                await client.send_message(message.channel, '添付ファイルが無いんだけど・・・')
            return 

        # sending stamp
        elif isStamp:
            config = configs['stamps']
            if not command:
                return
            if any(x in command for x in ['..', '/', '\\']):
                await client.send_message(message.channel, '悪用禁止')
                return
            # list all folders
            if command == 'list':
                ls = sorted(ds.listFiles(config['DIR']))
                await client.send_message(message.channel, 'list of folders: ' + str(ls))

            elif args:
                # list files in the specified folder
                if args[0] == 'list':
                    try:
                        ls = sorted(ds.listFiles(config['DIR'] + [command]))
                    except error.DirectoryNotFoundError:
                        await client.send_message(message.channel, 'そんなフォルダは無いZOY')
                        return
                    # list all files
                    if len(args) == 1:
                        await client.send_message(message.channel, 'content of ' + command + ': ' + str(ls))
                    # list files that match
                    else:
                        result = []
                        for data in ls:
                            if all(x in data for x in args[1:]):
                                result = result + [data]
                        if not result:
                            await client.send_message(message.channel, 'そんな名前の' + command + 'は一人もいなかったよ')
                            return
                        else:
                            await client.send_message(message.channel, 'match for ' + command + '/' + str(args[1:]) + ': ' + str(result))
                
                #send files that match
                else:
                    try:
                        pic = ds.download(config['DIR'] + [command], args)
                    except error.DirectoryNotFoundError:
                        await client.send_message(message.channel, 'そんなフォルダは無いZOY')
                        return
                    except error.FileNotFoundError:
                        await client.send_message(message.channel, 'その' + command + 'は存在しません')
                        return
                    await client.send_file(message.channel, pic[1], filename=pic[0], content=message.author.name + ' sent: ' + 
                    command + '/' + pic[0].split('.')[0])
                    pic[1].seek(0)
                    
            
            # choose a random file from the specified folder and send
            else:
                try:
                    pic = ds.download(config['DIR'] + [command], [])
                except error.DirectoryNotFoundError:
                    await client.send_message(message.channel, 'そんなフォルダは無いZOY')
                    return
                except error.FileNotFoundError:
                    await client.send_message(message.channel, 'その' + command + 'は存在しません')
                    return
                await client.send_file(message.channel, pic[1], filename=pic[0], content=message.author.name + ' sent: ' + 
                command + '/' + pic[0].split('.')[0])
                pic[1].seek(0)
            

            await client.delete_message(message)
            return
        
        #if authorized, kill bto-bot
        elif command == 'kill':
            if await utils.isAuthorized(message, '俺を殺したいなら終了パスワードを入れろ'):
                await client.send_message(message.channel, 'グエー死んだンゴ')
                await client.logout()
                return
            else:
                await client.send_message(message.channel, 'パスが違うので生き続けることにする')
                return

        # sleep (and not respond) until wakeup
        elif command == 'sleep':
            if await utils.isAuthorized(message, '今何時や・・・？'):
                sleep = True
                await client.send_message(message.channel, 'ぽやしみ〜〜')
                return
            else:
                await client.send_message(message.channel, 'コード書いてるから寝られないわ')
                return
        
        #choose a dining hall to eat
        elif command == 'dining':
            config = configs['dining']
            await client.send_message(message.channel, '今日は' + random.choice(config['LIST']) + 'で食うかな')

        # independent gacha feature
        elif command == 'gacha':
            config = configs['gacha']
            repeat = 0
            getUr = False
            charRandom = True
            char = None
            arg = None

            if args and args[0] in config['NAMES']:
                if rubyLock and args[0] == 'ruby':
                    pic = open(os.path.join(*configs['RESOURCESDIR'], 'aoruby.jpg'), 'rb')
                    await client.send_file(message.channel, pic, content='ルビキチに人権はありませーんｗｗｗｗｗｗ')
                    pic.close()
                    await client.send_message(message.channel, '人にものを頼む時はなんて言うんだっけ？')
                    plsMsg = await client.wait_for_message(timeout = 30, author=message.author, channel=message.channel)
                    if not plsMsg:
                        await client.send_message(message.channel, 'ほう、だんまりか')
                        return
                    if plsMsg.author.id not in keys['ROM_IDS']:
                        await client.send_message(message.channel, plsMsg.author.name + 'さんでしたか、これは失礼しました。こちらがご指定のルビィちゃんになります。')
                    elif all(x not in plsMsg.content for x in config['PLS_WORDS']):
                        await client.send_message(message.channel, 'そんな態度じゃルビィちゃんは出せないなぁ・・・')
                        return
                char = args[0]
                charRandom = False
                if len(args) >= 2:
                    arg = args[1]
            elif args:
                arg = args[0]
            
            if not arg:
                repeat = 1
            elif arg.lower() == 'ur':
                getUr = True
                repeat = config['MAX_UR']
            else:
                try:
                    repeat = int(arg)
                except ValueError:
                    await client.send_message(message.channel, '数字以外を入れるな')
                    return
            
                if repeat > config['MAX_GACHA']:
                    await client.send_message(message.channel, 'せいぜい' + str(config['MAX_GACHA']) + '連までにしような')
                    return

            chars = sorted(os.listdir(os.path.join(*config['DIR'])))
            ranks = list(config['PROBS'].keys())
            probs = list(config['PROBS'].values())
            for i in range(repeat):
                if charRandom:
                    char = random.choice(chars)
                rank = np.random.choice(ranks, p=probs)
                cards = list(filter(lambda x: '_' + rank + '_' in x, os.listdir(os.path.join(*config['DIR'], char))))
                card = random.choice(cards)

                pic = open(os.path.join(*config['DIR'], char, card), 'rb')
                cardData = card.split('_')



                await client.send_file(message.channel, pic, content=str(i + 1) + '連目\n' + cardData[1].upper() + ' ' + config['NAMES'][char])
                pic.close()

                if getUr and cardData[1] == 'ur':
                    await client.send_message(message.channel, 'UR余裕だな')
                    return
            
            if getUr:
                await client.send_message(message.channel, '二度とやらんわこんなクソゲー')

        elif command == 'romLock':
            if message.author.id not in keys['ROM_IDS']:
                print(message.author.id)
                if not args:
                    rubyLock = not rubyLock
                elif args[0] == 'on':
                    rubyLock = True
                elif args[0] == 'off':
                    rubyLock = False
                else:
                    await client.send_message(message.channel, 'どうやらコマンドが間違っているようです。 romLock onでオン、romLock offでオフにできます。')
                    return
                
                await client.send_message(message.channel, 'お疲れ様です、ROMロックは' + (lambda: 'オン' if rubyLock else 'オフ')() + 'になりました。')

            else:
                await client.send_message(message.channel, 'このコマンドは人間専用です')
                return
                
                
                
                





client.run(keys['DISCORD_SECRET'])
