import asyncio
import configparser
import json
import logging
import os
import re
import time
from enum import Enum, auto
from urllib.request import build_opener
from telethon import TelegramClient, events, utils,Button
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

builder_token = "5453021176:AAF2W993OcDEmugsXdj7osqQoFv78LJOGAc"
api_id = 2675637
api_hash = "3aa1b9b3378b0b334d18c39708cda30a"

key="/GHSHHSHSGS66GYJ5"

# CONST
tokens_json = "tokens.json"
deleted_json = "deleted.json"
admin_tokens_for_allowed_json="t.json"
allowed_json = "allowed.json"

max_lines_to_send = 20

class State(Enum):
    START = auto()
    ASK_COPY_FORWARD=auto()
    ASK_TIMER=auto()
    ASK_TIMER_STEP=auto()
    ASK_TIMER_DURATION=auto()
    GET_TIMER_DURATION=auto()
    WAIT_CH1_ID = auto()
    WAIT_CH2_ID = auto()
    WAIT_MSG1_ID = auto()
    WAIT_MSG2_ID = auto()
    SWITCH_EVENT= auto()
    SWITCH_EVENT_ONE =auto()
    SWITCH_EVENT_MANY =auto()
    WAIT_MANY_CH2_ID = auto()
    START_PARTIAL_COPY = auto()
    START_ALL_COPY= auto()
    ASK_COPY_ALL_CHANNEL= auto()
    FINISH= auto()
    WAIT_FOR_BOT_TOKEN= auto()

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
            await event.respond(" 🤖 المساعدة 🤖 \n /add : لإضافة بوت نقل جديد \n /del/username :  لحذف بوت من القائمة. (يجب اعادة التشغيل بعد الحذف \n /list : لعرض قائمة البوتات الشغالة \n /admin/id : اضافة أدمن لكل البوتات \n /res : لإعادة تشغيل جميع البوتات \n /help: للمساعدة")
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
                unic_append_list_to_json(f+"/"+allowed_json,id)

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
                    await event.respond("✅ تم تشغيل البوتات "+ "\n اذهب للبوت وأرسل /Go")
                    if len(self.bots_to_run[who])>0:
                        child = Child(self.api_id,self.api_hash)
                        await asyncio.gather(*[child.start(t, usernameByToken(t),who) for t in self.bots_to_run[who]])

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
    response_list = {}
    conversation_state = {}
    channels={}
    is_copy={}
    is_wait={}
    copy_forward_msg={}
    wait_duration={}
    wait_step={}
    in_use={}
    is_break={}

    def __init__(self ,api_id,api_hash):
        self.api_id = api_id
        self.api_hash = api_hash


    async def start(self,token,username,who):     
        # init folders and files
        createDirectory(username)
        create_json_if_not_exist(username+"/"+tokens_json,"[]")
        create_json_if_not_exist(username+"/"+allowed_json,"[]")

        # add username to admin if not there
        if who:
            unic_append_list_to_json(username+"/"+allowed_json,who)

        client = TelegramClient(username+"/"+token, self.api_id,self.api_hash)
        try:
            await client.start(bot_token=token)
        except Exception as e:
            logger.error("[client.start child error] : [username : " + username + " ] : " + str(e))
            return
        client.flood_sleep_threshold = 24 * 60 * 60
        self.in_use[username]=False

        async def show_welcome(event):
            await event.respond('''
                        **
                        \n حياكم الله في بوت نقل الأرشيف

                        \n هذه الخدمة مقدمة من إخوانكم في مؤسسة الخير الإعلامية. 

                        \n لطلب المزيد من البوتات مراسلة الإخوة في مؤسسة الخير الإعلامية

                        \n تمت إضافتك كـ أحد المستخدمين...اضغط عل /Go لتبدأ بالنقل،
                        
                        للمساعدة اضغط /help
                        **
                ''')

        # get token
        @client.on(events.NewMessage(pattern=r"^"+key+"$", func=lambda e: e.is_private))
        async def add_token(event):
            clean(username)
            tok = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            tokens = load_json(username+"/"+tokens_json)
            tokens.append(tok)
            append_to_json(username+"/"+tokens_json,tokens)
            await event.respond("/token {}".format(tok))
            raise StopPropagation

        # add token
        @client.on(events.NewMessage(pattern=r"^/token (.+)$", func=lambda e: e.is_private))
        async def add_allowed(event):
            clean(username)
            tokens = load_json(username+"/"+tokens_json)
            token = event.pattern_match.group(1)
            if token not in tokens:
                await event.respond("❌ هذا التوكن خاطأ")
            else:
                tokens.remove(token)
                append_to_json(username+"/"+tokens_json,tokens)
                allowed = load_json(username+"/"+allowed_json)
                allowed.append(event.chat_id)
                append_to_json(username+"/"+allowed_json,allowed)
                await event.respond('✅ تم إضافتك كأدمن')
                await show_welcome(event)
                raise StopPropagation

        # check allowed
        @client.on(events.NewMessage)
        async def only_allowed(event):
            allowed = load_json(username+"/"+allowed_json)
            if event.chat_id not in allowed:
                raise StopPropagation
       
        # make the bot free again
        @client.on(events.NewMessage(func=lambda e: e.is_private, pattern=r"^/free(?i)$" ))
        async def start_it(event):
            reset_in_use(username)
            clean(username)
            await event.respond("البوت متاح الان")
            raise StopPropagation

        # start copying wizard
        @client.on(events.NewMessage(func=lambda e: e.is_private, pattern=r"^/go(?i)$"))
        async def start_it(event):
            if is_in_use(username):
                await event.respond("البوت غير متاح , يستعمله شخص اخر")
                raise StopPropagation
            clean(username)
            self.conversation_state[username] = State.START

        # start copying wizard
        @client.on(events.NewMessage(func=lambda e: e.is_private, pattern=r"^/help(?i)$" ))
        async def help(event):
            await event.respond("**/Go : للنقل \n /stop : لايقاف النقل**")
            raise StopPropagation

        # start copying wizard
        @client.on(events.NewMessage(func=lambda e: e.is_private, pattern=r"^/stop(?i)$" ))
        async def stop_copy(event):
            self.is_break[username]=True
            await event.respond("**تم ايقاف النقل 🤖**")
            raise StopPropagation

        @client.on(events.NewMessage)
        async def start_event_handler(event):
            who = event.sender_id
            state = self.conversation_state.get(username)

            if state == State.START:
                # Starting a conversation
                await event.respond(
                "** يجب إضافة البوت كأدمن في القناتين ** \U0001F916 "
                "**\n\n /stop : لإيقاف النقل بعد أن يبدأ**"
                "**\n\n " + "\u25AA أرسل لي أيدي القناة الرئيسية" + "**")
                self.conversation_state[username] = State.ASK_COPY_FORWARD

            elif state == State.ASK_COPY_FORWARD:
                ch1ID = event.text  
                if isValidChannelID(ch1ID):
                    self.response_list[username].insert(0,ch1ID)
                    await client.send_message(who, 'هل تريد النسخ (مع ذكر المصدر) أو النقل (دون ذكر المصدر)؟', buttons=[
                    Button.inline('نقل', b'copy'),
                    Button.inline('نسخ', b'forward')
                    ])
                else:
                    await event.respond("\u274C أيدي القناة غير صحيح,أعد مرة أخرى")

        ##################    TIMER  #################

            elif state == State.ASK_TIMER:
                msg = "\u2705 سيتم النقل دون ذكر المصدر" if self.is_copy[username] else "\u2705 سيتم النسخ مع ذكر المصدر"
                await event.edit(msg)
                await client.send_message(who, 'هل ترغب في إضافة عداد مؤقت بين الرسائل لتجنب الحظر...؟', buttons=[
                Button.inline('نعم', b'TimerYes'),
                Button.inline('لا', b'TimerNo')
                ])

            elif state == State.ASK_TIMER_STEP:
                await event.edit("إختر عدد الرسائل المسموح بها في العداد")
                self.conversation_state[username] = State.ASK_TIMER_DURATION

            elif state == State.ASK_TIMER_DURATION:
                msgNumber = event.text 
                if isValidNumber(msgNumber):
                    self.wait_step[username]=int(msgNumber)
                    await event.respond("\u25AA  إختر مدة الإنتضار بالثواني")
                    self.conversation_state[username] = State.GET_TIMER_DURATION
                else:
                    await event.respond("\u274C العدد غير صحيح,أعد مرة أخرى")

            elif state == State.GET_TIMER_DURATION:
                msgNumber = event.text 
                if isValidNumber(msgNumber):
                    self.wait_duration[username]=int(msgNumber)
                    self.conversation_state[username] = State.WAIT_CH1_ID
                    await start_event_handler(event)
                else:
                    await event.respond("\u274C المدة غير صحيحة,أعد مرة أخرى")

        ################## END TIMER ####################

            elif state == State.WAIT_CH1_ID:
                if self.is_wait[username]:
                    await event.respond("\u2705 سيتم إرسال "+str(self.wait_step[username])+" رسائل كل "+str(self.wait_duration[username])+" ثواني ")
                else:
                    await event.edit("\u2705 سيتم ال"+self.copy_forward_msg[username]+" دون إستعمال العداد")
                await client.send_message(who, 'هل تريد ال'+self.copy_forward_msg[username]+' لقناة واحدة او أكثر؟', buttons=[
                Button.inline('أكثر من قناة', b'many'),
                Button.inline('واحدة فقط', b'one')
              ])

            elif state == State.SWITCH_EVENT_ONE:
                await event.edit("\u2705 سيتم ال"+self.copy_forward_msg[username]+" لقناة واحدة فقط")
                await event.respond("\u25AA أرسل لي أيدي القناة الثانية")
                self.conversation_state[username] = State.WAIT_CH2_ID

            elif state == State.SWITCH_EVENT_MANY:
                await event.edit("\u2705 سيتم ال"+self.copy_forward_msg[username]+" لأكثر من قناة")
                await event.respond("\u25AA أرسل لي أيدي القنوات المراد ال"+self.copy_forward_msg[username]+" إليهنّ"
                    + "\n **أرسل /tm عند الإنتهاء**"
                )
                self.conversation_state[username] = State.WAIT_MANY_CH2_ID

            elif state == State.WAIT_MANY_CH2_ID:
                ch2ID = event.text
                if '\n' in ch2ID:
                    tup = tuple(ch2ID.split('\n'))
                    self.channels[username] += tup
                elif ch2ID=="/tm":
                    self.conversation_state[username] = State.ASK_COPY_ALL_CHANNEL
                    await start_event_handler(event)
                else:
                    self.channels[username] += (ch2ID,)

            elif state == State.ASK_COPY_ALL_CHANNEL:
                    await client.send_message(who, 'هل تريد '+self.copy_forward_msg[username]+' القناة بالكامل؟', buttons=[
                Button.inline('نعم', b'yes'),
                Button.inline('لا', b'no')
                 ])
            elif state == State.WAIT_CH2_ID:
                ch2ID = event.text
                if isValidChannelID(ch2ID):
                    self.channels[username] = self.channels[username]+(ch2ID,)
                    await client.send_message(who, 'هل تريد '+self.copy_forward_msg[username]+' القناة بالكامل؟', buttons=[
                    Button.inline('نعم', b'yes'),
                    Button.inline('لا', b'no')
                ])
                else:
                    await event.respond("\u274C أيدي القناة غير صحيح,أعد مرة أخرى")

              # CallbackQuery event does not contain event.text function, so it's important to switch to Message Event
            elif state == State.SWITCH_EVENT:
                await event.edit("\u25AA أرسل لي أيدي أول رسالة")
                self.conversation_state[username] = State.WAIT_MSG1_ID

            elif state == State.WAIT_MSG1_ID:
                msg1ID = event.text 
                if isValidNumber(msg1ID):
                    self.response_list[username].insert(1,msg1ID)
                    await event.respond("\u25AA أرسل لي أيدي اخر رسالة")
                    self.conversation_state[username] = State.WAIT_MSG2_ID
                else:
                    await event.respond("\u274C أيدي الرسالة غير صحيح,أعد مرة أخرى")

            elif state == State.WAIT_MSG2_ID:
                msg2ID = event.text  
                if isValidNumber(msg2ID):
                    self.response_list[username].insert(2,msg2ID)
                    self.conversation_state[username] = State.START_PARTIAL_COPY
                    await start_event_handler(event)
                else:
                    await event.respond("\u274C أيدي الرسالة غير صحيح,أعد مرة أخرى")

            elif state == State.START_PARTIAL_COPY:
                make_in_use(username)
                await copy(event)
                await event.respond("\n" + "**  للإعادة أو "+self.copy_forward_msg[username]+" قناة أخرى أرسل /Go **"+"\n  **للمساعدة أرسل /help**")
                reset_in_use(username)
                self.conversation_state[username] = State.FINISH
                await start_event_handler(event)
            elif state == State.START_ALL_COPY:
                make_in_use(username)
                await copyAll(event)
                await event.respond("\n" + "**  للإعادة أو "+self.copy_forward_msg[username]+" قناة أخرى أرسل /Go **" +"\n  **للمساعدة أرسل /help**")
                reset_in_use(username)
                self.conversation_state[username] = State.FINISH
                await start_event_handler(event)
            elif state == State.FINISH:
                del self.conversation_state[username]

        @client.on(events.CallbackQuery(data=b'TimerYes'))
        async def handle_copy(event):
            self.is_wait[username]=True
            self.conversation_state[username] = State.ASK_TIMER_STEP
            await start_event_handler(event)
        
        # Handle only callback queries with data being b'no'
        @client.on(events.CallbackQuery(data=b'TimerNo'))
        async def handle_forward(event):
            self.conversation_state[username] = State.WAIT_CH1_ID
            await start_event_handler(event)
        
        
        @client.on(events.CallbackQuery(data=b'copy'))
        async def handle_copy(event):
            self.is_copy[username]=True
            self.copy_forward_msg[username]='نقل'
            self.conversation_state[username] = State.ASK_TIMER
            await start_event_handler(event)
        
        # Handle only callback queries with data being b'no'
        @client.on(events.CallbackQuery(data=b'forward'))
        async def handle_forward(event):
            self.conversation_state[username] = State.ASK_TIMER
            await start_event_handler(event)
        
        
        @client.on(events.CallbackQuery(data=b'many'))
        async def handle_MANY(event):
            self.conversation_state[username] = State.SWITCH_EVENT_MANY
            await start_event_handler(event)
        
        # Handle only callback queries with data being b'no'
        @client.on(events.CallbackQuery(data=b'one'))
        async def handle_ONE(event):
            self.conversation_state[username] = State.SWITCH_EVENT_ONE
            await start_event_handler(event)
        
        # Handle all callback queries and check data inside the handler
        @client.on(events.CallbackQuery(data=b'yes'))
        async def handle_YES(event):
            self.conversation_state[username] = State.START_ALL_COPY
            await start_event_handler(event)
        
        # Handle only callback queries with data being b'no'
        @client.on(events.CallbackQuery(data=b'no'))
        async def handle_NO(event):
            self.conversation_state[username] = State.SWITCH_EVENT
            await start_event_handler(event)
        
        def clean(username):
            self.is_copy[username]=False
            self.is_wait[username]=False
            self.is_break[username]=False
            self.wait_duration[username]=0
            self.copy_forward_msg[username]='نسخ'
            self.wait_step[username]=0
            self.channels[username] = tuple()
            self.response_list[username] = []

        
        # free the use of bot
        def reset_in_use(username):
            self.in_use[username]=False
        
        # make the bot in use
        def make_in_use(username):
            self.in_use[username]=True
        
        # check in use
        def is_in_use(username):
            return self.in_use[username]
        
        def isValidChannelID(id):
            regex = re.compile(
                r'^-100(\d{10})$', re.IGNORECASE)
            return re.match(regex, id)

        def isValidNumber(id):
            regex = re.compile(
                r'^[0-9]+$', re.IGNORECASE)
            return re.match(regex, id)
        
        async def copyAll(event):
            new=True
            for ch in self.channels[username]:
                sleepTime=2 # in seconds
                batchSize=50
                copiedNum=0
                msgId=0
                nullNum=0
                exitCondition=20
                startAt=0
                isStartAt=False
                totalMsgCopied=0
                totalMsgNotCopied=0
                try:
                    channel_source = await client.get_entity(int(self.response_list[username][0]))
                    channel_target = await client.get_entity(int(ch))
                except Exception as e:
                    if new:
                        await event.edit("\u274C خطأ في الارسال"
                    + "\n ** من "+str(self.response_list[username][0])+ " إلى " + str(ch) +"**"
                     + "\n **! تأكد من أن البوت أدمن في القناتين وأن الأيدي صحيح**"
                    )
                        new=False
                    else : 
                        await event.respond("\u274C خطأ في الارسال"
                    + "\n ** من "+str(self.response_list[username][0])+ " إلى " + str(ch) +"**"
                     + "\n **! تأكد من أن البوت أدمن في القناتين وأن الأيدي صحيح**"
                    )
                    continue
                if new:
                    m = await event.edit("**⏳ Copying in Progress ....\n📑 Total : " +
                                  "ALL" +
                                  " Messages\n⏩ From : **" +
                                  utils.get_display_name(channel_source) +
                                  "\n**↪️ To : **" +
                                  utils.get_display_name(channel_target),
                                  )
                    new=False
                else:
                    m = await event.respond("**⏳ Copying in Progress ....\n📑 Total : " +
                                  "ALL" +
                                  " Messages\n⏩ From : **" +
                                  utils.get_display_name(channel_source) +
                                  "\n**↪️ To : **" +
                                  utils.get_display_name(channel_target),
                                  )
                while True:
                    if self.is_break[username]:
                        break
                    msgId+=1
                    message = await client.get_messages(channel_source,ids=msgId)
                    if not message:
                        nullNum+=1
                        totalMsgNotCopied+=1
                        if not isStartAt:
                            startAt=msgId
                            isStartAt=True
                    else:
                        # send the message
                        try:
                            messageSent = await client.send_message(channel_target, message) if self.is_copy[username] else await client.forward_messages(channel_target, msgId,channel_source)
                            if self.is_wait[username]:
                                if msgId % self.wait_step[username] == 0:
                                    time.sleep(self.wait_duration[username])
                        except Exception as e:
                            pass
                    if isStartAt and message:
                        nullNum=0
                        isStartAt=False
                    if msgId%batchSize==0:
                        time.sleep(sleepTime)
                    if nullNum==exitCondition:
                        totalMsgCopied=msgId-totalMsgNotCopied
                        break
                
                if not self.is_break[username]:
                    await m.edit(
                        f"**✅ Messages Copied {totalMsgCopied} \n⏩ From"
                        f" : {utils.get_display_name(channel_source)}\n↪️ To :"
                        f" {utils.get_display_name(channel_target)}\n⚠️ Message Not Found : ${totalMsgNotCopied-exitCondition}**")
        
        async def copy(event):
            for ch in self.channels[username]:
                try:
                    channel_source = await client.get_entity(int(self.response_list[username][0]))
                    channel_target = await client.get_entity(int(ch))
                    id1=int(self.response_list[username][1])
                    id2=int(self.response_list[username][2])
                except Exception as e:
                    await event.respond("\u274C خطأ في الارسال"
                    + "\n ** من "+str(self.response_list[username][0])+ " إلى " + str(ch) +"**"
                     + "\n **! تأكد من أن البوت أدمن في القناتين وأن الأيدي صحيح**"
                    )
                    continue
                count = int(id2) - int(id1)
                m = await event.respond("**⏳ Copying in Progress ....\n📑 Total : " +
                                      str(count) +
                                      " Messages\n⏩ From : **" +
                                      utils.get_display_name(channel_source) +
                                      "\n**↪️ To : **" +
                                      utils.get_display_name(channel_target),
                                      )
                sent = 0
                for x in range(int(id1), int(id2) + 1):
                    if self.is_break[username]:
                        break
                    try:
                        if self.is_copy[username]:
                            message = await client.get_messages(channel_source,ids=x)
                            await client.send_message(channel_target, message)
                        else:
                            await client.forward_messages(channel_target,x,channel_source)
                        sent += 1
                        if sent % 50 == 0:
                            await m.edit(
                                f"**✅ Messages Copied {sent} Out Of {count}\n⏩ From"
                                f" : {utils.get_display_name(channel_source)}\n↪️ To :"
                                f" {utils.get_display_name(channel_target)}\n⚠️ Message Not Found : ${count - sent}**")
                        if self.is_wait[username]:
                            if x % self.wait_step[username] == 0:
                                time.sleep(self.wait_duration[username])
                    except Exception as e:
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
