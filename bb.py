import asyncio
import configparser
import os
import random
import sys
import time
import io

import aiohttp
import discord
import numpy as np
import DriveStorage

#load config
CONFIGDIR = 'config'
CONFIGFILE = 'config.ini'
KEYSFILE = 'keys.ini'
config = configparser.ConfigParser()
configKeys = configparser.ConfigParser()
config.read(os.path.join(CONFIGDIR, CONFIGFILE))
configKeys.read(os.path.join(CONFIGDIR, KEYSFILE))


# keys/IDs setup
DISCORD_SECRET = configKeys.get('keys', 'discord_secret')
MY_ID = configKeys.get('ids', 'my_id')
ROM_ID = configKeys.get('ids', 'rom_ids').splitlines()

# constant setup (from ini files)
MAX_GACHA = config.getint('constants', 'MAX_GACHA')
MAX_UR = config.getint('constants', 'MAX_UR')
ROOTID = config.get('directories', 'ROOTID')
STAMPDIR = config.get('directories', 'STAMPDIR')
GACHADIR = config.get('directories', 'GACHADIR')
RESOURCESDIR = config.get('directories', 'RESOURCESDIR')
DINING_HALL = config.get('lists', 'DINING_HALL').splitlines()
GACHA_NAME = dict(config.items('GACHA_NAME'))
GACHA_PROB = {k:float(v) for k, v in dict(config.items('GACHA_PROB')).items()}
PLS_WORDS = config.get('lists', 'PLS_WORDS').splitlines()

# global variables
sleep = False
rubyLock = True

# How to use

DOCUMENT = {
    'stamp':'\";;F P\"でフォルダF内の画像Pを表示\n' + '\";;F\"でフォルダF内の画像をランダムに表示\n' '\";;F+ P\"でフォルダF内（Fがなければ作成）に画像Pを登録\n'
}


# functions
def isMsgToMe(msg):
    return client.user.name in msg.content

async def isAuthorized(msg, prompt):
    passInt = random.randint(0,999)
    print(passInt)
    master = await client.get_user_info(MY_ID)
    await client.send_message(master, str(passInt))
    await client.send_message(msg.channel, prompt)
    answer = await client.wait_for_message(timeout = 20, author=msg.author, channel=msg.channel)
    return not (answer == None or str(passInt) != answer.content)

def timeDiff(start):
    end = time.time()
    print(end - start)

def getProb(card):
    return GACHA_PROB[card.split('_')[1]]

# initial setup
client = discord.Client()
ds = DriveStorage.DriveStorage(ROOTID)

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
        startTime = time.time()
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
                if await isAuthorized(message, '今日は何日？'):
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
            # save the picture
            else:
                await client.send_message(message.channel, 'よしいいぞ、' + 'フォルダ' + command + 'に' + args[0] + 'として登録したいファイルをよこせ')
                imgMsg = await client.wait_for_message(timeout = 60, author=message.author, channel=message.channel)
                if imgMsg.attachments:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(imgMsg.attachments[0]['url']) as resp:
                            attachment = await resp.read()
                            pic = io.BytesIO(attachment)
                            ds.upload(pic, [STAMPDIR, command], args[0])
                            pic.seek(0)
                            await client.send_file(message.channel, pic, filename=args[0], content='フォルダ' + command + 'に' + args[0] + 'を追加')
                            pic.seek(0)
                else:
                    await client.send_message(message.channel, '添付ファイルが無いんだけど・・・')
            return 

        # sending stamp
        elif isStamp:
            if not command:
                await client.send_message(message.channel, DOCUMENT['stamp'])
                return
            if any(x in command for x in ['..', '/', '\\']):
                await client.send_message(message.channel, '悪用禁止')
                return
            # list all folders
            if command == 'list':
                ls = sorted(ds.listFiles(tuple([STAMPDIR])))
                await client.send_message(message.channel, str(ls))
                return

            if args:
                # list files in the specified folder
                if args[0] == 'list':
                    try:
                        ls = sorted(ds.listFiles(tuple([STAMPDIR, command])))
                    except DriveStorage.DirectoryNotFoundError:
                        await client.send_message(message.channel, 'そんなフォルダは無いZOY')
                        return
                    # list all files
                    if len(args) == 1:
                        await client.send_message(message.channel, str(ls))
                        timeDiff(startTime)
                        return
                    # list files that match
                    else:
                        result = []
                        for data in ls:
                            if all(x in data for x in args[1:]):
                                result = result + [data]
                        if not result:
                            await client.send_message(message.channel, 'そんな名前の' + command + 'は一人もいなかったよ')
                            timeDiff(startTime)
                            return
                        else:
                            await client.send_message(message.channel, str(result))
                            timeDiff(startTime)
                            return
                
                #send files that match
                else:
                    try:
                        pic = ds.download([STAMPDIR, command], args)
                    except DriveStorage.DirectoryNotFoundError:
                        await client.send_message(message.channel, 'そんなフォルダは無いZOY')
                        return
                    except DriveStorage.FileNotFoundError:
                        await client.send_message(message.channel, 'その' + command + 'は存在しません')
                        return
                    await client.send_file(message.channel, pic[1], filename=pic[0], content=pic[0].split('.')[0])
                    pic[1].seek(0)
                    
            
            # choose a random file from the specified folder and send
            else:
                try:
                    pic = ds.download([STAMPDIR, command], [])
                except DriveStorage.DirectoryNotFoundError:
                    await client.send_message(message.channel, 'そんなフォルダは無いZOY')
                    return
                except DriveStorage.FileNotFoundError:
                    await client.send_message(message.channel, 'その' + command + 'は存在しません')
                    return
                await client.send_file(message.channel, pic[1], filename=pic[0], content=pic[0].split('.')[0])
                pic[1].seek(0)
            

            return

        # gacha
        elif command == 'g':
            if not args:
                await client.send_message(message.channel, '数字入れろ数字')
                return
            
            # Obtains server of message and finds rom-bot
            currentServer = message.server
            if currentServer == None:
                await client.send_message(message.channel, 'DMでガチャはできないの分かってて送っただろ')
                return
            target = currentServer.get_member_named('rom男-bot#5739')
            if target == None:
                await client.send_message(message.channel, 'rom男botがいないサーバーでガチャはできない')
                return
            
            # does gacha until ur
            if args[0] == 'ur':
                for i in range(100):
                    await client.send_message(message.channel, '/g')
                    received = await client.wait_for_message(timeout = 30, author=target, channel=message.channel, check=isMsgToMe)
                    if received == None:
                        await client.send_message(message.channel, 'ROM男bot死んだんじゃないの〜？')
                        return
                    elif 'UR' in received.content:
                        await client.send_message(message.channel, 'UR余裕だな')
                        return
                    elif i >= MAX_UR:
                        pic = open('muritura.jpg', 'rb')
                        await client.send_file(message.channel, pic, content='二度とやらんわこんなクソゲー')
                        pic.close()
                        return
            # does gacha n times
            else:
                try:
                  int(args[0])
                except ValueError:
                  await client.send_message(message.channel, '数字以外を入れるな')
                  return
            
                if int(args[0]) > MAX_GACHA:
                   await client.send_message(message.channel, 'せいぜい' + str(MAX_GACHA) + '連までにしような')
                   return
                for i in range(int(args[0])):
                    await client.send_message(message.channel, '/g')
        
        #if authorized, kill bto-bot
        elif command == 'kill':
            if await isAuthorized(message, '俺を殺したいなら終了パスワードを入れろ'):
                await client.send_message(message.channel, 'グエー死んだンゴ')
                await client.logout()
                return
            else:
                await client.send_message(message.channel, 'パスが違うので生き続けることにする')
                return

        # sleep (and not respond) until wakeup
        elif command == 'sleep':
            if await isAuthorized(message, '今何時や・・・？'):
                sleep = True
                await client.send_message(message.channel, 'ぽやしみ〜〜')
                return
            else:
                await client.send_message(message.channel, 'コード書いてるから寝られないわ')
                return
        
        #choose a dining hall to eat
        elif command == 'dining':
            await client.send_message(message.channel, '今日は' + random.choice(DINING_HALL) + 'で食うかな')

        # independent gacha feature
        elif command == 'gacha':
            repeat = 0
            getUr = False
            charRandom = True
            char = None
            arg = None

            if args and args[0] in GACHA_NAME:
                if rubyLock and args[0] == 'ruby':
                    pic = open(os.path.join(RESOURCESDIR, 'aoruby.jpg'), 'rb')
                    await client.send_file(message.channel, pic, content='ルビキチに人権はありませーんｗｗｗｗｗｗ')
                    pic.close()
                    await client.send_message(message.channel, '人にものを頼む時はなんて言うんだっけ？')
                    plsMsg = await client.wait_for_message(timeout = 30, author=message.author, channel=message.channel)
                    if not plsMsg:
                        await client.send_message(message.channel, 'ほう、だんまりか')
                        return
                    if plsMsg.author.id not in ROM_ID:
                        await client.send_message(message.channel, plsMsg.author.name + 'さんでしたか、これは失礼しました。こちらがご指定のルビィちゃんになります。')
                    elif all(x not in plsMsg.content for x in PLS_WORDS):
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
                repeat = MAX_UR
            else:
                try:
                    repeat = int(arg)
                except ValueError:
                    await client.send_message(message.channel, '数字以外を入れるな')
                    return
            
                if repeat > MAX_GACHA:
                    await client.send_message(message.channel, 'せいぜい' + str(MAX_GACHA) + '連までにしような')
                    return

            chars = sorted(os.listdir(os.path.join(GACHADIR)))
            ranks = list(GACHA_PROB.keys())
            probs = list(GACHA_PROB.values())
            for i in range(repeat):
                if charRandom:
                    char = random.choice(chars)
                rank = np.random.choice(ranks, p=probs)
                cards = list(filter(lambda x: '_' + rank + '_' in x, os.listdir(os.path.join(GACHADIR, char))))
                card = random.choice(cards)

                pic = open(os.path.join(GACHADIR, char, card), 'rb')
                cardData = card.split('_')



                await client.send_file(message.channel, pic, content=str(i + 1) + '連目\n' + cardData[1].upper() + ' ' + GACHA_NAME[char])
                pic.close()

                if getUr and cardData[1] == 'ur':
                    await client.send_message(message.channel, 'UR余裕だな')
                    return
            
            if getUr:
                await client.send_message(message.channel, '二度とやらんわこんなクソゲー')

        elif command == 'romLock':
            if message.author.id not in ROM_ID:
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
                
                
                
                





client.run(DISCORD_SECRET)
