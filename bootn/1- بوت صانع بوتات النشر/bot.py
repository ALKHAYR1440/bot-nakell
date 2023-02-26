import asyncio
import configparser
import json
import logging
import os
import re
from enum import Enum, auto
from urllib.request import build_opener
from telethon import TelegramClient, events
from telethon import utils
from telethon import errors
from telethon.events import StopPropagation
import telethon
import random
import string
from pathlib import Path
import nest_asyncio

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

builder_token = "5350608471:AAFg0G8-ytrIU-xVWCgfeDf3kYB17betecs"
api_id = 2675637
api_hash = "3aa1b9b3378b0b334d18c39708cda30a"

key="/OMAR66GYJ5"
dev = 2143156834

# CONST
tokens_json = "tokens.json"
deleted_json = "deleted.json"
source_channels_json = "source_channels.json"
target_channels_json = "target_channels.json"
admins_json = "admins.json"
admin_tokens_for_allowed_json="t.json"
allowed_json = "allowed.json"

max_lines_to_send = 20

class State(Enum):
    ASK_FOR_IDS=auto()
    SAVE_IDS=auto()
    WAIT_FOR_BOT_TOKEN=auto()

class Builder:
    conversation_state = {}
    bots_list={}
    bots_to_run={}
    def __init__(self, token,api_id,api_hash):
        self.token = token
        self.api_id = api_id
        self.api_hash = api_hash

    async def run_existing_bots(self):
        tokens = load_bots_tokens(tokens_json)
        if len(tokens)>0:
            child = Child(self.api_id,self.api_hash)
            await asyncio.gather(*[child.start(t, usernameByToken(t),None) for t in tokens])

    def clean(self,who):
        self.conversation_state[who] = {}
        self.bots_list[who] = []
        self.bots_to_run[who] = []

    async def start(self):
        # run builder client
        client = TelegramClient(self.token, self.api_id,self.api_hash)
        await client.start(bot_token=self.token)
        client.flood_sleep_threshold = 24 * 60 * 60
        
        # TODO : check if authorized with token

        async def show_help(event):
            await event.respond(" 🤖 المساعدة 🤖 \n /add : لإضافة بوت نشر جديد \n /del/username :  لحذف بوت من القائمة. (يجب اعادة التشغيل بعد الحذف \n /list : لعرض قائمة البوتات الشغالة \n /admin/id : اضافة أدمن لكل البوتات \n /res : لإعادة تشغيل جميع البوتات \n /help: للمساعدة")
            return

        async def add_bot(event,who,t):
            m = await event.respond("🤖 جاري التحقق من التوكن \n " + str(t))
            tokens = load_bots_tokens(tokens_json)
            if t in tokens:
                await m.edit("❌ هذا التوكن موجود \n"+str(t) + "\n وهذا بوته \n @" + usernameByToken(t))
                self.clean(who)
                return
            try:
                c = TelegramClient(telethon.sessions.MemorySession(), self.api_id,self.api_hash)
                await c.start(bot_token=t)
                u = await c.get_me()
                await c.disconnect()
            except Exception as e:
                logger.error("[add_bot check c.get_me()] [who : " + str(who) + " ] [error : " + str(e)+ " ]")
                await m.edit("❌ هذا التوكن لا يعمل \n "+str(t))
                self.clean(who)
                return
            # append to list of tokens
            save_token(u.username, t, tokens_json)
            self.bots_to_run[who].append(t)
            await m.edit("✅ تم اضافة التوكن \n "+str(t) +"\n @" + str(u.username))
            
        # get token
        @client.on(events.NewMessage(pattern=r"^"+key+"$", func=lambda e: e.is_private))
        async def add_token(event):
            tok = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            tokens = load_json(admin_tokens_for_allowed_json)
            tokens.append(tok)
            append_to_json(admin_tokens_for_allowed_json,tokens)
            await event.respond("/token {}".format(tok))
            raise StopPropagation

        # add token
        @client.on(events.NewMessage(pattern=r"^/token (.+)$", func=lambda e: e.is_private))
        async def add_allowed(event):
            tokens = load_json(admin_tokens_for_allowed_json)
            token = event.pattern_match.group(1)
            if token not in tokens:
                await event.respond("❌ هذا التوكن خاطأ")
            else:
                tokens.remove(token)
                append_to_json(admin_tokens_for_allowed_json,tokens)
                allowed = load_json(allowed_json)
                allowed.append(event.chat_id)
                append_to_json(allowed_json,allowed)
                await event.respond('✅ تم إضافتك كأدمن')
                await show_help(event)
                raise StopPropagation

        # check allowed
        @client.on(events.NewMessage)
        async def only_allowed(event):
            allowed = load_json(allowed_json)
            if event.chat_id not in allowed:
                raise StopPropagation

        # restart
        @client.on(events.NewMessage(pattern=r"^/res(?i)$", func=lambda e: e.is_private))
        async def restart(event):
            await event.respond("تم اعادة التشغيل")
            os.system("make restart")

        # list_bots
        @client.on(events.NewMessage(pattern=r"^/list(?i)$", func=lambda e: e.is_private))
        async def list_bots(event):
            msg = print_multiple_bots(tokens_json,max_lines_to_send)
            
            for i in range(0,len(msg)):
                if msg[i]:
                    await event.respond(str(msg[i]))
                else:
                    await event.respond("القائمة فارغة")
            return

        # delete bots
        @client.on(events.NewMessage(pattern=r"^/del/.*?(?i)", func=lambda e: e.is_private))
        async def delete_bot(event):
            username = event.message.message.split("/")[2]
            if username.startswith("@"):
                username = username[1:]
            ok = remove_by_username(tokens_json,username)                
            if ok:
                await event.respond(" ✅ تم حذف البوت من القائمة. عليك اعادة التشغيل كي يتوقف البوت نهائيا /res (ملاحظة : سيؤدي هذا الى اعادة تشغيل جميع البوتات)")
            else:
                await event.respond("❌ هذا البوت غير موجود في القائمة")
            # append to deleted json folder
            dels = load_json(deleted_json)
            dels.append(username)
            append_to_json(deleted_json,dels)
            # remove bot folder
            ### NOTE : this delete logic deleted all existing bots, even the builder bot, needs to be refactored
            #try:
            #    shutil.rmtree("./"+ username)
            #except Exception as e:
            #    logging.error(e)
            #    await event.respond("تم حذف البوت من القائمة لكن تعذر حذف ملفاته من السرفر. قم بحذف الملفات يدويا \n " + str(e))

        # delete bots
        @client.on(events.NewMessage(pattern=r"^/admin/[0-9]+(?i)$", func=lambda e: e.is_private))
        async def add_admin_bot(event):
            try:
                id = int(event.message.message.split("/")[2])
            except Exception as e:
                logging.error(e)
                await event.respond("❌ الأيدي يجب أن يكون رقم")
                return
            folders = load_bots_usernames(tokens_json)
            for f in folders:
                unic_append_list_to_json(f+"/"+admins_json,id)

            await event.respond("✅ تم الاضافة كأدمن لكل البوتات")

        # help
        @client.on(events.NewMessage(pattern=r"^/help(?i)$", func=lambda e: e.is_private))
        async def help(event):
            await show_help(event)

        # add token
        @client.on(events.NewMessage(pattern=r"^/add(?i)$", func=lambda e: e.is_private))
        async def ask_bot_token(event):
            await event.respond("🤖 أرسل توكن أو توكنات البوتات من @BotFather , أرسل /N عند الإنتهاء, أو /R للإعادة")
            who = event.sender_id
            # clean here to init bots_list[who]=[] and bots_to_run[who]=[], otherwise it will throw an error
            self.clean(who)
            self.conversation_state[who] = State.WAIT_FOR_BOT_TOKEN
            raise StopPropagation

        ##### get dialog #######
        @client.on(events.NewMessage(func=lambda event: event.is_private))
        async def run_new_bot(event):
            who = event.sender_id
            state = self.conversation_state.get(who)
            if state == State.WAIT_FOR_BOT_TOKEN:
                # check if token already exist
                if event.raw_text.upper()=="/N":
                    # clean conversation_state
                    self.conversation_state[who]={}
                    for b in self.bots_list[who]:
                        try:
                            await add_bot(event, who,b)
                        except Exception as e:
                            await event.respond("❌ خطأ في البوت \n" + str(b) + "\n" + str(e))
                            continue
                    # clean bots_list
                    self.bots_list[who] = []
                    await event.respond("✅ تم تشغيل البوتات ")
                    if len(self.bots_to_run[who])>0:
                        child = Child(self.api_id,self.api_hash)
                        await asyncio.gather(*[child.start(t, usernameByToken(t),None) for t in self.bots_to_run[who]])

                elif event.raw_text.upper()=="/R":
                    self.clean(who)
                    await event.respond("تم الاعادة")
                else:
                    try:
                        if '\n' in event.raw_text:
                            tup = tuple(event.raw_text.split('\n'))
                            for t in tup:
                                if t:
                                    self.bots_list[who].append(t)
                        else:
                            value = event.raw_text
                            if value:
                                self.bots_list[who].append(value)
                    except Exception as e:
                        await event.respond(" ❌ خطأ مع هذا التوكن. أعد")
                        self.clean(who)
        await client.run_until_disconnected()

class Child:
    conversation_state = {}
    target_ids = {}
    def __init__(self ,api_id,api_hash):
        self.api_id = api_id
        self.api_hash = api_hash

    async def start(self,token,username,who):     
        # init folders and files
        createDirectory(username)
        create_json_if_not_exist(username+"/"+admins_json,"[]")
        create_json_if_not_exist(username+"/"+source_channels_json,"[]")
        create_json_if_not_exist(username+"/"+target_channels_json,"[]")
        # add username to admin if not there
        if who:
            unic_append_list_to_json(username+"/"+admins_json,who)

        client = TelegramClient(username+"/"+token, self.api_id,self.api_hash)
        try:
            await client.start(bot_token=token)
        except Exception as e:
            logger.error("[client.start child error] : [username : " + username + " ] : " + str(e))
            return
        client.flood_sleep_threshold = 24 * 60 * 60


        async def show_menu(event):
            await event.respond(""""لم أفهمك. إليك قائمة التعليمات
            لمعرفة قائمة المديرين /showadmin
            لاضافة مدير استعمل /addadmin ثم id المدير
            لحذف المدير استعمل /removeadmin ثم id المدير
            لمعرفة قائمة القناة التي تنقل منها /showsource
            لاضافة قناة تنقل منها استعمل /addsource ثم id القناة
            لحذف قناة تنقل منها استعمل /removesource ثم id القناة
            لمعرفة قائمة القنوات التي ننقل اليها /showtarget
            لاضافة قناة أو عدة قنوات تنقل اليها استعمل /addtarget 
            لحذف قناة تنقل منها استعمل /removetarget ثم id القناة
            لحتى تعرف الid الخاص بقناة باستعمال الرابط اكتب /linktoid ثم رابط القناة
            اذا واجهتك مشكلة كلم صاحب البوت """)

        def clean(username):
            self.conversation_state[username]={}
            self.target_ids[username]=[]

        clean(username)

        @client.on(events.NewMessage(func=lambda event: event.is_private))
        async def answer_private_chat(event):
            who = event.sender_id
            state = self.conversation_state.get(username)
            admins_list = load_json(username+"/"+admins_json)
            if event.chat_id not in admins_list:
                await event.respond("هذا البوت تجريبي و غير شغال")
            else:
                if event.raw_text == "/showtarget":
                    
                    await event.respond("القنوات التي يتم النقل لها هي : \n" + "\n".join(map(str, load_json(username+"/"+target_channels_json))))
                elif event.raw_text == "/showsource":
                    await event.respond("القنوات التي يتم النقل منها هي : \n" + "\n".join(map(str, load_json(username+"/"+source_channels_json))))
                elif event.raw_text == "/showadmin":
                    await event.respond("قائمة المديرين هي : \n" + "\n".join(map(str, load_json(username+"/"+admins_json))))
                elif event.raw_text.startswith("/addtarget"):
                    regex = r"^\/addtarget$"
                    matches = re.search(regex, event.raw_text)
                    # todo add here logic
                    if matches:
                        await event.respond("أرسل  القناة أو القنوات التي ستنقل اليها, أرسل /N عند الإنتهاء, أو /R لإعادة التشغيل")
                        self.conversation_state[username] = State.ASK_FOR_IDS
                    else:
                        await show_menu(event)
                elif state == State.ASK_FOR_IDS:
                        if event.raw_text.upper()=="/N":
                            self.conversation_state[username]={}
                            target_channels = load_json(username+"/"+target_channels_json)
                            target_channels.extend(self.target_ids[username])
                            target_channels = list(set(target_channels))
                            with open(username+"/"+target_channels_json, "w", encoding="utf-8") as f:
                                json.dump(target_channels, f)
                            clean(username)
                            await event.respond("تمت الاضافة إلى القنوات التي يتم النقل اليها")

                        elif event.raw_text.upper()=="/R":
                            clean(username)
                            await event.respond("تم اعادة التشغيل")
                        else:
                            try:
                                if '\n' in event.raw_text:
                                    tup = tuple(event.raw_text.split('\n'))
                                    for t in tup:
                                        value = int(t)
                                        self.target_ids[username].append(value)
                                else:
                                    value = int(event.raw_text)
                                    self.target_ids[username].append(value)
                            except Exception as e:
                                await event.respond(" ❌ خطأ في id يجب أن يكون رقم ! تم اعادة التشغيل")
                                clean(username)
                elif state == State.SAVE_IDS:
                        target_channels = load_json(username+"/"+target_channels_json)
                elif event.raw_text.startswith("/removetarget"):
                    regex = r"^\/removetarget (-?\d+)$"
                    matches = re.search(regex, event.raw_text)
                    if matches:
                        target_channels = load_json(username+"/"+target_channels_json)
                        if int(matches.group(1)) in target_channels:
                            target_channels.remove(int(matches.group(1)))
                            with open(username+"/"+target_channels_json, "w", encoding="utf-8") as f:
                                json.dump(target_channels, f)
                            await event.respond("تم حذف {} من القنوات التي يتم النقل اليها".format(matches.group(1)))
                        else:
                            await event.respond("لم يتم العثور على القناة التالية : {}".format(matches.group(1)))

                    else:
                        await show_menu(event)
                elif event.raw_text.startswith("/addsource"):
                    regex = r"^\/addsource (-?\d+)$"
                    matches = re.search(regex, event.raw_text)
                    if matches:
                        source_channels = load_json(username+"/"+source_channels_json)
                        source_channels.append(int(matches.group(1)))
                        source_channels = list(set(source_channels))
                        with open(username+"/"+source_channels_json, "w", encoding="utf-8") as f:
                            json.dump(source_channels, f)
                        await event.respond("تمت اضافة {} إلى القنوات التي يتم النقل منها".format(matches.group(1)))
                    else:
                        await show_menu(event)
                elif event.raw_text.startswith("/removesource"):
                    regex = r"^\/removesource (-?\d+)$"
                    matches = re.search(regex, event.raw_text)
                    if matches:
                        source_channels = load_json(username+"/"+source_channels_json)
                        if int(matches.group(1)) in source_channels:
                            source_channels.remove(int(matches.group(1)))
                            with open(username+"/"+source_channels_json, "w", encoding="utf-8") as f:
                                json.dump(source_channels, f)
                            await event.respond("تم حذف {} من القنوات التي يتم النقل منها".format(matches.group(1)))
                        else:
                            await event.respond("لم يتم العثور على القناة التالية : {}".format(matches.group(1)))

                    else:
                        await show_menu(event)
                elif event.raw_text.startswith("/addadmin"):
                    regex = r"^\/addadmin (-?\d+)$"
                    matches = re.search(regex, event.raw_text)
                    if matches:
                        admins = load_json(username+"/"+admins_json)
                        admins.append(int(matches.group(1)))
                        with open(username+"/"+admins_json, "w", encoding="utf-8") as f:
                            json.dump(admins, f)
                        await event.respond("تمت اضافة {} إلى قائمة المديرين".format(matches.group(1)))
                    else:
                        await show_menu(event)
                elif event.raw_text.startswith("/removeadmin"):
                    regex = r"^\/removeadmin (-?\d+)$"
                    matches = re.search(regex, event.raw_text)
                    if matches:
                        admins = load_json(username+"/"+admins_json)
                        if int(matches.group(1)) in admins:
                            admins.remove(int(matches.group(1)))
                            with open(username+"/"+admins_json, "w", encoding="utf-8") as f:
                                json.dump(admins, f)
                            await event.respond("تم حذف {} من قائمة الاداريين".format(matches.group(1)))
                        else:
                            await event.respond("لم يتم العثور على المدير التالي : {}".format(matches.group(1)))

                    else:
                        await show_menu(event)
                elif event.raw_text.startswith("/linktoid"):
                    regex = r"^\/linktoid (.+)$"
                    matches = re.search(regex, event.raw_text)
                    if matches:
                        try:
                            res = utils.resolve_invite_link(matches.group(1).strip())[1]
                            if res is None:
                                await event.respond("الرجاء التأكد من الرابط جيدا")
                            else:
                                await event.respond("-100" + str(res))
                        except:
                            await event.respond("الرجاء التأكد من الرابط جيدا")

                    else:
                        await show_menu(event)
                else:
                    await show_menu(event)


        @client.on(events.NewMessage(func=lambda event: event.is_channel))
        async def answer_private_chat(event):
            source_channels = load_json(username+"/"+source_channels_json)
            if event.chat_id in source_channels:
                target_channels = load_json(username+"/"+target_channels_json)
                for target in target_channels:
                    try:
                        await client.forward_messages(target, event.message)
                    except Exception as ex:
                        try:
                            await client.send_message(self.dev, "يوجد مشكل مع القناة هذه : {}".format(target))
                            logger.error("[client.start child error] : [username : " + username + " ] : " + str(ex))
                        except Exception as e:
                            logger.error("[client.start child error] : [username : " + username + " ] : " + str(e))
                            pass
        
        await client.run_until_disconnected()

async def main():
    create_json_if_not_exist(tokens_json,"{}")
    create_json_if_not_exist(admin_tokens_for_allowed_json,"[]")
    create_json_if_not_exist(allowed_json,"[]")
    create_json_if_not_exist(deleted_json,"[]")
    # use nest to avoid This event loop is already running error
    nest_asyncio.apply()
    # create bot builder instance
    builder = Builder(builder_token,api_id,api_hash)
    # run existing bots and start bot builder
    await asyncio.gather(*[builder.run_existing_bots(),builder.start()])

###### HELPER ########
def create_json_if_not_exist(filepath, init):
    if not os.path.isfile(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(init)

def load_json(filename):
    with open(filename, "r", encoding="utf-8") as out:
        loaded_json = json.loads(out.read())
        return loaded_json

def append_to_json(filename, appended):
    with open(filename, "w", encoding="utf-8") as out:
        out.write(json.dumps(appended))

def unic_append_list_to_json(filename, appended):
    f = load_json(filename)
    f.append(appended)
    f = list(set(f))
    with open(filename, "w", encoding="utf-8") as out:
        json.dump(f, out)

def rewrite_json(filename, data):
    with open(filename, "w", encoding="utf-8") as out:
        json.dump(data, out)

def save_token(token,username,file):
    j = load_json(file)
    j[token] = username
    append_to_json(file,j)

def load_bots_tokens(info_json):
    infos = load_json(info_json)
    items = []
    if len(infos)==0:
        return items
    for key, value in infos.items():
        items.append(value)
    return items

def load_bots_usernames(info_json):
    infos = load_json(info_json)
    items = []
    if len(infos)==0:
        return items
    for key, value in infos.items():
        items.append(key)
    return items

def usernameByToken(tvalue):
    infos = load_json(tokens_json)
    for key, value in infos.items():  # for name, age in dictionary.iteritems():  (for Python 2.x)
        if tvalue == value:
            return key

def print_multiple_bots(info_json,max_per_send):
    infos = load_json(info_json)
    msg = []
    newmsg=""
    if len(infos)<=max_per_send:
        for key, value in infos.items():
            newmsg += "\n @"+str(key) 
        msg.append(newmsg)
        newmsg=""
    else:
        i = 0
        for key, value in infos.items():
            newmsg += "\n @"+str(key) 
            i+=1 
            if i>=max_per_send:
                msg.append(newmsg)
                newmsg=""
                i = 0
        # append remaining messages
        if newmsg:
            msg.append(newmsg)
    return msg

def remove_by_username(info_json, username):
    infos = load_json(info_json)
    if len(infos)==0:
        return False
    try:
        del infos[username]
        rewrite_json(tokens_json,infos)
        return True
    except Exception as e:
        print("[remove_by_username] error deleting key : "+ str(e))
        return False

def createDirectory(folder_path):
    try:
        Path(folder_path).mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        print(e)
        raise e

asyncio.get_event_loop().run_until_complete(main())
